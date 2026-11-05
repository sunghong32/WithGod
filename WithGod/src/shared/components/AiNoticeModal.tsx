import { baseFontFamily, colors, scaleFont } from "@/shared/styles";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";
import { Modal, StyleSheet, Text, TouchableOpacity, View } from "react-native";
import { ModalBackdrop } from "./ModalBackdrop";

type Props = {
  visible: boolean;
  onClose: () => void;
};

/**
 * AI 장애 사과 안내 모달(1회성).
 *
 * 확인 버튼 하나뿐이고, 닫으면(뒤로가기 포함) 다시 띄우지 않는다 —
 * 노출 여부는 aiNotice.ts 의 플래그로 홈 화면이 정한다.
 */
export function AiNoticeModal({ visible, onClose }: Props) {
  const { t } = useTranslation();
  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onClose}
    >
      <ModalBackdrop>
        <View style={styles.card}>
          <View style={styles.iconCircle}>
            <Ionicons name="heart-outline" size={28} color={colors.primary} />
          </View>
          <Text style={styles.title}>{t("aiNotice.title")}</Text>
          <Text style={styles.description}>{t("aiNotice.body1")}</Text>
          <Text style={[styles.description, styles.lastDescription]}>
            {t("aiNotice.body2")}
          </Text>
          <TouchableOpacity
            style={styles.confirmButton}
            activeOpacity={0.8}
            onPress={onClose}
            accessibilityRole="button"
            accessibilityLabel={t("aiNotice.confirmA11y")}
          >
            <Text style={styles.confirmButtonText}>{t("aiNotice.confirm")}</Text>
          </TouchableOpacity>
        </View>
      </ModalBackdrop>
    </Modal>
  );
}

const styles = StyleSheet.create({
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
  iconCircle: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: "#E7F0FF",
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 14,
  },
  title: {
    fontSize: scaleFont(20),
    lineHeight: scaleFont(28),
    fontWeight: "600",
    color: colors.textPrimary,
    textAlign: "center",
    fontFamily: baseFontFamily,
    marginBottom: 12,
  },
  description: {
    fontSize: scaleFont(15),
    lineHeight: scaleFont(24),
    color: "#4A5565",
    textAlign: "center",
    fontFamily: baseFontFamily,
    marginBottom: 10,
  },
  lastDescription: {
    marginBottom: 22,
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
