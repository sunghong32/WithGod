import { useBookmarks, useToggleBookmark } from "@/features/bookmarks";
import { useDailyVerse } from "@/features/verse/hooks/useDailyVerse";
import { NotificationPrimingModal } from "@/shared/components/NotificationPrimingModal";
import { WidgetGuideModal } from "@/shared/components/WidgetGuideModal";
import { VerseActionRow } from "@/shared/components/VerseActionRow";
import { useKeyboardVisible, useSafeAreaPadding } from "@/shared/hooks";
import { logAnalyticsEvent } from "@/shared/lib/analytics";
import {
  hasSeenNotificationPriming,
  markNotificationPrimingSeen,
} from "@/shared/lib/notificationSettings";
import {
  getPushPermissionStatusAsync,
  requestPermissionAndRegisterAsync,
} from "@/shared/lib/pushNotifications";
import {
  hasSeenWidgetPromo,
  markWidgetPromoSeen,
} from "@/shared/lib/widgetPromo";
import { baseFontFamily, colors, scaleFont } from "@/shared/styles";
import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { useFocusEffect, useRouter } from "expo-router";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  ActivityIndicator,
  Keyboard,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { KeyboardAvoidingView } from "react-native-keyboard-controller";

const LOGO_IMAGE = require("../../shared/assets/images/Logo.png");
const SEND_ICON = require("../../shared/assets/images/send.png");

