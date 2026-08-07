import type { HistoryEntry } from "@/features/history";
import { useSafeAreaPadding } from "@/shared/hooks";
import { t } from "@/shared/lib/i18n";
import { baseFontFamily, colors, scaleFont } from "@/shared/styles";
import { Ionicons } from "@expo/vector-icons";
import { useEffect, useRef } from "react";
import {
  Animated,
  Easing,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

/**
 * 기록을 길게 눌렀을 때 뜨는 미리보기 + 액션 메뉴.
 *
 * ChatGPT 앱과 같은 구성 — 위에 상담 내용 미리보기 카드, 아래에 메뉴.
 * 목록에서는 요약 제목만 보이므로, 내용을 확인할 수단이 여기 필요하다.
 */

type HistoryActionSheetProps = {
  entry: HistoryEntry | null;
  onClose: () => void;
  onOpen: (entry: HistoryEntry) => void;
  onRename: (entry: HistoryEntry) => void;
  onDelete: (entry: HistoryEntry) => void;
};

export function HistoryActionSheet({
  entry,
  onClose,
  onOpen,
  onRename,
  onDelete,
}: HistoryActionSheetProps) {
  const { insets } = useSafeAreaPadding();
  const progress = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!entry) return;
    progress.setValue(0);
    Animated.timing(progress, {
      toValue: 1,
      duration: 200,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    }).start();
  }, [entry, progress]);

  if (!entry) return null;

  const scale = progress.interpolate({
    inputRange: [0, 1],
    outputRange: [0.94, 1],
  });

  return (
    <Modal visible transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        {/* box-none 이라 빈 영역 탭은 backdrop 으로 내려가 닫힌다.
            카드와 메뉴는 각자 탭을 삼켜 실수로 닫히지 않는다. */}
        <View
          pointerEvents="box-none"
          style={[
            styles.sheet,
            { paddingTop: insets.top + 24, paddingBottom: insets.bottom + 24 },
          ]}
        >
          <Animated.View
            style={[styles.previewCard, { opacity: progress, transform: [{ scale }] }]}
          >
            <ScrollView
              style={styles.previewScroll}
              contentContainerStyle={styles.previewContent}
              showsVerticalScrollIndicator={false}
              onStartShouldSetResponder={() => true}
            >
              <View style={styles.moodBubble}>
                <Text style={styles.moodText}>{entry.mood}</Text>
              </View>
              {entry.verses.map((verse, index) => (
                <View key={`${verse.ref}-${index}`} style={styles.verseBlock}>
                  <Text style={styles.verseText}>{verse.text}</Text>
                  <Text style={styles.verseRef}>{verse.ref}</Text>
                  {!!verse.comment && (
                    <Text style={styles.verseComment}>{verse.comment}</Text>
                  )}
                </View>
              ))}
            </ScrollView>
          </Animated.View>

          <Animated.View
            style={[styles.menu, { opacity: progress, transform: [{ scale }] }]}
          >
            <TouchableOpacity
              style={styles.menuRow}
              activeOpacity={0.6}
              onPress={() => onOpen(entry)}
            >
              <Ionicons name="open-outline" size={20} color="#1E2939" />
              <Text style={styles.menuLabel}>{t("history.actionOpen")}</Text>
            </TouchableOpacity>
            <View style={styles.menuDivider} />
            <TouchableOpacity
              style={styles.menuRow}
              activeOpacity={0.6}
              onPress={() => onRename(entry)}
            >
              <Ionicons name="pencil-outline" size={20} color="#1E2939" />
              <Text style={styles.menuLabel}>{t("history.actionRename")}</Text>
            </TouchableOpacity>
            <View style={styles.menuDivider} />
            <TouchableOpacity
              style={styles.menuRow}
              activeOpacity={0.6}
              onPress={() => onDelete(entry)}
            >
              <Ionicons name="trash-outline" size={20} color="#DC2626" />
              <Text style={[styles.menuLabel, styles.menuLabelDanger]}>
                {t("history.removeConfirm")}
              </Text>
            </TouchableOpacity>
          </Animated.View>
        </View>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "rgba(17, 24, 39, 0.35)",
  },
  sheet: {
    flex: 1,
    justifyContent: "center",
    paddingHorizontal: 20,
  },
  previewCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 20,
    maxHeight: "58%",
    overflow: "hidden",
    shadowColor: "#000000",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.16,
    shadowRadius: 24,
    elevation: 12,
  },
  previewScroll: {
    flexGrow: 0,
  },
  previewContent: {
    padding: 20,
  },
  moodBubble: {
    alignSelf: "flex-end",
    maxWidth: "88%",
    backgroundColor: "#4A90E2",
    borderRadius: 16,
    paddingVertical: 10,
    paddingHorizontal: 14,
    marginBottom: 16,
  },
  moodText: {
    fontSize: scaleFont(14),
    color: "#FFFFFF",
    fontFamily: baseFontFamily,
  },
  verseBlock: {
    marginBottom: 18,
  },
  verseText: {
    fontSize: scaleFont(15),
    lineHeight: scaleFont(23),
    color: colors.textPrimary,
    fontFamily: baseFontFamily,
  },
  verseRef: {
    marginTop: 6,
    fontSize: scaleFont(13),
    color: colors.primary,
    fontFamily: baseFontFamily,
  },
  verseComment: {
    marginTop: 8,
    fontSize: scaleFont(13),
    lineHeight: scaleFont(21),
    color: colors.textSecondary,
    fontFamily: baseFontFamily,
  },
  menu: {
    marginTop: 16,
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    overflow: "hidden",
    shadowColor: "#000000",
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.14,
    shadowRadius: 18,
    elevation: 10,
  },
  menuRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 15,
    paddingHorizontal: 18,
  },
  menuDivider: {
    height: 1,
    backgroundColor: "rgba(0, 0, 0, 0.06)",
    marginHorizontal: 18,
  },
  menuLabel: {
    fontSize: scaleFont(15),
    color: "#1E2939",
    fontFamily: baseFontFamily,
  },
  menuLabelDanger: {
    color: "#DC2626",
  },
});
