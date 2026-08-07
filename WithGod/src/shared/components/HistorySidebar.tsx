import {
  backfillMissingTitles,
  useClearHistory,
  useHistory,
  useRemoveHistoryEntry,
  useRenameHistoryEntry,
  type HistoryEntry,
} from "@/features/history";
import { useSafeAreaPadding } from "@/shared/hooks";
import { useAppDrawer } from "./AppDrawer";
import { t } from "@/shared/lib/i18n";
import { baseFontFamily, colors, scaleFont } from "@/shared/styles";
import { Ionicons } from "@expo/vector-icons";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Alert,
  InteractionManager,
  Keyboard,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { HistoryActionSheet } from "./HistoryActionSheet";
import { HistoryRenameModal } from "./HistoryRenameModal";

/**
 * 기록 사이드바. ChatGPT·Claude 앱과 같은 단순 목록 구성이다.
 *
 * - 제목·닫기 버튼 없음 (드로어 자체를 밀거나 탭해 닫는다)
 * - 우측 상단 검색 버튼 → 눌러서 검색창 노출
 * - 목록에는 **요약 제목만** 띄운다. 고민 원문은 적나라하고 어깨너머로도
 *   읽히므로, 원문은 길게 눌러 미리보기에서만 확인한다.
 */

type HistorySidebarProps = {
  onSelect: (entry: HistoryEntry) => void;
};

type Group = { key: string; label: string; items: HistoryEntry[] };

const startOfDay = (date: Date): number =>
  new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();

const groupByDate = (entries: HistoryEntry[]): Group[] => {
  const today = startOfDay(new Date());
  const day = 24 * 60 * 60 * 1000;
  const buckets: Record<string, HistoryEntry[]> = {
    today: [],
    yesterday: [],
    week: [],
    earlier: [],
  };

  for (const entry of entries) {
    const diff = today - startOfDay(new Date(entry.createdAt));
    if (diff <= 0) buckets.today.push(entry);
    else if (diff <= day) buckets.yesterday.push(entry);
    else if (diff < 7 * day) buckets.week.push(entry);
    else buckets.earlier.push(entry);
  }

  return (
    [
      { key: "today", label: t("history.groupToday") },
      { key: "yesterday", label: t("history.groupYesterday") },
      { key: "week", label: t("history.groupThisWeek") },
      { key: "earlier", label: t("history.groupEarlier") },
    ] as const
  )
    .map((group) => ({ ...group, items: buckets[group.key] }))
    .filter((group) => group.items.length > 0);
};

/** 목록에 띄울 한 줄. 서버가 만든 요약 제목이 없으면 원문으로 폴백한다. */
const displayTitle = (entry: HistoryEntry): string =>
  (entry.title || "").trim() || entry.mood;

