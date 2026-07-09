import { useDailyVerse } from "@/features/verse/hooks/useDailyVerse";
import { useKeyboardVisible, useSafeAreaPadding } from "@/shared/hooks";
import { baseFontFamily, scaleFont } from "@/shared/styles";
import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { useRouter } from "expo-router";
import { useCallback, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

const LOGO_IMAGE = require("../../shared/assets/images/Logo.png");
const SEND_ICON = require("../../shared/assets/images/send.png");

export default function HomeScreen() {
  const [message, setMessage] = useState("");
  const isKeyboardVisible = useKeyboardVisible();
  const { headerPaddingTop, getInputBarPaddingBottom } = useSafeAreaPadding();
  const router = useRouter();

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
                      <View style={styles.verseDivider} />
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
    </View>
  );

  // iOS: KeyboardAvoidingView behavior="padding"
  // Android: app.json의 softwareKeyboardLayoutMode: "resize"가 자동으로 처리
  if (Platform.OS === "ios") {
    return (
      <KeyboardAvoidingView style={styles.flex} behavior="padding">
        {content}
      </KeyboardAvoidingView>
    );
  }

  return content;
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
    borderBottomWidth: 1,
    borderBottomColor: "#D1D5DC",
    borderStyle: "dashed",
    marginTop: 20,
    marginBottom: 20,
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
