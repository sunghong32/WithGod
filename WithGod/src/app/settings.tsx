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
import { WheelTimePicker } from "@/shared/components/WheelTimePicker";
import { baseFontFamily, scaleFont } from "@/shared/styles";
import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { useRouter } from "expo-router";
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

const BACK_ICON = require("../shared/assets/images/chevron-right.png");

const formatTime = (hour: number, minute: number): string => {
  const period = hour < 12 ? "오전" : "오후";
  const displayHour = hour % 12 === 0 ? 12 : hour % 12;
  const mm = String(minute).padStart(2, "0");
  return `${period} ${displayHour}:${mm}`;
};

export default function SettingsScreen() {
  const router = useRouter();
  const { insets, headerPaddingTop } = useSafeAreaPadding();

  const [settings, setSettings] = useState<NotificationSettings>(
    DEFAULT_NOTIFICATION_SETTINGS,
  );
  const [permission, setPermission] =
    useState<PushPermissionStatus>("undetermined");
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);

  // 가장 최근 설정값을 ref 로 유지(시각 스테퍼 연속 조작 시 최신값 기준 저장)
  const settingsRef = useRef(settings);
  settingsRef.current = settings;

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

  // 저장 + 백엔드 동기화. 권한이 없으면 동기화는 건너뛰고 로컬에만 저장.
  const persistAndSync = useCallback(
    async (next: NotificationSettings) => {
      await saveNotificationSettings(next);
      if (!isNative) return;
      if (!next.enabled) {
        // OFF 는 권한과 무관하게 서버에 반영(수신 거부)
        setIsSyncing(true);
        try {
          await syncNotificationSettingsAsync(next);
        } finally {
          setIsSyncing(false);
        }
        return;
      }
      const status = await getPushPermissionStatusAsync();
      setPermission(status);
      if (status !== "granted") return;
      setIsSyncing(true);
      try {
        await syncNotificationSettingsAsync(next);
      } finally {
        setIsSyncing(false);
      }
    },
    [isNative],
  );

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
      void persistAndSync(next);
    },
    [persistAndSync],
  );

  const openSystemSettings = useCallback(() => {
    Linking.openSettings().catch(() => {
      // best-effort
    });
  }, []);

  const showPermissionBanner =
    isNative && permission !== "granted" && settings.enabled;
  const timeControlsDisabled = !settings.enabled;

  return (
    <View style={styles.container}>
      <View style={[styles.header, { paddingTop: headerPaddingTop }]}>
        <TouchableOpacity
          style={styles.backButton}
          onPress={() => router.back()}
          activeOpacity={0.7}
          accessibilityRole="button"
          accessibilityLabel="뒤로 가기"
        >
          <Image
            source={BACK_ICON}
            style={styles.backIcon}
            contentFit="contain"
          />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>알림 설정</Text>
        <View style={styles.headerSpacer} />
      </View>

      <ScrollView
        contentContainerStyle={[
          styles.scrollContent,
          { paddingBottom: insets.bottom + 32 },
        ]}
        showsVerticalScrollIndicator={false}
      >
        {isLoading ? (
          <View style={styles.loadingWrap}>
            <ActivityIndicator size="small" color="#4A90E2" />
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
                  trackColor={{ false: "#E5E7EB", true: "#A9CBF1" }}
                  thumbColor={settings.enabled ? "#4A90E2" : "#F9FAFB"}
                  ios_backgroundColor="#E5E7EB"
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
    backgroundColor: "#F9FAFB",
  },
  header: {
    backgroundColor: "#FFFFFF",
    borderBottomColor: "#E5E7EB",
    borderBottomWidth: 1,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingBottom: 16,
  },
  backButton: {
    width: 32,
    height: 32,
    justifyContent: "center",
    alignItems: "center",
    marginRight: 8,
  },
  backIcon: {
    width: 8,
    height: 14,
    transform: [{ rotate: "180deg" }],
    tintColor: "#101828",
  },
  headerTitle: {
    flex: 1,
    fontSize: scaleFont(18),
    lineHeight: scaleFont(24),
    fontWeight: "600",
    color: "#101828",
    fontFamily: baseFontFamily,
  },
  headerSpacer: {
    width: 32,
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
    color: "#101828",
    fontFamily: baseFontFamily,
  },
  cardSubtitle: {
    fontSize: scaleFont(14),
    lineHeight: scaleFont(20),
    color: "#6A7282",
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
    color: "#4A90E2",
    fontFamily: baseFontFamily,
  },
  // 스테퍼 (미사용 — 휠 피커로 대체)
  stepperRow: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "center",
    marginTop: 20,
  },
  stepperGroup: {
    alignItems: "center",
  },
  stepperLabel: {
    fontSize: scaleFont(12),
    color: "#6A7282",
    fontFamily: baseFontFamily,
    marginBottom: 8,
  },
  stepperControls: {
    flexDirection: "row",
    alignItems: "center",
  },
  stepperButton: {
    width: 40,
    height: 40,
    borderRadius: 12,
    backgroundColor: "#F3F4F6",
    alignItems: "center",
    justifyContent: "center",
  },
  stepperValue: {
    fontSize: scaleFont(24),
    fontWeight: "700",
    color: "#1E2939",
    fontFamily: baseFontFamily,
    minWidth: 56,
    textAlign: "center",
  },
  stepperColon: {
    fontSize: scaleFont(24),
    fontWeight: "700",
    color: "#1E2939",
    fontFamily: baseFontFamily,
    marginHorizontal: 12,
    marginBottom: 8,
  },
  footerNote: {
    fontSize: scaleFont(13),
    color: "#9CA3AF",
    fontFamily: baseFontFamily,
    textAlign: "center",
    marginTop: 4,
  },
});
