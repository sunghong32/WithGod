import { baseFontFamily, colors, scaleFont } from "@/shared/styles";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
} from "react-native";

import {
  type AppLanguageChoice,
  LANGUAGE_NATIVE_NAMES,
  SUPPORTED_LANGUAGES,
} from "@/shared/lib/i18n";

/**
 * 언어 선택 팝업 (이슈 #14).
 *
 * 기본은 '시스템 언어 따르기'(기기 언어 자동 감지)이고, 폰 언어와 다른 언어로
 * 말씀을 읽고 싶은 사용자를 위한 수동 오버라이드를 제공한다.
 * 언어 이름은 각 언어의 자기 표기(한국어/English/Español …)로 고정 — 번역하지
 * 않는 것이 관례라 i18n 키가 아니다.
 */
interface Props {
  visible: boolean;
  current: AppLanguageChoice;
  onSelect: (choice: AppLanguageChoice) => void;
  onClose: () => void;
}

export function LanguagePickerModal({ visible, current, onSelect, onClose }: Props) {
  const { t } = useTranslation();

  const options: { value: AppLanguageChoice; label: string }[] = [
    { value: "system", label: t("settings.languageSystem") },
    ...SUPPORTED_LANGUAGES.map((lang) => ({
      value: lang as AppLanguageChoice,
      label: LANGUAGE_NATIVE_NAMES[lang],
    })),
  ];

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.card} onPress={(e) => e.stopPropagation()}>
          <Text style={styles.title}>{t("settings.languageTitle")}</Text>

          <ScrollView style={styles.list} bounces={false}>
            {options.map((option) => {
              const selected = option.value === current;
              return (
                <TouchableOpacity
                  key={option.value}
                  style={styles.row}
                  onPress={() => onSelect(option.value)}
                  activeOpacity={0.7}
                  accessibilityRole="button"
                  accessibilityState={{ selected }}
                  accessibilityLabel={option.label}
                >
                  <Text style={[styles.rowLabel, selected && styles.rowLabelSelected]}>
                    {option.label}
                  </Text>
                  {selected && (
                    <Ionicons name="checkmark" size={20} color={colors.primary} />
                  )}
                </TouchableOpacity>
              );
            })}
          </ScrollView>

          <TouchableOpacity
            style={styles.closeButton}
            onPress={onClose}
            activeOpacity={0.7}
            accessibilityRole="button"
            accessibilityLabel={t("common.close")}
          >
            <Text style={styles.closeButtonText}>{t("common.close")}</Text>
          </TouchableOpacity>
        </Pressable>
      </Pressable>
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
    maxHeight: "70%",
    backgroundColor: "#FFFFFF",
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingTop: 24,
    paddingBottom: 12,
    shadowColor: "#000000",
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.15,
    shadowRadius: 32,
    elevation: 12,
  },
  title: {
    fontSize: scaleFont(18),
    fontWeight: "600",
    color: colors.textPrimary,
    textAlign: "center",
    fontFamily: baseFontFamily,
    marginBottom: 12,
  },
  list: {
    flexGrow: 0,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: 13,
    paddingHorizontal: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  rowLabel: {
    fontSize: scaleFont(15),
    color: colors.textPrimary,
    fontFamily: baseFontFamily,
  },
  rowLabelSelected: {
    fontWeight: "600",
    color: colors.primary,
  },
  closeButton: {
    alignSelf: "stretch",
    paddingVertical: 14,
    alignItems: "center",
  },
  closeButtonText: {
    fontSize: scaleFont(15),
    fontWeight: "500",
    color: "#6A7282",
    fontFamily: baseFontFamily,
  },
});