export default function HomeScreen() {
  const { t } = useTranslation();
  const [message, setMessage] = useState("");
  const [showPriming, setShowPriming] = useState(false);
  const [showWidgetPromo, setShowWidgetPromo] = useState(false);
  const [showWidgetGuide, setShowWidgetGuide] = useState(false);
  const isKeyboardVisible = useKeyboardVisible();
  const { headerPaddingTop, getInputBarPaddingBottom } = useSafeAreaPadding();
  const router = useRouter();

  // 위젯 기능 1회성 안내 배너: 아직 안 봤으면 오늘의 말씀 카드 아래에 노출
  useEffect(() => {
    let active = true;
    (async () => {
      if (Platform.OS !== "ios" && Platform.OS !== "android") return;
      if (await hasSeenWidgetPromo()) return;
      if (active) setShowWidgetPromo(true);
    })();
    return () => {
      active = false;
    };
  }, []);

  const handleWidgetPromoOpen = useCallback(() => {
    setShowWidgetGuide(true);
  }, []);

  const handleWidgetGuideClose = useCallback(async () => {
    setShowWidgetGuide(false);
    setShowWidgetPromo(false);
    await markWidgetPromoSeen();
  }, []);

  const handleWidgetPromoDismiss = useCallback(async () => {
    setShowWidgetPromo(false);
    await markWidgetPromoSeen();
  }, []);

  // 첫 실행 프라이밍: 알림 권한이 미결정이고 안내를 아직 안 봤으면,
  // 시스템 팝업 대신 맥락을 설명하는 모달을 먼저 보여준다.
  // (홈이 포커스될 때 = 스플래시가 걷힌 뒤라 스플래시 위에 뜨지 않는다)
  useFocusEffect(
    useCallback(() => {
      let active = true;
      (async () => {
        if (Platform.OS !== "ios" && Platform.OS !== "android") return;
        if (await hasSeenNotificationPriming()) return;
        const status = await getPushPermissionStatusAsync();
        if (!active) return;
        // Android 는 '한 번도 안 물어봄'과 '거부'를 구분할 수 없어(check=false 뿐)
        // 프라이밍을 아직 안 봤다면 denied 도 미결정으로 간주하고 안내를 띄운다.
        const needsPriming =
          status === "undetermined" ||
          (Platform.OS === "android" && status === "denied");
        if (needsPriming) {
          setShowPriming(true);
        } else {
          // 이미 허용(또는 iOS 에서 확정 거부)된 상태면 프라이밍을 물을 필요가 없다
          await markNotificationPrimingSeen();
        }
      })();
      return () => {
        active = false;
      };
    }, [])
  );

  const handlePrimingAccept = useCallback(async () => {
    setShowPriming(false);
    await markNotificationPrimingSeen();
    // 여기서 시스템 권한 팝업이 뜨고, 허용 시 기본 설정(ON·오전 9시)으로 등록된다
    await requestPermissionAndRegisterAsync();
  }, []);

  const handlePrimingLater = useCallback(async () => {
    setShowPriming(false);
    await markNotificationPrimingSeen();
  }, []);

  // 오늘의 말씀 API 호출 (풀이 interpretation 포함, 향상된 에러 핸들링)
  const {
    data: dailyVerse,
    isLoading,
    isError,
    isFetching,
    refetch,
    errorMessage,
  } = useDailyVerse();

  // 오늘의 말씀 저장(하트) 토글
  const { data: savedVerses } = useBookmarks();
  const toggleBookmark = useToggleBookmark();
  const isDailyBookmarked = useMemo(
    () =>
      !!dailyVerse &&
      !!savedVerses?.some(
        (item) =>
          item.source === "daily" && item.reference === dailyVerse.reference,
      ),
    [dailyVerse, savedVerses],
  );
  const handleToggleDailyBookmark = useCallback(() => {
    if (!dailyVerse) return;
    toggleBookmark.mutate({
      reference: dailyVerse.reference,
      text: dailyVerse.text,
      note: dailyVerse.interpretation || dailyVerse.reflection || undefined,
      source: "daily",
    });
  }, [dailyVerse, toggleBookmark]);

  const inputBarPaddingTop = 16;
  const inputBarPaddingBottom = useMemo(() => {
    return getInputBarPaddingBottom(isKeyboardVisible);
  }, [getInputBarPaddingBottom, isKeyboardVisible]);

  const trimmedMessage = useMemo(() => message.trim(), [message]);

  const handleSend = useCallback(() => {
    if (!trimmedMessage) {
      return;
    }

    Keyboard.dismiss();
    // 입력 내용은 개인적인 마음이라 보내지 않고 길이만 기록한다
    void logAnalyticsEvent("mood_submit", { length: trimmedMessage.length });
    router.push({
      pathname: "/result",
      params: { mood: trimmedMessage },
    });
    setMessage("");
  }, [router, trimmedMessage]);

  const handleKeyPress = useCallback(
    (e: { nativeEvent: { key: string } }) => {
      if (e.nativeEvent.key === "Enter" && trimmedMessage) {
        handleSend();
      }
    },
    [handleSend, trimmedMessage]
  );

  const content = (
    <View style={styles.container}>
        <View style={[styles.header, { paddingTop: headerPaddingTop }]}>
          <View style={styles.headerLogoWrapper}>
            <Image
              source={LOGO_IMAGE}
              style={styles.headerLogo}
              contentFit="contain"
              accessibilityLabel={t("home.logoA11y")}
            />
          </View>
          <Text style={styles.headerTitle}>{t("common.appName")}</Text>
          <TouchableOpacity
            style={styles.headerIconButton}
            onPress={() => router.push("/bookmarks")}
            activeOpacity={0.7}
            accessibilityRole="button"
            accessibilityLabel={t("home.openBookmarksA11y")}
          >
            <Ionicons name="heart-outline" size={24} color="#1E2939" />
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.settingsButton}
            onPress={() => router.push("/settings")}
            activeOpacity={0.7}
            accessibilityRole="button"
            accessibilityLabel={t("home.openSettingsA11y")}
          >
            <Ionicons name="settings-outline" size={24} color="#1E2939" />
          </TouchableOpacity>
        </View>

        <ScrollView
          contentContainerStyle={styles.scrollContent}
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.todayCard}>
            <View style={styles.todayHeader}>
              <View style={styles.todayAccent} />
              <Text style={styles.todayTitle}>{t("home.dailyVerseTitle")}</Text>
            </View>

            <View style={styles.verseCard}>
              {/* 데이터가 이미 있으면 백그라운드 리페치 중에도 말씀을 유지(깜빡임 방지) */}
              {isLoading || (isFetching && !dailyVerse) ? (
                <ActivityIndicator size="small" color={colors.primary} style={styles.loader} />
              ) : isError ? (
                <TouchableOpacity onPress={() => refetch()} activeOpacity={0.7}>
                  <Text style={styles.errorText}>{errorMessage}</Text>
                  <Text style={styles.retryText}>{t("home.tapToRetry")}</Text>
                </TouchableOpacity>
              ) : (
                <>
                  <Text style={styles.verseText}>
                    {dailyVerse?.text ?? t("home.loadingVerse")}
                  </Text>
                  <Text style={styles.verseReference}>
                    {dailyVerse?.reference ?? ""}
                  </Text>
                  {!!dailyVerse?.interpretation && (
                    <>
                      <View style={styles.verseDivider}>
                        {Array.from({ length: 80 }).map((_, i) => (
                          <View key={i} style={styles.verseDash} />
                        ))}
                      </View>
                      <Text style={styles.verseInterpretation}>
                        {dailyVerse.interpretation}
                      </Text>
                    </>
                  )}
                  {/* 액션 줄 — 다른 말씀 카드들과 동일하게 카드 하단 우측.
                      오늘의 말씀 풀이는 전역 콘텐츠라 공유·복사에 함께 담는다. */}
                  {!!dailyVerse && (
                    <VerseActionRow
                      reference={dailyVerse.reference}
                      text={dailyVerse.text}
                      note={dailyVerse.interpretation || undefined}
                      isSaved={isDailyBookmarked}
                      onToggleSave={handleToggleDailyBookmark}
                      analyticsSource="daily"
                      saveLabel={
                        isDailyBookmarked
                          ? t("home.dailyUnsaveA11y")
                          : t("home.dailySaveA11y")
                      }
                      style={styles.dailyActionRow}
                    />
                  )}
                </>
              )}
            </View>
          </View>

          {showWidgetPromo && (
            <TouchableOpacity
              style={styles.widgetPromo}
              activeOpacity={0.85}
              onPress={handleWidgetPromoOpen}
              accessibilityRole="button"
              accessibilityLabel={t("home.widgetBannerA11y")}
            >
              <View style={styles.widgetPromoIcon}>
                <Ionicons name="grid-outline" size={16} color={colors.primary} />
              </View>
              <View style={styles.widgetPromoTextWrap}>
                <Text style={styles.widgetPromoTitle}>{t("home.widgetBannerTitle")}</Text>
                <Text style={styles.widgetPromoSubtitle}>
                  {t("home.widgetBannerSubtitle")}
                </Text>
              </View>
              <TouchableOpacity
                style={styles.widgetPromoClose}
                onPress={handleWidgetPromoDismiss}
                hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
                accessibilityRole="button"
                accessibilityLabel={t("home.widgetBannerCloseA11y")}
              >
                <Ionicons name="close" size={16} color="#9CA3AF" />
              </TouchableOpacity>
            </TouchableOpacity>
          )}

          <View style={styles.shareSection}>
            <Text style={styles.shareTitle}>{t("home.moodTitle")}</Text>
            <Text
              style={styles.shareDescription}
              numberOfLines={1}
              adjustsFontSizeToFit
              minimumFontScale={0.8}
            >
              {t("home.moodSubtitle")}
            </Text>
          </View>
        </ScrollView>

        <View style={[styles.inputBar, { paddingTop: inputBarPaddingTop, paddingBottom: inputBarPaddingBottom }]}>
          <TextInput
            style={styles.textInput}
            placeholder={t("home.moodPlaceholder")}
            placeholderTextColor={colors.textSecondary}
            value={message}
            onChangeText={setMessage}
            multiline
            returnKeyType="send"
            onSubmitEditing={handleSend}
            onKeyPress={handleKeyPress}
            blurOnSubmit={true}
          />
          <TouchableOpacity
            style={[
              styles.sendButton,
              trimmedMessage.length > 0 && styles.sendButtonActive,
            ]}
            activeOpacity={0.7}
            onPress={handleSend}
            disabled={!trimmedMessage}
            accessibilityRole="button"
            accessibilityLabel={t("home.sendA11y")}
          >
            <Image
              source={SEND_ICON}
              style={styles.sendIcon}
              contentFit="contain"
              accessibilityLabel={t("home.sendIconA11y")}
            />
          </TouchableOpacity>
        </View>

        <NotificationPrimingModal
          visible={showPriming}
          onAccept={handlePrimingAccept}
          onLater={handlePrimingLater}
        />

        <WidgetGuideModal
          visible={showWidgetGuide}
          onClose={handleWidgetGuideClose}
        />
    </View>
  );

  // iOS/Android 모두 keyboard-controller 의 KeyboardAvoidingView 로 처리.
  // 안드로이드 adjustResize 가 안 먹는 기기(갤럭시 등)도 IME inset 기반으로 일관 처리됨.
  return (
    <KeyboardAvoidingView style={styles.flex} behavior="padding">
      {content}
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: {
    flex: 1,
  },
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    backgroundColor: "#FFFFFF",
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 24,
    paddingBottom: 16,
  },
  headerLogoWrapper: {
    height: 40,
    width: 40,
    borderRadius: 20,
    backgroundColor: "#E7F0FF",
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12,
  },
  headerLogo: {
    height: 28,
    width: 28,
  },
  headerTitle: {
    flex: 1,
    fontSize: scaleFont(24),
    lineHeight: scaleFont(32),
    fontWeight: "600",
    color: colors.textPrimary,
    fontFamily: baseFontFamily,
  },
  // 배경 칩 없이 톱니와 같은 크기의 아이콘 버튼.
  // 저장 상태 하트와는 위치(카드 하단 우측)로 구분된다.
  headerIconButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    marginLeft: 12,
  },
  settingsButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    marginLeft: 4,
  },
  scrollContent: {
    paddingHorizontal: 24,
    paddingTop: 32,
    paddingBottom: 120,
  },
  todayCard: {
    backgroundColor: "rgba(245, 243, 240, 0.3)",
    borderColor: "rgba(139, 115, 85, 0.1)",
    borderWidth: 1,
    borderRadius: 16,
    paddingHorizontal: 25,
    paddingVertical: 25,
    marginBottom: 48,
  },
  todayHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 16,
  },
  todayAccent: {
    height: 24,
    width: 4,
    borderRadius: 999,
    backgroundColor: colors.primary,
    marginRight: 8,
  },
  todayTitle: {
    fontSize: scaleFont(20),
    lineHeight: scaleFont(28),
    fontWeight: "600",
    color: colors.textPrimary,
    fontFamily: baseFontFamily,
  },
  dailyActionRow: {
    marginTop: 16,
  },
  verseCard: {
    backgroundColor: "#FFFFFF",
    borderColor: "rgba(229, 231, 235, 0.6)",
    borderWidth: 1,
    borderRadius: 14,
    paddingHorizontal: 25,
    paddingVertical: 25,
    minHeight: 120,
  },
  loader: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  errorText: {
    fontSize: scaleFont(16),
    color: colors.textSecondary,
    textAlign: "center",
    fontFamily: baseFontFamily,
    marginBottom: 8,
  },
  retryText: {
    fontSize: scaleFont(14),
    color: colors.primary,
    textAlign: "center",
    fontFamily: baseFontFamily,
    fontWeight: "500",
  },
  verseText: {
    fontSize: scaleFont(18),
    lineHeight: scaleFont(29),
    color: "#1E2939",
    marginBottom: 16,
    letterSpacing: -0.2,
    fontFamily: baseFontFamily,
    textAlign: "left",
  },
  verseReference: {
    fontSize: scaleFont(16),
    lineHeight: scaleFont(24),
    fontWeight: "600",
    color: colors.primary,
    letterSpacing: -0.2,
    fontFamily: baseFontFamily,
    alignSelf: "flex-end",
  },
  verseDivider: {
    flexDirection: "row",
    overflow: "hidden",
    marginTop: 20,
    marginBottom: 20,
  },
  verseDash: {
    width: 5,
    height: 1,
    marginRight: 4,
    backgroundColor: "#D1D5DC",
  },
  verseInterpretation: {
    fontSize: scaleFont(16),
    lineHeight: scaleFont(26),
    color: colors.textSecondary,
    letterSpacing: -0.2,
    fontFamily: baseFontFamily,
    textAlign: "left",
  },
  widgetPromo: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#F0F6FF",
    borderColor: "#D8E6FA",
    borderWidth: 1,
    borderRadius: 14,
    paddingVertical: 12,
    paddingHorizontal: 14,
    marginTop: -24,
    marginBottom: 24,
  },
  widgetPromoIcon: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center",
    marginRight: 10,
  },
  widgetPromoTextWrap: {
    flex: 1,
  },
  widgetPromoTitle: {
    fontSize: scaleFont(14),
    fontWeight: "600",
    color: colors.textPrimary,
    fontFamily: baseFontFamily,
  },
  widgetPromoSubtitle: {
    fontSize: scaleFont(12),
    lineHeight: scaleFont(17),
    color: colors.textSecondary,
    fontFamily: baseFontFamily,
    marginTop: 2,
  },
  widgetPromoClose: {
    marginLeft: 8,
    padding: 2,
  },
  shareSection: {
    alignItems: "center",
  },
  shareTitle: {
    fontSize: scaleFont(20),
    lineHeight: scaleFont(28),
    fontWeight: "500",
    color: "#1E2939",
    textAlign: "center",
    marginBottom: 12,
    fontFamily: baseFontFamily,
  },
  shareDescription: {
    fontSize: scaleFont(18),
    lineHeight: scaleFont(29),
    color: "#4A5565",
    textAlign: "center",
    fontFamily: baseFontFamily,
  },
  inputBar: {
    backgroundColor: "rgba(255, 255, 255, 0.95)",
    borderTopColor: colors.border,
    borderTopWidth: 1,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 24,
    paddingVertical: 16,
  },
  textInput: {
    flex: 1,
    backgroundColor: "#F3F3F5",
    borderColor: "#D1D5DC",
    borderWidth: 1,
    borderRadius: 14,
    paddingHorizontal: 16,
    fontSize: scaleFont(16),
    color: "#1E2939",
    fontFamily: baseFontFamily,
    minHeight: 44,
    maxHeight: 100,
    ...Platform.select({
      ios: {
        paddingTop: 12,
        paddingBottom: 12,
      },
      android: {
        paddingTop: 0,
        paddingBottom: 0,
        textAlignVertical: "center",
      },
    }),
  },
  sendButton: {
    height: 44,
    width: 44,
    borderRadius: 14,
    backgroundColor: "rgba(74, 144, 226, 0.5)",
    alignItems: "center",
    justifyContent: "center",
    marginLeft: 12,
  },
  sendIcon: {
    height: 16,
    width: 16,
  },
  sendButtonActive: {
    backgroundColor: colors.primary,
  },
});
