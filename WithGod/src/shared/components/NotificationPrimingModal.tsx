import { baseFontFamily, colors, scaleFont } from "@/shared/styles";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";
import { Modal, StyleSheet, Text, TouchableOpacity, View } from "react-native";

type Props = {
  visible: boolean;
  onAccept: () => void;
  onLater: () => void;
};

/**
 * 알림 권한 프라이밍(사전 안내) 모달.
 *
 * iOS 시스템 권한 팝업은 앱당 한 번만 뜨고 거부하면 재요청이 불가능하므로,
 * 맥락 없는 즉시 요청 대신 "왜 알림이 필요한지"를 먼저 설명하고
 * 사용자가 '알림 받기'를 눌렀을 때만 시스템 팝업을 띄운다.
 */
export function NotificationPrimingModal({ visible, onAccept, onLater }: Props) {
  const { t } = useTranslation();
  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onLater}
    >
      <View style={styles.backdrop}>
        <View style={styles.card}>
          <View style={styles.iconCircle}>
            <Ionicons name="notifications-outline" size={28} color={colors.primary} />
          </View>
          <Text style={styles.title}>{t("notifPriming.title")}</Text>
          <Text style={styles.description}>{t("notifPriming.body")}</Text>
          <TouchableOpacity
            style={styles.acceptButton}
            activeOpacity={0.8}
            onPress={onAccept}
            accessibilityRole="button"
            accessibilityLabel={t("notifPriming.acceptA11y")}
          >
            <Text style={styles.acceptButtonText}>{t("notifPriming.accept")}</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.laterButton}
            activeOpacity={0.6}
            onPress={onLater}
            accessibilityRole="button"
            accessibilityLabel={t("notifPriming.laterA11y")}
          >
            <Text style={styles.laterButtonText}>{t("notifPriming.later")}</Text>
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
    fontFamily: baseFontFamily,
    marginBottom: 10,
  },
  description: {
    fontSize: scaleFont(15),
    lineHeight: scaleFont(24),
    color: "#4A5565",
    textAlign: "center",
    fontFamily: baseFontFamily,
    marginBottom: 22,
  },
  acceptButton: {
    alignSelf: "stretch",
    backgroundColor: colors.primary,
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: "center",
  },
  acceptButtonText: {
    fontSize: scaleFont(16),
    fontWeight: "600",
    color: "#FFFFFF",
    fontFamily: baseFontFamily,
  },
  laterButton: {
    alignSelf: "stretch",
    paddingVertical: 12,
    alignItems: "center",
    marginTop: 6,
  },
  laterButtonText: {
    fontSize: scaleFont(15),
    color: colors.textSecondary,
    fontFamily: baseFontFamily,
  },
});
