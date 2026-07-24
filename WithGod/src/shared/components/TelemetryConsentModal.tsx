import { baseFontFamily, colors, scaleFont } from "@/shared/styles";
import { useEffect, useState } from "react";
import { Modal, StyleSheet, Text, TouchableOpacity, View } from "react-native";

import {
  needsConsentPrompt,
  setTelemetryEnabled,
} from "@/shared/lib/telemetry";

/**
 * 통계 수집 동의창(첫 실행).
 *
 * 유럽(EU/EEA)은 GDPR상 명시적 동의 전에는 수집할 수 없어, 해당 지역에서만
 * 첫 실행 시 이 창을 띄운다(needsConsentPrompt 가 지역·동의여부로 판단).
 * 그 외 지역은 이 창이 뜨지 않고 기본 수집되며, 설정에서 끌 수 있다.
 *
 * 동의를 미루고 앱을 그냥 쓸 수는 없게(수집을 확실히 정하도록) 두 버튼 중
 * 하나를 반드시 고르게 한다 — 배경 탭이나 뒤로가기로 닫히지 않는다.
 */
export function TelemetryConsentModal() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    let mounted = true;
    void needsConsentPrompt().then((needed) => {
      if (mounted && needed) setVisible(true);
    });
    return () => {
      mounted = false;
    };
  }, []);

  const decide = (granted: boolean) => {
    // 창을 먼저 닫아 응답성을 확보하고, 저장은 뒤에서 처리한다(실패해도 흐름 유지).
    setVisible(false);
    void setTelemetryEnabled(granted);
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      // onRequestClose(안드로이드 뒤로가기)에서 닫지 않는다 — 선택을 강제한다.
      onRequestClose={() => {}}
    >
      <View style={styles.backdrop}>
        <View style={styles.card}>
          <Text style={styles.title}>사용 통계 수집 동의</Text>

          <Text style={styles.description}>
            신과함께는 서비스 개선을 위해 익명으로 앱 사용 통계(화면 이동, 기능
            사용 등)를 수집합니다.
          </Text>
          <Text style={styles.description}>
            이름·이메일 같은 개인 식별 정보나 입력하신 마음 내용은 수집하지
            않습니다. 동의하지 않으셔도 모든 기능을 그대로 이용하실 수 있고,
            설정에서 언제든 바꿀 수 있어요.
          </Text>

          <TouchableOpacity
            style={styles.primaryButton}
            onPress={() => decide(true)}
            activeOpacity={0.8}
            accessibilityRole="button"
            accessibilityLabel="사용 통계 수집에 동의"
          >
            <Text style={styles.primaryButtonText}>동의</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.secondaryButton}
            onPress={() => decide(false)}
            activeOpacity={0.7}
            accessibilityRole="button"
            accessibilityLabel="사용 통계 수집에 동의하지 않음"
          >
            <Text style={styles.secondaryButtonText}>동의 안 함</Text>
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
    marginBottom: 14,
  },
  description: {
    fontSize: scaleFont(15),
    lineHeight: scaleFont(24),
    color: "#4A5565",
    textAlign: "left",
    fontFamily: baseFontFamily,
    marginBottom: 12,
  },
  primaryButton: {
    alignSelf: "stretch",
    backgroundColor: colors.primary,
    borderRadius: 14,
    paddingVertical: 14,
    alignItems: "center",
    marginTop: 8,
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
