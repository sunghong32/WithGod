import {
  createIndexedTokenParser,
  createRecommendStreamParser,
  verseApi,
  type RecommendItem,
  type RecommendStreamController,
  type RecommendStreamVerse,
  type StreamKey,
} from "@/features/verse";
import { useBookmarks, useToggleBookmark } from "@/features/bookmarks";
import {
  appendHistory,
  loadHistory,
  type HistoryVerse,
} from "@/features/history";
import { ScreenHeader } from "@/shared/components/ScreenHeader";
import { VerseActionRow } from "@/shared/components/VerseActionRow";
import { useSafeAreaPadding } from "@/shared/hooks";
import { baseFontFamily, colors, scaleFont } from "@/shared/styles";
import { useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  AccessibilityInfo,
  ActivityIndicator,
  Animated,
  Easing,
  type LayoutChangeEvent,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

const TYPING_TICK_MS = 30;
const TYPING_CHARS_PER_TICK = 2;
const VERSE_TYPING_TICK_MS = 24;
const VERSE_TYPING_CHARS_PER_TICK = 1;
const AUTO_SCROLL_BOTTOM_THRESHOLD = 80;

// 로딩 문구 전환 타이밍.
// 첫 말씀까지 실측 2~3초(서버가 첫 카드 전에 OpenAI를 두 번 호출한다)라 문구
// 두 개를 보여줄 시간이 나온다. 안내를 위해 로딩을 인위적으로 늘리지는 않는다 —
// 응답이 빠르면 두 번째 문구는 스쳐 지나가는데, 기다림이 없던 사람은 어차피
// 자기가 적은 내용을 곱씹을 틈도 없었으므로 의도된 동작이다.
const LOADING_SWAP_DELAY_MS = 1200;
const LOADING_FADE_OUT_MS = 260;
const LOADING_FADE_IN_MS = 420;

type VerseTypingKey = "text" | "ref";

type VerseTypingTask = {
  index: number;
  key: VerseTypingKey;
  value: string;
  cursor: number;
};

export default function ResultScreen() {
  const { t } = useTranslation();
  // historyId 가 오면 지난 기록 다시보기 — 새로 스트리밍하지 않고 저장분을 보여준다.
  const { mood: moodParam, historyId } = useLocalSearchParams<{
    mood?: string;
    historyId?: string;
  }>();
  const isReplay = !!historyId;
  const [replayMood, setReplayMood] = useState("");
  const [isReplayLoading, setIsReplayLoading] = useState(isReplay);
  const mood = isReplay ? replayMood : (moodParam ?? "");
  const { insets } = useSafeAreaPadding();
  const [results, setResults] = useState<RecommendItem[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [activeField, setActiveField] = useState<{
    index: number;
    key: StreamKey;
  } | null>(null);
  const [cursorVisible, setCursorVisible] = useState(false);
  const [isVerseTyping, setIsVerseTyping] = useState(false);

  const streamRef = useRef<RecommendStreamController | null>(null);
  const scrollViewRef = useRef<ScrollView | null>(null);
  const draftRef = useRef<RecommendItem[]>([]);
  const isMountedRef = useRef(true);
  // 언마운트 시점의 기록 저장에 쓰는 스냅샷 — 정리 콜백은 state 를 볼 수 없다
  const resultsRef = useRef<RecommendItem[]>([]);
  const streamErrorRef = useRef<string | null>(null);
  const moodRef = useRef("");
  const historySavedRef = useRef(false);
  /**
   * 기록 저장 전용 수집기. 화면 표시용 파이프라인(타이핑 애니메이션·state)과
   * 완전히 분리해 **마운트 여부와 무관하게** 원본 토큰을 그대로 쌓는다.
   * 사용자가 스트리밍 중 화면을 벗어나도 연결을 끊지 않고 여기 계속 쌓아,
   * 완료되면 전체 내용을 기록에 남긴다.
   */
  const captureRef = useRef<{
    verses: Map<number, HistoryVerse>;
    parsers: Map<number, ReturnType<typeof createIndexedTokenParser>>;
    title: string;
    failed: boolean;
  }>({ verses: new Map(), parsers: new Map(), title: "", failed: false });
  const isBackgroundRef = useRef(false);
  const flushTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const typingQueueRef = useRef("");
  const typingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pendingDoneRef = useRef<unknown | null>(null);
  const receivedTokenRef = useRef(false);
  const hasVersesSeedRef = useRef(false);
  const isVerseTypingRef = useRef(false);
  const isIndexedModeRef = useRef(false);
  const currentIndexedTokenIndexRef = useRef(0);
  const queuedVerseIndicesRef = useRef<Set<number>>(new Set());
  const indexedTokenQueueRef = useRef<{ index: number; content: string }[]>([]);
  const indexedCompletedRef = useRef<Set<number>>(new Set());
  const indexedTokenTimerRef = useRef<ReturnType<typeof setInterval> | null>(
    null,
  );
  const verseTargetsRef = useRef<Map<number, RecommendStreamVerse>>(new Map());
  const indexedTokenParsersRef = useRef<
    Map<number, ReturnType<typeof createIndexedTokenParser>>
  >(new Map());
  const verseTypingQueueRef = useRef<VerseTypingTask[]>([]);
  const verseTypingTimerRef = useRef<ReturnType<typeof setInterval> | null>(
    null,
  );
  const timingRef = useRef({
    startAt: 0,
    metaAt: 0,
    firstTokenAt: 0,
  });
  const commentLoggedIndicesRef = useRef<Set<number>>(new Set());
  const autoScrollEnabledRef = useRef(true);
  const scrollMetricsRef = useRef({
    contentHeight: 0,
    layoutHeight: 0,
    offsetY: 0,
  });

  const updateAutoScrollEnabled = useCallback(() => {
    const { contentHeight, layoutHeight, offsetY } = scrollMetricsRef.current;
    const distanceToBottom = contentHeight - (offsetY + layoutHeight);
    autoScrollEnabledRef.current =
      distanceToBottom <= AUTO_SCROLL_BOTTOM_THRESHOLD;
  }, []);

  const scrollToBottom = useCallback((animated = false) => {
    scrollViewRef.current?.scrollToEnd({ animated });
  }, []);

  const handleScroll = useCallback(
    (event: NativeSyntheticEvent<NativeScrollEvent>) => {
      const { contentOffset, contentSize, layoutMeasurement } =
        event.nativeEvent;
      scrollMetricsRef.current = {
        contentHeight: contentSize.height,
        layoutHeight: layoutMeasurement.height,
        offsetY: contentOffset.y,
      };
      updateAutoScrollEnabled();
    },
    [updateAutoScrollEnabled],
  );

  const handleScrollLayout = useCallback(
    (event: LayoutChangeEvent) => {
      scrollMetricsRef.current.layoutHeight = event.nativeEvent.layout.height;
      updateAutoScrollEnabled();
    },
    [updateAutoScrollEnabled],
  );

  const handleContentSizeChange = useCallback(
    (_: number, contentHeight: number) => {
      const wasAutoScrollEnabled = autoScrollEnabledRef.current;
      scrollMetricsRef.current.contentHeight = contentHeight;
      if (isStreaming && wasAutoScrollEnabled) {
        autoScrollEnabledRef.current = true;
        requestAnimationFrame(() => scrollToBottom(false));
        return;
      }
      updateAutoScrollEnabled();
    },
    [isStreaming, scrollToBottom, updateAutoScrollEnabled],
  );

  const scheduleFlush = useCallback(() => {
    if (flushTimerRef.current) return;
    flushTimerRef.current = setTimeout(() => {
      flushTimerRef.current = null;
      setResults([...draftRef.current]);
    }, 16);
  }, []);

  const stopTyping = useCallback(() => {
    typingQueueRef.current = "";
    if (typingTimerRef.current) {
      clearInterval(typingTimerRef.current);
      typingTimerRef.current = null;
    }
  }, []);

  const stopVerseTyping = useCallback((clearQueue = true) => {
    if (verseTypingTimerRef.current) {
      clearInterval(verseTypingTimerRef.current);
      verseTypingTimerRef.current = null;
    }
    isVerseTypingRef.current = false;
    if (clearQueue) {
      verseTypingQueueRef.current = [];
      queuedVerseIndicesRef.current.clear();
    }
    setIsVerseTyping(false);
  }, []);

  const stopIndexedTokenPump = useCallback(() => {
    if (indexedTokenTimerRef.current) {
      clearInterval(indexedTokenTimerRef.current);
      indexedTokenTimerRef.current = null;
    }
  }, []);

  const handleItemStart = useCallback(
    (index: number) => {
      const draft = draftRef.current;
      if (draft[index]) return;
      draft[index] = { ref: "", text: "", comment: "", tag: "" };
      draftRef.current = draft;
      scheduleFlush();
    },
    [scheduleFlush],
  );

  const handleFieldUpdate = useCallback(
    (index: number, key: StreamKey, value: string) => {
      const draft = draftRef.current;
      const existing = draft[index] ?? {};
      const prevValue = typeof existing[key] === "string" ? existing[key] : "";
      if (hasVersesSeedRef.current && (key === "ref" || key === "text")) {
        return;
      }
      if (prevValue === value) return;
      if (
        __DEV__ &&
        key === "comment" &&
        prevValue.length === 0 &&
        value.length > 0 &&
        !commentLoggedIndicesRef.current.has(index)
      ) {
        commentLoggedIndicesRef.current.add(index);
        const now = Date.now();
        const ms = timingRef.current.startAt
          ? now - timingRef.current.startAt
          : 0;
        console.log(`[SSE Timing] comment[${index}] in ${ms}ms`);
      }
      draft[index] = { ...existing, [key]: value };
      draftRef.current = draft;
      scheduleFlush();
    },
    [scheduleFlush],
  );

  const handleActiveField = useCallback(
    (index: number, key: StreamKey | null) => {
      if (key === null) {
        setActiveField(null);
        return;
      }
      setActiveField({ index, key });
    },
    [],
  );

  const parserRef = useRef(
    createRecommendStreamParser({
      onItemStart: handleItemStart,
      onFieldUpdate: handleFieldUpdate,
      onActiveField: handleActiveField,
    }),
  );

  const getIndexedTokenParser = useCallback(
    (index: number) => {
      const cached = indexedTokenParsersRef.current.get(index);
      if (cached) return cached;

      const parser = createIndexedTokenParser({
        onFieldUpdate: (key, value) => {
          handleFieldUpdate(index, key, value);
        },
        onActiveField: (key) => {
          handleActiveField(index, key as StreamKey | null);
        },
        onObjectDone: () => {
          indexedCompletedRef.current.add(index);
        },
      });

      indexedTokenParsersRef.current.set(index, parser);
      return parser;
    },
    [handleActiveField, handleFieldUpdate],
  );

  const isVerseReadyForIndex = useCallback((index: number) => {
    const target = verseTargetsRef.current.get(index);
    if (!target) {
      // indexed 스트림에서는 해당 index verse 이벤트가 올 때까지 대기
      if (isIndexedModeRef.current) return false;
      return !hasVersesSeedRef.current;
    }
    const item = draftRef.current[index];
    if (!item) return false;
    const targetText = target.text ?? "";
    const targetRef = target.ref ?? "";
    return item.text === targetText && item.ref === targetRef;
  }, []);

  const startVerseTyping = useCallback(() => {
    if (
      verseTypingTimerRef.current ||
      verseTypingQueueRef.current.length === 0
    ) {
      return;
    }

    isVerseTypingRef.current = true;
    setIsVerseTyping(true);
    verseTypingTimerRef.current = setInterval(() => {
      const queue = verseTypingQueueRef.current;
      const task = queue[0];
      if (!task) {
        stopVerseTyping();
        return;
      }

      const nextCursor = Math.min(
        task.cursor + VERSE_TYPING_CHARS_PER_TICK,
        task.value.length,
      );
      task.cursor = nextCursor;

      const draft = [...draftRef.current];
      const existing = draft[task.index] ?? {
        ref: "",
        text: "",
        comment: "",
        tag: "",
      };
      const nextValue = task.value.slice(0, nextCursor);

      if (existing[task.key] !== nextValue) {
        draft[task.index] = { ...existing, [task.key]: nextValue };
        draftRef.current = draft;
        scheduleFlush();
      }

      if (nextCursor >= task.value.length) {
        queue.shift();
      }
      if (isVerseReadyForIndex(task.index)) {
        queuedVerseIndicesRef.current.delete(task.index);
      }
      if (queue.length === 0) {
        stopVerseTyping(false);
      }
    }, VERSE_TYPING_TICK_MS);
  }, [isVerseReadyForIndex, scheduleFlush, stopVerseTyping]);

  const enqueueVerseTypingForIndex = useCallback(
    (index: number) => {
      const target = verseTargetsRef.current.get(index);
      if (!target) return;
      if (queuedVerseIndicesRef.current.has(index)) return;
      if (isVerseReadyForIndex(index)) return;

      const draft = [...draftRef.current];
      const existing = draft[index] ?? {
        ref: "",
        text: "",
        comment: "",
        tag: "",
      };

      draft[index] = {
        ...existing,
        text: "",
        ref: "",
      };
      draftRef.current = draft;

      const text = target.text ?? "";
      const ref = target.ref ?? "";
      if (text) {
        verseTypingQueueRef.current.push({
          index,
          key: "text",
          value: text,
          cursor: 0,
        });
      }
      if (ref) {
        verseTypingQueueRef.current.push({
          index,
          key: "ref",
          value: ref,
          cursor: 0,
        });
      }
      queuedVerseIndicesRef.current.add(index);
      scheduleFlush();
      startVerseTyping();
    },
    [isVerseReadyForIndex, scheduleFlush, startVerseTyping],
  );

  const handleVerses = useCallback(
    (verses: RecommendStreamVerse[]) => {
      if (!Array.isArray(verses) || verses.length === 0) return;
      hasVersesSeedRef.current = true;

      verses.forEach((verse, index) => {
        const verseText = verse?.text ?? "";
        const verseRef = verse?.ref ?? "";
        verseTargetsRef.current.set(index, { text: verseText, ref: verseRef });
      });
      enqueueVerseTypingForIndex(currentIndexedTokenIndexRef.current);
    },
    [enqueueVerseTypingForIndex],
  );

  const handleVerse = useCallback(
    (index: number, verse: RecommendStreamVerse) => {
      if (index < 0) return;
      hasVersesSeedRef.current = true;

      const verseText = verse?.text ?? "";
      const verseRef = verse?.ref ?? "";
      verseTargetsRef.current.set(index, { text: verseText, ref: verseRef });
      if (index === currentIndexedTokenIndexRef.current) {
        enqueueVerseTypingForIndex(index);
      }
    },
    [enqueueVerseTypingForIndex],
  );

  const stopStream = useCallback(() => {
    streamRef.current?.close();
    streamRef.current = null;
  }, []);

  // ---------- 기록 수집기 ----------
  // 화면 표시용 파이프라인과 독립적으로 원본을 쌓는다. 마운트 여부를 보지 않는다.
  const captureVerse = useCallback(
    (index?: number, verse?: RecommendStreamVerse) => {
      if (typeof index !== "number" || !verse) return;
      const prev = captureRef.current.verses.get(index);
      captureRef.current.verses.set(index, {
        ref: verse.ref ?? prev?.ref ?? "",
        text: verse.text ?? prev?.text ?? "",
        comment: prev?.comment,
        tag: prev?.tag,
      });
    },
    [],
  );

  const captureToken = useCallback((content: string, index?: number) => {
    if (typeof index !== "number" || !content) return;
    let parser = captureRef.current.parsers.get(index);
    if (!parser) {
      parser = createIndexedTokenParser({
        onFieldUpdate: (key, value) => {
          const current = captureRef.current.verses.get(index) ?? {
            ref: "",
            text: "",
          };
          captureRef.current.verses.set(index, { ...current, [key]: value });
        },
        onActiveField: () => {},
      });
      captureRef.current.parsers.set(index, parser);
    }
    parser.feed(content);
  }, []);

  const resetCapture = useCallback(() => {
    captureRef.current = {
      verses: new Map(),
      parsers: new Map(),
      title: "",
      failed: false,
    };
  }, []);

  /**
   * 수집한 내용을 기록으로 남긴다.
   * - 에러가 났으면 남기지 않는다
   * - 받은 말씀이 하나도 없으면 남기지 않는다
   * - 앱이 강제 종료되면 애초에 호출되지 않는다
   */
  const saveCapture = useCallback(() => {
    if (isReplay || historySavedRef.current) return;
    if (captureRef.current.failed || streamErrorRef.current) return;

    const captured = [...captureRef.current.verses.entries()]
      .sort(([a], [b]) => a - b)
      .map(([, verse]) => verse);
    // indexed 모드가 아닌 레거시 경로면 화면에 그려진 결과를 그대로 쓴다
    const verses = (
      captured.length > 0
        ? captured
        : resultsRef.current.map((item) => ({
            ref: item.ref ?? "",
            text: item.text ?? "",
            comment: item.comment || undefined,
            tag: item.tag || undefined,
          }))
    ).filter((verse) => !!verse.ref && !!verse.text);

    if (verses.length === 0) return;
    historySavedRef.current = true;
    void appendHistory({
      mood: moodRef.current,
      title: captureRef.current.title || undefined,
      verses,
    });
  }, [isReplay]);

  const extractResults = useCallback(
    (payload: unknown): RecommendItem[] | null => {
      const unwrap = (
        value: unknown,
        depth: number,
      ): RecommendItem[] | null => {
        if (Array.isArray(value)) {
          // 서버가 배열 원소로 null/문자열 등을 보내도 렌더 경로가 깨지지 않도록 방어
          return value.filter(
            (item): item is RecommendItem =>
              !!item && typeof item === "object",
          );
        }
        if (!value || typeof value !== "object" || depth <= 0) return null;
        const record = value as Record<string, unknown>;
        const candidates = [
          record.results,
          record.result,
          record.comments,
          record.data,
        ];
        for (const candidate of candidates) {
          const found = unwrap(candidate, depth - 1);
          if (found) return found;
        }
        return null;
      };

      return unwrap(payload, 2);
    },
    [],
  );

  const finalizeResults = useCallback((items: RecommendItem[]) => {
    draftRef.current = items;
    setResults(items);
  }, []);

  const finalizeFromPayload = useCallback(
    (payload: unknown) => {
      const extracted = extractResults(payload);
      const fallback = draftRef.current
        .map((item) => ({
          ref: item?.ref ?? "",
          text: item?.text ?? "",
          comment: item?.comment ?? "",
          tag: item?.tag ?? "",
        }))
        .filter(
          (item) =>
            item.ref.length > 0 ||
            item.text.length > 0 ||
            item.comment.length > 0 ||
            item.tag.length > 0,
        );

      // done 이벤트에 결과 payload가 없거나 빈 배열([])인 경우,
      // 스트리밍 중 누적된 draft를 최종 결과로 사용
      if (!extracted || extracted.length === 0) {
        const reason = !extracted
          ? "no extractable payload"
          : "extracted empty array";
        if (fallback.length > 0) {
          if (__DEV__) {
            console.log(
              `[SSE] done payload empty (${reason}) -> finalize from draft (${fallback.length} items)`,
            );
          }
          finalizeResults(fallback);
          setIsStreaming(false);
          return;
        }

        if (__DEV__) {
          console.group("[SSE Finalize Error]");
          console.log(`Reason: ${reason} and no draft fallback`);
          console.log("Done payload:", payload);
          console.log("Current draft:", draftRef.current);
          console.groupEnd();
        }
        setStreamError(t("result.loadFailed"));
        setIsStreaming(false);
        return;
      }

      const errorItem = extracted.find(
        (item) =>
          item &&
          typeof item === "object" &&
          "error" in item &&
          typeof (item as { error?: string }).error === "string",
      ) as { error?: string } | undefined;

      if (errorItem?.error) {
        setStreamError(errorItem.error);
        setIsStreaming(false);
        return;
      }

      finalizeResults(extracted);
      setIsStreaming(false);
    },
    [extractResults, finalizeResults, t],
  );

  const tryFinalizePendingDone = useCallback(() => {
    if (pendingDoneRef.current === null) return;
    if (typingQueueRef.current.length > 0) return;
    if (indexedTokenQueueRef.current.length > 0) return;
    if (isVerseTypingRef.current) return;

    const payload = pendingDoneRef.current;
    pendingDoneRef.current = null;
    finalizeFromPayload(payload);
  }, [finalizeFromPayload]);

  const ensureIndexedTokenPump = useCallback(() => {
    if (indexedTokenTimerRef.current) return;

    indexedTokenTimerRef.current = setInterval(() => {
      const currentIndex = currentIndexedTokenIndexRef.current;

      if (!isVerseReadyForIndex(currentIndex)) {
        tryFinalizePendingDone();
        return;
      }

      const queue = indexedTokenQueueRef.current;
      const queueItem = queue.find((item) => item.index === currentIndex);

      if (!queueItem) {
        if (indexedCompletedRef.current.has(currentIndex)) {
          const nextIndex = currentIndex + 1;
          currentIndexedTokenIndexRef.current = nextIndex;
          enqueueVerseTypingForIndex(nextIndex);
          tryFinalizePendingDone();
          return;
        }

        if (queue.length === 0) {
          stopIndexedTokenPump();
        }
        tryFinalizePendingDone();
        return;
      }

      const chunk = queueItem.content.slice(0, TYPING_CHARS_PER_TICK);
      queueItem.content = queueItem.content.slice(TYPING_CHARS_PER_TICK);

      const parser = getIndexedTokenParser(currentIndex);
      parser.feed(chunk);

      if (queueItem.content.length === 0) {
        const removeIdx = queue.indexOf(queueItem);
        if (removeIdx >= 0) queue.splice(removeIdx, 1);
      }

      if (
        indexedCompletedRef.current.has(currentIndex) &&
        !queue.some((item) => item.index === currentIndex)
      ) {
        const nextIndex = currentIndex + 1;
        currentIndexedTokenIndexRef.current = nextIndex;
        enqueueVerseTypingForIndex(nextIndex);
      }

      if (queue.length === 0 && pendingDoneRef.current !== null) {
        tryFinalizePendingDone();
      }
    }, TYPING_TICK_MS);
  }, [
    enqueueVerseTypingForIndex,
    getIndexedTokenParser,
    isVerseReadyForIndex,
    stopIndexedTokenPump,
    tryFinalizePendingDone,
  ]);

  const buildTypingPayload = useCallback((items: RecommendItem[]) => {
    const normalized = items.map((item) => ({
      ref: item.ref ?? "",
      text: item.text ?? "",
      tag: item.tag ?? "",
      comment: item.comment ?? "",
    }));
    return JSON.stringify({ result: normalized }, null, 2);
  }, []);

  const ensureTyping = useCallback(() => {
    if (isVerseTypingRef.current) return;
    if (typingTimerRef.current) return;
    typingTimerRef.current = setInterval(() => {
      const buffer = typingQueueRef.current;
      if (!buffer) {
        if (typingTimerRef.current) {
          clearInterval(typingTimerRef.current);
          typingTimerRef.current = null;
        }
        tryFinalizePendingDone();
        return;
      }
      const chunk = buffer.slice(0, TYPING_CHARS_PER_TICK);
      typingQueueRef.current = buffer.slice(TYPING_CHARS_PER_TICK);
      parserRef.current.feed(chunk);
    }, TYPING_TICK_MS);
  }, [tryFinalizePendingDone]);

  const enqueueTokens = useCallback(
    (content: string) => {
      if (!content) return;
      typingQueueRef.current += content;
      ensureTyping();
    },
    [ensureTyping],
  );

  useEffect(() => {
    if (isVerseTyping) return;
    if (!typingQueueRef.current) return;
    ensureTyping();
    tryFinalizePendingDone();
  }, [ensureTyping, isVerseTyping, tryFinalizePendingDone]);

  const handleStreamDone = useCallback(
    (payload: unknown) => {
      if (!isMountedRef.current) return;
      setActiveField(null);
      stopStream();
      if (__DEV__) {
        const now = Date.now();
        const total = timingRef.current.startAt
          ? now - timingRef.current.startAt
          : 0;
        const firstTokenAt = timingRef.current.firstTokenAt;
        const afterFirstToken = firstTokenAt ? now - firstTokenAt : 0;
        console.log(
          `[SSE Timing] done in ${total}ms (after first token ${afterFirstToken}ms)`,
        );
      }
      if (!receivedTokenRef.current) {
        const extracted = extractResults(payload);
        if (extracted && extracted.length > 0) {
          parserRef.current.reset();
          draftRef.current = [];
          setResults([]);
          const typingPayload = buildTypingPayload(extracted);
          pendingDoneRef.current = payload;
          enqueueTokens(typingPayload);
          return;
        }
      }
      if (
        isIndexedModeRef.current &&
        (indexedTokenQueueRef.current.length > 0 || isVerseTypingRef.current)
      ) {
        pendingDoneRef.current = payload;
        tryFinalizePendingDone();
        return;
      }
      if (typingQueueRef.current) {
        pendingDoneRef.current = payload;
        tryFinalizePendingDone();
        return;
      }
      finalizeFromPayload(payload);
    },
    [
      buildTypingPayload,
      enqueueTokens,
      extractResults,
      finalizeFromPayload,
      stopStream,
      tryFinalizePendingDone,
    ],
  );

  const startStream = useCallback(() => {
    if (!mood) return;
    stopStream();
    stopTyping();
    stopVerseTyping();
    stopIndexedTokenPump();
    parserRef.current.reset();
    indexedTokenParsersRef.current.clear();
    indexedTokenQueueRef.current = [];
    indexedCompletedRef.current.clear();
    verseTargetsRef.current.clear();
    isIndexedModeRef.current = false;
    currentIndexedTokenIndexRef.current = 0;
    draftRef.current = [];
    pendingDoneRef.current = null;
    receivedTokenRef.current = false;
    hasVersesSeedRef.current = false;
    commentLoggedIndicesRef.current.clear();
    resetCapture();
    isBackgroundRef.current = false;
    historySavedRef.current = false;
    timingRef.current = {
      startAt: Date.now(),
      metaAt: 0,
      firstTokenAt: 0,
    };
    if (__DEV__) {
      console.log("[SSE Timing] start");
    }
    setResults([]);
    setStreamError(null);
    setIsStreaming(true);
    setActiveField(null);

    streamRef.current = verseApi.streamRecommendation(
      { mood: mood ?? "" },
      {
        onMeta: () => {
          if (!timingRef.current.metaAt) {
            timingRef.current.metaAt = Date.now();
            if (__DEV__) {
              const ms = timingRef.current.metaAt - timingRef.current.startAt;
              console.log(`[SSE Timing] meta in ${ms}ms`);
            }
          }
        },
        onVerses: (verses) => {
          if (!isMountedRef.current) return;
          if (__DEV__) {
            const now = Date.now();
            const ms = timingRef.current.startAt
              ? now - timingRef.current.startAt
              : 0;
            console.log(
              `[SSE Timing] verses in ${ms}ms (${verses.length} items)`,
            );
          }
          handleVerses(verses);
        },
        onTitle: (title) => {
          captureRef.current.title = title;
        },
        onVerse: (event) => {
          captureVerse(event.index, event.verse);
          if (!isMountedRef.current) return;
          const index = event.index;
          const verse = event.verse;
          if (typeof index !== "number" || !verse) return;
          if (__DEV__) {
            const now = Date.now();
            const ms = timingRef.current.startAt
              ? now - timingRef.current.startAt
              : 0;
            console.log(`[SSE Timing] verse[${index}] in ${ms}ms`);
          }
          handleVerse(index, verse);
        },
        onToken: (content, tokenIndex) => {
          captureToken(content, tokenIndex);
          if (!isMountedRef.current) return;
          receivedTokenRef.current = true;
          if (!timingRef.current.firstTokenAt) {
            timingRef.current.firstTokenAt = Date.now();
            if (__DEV__) {
              const ms =
                timingRef.current.firstTokenAt - timingRef.current.startAt;
              console.log(`[SSE Timing] first token in ${ms}ms`);
            }
          }
          if (typeof tokenIndex === "number") {
            isIndexedModeRef.current = true;
            indexedTokenQueueRef.current.push({ index: tokenIndex, content });
            ensureIndexedTokenPump();
            return;
          }
          enqueueTokens(content);
        },
        onDone: (payload) => {
          // 백그라운드(화면 이탈 후)면 UI 갱신 없이 기록만 남기고 연결을 닫는다
          if (isBackgroundRef.current) {
            saveCapture();
            stopStream();
            return;
          }
          handleStreamDone(payload);
        },
        onError: (message, context) => {
          // 에러가 나면 기록을 남기지 않는다 — 백그라운드에서도 마찬가지
          captureRef.current.failed = true;
          if (isBackgroundRef.current) {
            stopStream();
            return;
          }
          if (!isMountedRef.current) return;
          setStreamError(message || t("result.loadFailed"));
          setIsStreaming(false);
          if (__DEV__) {
            const now = Date.now();
            const total = timingRef.current.startAt
              ? now - timingRef.current.startAt
              : 0;
            console.log(`[SSE Timing] error after ${total}ms`);
            console.group("[SSE Error]");
            console.log("Message:", message);
            console.log("Context:", context);
            if (context?.status) {
              console.log("HTTP Status:", context.status);
            }
            if (context?.url) {
              console.log("URL:", context.url);
            }
            if (context?.responseText) {
              console.log("Response Text (tail):", context.responseText);
            }
            console.groupEnd();
          }
          stopTyping();
          // 에러 이후에도 verse 타이핑·indexed 토큰 펌프 인터벌이 계속 돌지 않도록 함께 정지
          stopVerseTyping();
          stopIndexedTokenPump();
          pendingDoneRef.current = null;
          stopStream();
        },
      },
    );
  }, [
    captureToken,
    captureVerse,
    enqueueTokens,
    ensureIndexedTokenPump,
    handleStreamDone,
    handleVerse,
    handleVerses,
    mood,
    resetCapture,
    saveCapture,
    stopStream,
    stopTyping,
    stopVerseTyping,
    stopIndexedTokenPump,
    t,
  ]);

  const refetch = useCallback(() => {
    startStream();
  }, [startStream]);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      // 스트리밍이 아직 안 끝났으면 연결을 끊지 않고 백그라운드로 마저 받는다.
      // 실수로 화면을 벗어나도 기록에는 온전한 내용이 남게 하기 위해서다.
      // 화면용 타이머는 전부 멈추므로 비용은 수신·파싱뿐이다.
      if (streamRef.current && !isReplay && !captureRef.current.failed) {
        isBackgroundRef.current = true;
      } else {
        stopStream();
        saveCapture();
      }
      stopTyping();
      stopVerseTyping();
      stopIndexedTokenPump();
      if (flushTimerRef.current) {
        clearTimeout(flushTimerRef.current);
        flushTimerRef.current = null;
      }
    };
  }, [
    isReplay,
    saveCapture,
    stopStream,
    stopTyping,
    stopVerseTyping,
    stopIndexedTokenPump,
  ]);

  useEffect(() => {
    if (isReplay || !mood) return;
    startStream();
    return () => {
      // 백그라운드 수신으로 넘어갔으면 연결을 유지한다
      if (!isBackgroundRef.current) stopStream();
      stopVerseTyping();
      stopIndexedTokenPump();
    };
  }, [
    isReplay,
    mood,
    startStream,
    stopStream,
    stopVerseTyping,
    stopIndexedTokenPump,
  ]);

  // 지난 기록 다시보기: 로컬 저장분을 그대로 채운다(스트리밍/타이핑 없음).
  useEffect(() => {
    if (!historyId) return;
    let active = true;
    void (async () => {
      const entries = await loadHistory();
      const entry = entries.find((item) => item.id === historyId);
      if (!active) return;
      if (entry) {
        setReplayMood(entry.mood);
        setResults(
          entry.verses.map((verse) => ({
            ref: verse.ref,
            text: verse.text,
            comment: verse.comment ?? "",
            tag: verse.tag ?? "",
          })),
        );
      }
      setIsReplayLoading(false);
    })();
    return () => {
      active = false;
    };
  }, [historyId]);

  useEffect(() => {
    resultsRef.current = results;
  }, [results]);

  useEffect(() => {
    streamErrorRef.current = streamError;
  }, [streamError]);

  useEffect(() => {
    moodRef.current = mood;
  }, [mood]);

  useEffect(() => {
    if (!isStreaming) {
      setCursorVisible(false);
      return;
    }
    setCursorVisible(true);
    const timer = setInterval(() => setCursorVisible((prev) => !prev), 500);
    return () => clearInterval(timer);
  }, [isStreaming]);

  useEffect(() => {
    if (!isStreaming) return;
    autoScrollEnabledRef.current = true;
    requestAnimationFrame(() => scrollToBottom(false));
  }, [isStreaming, scrollToBottom]);

  const hasVisibleResultContent = useCallback((item: RecommendItem) => {
    const text = item.text ?? "";
    const ref = item.ref ?? "";
    const comment = item.comment ?? "";
    const tag = (item.tag ?? "").trim();
    return (
      text.length > 0 || ref.length > 0 || comment.length > 0 || tag.length > 0
    );
  }, []);

  const visibleResults = results.filter(hasVisibleResultContent);

  const showLoading =
    (isStreaming || isReplayLoading) && visibleResults.length === 0;
  const hasError =
    !isReplayLoading &&
    ((!isStreaming && visibleResults.length === 0) ||
      (!!streamError && visibleResults.length === 0));

  const errorMessage =
    streamError ?? (hasError ? t("result.loadFailed") : null);

  return (
    <View style={styles.container}>
      {/* Header - 위로의 말씀 */}
      <ScreenHeader title={t("result.headerTitle")} />

      <ScrollView
        ref={scrollViewRef}
        contentContainerStyle={[
          styles.scrollContentContainer,
          { paddingBottom: insets.bottom + 32 },
        ]}
        showsVerticalScrollIndicator={false}
        onLayout={handleScrollLayout}
        onScroll={handleScroll}
        onContentSizeChange={handleContentSizeChange}
        scrollEventThrottle={16}
      >
        <View
          style={[styles.scrollContent, { paddingBottom: insets.bottom + 32 }]}
        >
          {/* 유저 입력 말풍선 - 오른쪽 정렬 */}
          <View style={styles.userMessageContainer}>
            <View style={styles.userMessageBubble}>
              <Text style={styles.userMessageText}>{mood}</Text>
            </View>
          </View>

          {/* 당신을 위한 말씀 섹션 */}
          <Text style={styles.sectionTitle}>{t("result.sectionTitle")}</Text>

          {showLoading ? (
            // 로딩 중: 유저 메시지 아래에 로딩 표시
            <LoadingCard
              primary={t("result.searching")}
              secondary={t("result.privacyNote")}
            />
          ) : hasError ? (
            <TouchableOpacity
              style={styles.errorContainer}
              onPress={() => refetch()}
              activeOpacity={0.7}
            >
              <Text style={styles.errorTitle}>{errorMessage}</Text>
              <Text style={styles.errorDescription}>
                {t("result.tapToRetry")}
              </Text>
            </TouchableOpacity>
          ) : (
            <>
              <View style={styles.resultsContainer}>
                {results.map((result, index) => {
                  if (!hasVisibleResultContent(result)) {
                    return null;
                  }
                  const isFieldActive = (key: StreamKey) =>
                    isStreaming &&
                    activeField?.index === index &&
                    activeField?.key === key;

                  return (
                    <VerseResultCard
                      key={`result-${index}`}
                      result={result}
                      mood={mood}
                      canSave={!isStreaming && !streamError}
                      isStreaming={isStreaming}
                      isTextActive={isFieldActive("text")}
                      isCommentActive={isFieldActive("comment")}
                      isTagActive={isFieldActive("tag")}
                      cursorVisible={cursorVisible}
                    />
                  );
                })}
              </View>

              {/* 다시 검색하기 버튼 */}
              {!isStreaming && visibleResults.length > 0 && !streamError && (
                <TouchableOpacity
                  style={styles.searchAgainButton}
                  onPress={() => refetch()}
                  activeOpacity={0.7}
                >
                  <Text style={styles.searchAgainButtonText}>
                    {t("result.searchAgain")}
                  </Text>
                </TouchableOpacity>
              )}
            </>
          )}
        </View>
      </ScrollView>
    </View>
  );
}

