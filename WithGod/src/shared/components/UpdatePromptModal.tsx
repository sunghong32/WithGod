import { baseFontFamily, colors, scaleFont } from "@/shared/styles";
import { useEffect, useState } from "react";
import { Linking, Modal, StyleSheet, Text, TouchableOpacity, View } from "react-native";

import { checkForUpdate, type UpdateStatus } from "@/shared/lib/appUpdate";

/**
 * 업데이트 안내 팝업.
 *
 * 앱 실행 시 서버에 최신 버전을 확인해, 새 버전이 있으면 스토어로 안내한다.
 * - forced: 닫을 수 없고 '업데이트'만 (구버전으로 계속 쓰지 못하게)
 * - optional: '업데이트' / '나중에'
 * 서버 미응답이면 아무것도 뜨지 않는다(checkForUpdate 가 none 반환).
 */
export function UpdatePromptModal() {
  const [status, setStatus] = useState<UpdateStatus>({ type: "none" });

  useEffect(() => {
    let mounted = true;
    void checkForUpdate().then((result) => {
      if (mounted) setStatus(result);
    });
    return () => {
      mounted = false;
    };
  }, []);

  if (status.type === "none") return null;

  const forced = status.type === "forced";

  const openStore = () => {
    void Linking.openURL(status.storeUrl).catch(() => {
      // 스토어 열기 실패는 조용히 넘긴다.
    });
    // 강제 업데이트가 아니면 스토어로 보낸 뒤 팝업을 닫는다.
    if (!forced) setStatus({ type: "none" });
  };

  const dismiss = () => setStatus({ type: "none" });

  return (
    <Modal
      visible
      transparent
      animationType="fade"
      // 강제 업데이트면 뒤로가기로도 닫히지 않게 한다.
      onRequestClose={forced ? () => {} : dismiss}
    >
      <View style={styles.backdrop}>
        <View style={styles.card}>
          <Text style={styles.title}>
            {forced ? "업데이트가 필요해요" : "새로운 버전이 있어요"}
          </Text>

          <Text style={styles.description}>
            {forced
              ? "원활한 이용을 위해 최신 버전으로 업데이트해 주세요. 업데이트 후 계속 이용하실 수 있어요."
              : "더 나아진 신과함께를 만나보세요. 스토어에서 최신 버전으로 업데이트할 수 있어요."}
          </Text>

          <TouchableOpacity
            style={styles.primaryButton}
            onPress={openStore}
            activeOpacity={0.8}
            accessibilityRole="button"
            accessibilityLabel="스토어에서 업데이트"
          >
            <Text style={styles.primaryButtonText}>업데이트</Text>
          </TouchableOpacity>

          {!forced && (
            <TouchableOpacity
              style={styles.secondaryButton}
              onPress={dismiss}
              activeOpacity={0.7}
              accessibilityRole="button"
              accessibilityLabel="나중에 업데이트"
            >
              <Text style={styles.secondaryButtonText}>나중에</Text>
            </TouchableOpacity>
          )}
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
    marginBottom: 12,
  },
  description: {
    fontSize: scaleFont(15),
    lineHeight: scaleFont(24),
    color: "#4A5565",
    textAlign: "center",
    fontFamily: baseFontFamily,
    marginBottom: 20,
  },
  primaryButton: {
    alignSelf: "stretch",
    backgroundColor: colors.primary,
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: "center",
  },
  primaryButtonText: {
    fontSize: scaleFont(16),
    fontWeight: "600",
    color: "#FFFFFF",
    fontFamily: baseFontFamily,
  },
  secondaryButton: {
    alignSelf: "stretch",
    paddingVertical: 14,
    alignItems: "center",
    marginTop: 4,
  },
  secondaryButtonText: {
    fontSize: scaleFont(15),
    fontWeight: "500",
    color: "#6A7282",
    fontFamily: baseFontFamily,
  },
});
