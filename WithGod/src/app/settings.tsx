import { useSafeAreaPadding } from "@/shared/hooks";
import {
  DEFAULT_NOTIFICATION_SETTINGS,
  getNotificationSettings,
  saveNotificationSettings,
  type NotificationSettings,
} from "@/shared/lib/notificationSettings";
import {
  getPushPermissionStatusAsync,
  requestPushPermissionAsync,
  syncNotificationSettingsAsync,
  type PushPermissionStatus,
} from "@/shared/lib/pushNotifications";
import {
  isConsentRequiredRegion,
  isTelemetryEnabled,
  setTelemetryEnabled,
} from "@/shared/lib/telemetry";
import { LanguagePickerModal } from "@/shared/components/LanguagePickerModal";
import { ScreenHeader } from "@/shared/components/ScreenHeader";
import { WheelTimePicker } from "@/shared/components/WheelTimePicker";
import { WidgetGuideModal } from "@/shared/components/WidgetGuideModal";
import {
  type AppLanguageChoice,
  LANGUAGE_NATIVE_NAMES,
  getAppLanguageChoice,
  setAppLanguageChoice,
  t,
} from "@/shared/lib/i18n";
import { refreshHomeWidgetAsync } from "@/widgets/refreshHomeWidget";
import { clearDailyVerseCache } from "@/widgets/widgetTaskHandler";
import { syncWidgetLanguage } from "../../modules/widget-bridge";
import { baseFontFamily, colors, scaleFont } from "@/shared/styles";
import { Ionicons } from "@expo/vector-icons";
import Constants from "expo-constants";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  ActivityIndicator,
  AppState,
  Linking,
  Platform,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

const formatTime = (hour: number, minute: number): string => {
  const period = hour < 12 ? t("settings.am") : t("settings.pm");
  const displayHour = hour % 12 === 0 ? 12 : hour % 12;
  const mm = String(minute).padStart(2, "0");
  return `${period} ${displayHour}:${mm}`;
};

// 휠 연속 조작 시 서버 동기화를 마지막 변경만 보내기 위한 대기 시간
const TIME_SYNC_DEBOUNCE_MS = 600;

// 설치된 앱 버전. OTA 업데이트 중에도 스토어 빌드 기준 버전이 유지된다.
const appVersion =
  Constants.expoConfig?.version ?? Constants.nativeAppVersion ?? "-";

