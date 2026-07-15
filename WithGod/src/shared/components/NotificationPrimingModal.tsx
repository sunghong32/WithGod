import { baseFontFamily, scaleFont } from "@/shared/styles";
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
  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onLater}
    >
      <View style={styles.backdrop}>
        <View style={styles.card}>
          <Text style={styles.emoji}>🙏</Text>
          <Text style={styles.title}>매일 말씀 알림</Text>
          <Text style={styles.description}>
            매일 원하는 시간에 오늘의 말씀과{"\n"}따뜻한 풀이를 보내드려요.
            {"\n"}알림을 받아보시겠어요?
          </Text>
          <TouchableOpacity
            style={styles.acceptButton}
            activeOpacity={0.8}
            onPress={onAccept}
            accessibilityRole="button"
            accessibilityLabel="알림 받기"
          >
            <Text style={styles.acceptButtonText}>좋아요, 알림 받을게요</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.laterButton}
            activeOpacity={0.6}
            onPress={onLater}
            accessibilityRole="button"
            accessibilityLabel="나중에 받기"
          >
            <Text style={styles.laterButtonText}>나중에요</Text>
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
  emoji: {
    fontSize: scaleFont(40),
    marginBottom: 12,
  },
  title: {
    fontSize: scaleFont(20),
    lineHeight: scaleFont(28),
    fontWeight: "600",
    color: "#101828",
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
    backgroundColor: "#4A90E2",
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
    color: "#6A7282",
    fontFamily: baseFontFamily,
  },
});