type LoadingCardProps = {
  /** 처음 보이는 문구 */
  primary: string;
  /** 잠시 뒤 크로스페이드로 바뀌는 문구(안내). 이후 로딩이 끝날 때까지 유지 */
  secondary: string;
};

/**
 * 로딩 카드. 문구가 한 번 바뀐다(primary → secondary).
 *
 * 순환시키지 않고 두 단계로 끝낸다 — 힘든 마음으로 여는 앱이라 문구가 계속
 * 도는 건 톤에 맞지 않는다. 문구가 바뀌어도 스크린리더에는 primary 하나만
 * 읽히도록 카드를 단일 접근성 요소로 묶는다.
 */
function LoadingCard({ primary, secondary }: LoadingCardProps) {
  const [message, setMessage] = useState(primary);
  const opacity = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    let cancelled = false;
    let swapTimer: ReturnType<typeof setTimeout> | null = null;

    void (async () => {
      let reduceMotion = false;
      try {
        reduceMotion = await AccessibilityInfo.isReduceMotionEnabled();
      } catch {
        // best-effort — 확인 실패 시엔 애니메이션을 적용한다
      }
      if (cancelled) return;

      swapTimer = setTimeout(() => {
        if (cancelled) return;
        // Reduce Motion 이면 페이드 없이 즉시 교체
        if (reduceMotion) {
          setMessage(secondary);
          return;
        }
        // 움직임 없이 제자리에서 서서히 사라졌다가 서서히 나타난다
        Animated.timing(opacity, {
          toValue: 0,
          duration: LOADING_FADE_OUT_MS,
          easing: Easing.inOut(Easing.quad),
          useNativeDriver: true,
        }).start(({ finished }) => {
          // 투명해진 순간에 교체해 글자가 겹쳐 보이지 않게 한다
          if (!finished || cancelled) return;
          setMessage(secondary);
          Animated.timing(opacity, {
            toValue: 1,
            duration: LOADING_FADE_IN_MS,
            easing: Easing.inOut(Easing.quad),
            useNativeDriver: true,
          }).start();
        });
      }, LOADING_SWAP_DELAY_MS);
    })();

    return () => {
      cancelled = true;
      if (swapTimer) clearTimeout(swapTimer);
    };
  }, [opacity, secondary]);

  return (
    <View style={styles.loadingCard} accessible accessibilityLabel={primary}>
      <ActivityIndicator
        size="small"
        color={colors.primary}
        style={styles.loadingIndicator}
      />
      <Animated.Text style={[styles.loadingCardText, { opacity }]}>
        {message}
      </Animated.Text>
    </View>
  );
}