export default function SettingsScreen() {
  const { t } = useTranslation();
  const { insets } = useSafeAreaPadding();

  const [settings, setSettings] = useState<NotificationSettings>(
    DEFAULT_NOTIFICATION_SETTINGS,
  );
  const [permission, setPermission] =
    useState<PushPermissionStatus>("undetermined");
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncFailed, setSyncFailed] = useState(false);
  const [showWidgetGuide, setShowWidgetGuide] = useState(false);
  const [showLanguagePicker, setShowLanguagePicker] = useState(false);
  const [languageChoice, setLanguageChoice] =
    useState<AppLanguageChoice>("system");
  const [telemetryOn, setTelemetryOn] = useState(isTelemetryEnabled());
  // 동의가 필요한 지역(EU/EEA)에서만 통계 토글을 노출한다. 지역은 실행 중
  // 바뀌지 않으므로 최초 1회만 계산한다.
  const [showTelemetryToggle] = useState(() => isConsentRequiredRegion());

  // 통계 수집 여부는 SDK 초기화(비동기) 후에 확정되므로 화면 진입 시 다시 읽는다.
  useEffect(() => {
    setTelemetryOn(isTelemetryEnabled());
    void getAppLanguageChoice().then(setLanguageChoice);
  }, []);

  // 언어 변경: 즉시 적용 + 푸시 재등록(제목·본문 언어 반영) + 위젯 캐시 갱신.
  const handleSelectLanguage = useCallback(
    (choice: AppLanguageChoice) => {
      setLanguageChoice(choice);
      setShowLanguagePicker(false);
      void (async () => {
        await setAppLanguageChoice(choice);
        // 실패해도 무해한 best-effort 후속 처리들
        void syncNotificationSettingsAsync(settingsRef.current);
        await clearDailyVerseCache();
        void refreshHomeWidgetAsync();
        // iOS 위젯은 별도 프로세스라 App Group 으로 언어를 공유해야 따라온다
        syncWidgetLanguage(choice === "system" ? null : choice);
      })();
    },
    [],
  );

  const handleToggleTelemetry = useCallback((next: boolean) => {
    setTelemetryOn(next);
    void setTelemetryEnabled(next);
  }, []);

  // 가장 최근 설정값을 ref 로 유지(시각 휠 연속 조작 시 최신값 기준 저장).
  // 렌더 중 ref 변이는 React 규칙 위반이므로 커밋 후 effect 에서 동기화한다.
  const settingsRef = useRef(settings);
  useEffect(() => {
    settingsRef.current = settings;
  }, [settings]);

  const syncTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const isNative = Platform.OS === "ios" || Platform.OS === "android";

  const refreshPermission = useCallback(async () => {
    const status = await getPushPermissionStatusAsync();
    setPermission(status);
    return status;
  }, []);

  useEffect(() => {
    let isMounted = true;
    (async () => {
      const [saved] = await Promise.all([
        getNotificationSettings(),
        refreshPermission(),
      ]);
      if (!isMounted) return;
      setSettings(saved);
      setIsLoading(false);
    })();
    return () => {
      isMounted = false;
    };
  }, [refreshPermission]);

  // 서버 동기화. 알림 ON 상태에서 권한이 없으면 건너뛴다(OFF 는 권한과 무관하게 수신 거부를 반영).
  const syncToServer = useCallback(
    async (next: NotificationSettings) => {
      if (!isNative) return;
      if (next.enabled) {
        const status = await getPushPermissionStatusAsync();
        setPermission(status);
        if (status !== "granted") return;
      }
      setIsSyncing(true);
      try {
        const ok = await syncNotificationSettingsAsync(next);
        setSyncFailed(!ok);
      } finally {
        setIsSyncing(false);
      }
    },
    [isNative],
  );

  // 저장 + 백엔드 즉시 동기화. 대기 중인 디바운스 동기화는 취소한다(이 호출이 최신값을 전송하므로).
  const persistAndSync = useCallback(
    async (next: NotificationSettings) => {
      if (syncTimerRef.current) {
        clearTimeout(syncTimerRef.current);
        syncTimerRef.current = null;
      }
      await saveNotificationSettings(next);
      await syncToServer(next);
    },
    [syncToServer],
  );

  // 화면 이탈 시 대기 중인 시간 변경 동기화를 유실하지 않도록 즉시 전송(best-effort)
  useEffect(() => {
    return () => {
      if (syncTimerRef.current) {
        clearTimeout(syncTimerRef.current);
        syncTimerRef.current = null;
        void syncToServer(settingsRef.current);
      }
    };
  }, [syncToServer]);

  // 시스템 설정에서 권한을 바꾸고 앱으로 돌아오면 권한을 재확인해 배너를 갱신.
  useEffect(() => {
    if (!isNative) return;
    const sub = AppState.addEventListener("change", (state) => {
      if (state !== "active") return;
      void (async () => {
        const status = await refreshPermission();
        // 권한이 새로 켜졌고 알림이 ON 이면 서버에 기기 재등록(동기화).
        if (status === "granted" && settingsRef.current.enabled) {
          void persistAndSync(settingsRef.current);
        }
      })();
    });
    return () => sub.remove();
  }, [isNative, refreshPermission, persistAndSync]);

  const handleToggleEnabled = useCallback(
    async (value: boolean) => {
      if (value && isNative) {
        // ON 시도 시 권한 확인/요청
        const current = await getPushPermissionStatusAsync();
        if (current === "undetermined") {
          await requestPushPermissionAsync();
        }
        const status = await refreshPermission();
        if (status !== "granted") {
          // 권한이 없으면 토글은 켜되 안내 배너를 노출(아래 권한 배너)
          const next = { ...settingsRef.current, enabled: true };
          setSettings(next);
          await saveNotificationSettings(next);
          return;
        }
      }
      const next = { ...settingsRef.current, enabled: value };
      setSettings(next);
      await persistAndSync(next);
    },
    [isNative, persistAndSync, refreshPermission],
  );

  const handleTimeChange = useCallback(
    (hour: number, minute: number) => {
      const next = {
        ...settingsRef.current,
        scheduleHour: hour,
        scheduleMinute: minute,
      };
      setSettings(next);
      // 로컬 저장은 즉시, 서버 동기화는 휠 연속 조작이 끝난 뒤 마지막 값만 전송
      // (요청 폭주 및 네트워크 응답 순서 역전으로 이전 시각이 남는 문제 방지)
      void saveNotificationSettings(next);
      if (syncTimerRef.current) clearTimeout(syncTimerRef.current);
      syncTimerRef.current = setTimeout(() => {
        syncTimerRef.current = null;
        void syncToServer(settingsRef.current);
      }, TIME_SYNC_DEBOUNCE_MS);
    },
    [syncToServer],
  );

  const openSystemSettings = useCallback(() => {
    Linking.openSettings().catch(() => {
      // best-effort
    });
  }, []);

  // 권한이 명시적으로 "거부됨" 일 때만 배너 노출(미결정 단계에선 OS 팝업이 처리하므로 숨김).
  const showPermissionBanner =
    isNative && permission === "denied" && settings.enabled;
  const timeControlsDisabled = !settings.enabled;

  return (
    <View style={styles.container}>
      <ScreenHeader title={t("settings.headerTitle")} />

      <ScrollView
        contentContainerStyle={[
          styles.scrollContent,
          { paddingBottom: insets.bottom + 32 },
        ]}
        showsVerticalScrollIndicator={false}
      >
        {isLoading ? (
          <View style={styles.loadingWrap}>
            <ActivityIndicator size="small" color={colors.primary} />
          </View>
        ) : (
          <>
            {/* 권한 거부 안내 배너 */}
            {showPermissionBanner && (
              <View style={styles.permissionBanner}>
                <View style={styles.permissionRow}>
                  <Ionicons
                    name="notifications-off-outline"
                    size={20}
                    color="#B45309"
                    style={styles.permissionIcon}
                  />
                  <Text style={styles.permissionTitle}>
                    {t("settings.permBannerTitle")}
                  </Text>
                </View>
                <Text style={styles.permissionDescription}>
                  {t("settings.permBannerDesc")}
                </Text>
                <TouchableOpacity
                  style={styles.permissionButton}
                  onPress={openSystemSettings}
                  activeOpacity={0.7}
                  accessibilityRole="button"
                  accessibilityLabel={t("settings.permBannerButtonA11y")}
                >
                  <Text style={styles.permissionButtonText}>
                    {t("settings.permBannerButton")}
                  </Text>
                </TouchableOpacity>
              </View>
            )}

            {/* 알림 — 수신 여부와 시각은 한 기능이라 같은 카드로 묶는다 */}
            <View style={styles.card}>
              <View style={styles.cardRow}>
                <View style={styles.cardRowText}>
                  <Text style={styles.cardTitle}>{t("settings.notifTitle")}</Text>
                  <Text style={styles.cardSubtitle}>
                    {t("settings.notifSubtitle")}
                  </Text>
                </View>
                <Switch
                  value={settings.enabled}
                  onValueChange={handleToggleEnabled}
                  trackColor={{ false: colors.border, true: "#A9CBF1" }}
                  thumbColor={settings.enabled ? colors.primary : colors.background}
                  ios_backgroundColor={colors.border}
                />
              </View>

              <View style={styles.cardDivider} />

              {/* 알림이 꺼져 있으면 시간 영역만 흐리게 — 토글은 항상 조작 가능해야 한다 */}
              <View style={timeControlsDisabled ? styles.cardDisabled : null}>
                <View style={styles.timeHeaderRow}>
                  <Text style={styles.cardTitle}>{t("settings.notifTime")}</Text>
                  <Text style={styles.timeValue}>
                    {formatTime(settings.scheduleHour, settings.scheduleMinute)}
                  </Text>
                </View>

                <WheelTimePicker
                  hour={settings.scheduleHour}
                  minute={settings.scheduleMinute}
                  onChange={handleTimeChange}
                  disabled={timeControlsDisabled}
                />
              </View>

              {/* 서버 저장 상태 — 알림 설정만 서버에 동기화되므로 이 카드 안에 둔다.
                  토글 변경도 저장 대상이라 흐림(disabled) 영역 밖에 배치한다. */}
              <Text style={styles.syncNote}>
                {isSyncing
                  ? t("settings.saving")
                  : syncFailed
                    ? t("settings.syncFailed")
                    : t("settings.autoSaved")}
              </Text>
            </View>

            {/*
              사용 통계 토글은 동의가 필요한 지역(EU/EEA)에서만 노출한다.
              그 외 지역은 기본 수집이라 토글이 없다 — 대다수 사용자에게 불필요한
              선택을 강요하지 않기 위해서다. 유럽은 GDPR상 철회 수단이 필수라 유지.
            */}
            {showTelemetryToggle && (
              <View style={styles.card}>
                <View style={styles.cardRow}>
                  <View style={styles.cardRowText}>
                    <Text style={styles.cardTitle}>
                      {t("settings.telemetryTitle")}
                    </Text>
                    <Text style={styles.cardSubtitle}>
                      {t("settings.telemetrySubtitle")}
                    </Text>
                  </View>
                  <Switch
                    value={telemetryOn}
                    onValueChange={handleToggleTelemetry}
                    trackColor={{ false: colors.border, true: "#A9CBF1" }}
                    thumbColor={telemetryOn ? colors.primary : colors.background}
                    ios_backgroundColor={colors.border}
                  />
                </View>
              </View>
            )}

            {/* 언어 — 기본은 기기 언어 자동 감지, 수동 오버라이드 제공 (이슈 #14) */}
            <TouchableOpacity
              style={styles.card}
              activeOpacity={0.8}
              onPress={() => setShowLanguagePicker(true)}
              accessibilityRole="button"
              accessibilityLabel={t("settings.languageCardA11y")}
            >
              <View style={styles.cardRow}>
                <View style={styles.cardRowText}>
                  <Text style={styles.cardTitle}>
                    {t("settings.languageTitle")}
                  </Text>
                  <Text style={styles.cardSubtitle}>
                    {languageChoice === "system"
                      ? t("settings.languageSystem")
                      : LANGUAGE_NATIVE_NAMES[languageChoice]}
                  </Text>
                </View>
                <Ionicons name="chevron-forward" size={18} color="#9CA3AF" />
              </View>
            </TouchableOpacity>

            {/* 홈 화면 위젯 안내 */}
            <TouchableOpacity
              style={styles.card}
              activeOpacity={0.8}
              onPress={() => setShowWidgetGuide(true)}
              accessibilityRole="button"
              accessibilityLabel={t("settings.widgetCardA11y")}
            >
              <View style={styles.cardRow}>
                <View style={styles.cardRowText}>
                  <Text style={styles.cardTitle}>
                    {t("settings.widgetCardTitle")}
                  </Text>
                  <Text style={styles.cardSubtitle}>
                    {t("settings.widgetCardSubtitle")}
                  </Text>
                </View>
                <Ionicons name="chevron-forward" size={18} color="#9CA3AF" />
              </View>
            </TouchableOpacity>

            {/* 현재 앱 버전 — 업데이트 안내 팝업 도입으로 확인 수단이 필요해짐 */}
            <Text style={styles.versionText}>
              {t("settings.version", { version: appVersion })}
            </Text>
          </>
        )}
      </ScrollView>

      <WidgetGuideModal
        visible={showWidgetGuide}
        onClose={() => setShowWidgetGuide(false)}
      />

      <LanguagePickerModal
        visible={showLanguagePicker}
        current={languageChoice}
        onSelect={handleSelectLanguage}
        onClose={() => setShowLanguagePicker(false)}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingTop: 20,
  },
  loadingWrap: {
    paddingTop: 48,
    alignItems: "center",
  },
  // 권한 배너
  permissionBanner: {
    backgroundColor: "#FEF3C7",
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#FDE68A",
    padding: 16,
    marginBottom: 16,
  },
  permissionRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 6,
  },
  permissionIcon: {
    marginRight: 8,
  },
  permissionTitle: {
    fontSize: scaleFont(16),
    fontWeight: "600",
    color: "#92400E",
    fontFamily: baseFontFamily,
  },
  permissionDescription: {
    fontSize: scaleFont(14),
    lineHeight: scaleFont(20),
    color: "#92400E",
    fontFamily: baseFontFamily,
    marginBottom: 12,
  },
  permissionButton: {
    backgroundColor: "#F59E0B",
    borderRadius: 10,
    paddingVertical: 10,
    alignItems: "center",
  },
  permissionButtonText: {
    fontSize: scaleFont(14),
    fontWeight: "600",
    color: "#FFFFFF",
    fontFamily: baseFontFamily,
  },
  // 카드
  card: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "rgba(139, 115, 85, 0.1)",
    padding: 20,
    marginBottom: 16,
    shadowColor: "#8B7355",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
  },
  cardDisabled: {
    opacity: 0.5,
  },
  cardDivider: {
    height: 1,
    backgroundColor: colors.border,
    marginVertical: 18,
  },
  cardRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  cardRowText: {
    flex: 1,
    marginRight: 12,
  },
  cardTitle: {
    fontSize: scaleFont(16),
    fontWeight: "600",
    color: colors.textPrimary,
    fontFamily: baseFontFamily,
  },
  cardSubtitle: {
    fontSize: scaleFont(14),
    lineHeight: scaleFont(20),
    color: colors.textSecondary,
    fontFamily: baseFontFamily,
    marginTop: 4,
  },
  timeHeaderRow: {
    flexDirection: "row",
    alignItems: "baseline",
    justifyContent: "space-between",
    marginBottom: 12,
  },
  timeValue: {
    fontSize: scaleFont(18),
    fontWeight: "500",
    color: colors.primary,
    fontFamily: baseFontFamily,
  },
  syncNote: {
    fontSize: scaleFont(12),
    color: "#9CA3AF",
    fontFamily: baseFontFamily,
    textAlign: "center",
    marginTop: 12,
  },
  versionText: {
    fontSize: scaleFont(13),
    color: "#B0B5BD",
    fontFamily: baseFontFamily,
    textAlign: "center",
    marginTop: 8,
  },
});
