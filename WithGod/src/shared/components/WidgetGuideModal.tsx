import { baseFontFamily, colors, scaleFont } from "@/shared/styles";
import { Image } from "expo-image";
import {
  Modal,
  Platform,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

const WIDGET_PREVIEW = require("../assets/widget/daily-verse-preview.png");

type Props = {
  visible: boolean;
  onClose: () => void;
};

const IOS_STEPS = [
  "홈 화면의 빈 곳을 길게 눌러요",
  "왼쪽 위 '편집' → '위젯 추가'를 눌러요",
  "'신과함께'를 찾아 위젯을 추가해요",
];

const ANDROID_STEPS = [
  "홈 화면의 빈 곳을 길게 눌러요",
  "'위젯'을 선택해요",
  "'신과함께'의 오늘의 말씀을 홈 화면에 놓아요",
];

/**
 * 홈 화면 위젯 추가 방법 안내 모달.
 * OS가 위젯 추가를 앱에서 직접 실행할 방법을 제공하지 않아(원탭 API 부재)
 * 방법을 단계별로 안내한다.
 */
export function WidgetGuideModal({ visible, onClose }: Props) {
  const steps = Platform.OS === "ios" ? IOS_STEPS : ANDROID_STEPS;

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onClose}
    >
      <View style={styles.backdrop}>
        <View style={styles.card}>
          <Text style={styles.title}>홈 화면에서 만나는{"\n"}오늘의 말씀</Text>
          <Text style={styles.description}>
            앱을 열지 않아도 홈 화면 위젯으로{"\n"}매일 새로운 말씀을 볼 수 있어요.
          </Text>

          <Image
            source={WIDGET_PREVIEW}
            style={styles.preview}
            contentFit="contain"
            accessibilityLabel="오늘의 말씀 위젯 미리보기"
          />

          <View style={styles.steps}>
            {steps.map((step, index) => (
              <View key={index} style={styles.stepRow}>
                <View style={styles.stepBadge}>
                  <Text style={styles.stepBadgeText}>{index + 1}</Text>
                </View>
                <Text style={styles.stepText}>{step}</Text>
              </View>
            ))}
          </View>

          <TouchableOpacity
            style={styles.confirmButton}
            activeOpacity={0.8}
            onPress={onClose}
            accessibilityRole="button"
            accessibilityLabel="안내 닫기"
          >
            <Text style={styles.confirmButtonText}>확인했어요</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(16, 24, 40, 0.45)",
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 32,
  },
  card: {
    width: "100%",
    maxWidth: 340,
    backgroundColor: "#FFFFFF",
    borderRadius: 20,
    paddingHorizontal: 24,
    paddingTop: 28,
    paddingBottom: 20,
    alignItems: "center",
    shadowColor: "#000000",
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.15,
    shadowRadius: 32,
    elevation: 12,
  },
  title: {
    fontSize: scaleFont(20),
    lineHeight: scaleFont(28),
    fontWeight: "600",
    color: colors.textPrimary,
    textAlign: "center",
    fontFamily: baseFontFamily,
    marginBottom: 10,
  },
  description: {
    fontSize: scaleFont(15),
    lineHeight: scaleFont(24),
    color: "#4A5565",
    textAlign: "center",
    fontFamily: baseFontFamily,
    marginBottom: 16,
  },
  preview: {
    width: "100%",
    height: 120,
    marginBottom: 16,
  },
  steps: {
    alignSelf: "stretch",
    marginBottom: 20,
  },
  stepRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 10,
  },
  stepBadge: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: "#E7F0FF",
    alignItems: "center",
    justifyContent: "center",
    marginRight: 10,
  },
  stepBadgeText: {
    fontSize: scaleFont(12),
    fontWeight: "600",
    color: colors.primary,
    fontFamily: baseFontFamily,
  },
  stepText: {
    flex: 1,
    fontSize: scaleFont(14),
    lineHeight: scaleFont(20),
    color: colors.textPrimary,
    fontFamily: baseFontFamily,
  },
  confirmButton: {
    alignSelf: "stretch",
    backgroundColor: colors.primary,
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: "center",
  },
  confirmButtonText: {
    fontSize: scaleFont(16),
    fontWeight: "600",
    color: "#FFFFFF",
    fontFamily: baseFontFamily,
  },
});