type VerseResultCardProps = {
  result: RecommendItem;
  /** 저장 시 함께 기록할 사용자 입력(마음) */
  mood?: string;
  /** 스트리밍이 에러 없이 끝나 카드 내용이 온전할 때만 true (하트 노출 조건) */
  canSave?: boolean;
  isStreaming?: boolean;
  isTextActive?: boolean;
  isCommentActive?: boolean;
  isTagActive?: boolean;
  cursorVisible?: boolean;
};

function VerseResultCard({
  result,
  mood,
  canSave = false,
  isStreaming = false,
  isTextActive = false,
  isCommentActive = false,
  isTagActive = false,
  cursorVisible = false,
}: VerseResultCardProps) {
  const { data: savedVerses } = useBookmarks();
  const toggleBookmark = useToggleBookmark();

  const showVerseText = (result.text?.length ?? 0) > 0;
  const showReference = showVerseText && !!result.ref;
  const tagValue = (result.tag ?? "").trim();
  const showTag = showVerseText && tagValue.length > 0 && !isTagActive;
  const canShowComment = showVerseText && (tagValue.length > 0 || !isStreaming);
  const showComment = canShowComment && (result.comment?.length ?? 0) > 0;

  // 액션 줄(하트·복사·공유)은 스트리밍이 에러 없이 끝나 내용이 온전할 때만
  // 노출 (중단된 스트림의 잘린 ref/text 가 저장·공유되는 것을 막는다)
  const showActions = showReference && canSave;
  const isSaved =
    !!result.ref &&
    !!savedVerses?.some(
      (item) => item.source === "recommend" && item.reference === result.ref,
    );

  const handleToggleSave = () => {
    if (!result.ref) return;
    toggleBookmark.mutate({
      reference: result.ref,
      text: result.text ?? "",
      note: result.comment || undefined,
      tag: tagValue || undefined,
      mood: mood || undefined,
      source: "recommend",
    });
  };

  return (
    <View style={styles.verseCard}>
      {/* 성경 구절 */}
      {showVerseText && (
        <Text style={styles.verseText}>
          {'"'}
          {result.text ?? ""}
          {isTextActive && cursorVisible ? (
            <Text style={styles.typingCursor}>▍</Text>
          ) : null}
          {'"'}
        </Text>
      )}

      {/* 성경 몇장 몇절 */}
      {showReference && (
        <Text style={styles.verseReference}>{result.ref}</Text>
      )}

      {/* 태그 */}
      {showTag && (
        <View style={styles.tagRow}>
          <View style={styles.tag}>
            <Text style={styles.tagText}>{tagValue}</Text>
          </View>
        </View>
      )}

      {/* 코멘트 (말풍선 스타일) */}
      {showComment && (
        <View style={styles.commentBubble}>
          <Text style={styles.commentText}>
            {result.comment ?? ""}
            {isCommentActive && cursorVisible ? (
              <Text style={styles.typingCursor}>▍</Text>
            ) : null}
          </Text>
        </View>
      )}

      {/* 하단 액션 줄: 하트 · 복사 · 공유 */}
      {showActions && (
        <VerseActionRow
          reference={result.ref}
          text={result.text ?? ""}
          isSaved={isSaved}
          onToggleSave={handleToggleSave}
          analyticsSource="recommend"
          style={styles.actionRow}
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
  scrollContentContainer: {
    flexGrow: 1,
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingTop: 20,
  },
  // 유저 메시지 - 오른쪽 정렬
  userMessageContainer: {
    alignItems: "flex-end",
    marginBottom: 24,
  },
  userMessageBubble: {
    backgroundColor: colors.primary,
    borderRadius: 16,
    borderBottomRightRadius: 4,
    paddingHorizontal: 16,
    paddingVertical: 12,
    maxWidth: "80%",
  },
  userMessageText: {
    fontSize: scaleFont(16),
    lineHeight: scaleFont(24),
    color: "#FFFFFF",
    fontFamily: baseFontFamily,
  },
  // 섹션 타이틀
  sectionTitle: {
    fontSize: scaleFont(18),
    fontWeight: "600",
    color: colors.textPrimary,
    marginBottom: 16,
    fontFamily: baseFontFamily,
  },
  // 로딩 카드
  loadingCard: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "rgba(139, 115, 85, 0.1)",
    padding: 20,
    flexDirection: "row",
    alignItems: "center",
    shadowColor: "#8B7355",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 8,
    elevation: 2,
  },
  loadingIndicator: {
    marginRight: 12,
  },
  loadingCardText: {
    // 안내 문구는 첫 문구보다 길어 줄바꿈이 필요하다 — flex 없이 두면 카드를 넘친다
    flex: 1,
    fontSize: scaleFont(16),
    color: colors.textSecondary,
    fontFamily: baseFontFamily,
  },
  // 에러
  errorContainer: {
    backgroundColor: "#FFFFFF",
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "rgba(229, 231, 235, 0.9)",
    padding: 20,
    alignItems: "center",
  },
  errorTitle: {
    fontSize: scaleFont(16),
    color: colors.textSecondary,
    marginBottom: 4,
    fontFamily: baseFontFamily,
    textAlign: "center",
  },
  errorDescription: {
    fontSize: scaleFont(16),
    color: colors.textSecondary,
    fontFamily: baseFontFamily,
    textAlign: "center",
  },
  // 결과 컨테이너
  resultsContainer: {
    gap: 16,
  },
  // 말씀 카드
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
  typingCursor: {
    color: colors.primary,
    fontWeight: "600",
  },
  // 레퍼런스
  verseReference: {
    fontSize: scaleFont(14),
    fontWeight: "600",
    color: colors.primary,
    fontFamily: baseFontFamily,
    marginBottom: 6,
  },
  actionRow: {
    marginTop: 14,
  },
  tagRow: {
    alignSelf: "flex-end",
    marginBottom: 12,
  },
  // 태그
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
  // 코멘트 말풍선
  commentBubble: {
    backgroundColor: "rgba(245, 243, 240, 0.8)",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "rgba(139, 115, 85, 0.08)",
    padding: 14,
    marginTop: 4,
  },
  commentText: {
    fontSize: scaleFont(14),
    lineHeight: scaleFont(22),
    color: "#5C4A32",
    fontFamily: baseFontFamily,
  },
  // 다시 검색하기 버튼
  searchAgainButton: {
    backgroundColor: colors.primary,
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: "center",
    marginTop: 24,
  },
  searchAgainButtonText: {
    fontSize: scaleFont(16),
    fontWeight: "600",
    color: "#FFFFFF",
    fontFamily: baseFontFamily,
  },
});
