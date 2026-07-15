import { useDailyVerse } from "@/features/verse/hooks/useDailyVerse";
import { NotificationPrimingModal } from "@/shared/components/NotificationPrimingModal";
import { useKeyboardVisible, useSafeAreaPadding } from "@/shared/hooks";
import {
  hasSeenNotificationPriming,
  markNotificationPrimingSeen,
} from "@/shared/lib/notificationSettings";
import {
  getPushPermissionStatusAsync,
  requestPermissionAndRegisterAsync,
} from "@/shared/lib/pushNotifications";
import { baseFontFamily, scaleFont } from "@/shared/styles";
import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { useFocusEffect, useRouter } from "expo-router";
import { useCallback, useMemo, useState } from "react";
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
  const [message, setMessage] = useState("");
  const [showPriming, setShowPriming] = useState(false);
  const isKeyboardVisible = useKeyboardVisible();
  const { headerPaddingTop, getInputBarPaddingBottom } = useSafeAreaPadding();
  const router = useRouter();

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
              accessibilityLabel="신과함께 로고"
            />
          </View>
          <Text style={styles.headerTitle}>신과함께</Text>
          <TouchableOpacity
            style={styles.settingsButton}
            onPress={() => router.push("/settings")}
            activeOpacity={0.7}
            accessibilityRole="button"
            accessibilityLabel="알림 설정"
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
              <Text style={styles.todayTitle}>오늘의 말씀</Text>
            </View>

            <View style={styles.verseCard}>
              {isLoading || isFetching ? (
                <ActivityIndicator size="small" color="#4A90E2" style={styles.loader} />
              ) : isError ? (
                <TouchableOpacity onPress={() => refetch()} activeOpacity={0.7}>
                  <Text style={styles.errorText}>{errorMessage}</Text>
                  <Text style={styles.retryText}>탭하여 다시 시도</Text>
                </TouchableOpacity>
              ) : (
                <>
                  <Text style={styles.verseText}>
                    {dailyVerse?.text ?? "말씀을 불러오는 중..."}
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
                </>
              )}
            </View>
          </View>

          <View style={styles.shareSection}>
            <Text style={styles.shareTitle}>오늘 당신의 마음은 어떤가요?</Text>
            <Text
              style={styles.shareDescription}
              numberOfLines={1}
              adjustsFontSizeToFit
              minimumFontScale={0.8}
            >
              편히 들려주시면 꼭 맞는 말씀을 전해드릴게요.
            </Text>
          </View>
        </ScrollView>

        <View style={[styles.inputBar, { paddingTop: inputBarPaddingTop, paddingBottom: inputBarPaddingBottom }]}>
          <TextInput
            style={styles.textInput}
            placeholder="지금 마음이나 고민을 들려주세요"
            placeholderTextColor="#6A7282"
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
            accessibilityLabel="마음 전송 버튼"
          >
            <Image
              source={SEND_ICON}
              style={styles.sendIcon}
              contentFit="contain"
              accessibilityLabel="마음 전송 아이콘"
            />
          </TouchableOpacity>
        </View>

        <NotificationPrimingModal
          visible={showPriming}
          onAccept={handlePrimingAccept}
          onLater={handlePrimingLater}
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
    backgroundColor: "#F9FAFB",
  },
  header: {
    backgroundColor: "#FFFFFF",
    borderBottomColor: "#E5E7EB",
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
    color: "#101828",
    fontFamily: baseFontFamily,
  },
  settingsButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    marginLeft: 12,
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
    backgroundColor: "#4A90E2",
    marginRight: 8,
  },
  todayTitle: {
    fontSize: scaleFont(20),
    lineHeight: scaleFont(28),
    fontWeight: "600",
    color: "#101828",
    fontFamily: baseFontFamily,
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
    color: "#6A7282",
    textAlign: "center",
    fontFamily: baseFontFamily,
    marginBottom: 8,
  },
  retryText: {
    fontSize: scaleFont(14),
    color: "#4A90E2",
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
    color: "#4A90E2",
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
    color: "#6A7282",
    letterSpacing: -0.2,
    fontFamily: baseFontFamily,
    textAlign: "left",
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
    borderTopColor: "#E5E7EB",
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
    backgroundColor: "#4A90E2",
  },
});
