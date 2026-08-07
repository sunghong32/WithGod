import { t } from "@/shared/lib/i18n";
import { baseFontFamily, colors, scaleFont } from "@/shared/styles";
import { useEffect, useState } from "react";
import {
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

/**
 * 기록 이름 바꾸기 입력창.
 *
 * `Alert.prompt` 는 iOS 전용이라 안드로이드에서 아무것도 안 뜬다. 양쪽에서
 * 같게 보이도록 직접 만든다.
 */

type HistoryRenameModalProps = {
  visible: boolean;
  /** 처음 채워둘 이름(현재 제목) */
  initialTitle: string;
  onCancel: () => void;
  onSubmit: (title: string) => void;
};

export function HistoryRenameModal({
  visible,
  initialTitle,
  onCancel,
  onSubmit,
}: HistoryRenameModalProps) {
  const [value, setValue] = useState(initialTitle);

  // 열릴 때마다 현재 제목으로 초기화한다(직전에 고치던 값이 남지 않도록).
  useEffect(() => {
    if (visible) setValue(initialTitle);
  }, [visible, initialTitle]);

  const trimmed = value.trim();
  const canSave = trimmed.length > 0;

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onCancel}
    >
      <Pressable style={styles.backdrop} onPress={onCancel}>
        <KeyboardAvoidingView
          style={styles.center}
          behavior={Platform.OS === "ios" ? "padding" : undefined}
          pointerEvents="box-none"
        >
          {/* 카드 안쪽 탭이 backdrop 으로 새지 않도록 감싼다 */}
          <Pressable style={styles.card} onPress={() => {}}>
            <Text style={styles.title}>{t("history.renameTitle")}</Text>
            <TextInput
              style={styles.input}
              value={value}
              onChangeText={setValue}
              placeholder={t("history.renamePlaceholder")}
              placeholderTextColor="#B0B5BD"
              autoFocus
              maxLength={40}
              returnKeyType="done"
              onSubmitEditing={() => canSave && onSubmit(trimmed)}
            />
            <View style={styles.buttonRow}>
              <TouchableOpacity
                style={styles.button}
                onPress={onCancel}
                activeOpacity={0.7}
              >
                <Text style={styles.buttonText}>{t("common.cancel")}</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.button}
                onPress={() => canSave && onSubmit(trimmed)}
                activeOpacity={0.7}
                disabled={!canSave}
              >
                <Text
                  style={[
                    styles.buttonText,
                    styles.buttonPrimary,
                    !canSave && styles.buttonDisabled,
                  ]}
                >
                  {t("history.renameSave")}
                </Text>
              </TouchableOpacity>
            </View>
          </Pressable>
        </KeyboardAvoidingView>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(17, 24, 39, 0.35)",
  },
  center: {
    flex: 1,
    justifyContent: "center",
    paddingHorizontal: 32,
  },
  card: {
    backgroundColor: "#FFFFFF",
    borderRadius: 18,
    paddingTop: 20,
    paddingHorizontal: 20,
    paddingBottom: 8,
    shadowColor: "#000000",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.16,
    shadowRadius: 24,
    elevation: 12,
  },
  title: {
    fontSize: scaleFont(16),
    fontWeight: "700",
    color: colors.textPrimary,
    fontFamily: baseFontFamily,
    marginBottom: 14,
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: scaleFont(15),
    color: colors.textPrimary,
    fontFamily: baseFontFamily,
  },
  buttonRow: {
    flexDirection: "row",
    justifyContent: "flex-end",
    marginTop: 8,
  },
  button: {
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  buttonText: {
    fontSize: scaleFont(15),
    color: colors.textSecondary,
    fontFamily: baseFontFamily,
  },
  buttonPrimary: {
    color: colors.primary,
    fontWeight: "600",
  },
  buttonDisabled: {
    color: "#C7CBD1",
  },
});
