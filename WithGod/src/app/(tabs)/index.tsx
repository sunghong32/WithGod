import { Image } from "expo-image";
import { useEffect, useState } from "react";
import {
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

const LOGO_IMAGE = require("../../shared/assets/images/Logo.png");
const LINK_ICON = require("../../shared/assets/images/chevron-right.png");
const SEND_ICON = require("../../shared/assets/images/send.png");

const baseFontFamily = Platform.select({
  ios: "System",
  android: "Roboto",
  web: "sans-serif",
  default: "sans-serif",
});

export default function HomeScreen() {
  const insets = useSafeAreaInsets();
  const [message, setMessage] = useState("");
  const [isKeyboardVisible, setIsKeyboardVisible] = useState(false);

  useEffect(() => {
    if (Platform.OS === "ios") {
      const showSub = Keyboard.addListener("keyboardWillShow", () => {
        setIsKeyboardVisible(true);
      });
      const hideSub = Keyboard.addListener("keyboardWillHide", () => {
        setIsKeyboardVisible(false);
      });
      return () => {
        showSub.remove();
        hideSub.remove();
      };
    }
  }, []);

  const headerPaddingTop = Platform.OS === "android"
    ? (StatusBar.currentHeight ?? 0) + 12
    : insets.top + 12;

  const inputBarPaddingBottom = Platform.OS === "ios"
    ? (isKeyboardVisible ? 16 : insets.bottom + 16)
    : Math.max(insets.bottom, 16);

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
              <Text style={styles.verseText}>
                수고하고 무거운 짐 진 자들아 다 내게로 오라 내가 너희를 쉬게
                하리라
              </Text>
              <View style={styles.verseFooter}>
                <Text style={styles.verseReference}>마태복음 11:28</Text>
                <TouchableOpacity style={styles.link} activeOpacity={0.7}>
                  <Text style={styles.linkLabel}>자세히 보기</Text>
                  <Image
                    source={LINK_ICON}
                    style={styles.linkIcon}
                    contentFit="contain"
                    accessibilityLabel="자세히 보기 아이콘"
                  />
                </TouchableOpacity>
              </View>
            </View>
          </View>

          <View style={styles.shareSection}>
            <Text style={styles.shareTitle}>마음을 나누어 주세요</Text>
            <Text style={styles.shareDescription}>
              고민이나 걱정이 있으시다면 편하게 말씀해 주세요{"\n"}
              성경의 위로가 되는 말씀을 전해드릴게요
            </Text>
          </View>
        </ScrollView>

        <View style={[styles.inputBar, { paddingBottom: inputBarPaddingBottom }]}>
          <TextInput
            style={styles.textInput}
            placeholder="지금 마음이나 고민을 들려주세요"
            placeholderTextColor="#6A7282"
            value={message}
            onChangeText={setMessage}
            multiline
          />
          <TouchableOpacity style={styles.sendButton} activeOpacity={0.7}>
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

  if (Platform.OS === "ios") {
    return (
      <KeyboardAvoidingView
        style={styles.flex}
        behavior="padding"
      >
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
    fontSize: 24,
    lineHeight: 32,
    fontWeight: "600",
    color: "#101828",
    fontFamily: baseFontFamily,
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
    fontSize: 20,
    lineHeight: 28,
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
  },
  verseText: {
    fontSize: 18,
    lineHeight: 29,
    color: "#1E2939",
    marginBottom: 16,
    letterSpacing: -0.2,
    fontFamily: baseFontFamily,
  },
  verseFooter: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  verseReference: {
    fontSize: 16,
    lineHeight: 24,
    fontWeight: "600",
    color: "#4A90E2",
    letterSpacing: -0.2,
    fontFamily: baseFontFamily,
  },
  link: {
    flexDirection: "row",
    alignItems: "center",
  },
  linkLabel: {
    fontSize: 16,
    lineHeight: 20,
    color: "#8B7355",
    marginRight: 6,
    fontFamily: baseFontFamily,
  },
  linkIcon: {
    height: 10,
    width: 4,
  },
  shareSection: {
    alignItems: "center",
  },
  shareTitle: {
    fontSize: 20,
    lineHeight: 28,
    fontWeight: "500",
    color: "#1E2939",
    textAlign: "center",
    marginBottom: 12,
    fontFamily: baseFontFamily,
  },
  shareDescription: {
    fontSize: 18,
    lineHeight: 29,
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
    paddingVertical: 11,
    fontSize: 16,
    color: "#1E2939",
    fontFamily: baseFontFamily,
    maxHeight: 100,
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
});
