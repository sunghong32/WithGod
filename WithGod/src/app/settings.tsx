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
import { ScreenHeader } from "@/shared/components/ScreenHeader";
import { WheelTimePicker } from "@/shared/components/WheelTimePicker";
import { baseFontFamily, colors, scaleFont } from "@/shared/styles";
import { Ionicons } from "@expo/vector-icons";
import { useCallback, useEffect, useRef, useState } from "react";
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
  const period = hour < 12 ? "오전" : "오후";
  const displayHour = hour % 12 === 0 ? 12 : hour % 12;
  const mm = String(minute).padStart(2, "0");
  return `${period} ${displayHour}:${mm}`;
};

// 휠 연속 조작 시 서버 동기화를 마지막 변경만 보내기 위한 대기 시간
const TIME_SYNC_DEBOUNCE_MS = 600;

export default function SettingsScreen() {
  const { insets } = useSafeAreaPadding();

  const [settings, setSettings] = useState<NotificationSettings>(
    DEFAULT_NOTIFICATION_SETTINGS,
  );
  const [permission, setPermission] =
    useState<PushPermissionStatus>("undetermined");
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncFailed, setSyncFailed] = useState(false);

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
      <ScreenHeader title="알림 설정" />

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
                    알림이 꺼져 있어요
                  </Text>
                </View>
                <Text style={styles.permissionDescription}>
                  알림을 받으려면 시스템 설정에서 알림 권한을 켜주세요.
                </Text>
                <TouchableOpacity
                  style={styles.permissionButton}
                  onPress={openSystemSettings}
                  activeOpacity={0.7}
                  accessibilityRole="button"
                  accessibilityLabel="시스템 설정 열기"
                >
                  <Text style={styles.permissionButtonText}>
                    설정에서 켜기
                  </Text>
                </TouchableOpacity>
              </View>
            )}

            {/* 알림 받기 토글 */}
            <View style={styles.card}>
              <View style={styles.cardRow}>
                <View style={styles.cardRowText}>
                  <Text style={styles.cardTitle}>알림 받기</Text>
                  <Text style={styles.cardSubtitle}>
                    매일 위로의 말씀을 받아보세요
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
            </View>

            {/* 알림 시간 */}
            <View
              style={[styles.card, timeControlsDisabled && styles.cardDisabled]}
            >
              <View style={styles.timeHeaderRow}>
                <Text style={styles.cardTitle}>알림 시간</Text>
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

            <Text style={styles.footerNote}>
              {isSyncing
                ? "저장 중..."
                : syncFailed
                  ? "서버에 반영하지 못했어요. 잠시 후 다시 시도해주세요."
                  : "변경 사항은 자동으로 저장됩니다."}
            </Text>
          </>
        )}
      </ScrollView>
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
  footerNote: {
    fontSize: scaleFont(13),
    color: "#9CA3AF",
    fontFamily: baseFontFamily,
    textAlign: "center",
    marginTop: 4,
  },
});