export function HistorySidebar({ onSelect }: HistorySidebarProps) {
  useTranslation(); // 언어 변경 시 다시 그리기
  const { insets } = useSafeAreaPadding();
  const { data: entries = [], refetch } = useHistory();
  const removeEntry = useRemoveHistoryEntry();
  const renameEntry = useRenameHistoryEntry();
  const clearAll = useClearHistory();

  const [searching, setSearching] = useState(false);
  const [query, setQuery] = useState("");
  const [pressedEntry, setPressedEntry] = useState<HistoryEntry | null>(null);
  const [renameTarget, setRenameTarget] = useState<HistoryEntry | null>(null);

  // 사이드바는 항상 마운트돼 있다(스와이프로 드러나는 순간 이미 내용이 차 있어야
  // 하기 때문). 대신 드러나기 시작할 때마다 다시 읽어, 방금 결과 화면에서 남긴
  // 기록이 바로 반영되게 한다.
  // **완전히 열린 뒤에** 다시 읽는다. 드러나기 시작할 때(isVisible) 읽으면
  // 파일 I/O 가 여는 제스처 도중에 터져 JS 스레드를 붙잡고, 남은 터치가 유실돼
  // 드로어가 되돌아간다(콜드 스타트 첫 스와이프가 항상 실패하던 원인).
  // 목록 자체는 앱 시작 때 이미 읽어둬서 드래그 중에도 비어 보이지 않는다.
  const { isOpen, isVisible } = useAppDrawer();
  useEffect(() => {
    if (!isOpen) return;
    const task = InteractionManager.runAfterInteractions(() => {
      void refetch();
    });
    return () => task.cancel();
  }, [isOpen, refetch]);

  // 제목 없이 남은 기록(생성 실패·구버전 서버)에 뒤늦게 요약 제목을 채운다.
  // 네트워크 요청이라 더더욱 제스처가 끝난 뒤로 미룬다.
  // 실패해도 조용히 넘어가고 목록은 원문으로 계속 폴백한다.
  useEffect(() => {
    if (!isOpen || entries.length === 0) return;
    const task = InteractionManager.runAfterInteractions(() => {
      void (async () => {
        if (await backfillMissingTitles(entries)) await refetch();
      })();
    });
    return () => task.cancel();
  }, [isOpen, entries, refetch]);

  // 닫히면 검색 상태를 정리해 다음에 열 때 전체 목록부터 보이게 한다.
  useEffect(() => {
    if (isVisible) return;
    setSearching(false);
    setQuery("");
    setPressedEntry(null);
    setRenameTarget(null);
  }, [isVisible]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return entries;
    return entries.filter((entry) => {
      const haystack = [
        entry.title ?? "",
        entry.mood,
        ...entry.verses.map((verse) => `${verse.ref} ${verse.text}`),
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [entries, query]);

  const groups = useMemo(() => groupByDate(filtered), [filtered]);

  const closeSearch = () => {
    setSearching(false);
    setQuery("");
    Keyboard.dismiss();
  };

  const confirmRemove = (entry: HistoryEntry) => {
    setPressedEntry(null);
    Alert.alert(t("history.removeTitle"), t("history.removeBody"), [
      { text: t("common.cancel"), style: "cancel" },
      {
        text: t("history.removeConfirm"),
        style: "destructive",
        onPress: () => removeEntry.mutate(entry.id),
      },
    ]);
  };

  const confirmClearAll = () => {
    Alert.alert(t("history.clearTitle"), t("history.clearBody"), [
      { text: t("common.cancel"), style: "cancel" },
      {
        text: t("history.clearConfirm"),
        style: "destructive",
        onPress: () => clearAll.mutate(),
      },
    ]);
  };

  return (
    <View style={[styles.root, { paddingTop: insets.top + 8 }]}>
      <View style={styles.topBar}>
        {searching ? (
          <>
            <View style={styles.searchField}>
              <Ionicons name="search" size={16} color="#9CA3AF" />
              <TextInput
                style={styles.searchInput}
                value={query}
                onChangeText={setQuery}
                placeholder={t("history.searchPlaceholder")}
                placeholderTextColor="#B0B5BD"
                autoFocus
                returnKeyType="search"
                clearButtonMode="while-editing"
              />
            </View>
            <TouchableOpacity
              onPress={closeSearch}
              activeOpacity={0.7}
              hitSlop={8}
              style={styles.topButton}
              accessibilityRole="button"
              accessibilityLabel={t("common.cancel")}
            >
              <Ionicons name="close" size={20} color="#6B7280" />
            </TouchableOpacity>
          </>
        ) : (
          <>
            <View style={styles.topSpacer} />
            <TouchableOpacity
              onPress={() => setSearching(true)}
              activeOpacity={0.7}
              hitSlop={8}
              style={styles.topButton}
              accessibilityRole="button"
              accessibilityLabel={t("history.searchA11y")}
            >
              <Ionicons name="search" size={20} color="#1E2939" />
            </TouchableOpacity>
          </>
        )}
      </View>

      {filtered.length === 0 ? (
        <View style={styles.emptyWrap}>
          <Text style={styles.emptyTitle}>
            {query.trim()
              ? t("history.emptySearch")
              : t("history.emptyTitle")}
          </Text>
          {!query.trim() && (
            <Text style={styles.emptyDesc}>{t("history.emptyDesc")}</Text>
          )}
        </View>
      ) : (
        // 항목이 화면을 넘어가면 자동으로 스크롤된다(내용이 짧으면 스크롤 없음)
        <ScrollView
          style={styles.list}
          contentContainerStyle={styles.listContent}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          {groups.map((group) => (
            <View key={group.key} style={styles.group}>
              <Text style={styles.groupLabel}>{group.label}</Text>
              {group.items.map((entry) => (
                <TouchableOpacity
                  key={entry.id}
                  style={styles.item}
                  activeOpacity={0.6}
                  onPress={() => onSelect(entry)}
                  onLongPress={() => setPressedEntry(entry)}
                  delayLongPress={350}
                  accessibilityRole="button"
                  accessibilityLabel={t("history.itemA11y", {
                    mood: displayTitle(entry),
                  })}
                >
                  <Text style={styles.itemTitle} numberOfLines={1}>
                    {displayTitle(entry)}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          ))}
        </ScrollView>
      )}

      <View style={[styles.footer, { paddingBottom: insets.bottom + 12 }]}>
        {entries.length > 0 && (
          <TouchableOpacity
            onPress={confirmClearAll}
            activeOpacity={0.7}
            style={styles.clearButton}
            accessibilityRole="button"
            accessibilityLabel={t("history.clearTitle")}
          >
            <Ionicons name="trash-outline" size={15} color="#9CA3AF" />
            <Text style={styles.clearLabel}>{t("history.clearAction")}</Text>
          </TouchableOpacity>
        )}
        <Text style={styles.footerNote}>{t("history.privacyNote")}</Text>
      </View>

      <HistoryActionSheet
        entry={pressedEntry}
        onClose={() => setPressedEntry(null)}
        onOpen={(entry) => {
          setPressedEntry(null);
          onSelect(entry);
        }}
        onRename={(entry) => {
          setPressedEntry(null);
          setRenameTarget(entry);
        }}
        onDelete={confirmRemove}
      />

      <HistoryRenameModal
        visible={!!renameTarget}
        initialTitle={renameTarget ? displayTitle(renameTarget) : ""}
        onCancel={() => setRenameTarget(null)}
        onSubmit={(title) => {
          if (renameTarget) {
            renameEntry.mutate({ id: renameTarget.id, title });
          }
          setRenameTarget(null);
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: "#F7F8FA",
  },
  topBar: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingBottom: 10,
    gap: 8,
  },
  topSpacer: {
    flex: 1,
  },
  topButton: {
    padding: 4,
  },
  searchField: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    backgroundColor: "#FFFFFF",
    borderRadius: 10,
    paddingHorizontal: 10,
    paddingVertical: 7,
  },
  searchInput: {
    flex: 1,
    padding: 0,
    fontSize: scaleFont(14),
    color: colors.textPrimary,
    fontFamily: baseFontFamily,
  },
  list: {
    flex: 1,
  },
  listContent: {
    paddingHorizontal: 8,
    paddingBottom: 16,
  },
  group: {
    marginBottom: 14,
  },
  groupLabel: {
    fontSize: scaleFont(12),
    color: "#9CA3AF",
    fontFamily: baseFontFamily,
    paddingHorizontal: 12,
    marginBottom: 4,
  },
  item: {
    paddingVertical: 11,
    paddingHorizontal: 12,
    borderRadius: 10,
  },
  itemTitle: {
    fontSize: scaleFont(15),
    color: colors.textPrimary,
    fontFamily: baseFontFamily,
  },
  emptyWrap: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 24,
  },
  emptyTitle: {
    fontSize: scaleFont(15),
    color: colors.textSecondary,
    fontFamily: baseFontFamily,
    textAlign: "center",
  },
  emptyDesc: {
    marginTop: 6,
    fontSize: scaleFont(13),
    color: "#9CA3AF",
    fontFamily: baseFontFamily,
    textAlign: "center",
  },
  footer: {
    borderTopWidth: 1,
    borderTopColor: "rgba(0, 0, 0, 0.06)",
    paddingHorizontal: 16,
    paddingTop: 12,
  },
  clearButton: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingVertical: 6,
    marginBottom: 6,
  },
  clearLabel: {
    fontSize: scaleFont(13),
    color: "#9CA3AF",
    fontFamily: baseFontFamily,
  },
  footerNote: {
    fontSize: scaleFont(11),
    lineHeight: scaleFont(16),
    color: "#B0B5BD",
    fontFamily: baseFontFamily,
  },
});
