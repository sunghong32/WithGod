import {
  useBookmarks,
  useRemoveBookmark,
  type Bookmark,
  type BookmarkSource,
} from "@/features/bookmarks";
import { ScreenHeader } from "@/shared/components/ScreenHeader";
import { VerseActionRow } from "@/shared/components/VerseActionRow";
import { useSafeAreaPadding } from "@/shared/hooks";
import { baseFontFamily, colors, scaleFont } from "@/shared/styles";
import { Ionicons } from "@expo/vector-icons";
import { useCallback, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Platform,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

const SOURCE_LABELS: Record<BookmarkSource, string> = {
  daily: "오늘의 말씀",
  recommend: "위로의 말씀",
};

type Filter = "all" | BookmarkSource;

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "전체" },
  { key: "daily", label: "오늘의 말씀" },
  { key: "recommend", label: "위로의 말씀" },
];

function formatSavedDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const monthDay = `${date.getMonth() + 1}월 ${date.getDate()}일`;
  return date.getFullYear() === new Date().getFullYear()
    ? monthDay
    : `${date.getFullYear()}년 ${monthDay}`;
}

export default function BookmarksScreen() {
  const { insets } = useSafeAreaPadding();
  const { data: bookmarks, isLoading } = useBookmarks();
  const removeBookmark = useRemoveBookmark();
  const [filter, setFilter] = useState<Filter>("all");

  const filtered = useMemo(() => {
    if (!bookmarks) return [];
    if (filter === "all") return bookmarks;
    return bookmarks.filter((item) => item.source === filter);
  }, [bookmarks, filter]);

  // 지난 추천 코멘트는 다시 만들 수 없으므로 목록에서의 해제는 한 번 확인을 거친다
  const handleRemove = useCallback(
    (item: Bookmark) => {
      const message = `${item.reference} 말씀을 목록에서 뺄까요?`;
      const confirmRemove = () =>
        removeBookmark.mutate({
          reference: item.reference,
          source: item.source,
        });
      // react-native-web 의 Alert 는 빈 스텁이라 웹에서는 window.confirm 으로 확인
      if (Platform.OS === "web") {
        if (typeof window !== "undefined" && window.confirm(message)) {
          confirmRemove();
        }
        return;
      }
      Alert.alert("마음에서 빼기", message, [
        { text: "취소", style: "cancel" },
        { text: "빼기", style: "destructive", onPress: confirmRemove },
      ]);
    },
    [removeBookmark],
  );

  const renderItem = useCallback(
    ({ item }: { item: Bookmark }) => (
      <View style={styles.verseCard}>
        <Text style={styles.verseText}>
          {'"'}
          {item.text}
          {'"'}
        </Text>
        <Text style={styles.verseReference}>{item.reference}</Text>
        {!!item.tag && (
          <View style={styles.tagRow}>
            <View style={styles.tag}>
              <Text style={styles.tagText}>{item.tag}</Text>
            </View>
          </View>
        )}
        {!!item.note && (
          <View style={styles.noteBubble}>
            <Text style={styles.noteText}>{item.note}</Text>
          </View>
        )}
        <View style={styles.bottomRow}>
          <Text style={styles.metaText}>
            {SOURCE_LABELS[item.source]}
            {" · "}
            {formatSavedDate(item.createdAt)}
          </Text>
          <VerseActionRow
            reference={item.reference}
            text={item.text}
            isSaved
            onToggleSave={() => handleRemove(item)}
            analyticsSource={item.source}
            // 위로의 말씀 코멘트에는 사용자가 입력한 마음이 인용돼 있어 제외
            note={item.source === "daily" ? item.note : undefined}
            saveLabel={`${item.reference} 마음에서 빼기`}
          />
        </View>
        {!!item.mood && (
          <Text style={styles.moodText} numberOfLines={1}>
            {'"'}
            {item.mood}
            {'"'}
          </Text>
        )}
      </View>
    ),
    [handleRemove],
  );

  const hasAnyBookmark = (bookmarks?.length ?? 0) > 0;

  return (
    <View style={styles.container}>
      <ScreenHeader title="마음에 담은 말씀" />

      <View style={styles.filterRow}>
        {FILTERS.map(({ key, label }) => {
          const isActive = filter === key;
          return (
            <TouchableOpacity
              key={key}
              style={[styles.filterChip, isActive && styles.filterChipActive]}
              onPress={() => setFilter(key)}
              activeOpacity={0.7}
              hitSlop={{ top: 6, bottom: 6, left: 2, right: 2 }}
              accessibilityRole="button"
              accessibilityState={{ selected: isActive }}
              accessibilityLabel={`${label} 보기`}
            >
              <Text
                style={[
                  styles.filterChipText,
                  isActive && styles.filterChipTextActive,
                ]}
              >
                {label}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>

      {isLoading ? (
        <ActivityIndicator
          size="small"
          color={colors.primary}
          style={styles.loader}
        />
      ) : (
        <FlatList
          data={filtered}
          keyExtractor={(item) => `${item.source}:${item.reference}`}
          renderItem={renderItem}
          contentContainerStyle={[
            styles.listContent,
            { paddingBottom: insets.bottom + 32 },
            filtered.length === 0 && styles.listContentEmpty,
          ]}
          showsVerticalScrollIndicator={false}
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Ionicons name="heart-outline" size={44} color="#D1D5DC" />
              <Text style={styles.emptyTitle}>
                {hasAnyBookmark
                  ? "이 분류에 담은 말씀이 없어요"
                  : "아직 마음에 담은 말씀이 없어요"}
              </Text>
              {!hasAnyBookmark && (
                <Text style={styles.emptyDescription}>
                  말씀 카드의 하트를 누르면 여기에 담아드려요
                </Text>
              )}
            </View>
          }
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  filterRow: {
    flexDirection: "row",
    gap: 8,
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 4,
  },
  filterChip: {
    backgroundColor: "#FFFFFF",
    borderColor: colors.border,
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 16,
    paddingVertical: 9,
    minHeight: 36,
    justifyContent: "center",
  },
  filterChipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  filterChipText: {
    fontSize: scaleFont(13),
    fontWeight: "500",
    color: colors.textSecondary,
    fontFamily: baseFontFamily,
  },
  filterChipTextActive: {
    color: "#FFFFFF",
  },
  loader: {
    marginTop: 48,
  },
  listContent: {
    paddingHorizontal: 16,
    paddingTop: 16,
    gap: 16,
  },
  listContentEmpty: {
    flexGrow: 1,
    justifyContent: "center",
  },
  verseCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "rgba(139, 115, 85, 0.1)",
    padding: 20,
    shadowColor: "#8B7355",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
  },
  verseText: {
    fontSize: scaleFont(16),
    lineHeight: scaleFont(26),
    color: "#1E2939",
    marginBottom: 8,
    fontFamily: baseFontFamily,
  },
  verseReference: {
    fontSize: scaleFont(14),
    fontWeight: "600",
    color: colors.primary,
    fontFamily: baseFontFamily,
    marginBottom: 6,
  },
  tagRow: {
    alignSelf: "flex-end",
    marginBottom: 12,
  },
  tag: {
    backgroundColor: "rgba(106, 114, 130, 0.1)",
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 4,
  },
  tagText: {
    fontSize: scaleFont(12),
    fontWeight: "500",
    color: colors.textSecondary,
    fontFamily: baseFontFamily,
  },
  noteBubble: {
    backgroundColor: "rgba(245, 243, 240, 0.8)",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "rgba(139, 115, 85, 0.08)",
    padding: 14,
    marginTop: 4,
  },
  noteText: {
    fontSize: scaleFont(14),
    lineHeight: scaleFont(22),
    color: "#5C4A32",
    fontFamily: baseFontFamily,
  },
  bottomRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 14,
  },
  metaText: {
    flex: 1,
    fontSize: scaleFont(12),
    color: "#9CA3AF",
    fontFamily: baseFontFamily,
    marginRight: 8,
  },
  moodText: {
    fontSize: scaleFont(12),
    color: "#9CA3AF",
    fontFamily: baseFontFamily,
    marginTop: 4,
  },
  emptyContainer: {
    alignItems: "center",
    paddingHorizontal: 32,
  },
  emptyTitle: {
    fontSize: scaleFont(16),
    fontWeight: "500",
    color: colors.textSecondary,
    fontFamily: baseFontFamily,
    marginTop: 16,
    textAlign: "center",
  },
  emptyDescription: {
    fontSize: scaleFont(14),
    color: "#9CA3AF",
    fontFamily: baseFontFamily,
    marginTop: 6,
    textAlign: "center",
  },
});
