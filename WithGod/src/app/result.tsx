import {
  verseApi,
  type RecommendItem,
  type RecommendStreamController,
  type RecommendStreamVerse,
} from "@/features/verse";
import { useSafeAreaPadding } from "@/shared/hooks";
import { baseFontFamily, scaleFont } from "@/shared/styles";
import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { useLocalSearchParams, useRouter } from "expo-router";
import * as Sharing from "expo-sharing";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { captureRef } from "react-native-view-shot";

const BACK_ICON = require("../shared/assets/images/chevron-right.png");

type StreamKey = "ref" | "text" | "comment" | "tag";
type IndexedTokenKey = "comment" | "tag";

const STREAM_KEYS = new Set<StreamKey>(["ref", "text", "comment", "tag"]);
const TYPING_TICK_MS = 30;
const TYPING_CHARS_PER_TICK = 2;
const VERSE_TYPING_TICK_MS = 24;
const VERSE_TYPING_CHARS_PER_TICK = 1;

type VerseTypingKey = "text" | "ref";

type VerseTypingTask = {
  index: number;
  key: VerseTypingKey;
  value: string;
  cursor: number;
};

const decodePartialJsonString = (raw: string) => {
  let output = "";
  let escape = false;
  let unicodeMode = false;
  let unicodeBuffer = "";

  for (let i = 0; i < raw.length; i += 1) {
    const char = raw[i];
    if (unicodeMode) {
      if (/[0-9a-fA-F]/.test(char)) {
        unicodeBuffer += char;
        if (unicodeBuffer.length === 4) {
          output += String.fromCharCode(parseInt(unicodeBuffer, 16));
          unicodeMode = false;
          unicodeBuffer = "";
          escape = false;
        }
      } else {
        output += `\\u${unicodeBuffer}${char}`;
        unicodeMode = false;
        unicodeBuffer = "";
        escape = false;
      }
      continue;
    }

    if (escape) {
      switch (char) {
        case "n":
          output += "\n";
          break;
        case "r":
          output += "\r";
          break;
        case "t":
          output += "\t";
          break;
        case '"':
          output += '"';
          break;
        case "\\":
          output += "\\";
          break;
        case "/":
          output += "/";
          break;
        case "u":
          unicodeMode = true;
          unicodeBuffer = "";
          break;
        default:
          output += char;
      }
      if (!unicodeMode) {
        escape = false;
      }
      continue;
    }

    if (char === "\\") {
      escape = true;
      continue;
    }

    output += char;
  }

  if (unicodeMode) {
    output += `\\u${unicodeBuffer}`;
  } else if (escape) {
    output += "\\";
  }

  return output;
};

const createRecommendStreamParser = (callbacks: {
  onItemStart: (index: number) => void;
  onFieldUpdate: (index: number, key: StreamKey, value: string) => void;
  onActiveField: (index: number, key: StreamKey | null) => void;
}) => {
  const state = {
    inString: false,
    escape: false,
    stringBuffer: "",
    pendingKey: null as string | null,
    expectingValueKey: null as string | null,
    activeValueKey: null as StreamKey | null,
    awaitingResultsArray: false,
    arrayDepth: 0,
    resultsArrayDepth: 0,
    currentIndex: -1,
  };

  const reset = () => {
    state.inString = false;
    state.escape = false;
    state.stringBuffer = "";
    state.pendingKey = null;
    state.expectingValueKey = null;
    state.activeValueKey = null;
    state.awaitingResultsArray = false;
    state.arrayDepth = 0;
    state.resultsArrayDepth = 0;
    state.currentIndex = -1;
  };

  const feed = (chunk: string) => {
    if (!chunk) return;
    for (let i = 0; i < chunk.length; i += 1) {
      const char = chunk[i];
      if (state.inString) {
        if (state.escape) {
          state.escape = false;
          state.stringBuffer += char;
          if (state.activeValueKey && state.currentIndex >= 0) {
            callbacks.onFieldUpdate(
              state.currentIndex,
              state.activeValueKey,
              decodePartialJsonString(state.stringBuffer),
            );
          }
          continue;
        }

        if (char === "\\") {
          state.escape = true;
          state.stringBuffer += "\\";
          continue;
        }

        if (char === '"') {
          state.inString = false;
          const finished = state.stringBuffer;
          state.stringBuffer = "";
          if (state.activeValueKey && state.currentIndex >= 0) {
            callbacks.onFieldUpdate(
              state.currentIndex,
              state.activeValueKey,
              decodePartialJsonString(finished),
            );
            callbacks.onActiveField(state.currentIndex, null);
          } else {
            state.pendingKey = decodePartialJsonString(finished);
          }
          state.activeValueKey = null;
          continue;
        }

        state.stringBuffer += char;
        if (state.activeValueKey && state.currentIndex >= 0) {
          callbacks.onFieldUpdate(
            state.currentIndex,
            state.activeValueKey,
            decodePartialJsonString(state.stringBuffer),
          );
        }
        continue;
      }

      if (char === '"') {
        if (state.awaitingResultsArray) {
          state.awaitingResultsArray = false;
        }
        state.inString = true;
        state.stringBuffer = "";
        if (
          state.expectingValueKey &&
          STREAM_KEYS.has(state.expectingValueKey as StreamKey)
        ) {
          state.activeValueKey = state.expectingValueKey as StreamKey;
          if (state.currentIndex >= 0) {
            callbacks.onActiveField(state.currentIndex, state.activeValueKey);
          }
        } else {
          state.activeValueKey = null;
        }
        state.expectingValueKey = null;
        continue;
      }

      if (char === "[") {
        state.arrayDepth += 1;
        if (state.awaitingResultsArray) {
          state.resultsArrayDepth = state.arrayDepth;
          state.awaitingResultsArray = false;
        } else if (state.resultsArrayDepth === 0 && state.currentIndex < 0) {
          // top-level array 응답 대응
          state.resultsArrayDepth = state.arrayDepth;
        }
        continue;
      }

      if (char === "]") {
        if (state.arrayDepth > 0) {
          if (state.resultsArrayDepth === state.arrayDepth) {
            state.resultsArrayDepth = 0;
          }
          state.arrayDepth -= 1;
        }
        continue;
      }

      if (char === "{") {
        if (state.awaitingResultsArray) {
          state.awaitingResultsArray = false;
        }
        if (
          state.resultsArrayDepth > 0 &&
          state.arrayDepth >= state.resultsArrayDepth
        ) {
          state.currentIndex += 1;
          callbacks.onItemStart(state.currentIndex);
        }
        continue;
      }

      if (char === ":" && state.pendingKey) {
        state.expectingValueKey = state.pendingKey;
        state.awaitingResultsArray =
          state.pendingKey === "result" ||
          state.pendingKey === "results" ||
          state.pendingKey === "comments" ||
          state.pendingKey === "data";
        state.pendingKey = null;
        continue;
      }

      if (
        (char === "," || char === "}" || char === "]") &&
        state.expectingValueKey
      ) {
        state.expectingValueKey = null;
      }
    }
  };

  return { feed, reset };
};

const createIndexedTokenParser = (callbacks: {
  onFieldUpdate: (key: IndexedTokenKey, value: string) => void;
  onActiveField: (key: IndexedTokenKey | null) => void;
  onObjectDone?: () => void;
}) => {
  const state = {
    inString: false,
    escape: false,
    stringBuffer: "",
    pendingKey: null as string | null,
    expectingValueKey: null as string | null,
    activeValueKey: null as IndexedTokenKey | null,
    objectDepth: 0,
    sawObjectStart: false,
  };

  const reset = () => {
    state.inString = false;
    state.escape = false;
    state.stringBuffer = "";
    state.pendingKey = null;
    state.expectingValueKey = null;
    state.activeValueKey = null;
    state.objectDepth = 0;
    state.sawObjectStart = false;
  };

  const feed = (chunk: string) => {
    if (!chunk) return;

    for (let i = 0; i < chunk.length; i += 1) {
      const char = chunk[i];

      if (state.inString) {
        if (state.escape) {
          state.escape = false;
          state.stringBuffer += char;
          if (state.activeValueKey) {
            callbacks.onFieldUpdate(
              state.activeValueKey,
              decodePartialJsonString(state.stringBuffer),
            );
          }
          continue;
        }

        if (char === "\\") {
          state.escape = true;
          state.stringBuffer += "\\";
          continue;
        }

        if (char === '"') {
          state.inString = false;
          const finished = state.stringBuffer;
          state.stringBuffer = "";

          if (state.activeValueKey) {
            callbacks.onFieldUpdate(
              state.activeValueKey,
              decodePartialJsonString(finished),
            );
            callbacks.onActiveField(null);
            state.activeValueKey = null;
          } else {
            state.pendingKey = decodePartialJsonString(finished);
          }
          continue;
        }

        state.stringBuffer += char;
        if (state.activeValueKey) {
          callbacks.onFieldUpdate(
            state.activeValueKey,
            decodePartialJsonString(state.stringBuffer),
          );
        }
        continue;
      }

      if (char === '"') {
        state.inString = true;
        state.stringBuffer = "";
        if (
          state.expectingValueKey === "comment" ||
          state.expectingValueKey === "tag"
        ) {
          state.activeValueKey = state.expectingValueKey;
          callbacks.onActiveField(state.activeValueKey);
        } else {
          state.activeValueKey = null;
        }
        state.expectingValueKey = null;
        continue;
      }

      if (char === "{") {
        state.sawObjectStart = true;
        state.objectDepth += 1;
        continue;
      }

      if (char === "}" && state.objectDepth > 0) {
        state.objectDepth -= 1;
        if (state.sawObjectStart && state.objectDepth === 0) {
          callbacks.onObjectDone?.();
        }
        continue;
      }

      if (char === ":" && state.pendingKey) {
        state.expectingValueKey = state.pendingKey;
        state.pendingKey = null;
        continue;
      }

      if (
        (char === "," || char === "}" || char === "]") &&
        state.expectingValueKey
      ) {
        state.expectingValueKey = null;
      }
    }
  };

  return { feed, reset };
};

export default function ResultScreen() {
  const router = useRouter();
  const { mood } = useLocalSearchParams<{ mood: string }>();
  const { insets, headerPaddingTop } = useSafeAreaPadding();
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
  const draftRef = useRef<RecommendItem[]>([]);
  const isMountedRef = useRef(true);
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

  const extractResults = useCallback(
    (payload: unknown): RecommendItem[] | null => {
      const unwrap = (
        value: unknown,
        depth: number,
      ): RecommendItem[] | null => {
        if (Array.isArray(value)) return value as RecommendItem[];
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

      if (!extracted) {
        setStreamError("말씀을 불러오지 못했어요");
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
    [extractResults, finalizeResults],
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
        onVerse: (event) => {
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
        onDone: handleStreamDone,
        onError: (message) => {
          if (!isMountedRef.current) return;
          setStreamError(message || "말씀을 불러오지 못했어요");
          setIsStreaming(false);
          if (__DEV__) {
            const now = Date.now();
            const total = timingRef.current.startAt
              ? now - timingRef.current.startAt
              : 0;
            console.log(`[SSE Timing] error after ${total}ms`);
          }
          stopTyping();
          stopStream();
        },
      },
    );
  }, [
    enqueueTokens,
    ensureIndexedTokenPump,
    handleStreamDone,
    handleVerse,
    handleVerses,
    mood,
    stopStream,
    stopTyping,
    stopVerseTyping,
    stopIndexedTokenPump,
  ]);

  const refetch = useCallback(() => {
    startStream();
  }, [startStream]);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      stopStream();
      stopTyping();
      stopVerseTyping();
      stopIndexedTokenPump();
      if (flushTimerRef.current) {
        clearTimeout(flushTimerRef.current);
        flushTimerRef.current = null;
      }
    };
  }, [stopStream, stopTyping, stopVerseTyping, stopIndexedTokenPump]);

  useEffect(() => {
    if (!mood) return;
    startStream();
    return () => {
      stopStream();
      stopVerseTyping();
      stopIndexedTokenPump();
    };
  }, [mood, startStream, stopStream, stopVerseTyping, stopIndexedTokenPump]);

  useEffect(() => {
    if (!isStreaming) {
      setCursorVisible(false);
      return;
    }
    setCursorVisible(true);
    const timer = setInterval(() => setCursorVisible((prev) => !prev), 500);
    return () => clearInterval(timer);
  }, [isStreaming]);

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

  const showLoading = isStreaming && visibleResults.length === 0;
  const hasError =
    (!isStreaming && visibleResults.length === 0) ||
    (!!streamError && visibleResults.length === 0);

  const errorMessage =
    streamError ?? (hasError ? "말씀을 불러오지 못했어요" : null);

  const contentRef = useRef<View>(null);
  const captureViewRef = useRef<View>(null);
  const [contentLayout, setContentLayout] = useState<{
    width: number;
    height: number;
  } | null>(null);
  const [isCapturing, setIsCapturing] = useState(false);

  const handleCaptureAndShare = useCallback(async () => {
    if (!contentLayout || contentLayout.height <= 0 || results.length === 0)
      return;
    setIsCapturing(true);
  }, [contentLayout, results.length]);

  useEffect(() => {
    if (!isCapturing || !contentLayout || !captureViewRef.current) return;
    const canShare = Sharing.isAvailableAsync().then(Boolean);
    const timer = setTimeout(async () => {
      try {
        const uri = await captureRef(captureViewRef, {
          format: "png",
          quality: 1,
          width: contentLayout.width,
          height: contentLayout.height,
          result: "tmpfile",
        });
        if (await canShare) {
          await Sharing.shareAsync(uri, {
            mimeType: "image/png",
            dialogTitle: "위로의 말씀 이미지 공유",
          });
        } else if (Platform.OS === "web") {
          const link = document.createElement("a");
          link.href = uri;
          link.download = "withgod-comfort.png";
          link.click();
        }
      } catch (e) {
        if (__DEV__) console.warn("Capture failed:", e);
      } finally {
        setIsCapturing(false);
      }
    }, 500);
    return () => clearTimeout(timer);
  }, [isCapturing, contentLayout]);

  const canCapture =
    !showLoading &&
    !isStreaming &&
    !hasError &&
    visibleResults.length > 0 &&
    contentLayout &&
    contentLayout.height > 0;

  return (
    <View style={styles.container}>
      {/* Header - 위로의 말씀 */}
      <View style={[styles.header, { paddingTop: headerPaddingTop }]}>
        <TouchableOpacity
          style={styles.backButton}
          onPress={() => router.back()}
          activeOpacity={0.7}
        >
          <Image
            source={BACK_ICON}
            style={styles.backIcon}
            contentFit="contain"
          />
        </TouchableOpacity>
        <Text style={styles.headerTitle}>위로의 말씀</Text>
        {canCapture ? (
          <TouchableOpacity
            style={styles.captureButton}
            onPress={handleCaptureAndShare}
            disabled={isCapturing}
            accessibilityRole="button"
            accessibilityLabel="전체 화면을 이미지로 저장·공유"
          >
            <Ionicons
              name={isCapturing ? "hourglass-outline" : "share-outline"}
              size={22}
              color={isCapturing ? "#9CA3AF" : "#1E2939"}
            />
          </TouchableOpacity>
        ) : (
          <View style={styles.headerSpacer} />
        )}
      </View>

      <ScrollView
        contentContainerStyle={[
          styles.scrollContentContainer,
          { paddingBottom: insets.bottom + 32 },
        ]}
        showsVerticalScrollIndicator={false}
      >
        <View
          ref={contentRef}
          onLayout={(e) =>
            setContentLayout({
              width: e.nativeEvent.layout.width,
              height: e.nativeEvent.layout.height,
            })
          }
          collapsable={false}
          style={[styles.scrollContent, { paddingBottom: insets.bottom + 32 }]}
        >
          {/* 유저 입력 말풍선 - 오른쪽 정렬 */}
          <View style={styles.userMessageContainer}>
            <View style={styles.userMessageBubble}>
              <Text style={styles.userMessageText}>{mood}</Text>
            </View>
          </View>

          {/* 당신을 위한 말씀 섹션 */}
          <Text style={styles.sectionTitle}>당신을 위한 말씀</Text>

          {showLoading ? (
            // 로딩 중: 유저 메시지 아래에 로딩 표시
            <View style={styles.loadingCard}>
              <ActivityIndicator
                size="small"
                color="#4A90E2"
                style={styles.loadingIndicator}
              />
              <Text style={styles.loadingCardText}>말씀을 찾고 있어요...</Text>
            </View>
          ) : hasError ? (
            <TouchableOpacity
              style={styles.errorContainer}
              onPress={() => refetch()}
              activeOpacity={0.7}
            >
              <Text style={styles.errorTitle}>{errorMessage}</Text>
              <Text style={styles.errorDescription}>
                탭하여 다시 시도해주세요
              </Text>
            </TouchableOpacity>
          ) : (
            <>
              <View style={styles.resultsContainer}>
                {results.map((result, index) => {
                  if (!hasVisibleResultContent(result)) {
                    return null;
                  }
                  const isTextActive =
                    isStreaming &&
                    activeField?.index === index &&
                    activeField?.key === "text";
                  const isCommentActive =
                    isStreaming &&
                    activeField?.index === index &&
                    activeField?.key === "comment";
                  const isTagActive =
                    isStreaming &&
                    activeField?.index === index &&
                    activeField?.key === "tag";
                  const showVerseText = (result.text?.length ?? 0) > 0;
                  const showReference = showVerseText && !!result.ref;
                  const tagValue = (result.tag ?? "").trim();
                  const showTag =
                    showVerseText && tagValue.length > 0 && !isTagActive;
                  const canShowComment =
                    showVerseText && (tagValue.length > 0 || !isStreaming);
                  const showComment =
                    canShowComment && (result.comment?.length ?? 0) > 0;

                  return (
                    <View key={`result-${index}`} style={styles.verseCard}>
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
                    </View>
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
                    다시 검색하기
                  </Text>
                </TouchableOpacity>
              )}
            </>
          )}
        </View>
      </ScrollView>

      {/* 전체 스크롤 콘텐츠 캡처용 오프스크린 뷰 */}
      {isCapturing && contentLayout && contentLayout.height > 0 && (
        <View
          style={[
            styles.captureOffscreen,
            {
              left: -contentLayout.width - 100,
              width: contentLayout.width,
              height: contentLayout.height,
            },
          ]}
          pointerEvents="none"
        >
          <View
            ref={captureViewRef}
            style={[
              styles.scrollContent,
              styles.captureBackground,
              styles.captureContentPadding,
              {
                width: contentLayout.width,
                height: contentLayout.height,
              },
            ]}
            collapsable={false}
          >
            <View style={styles.userMessageContainer}>
              <View style={styles.userMessageBubble}>
                <Text style={styles.userMessageText}>{mood}</Text>
              </View>
            </View>
            <Text style={styles.sectionTitle}>당신을 위한 말씀</Text>
            <View style={styles.resultsContainer}>
              {visibleResults.map((result, index) => (
                <View key={`capture-${index}`} style={styles.verseCard}>
                  <Text style={styles.verseText}>
                    {'"'}
                    {result.text ?? ""}
                    {'"'}
                  </Text>
                  {result.ref ? (
                    <Text style={styles.verseReference}>{result.ref}</Text>
                  ) : null}
                  {result.tag ? (
                    <View style={styles.tagRow}>
                      <View style={styles.tag}>
                        <Text style={styles.tagText}>{result.tag}</Text>
                      </View>
                    </View>
                  ) : null}
                  {result.comment ? (
                    <View style={styles.commentBubble}>
                      <Text style={styles.commentText}>{result.comment}</Text>
                    </View>
                  ) : null}
                </View>
              ))}
            </View>
          </View>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#F9FAFB",
  },
  header: {
    backgroundColor: "#FFFFFF",
    borderBottomColor: "#E5E7EB",
    borderBottomWidth: 1,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingBottom: 16,
  },
  backButton: {
    width: 32,
    height: 32,
    justifyContent: "center",
    alignItems: "center",
    marginRight: 8,
  },
  backIcon: {
    width: 8,
    height: 14,
    transform: [{ rotate: "180deg" }],
    tintColor: "#101828",
  },
  headerTitle: {
    flex: 1,
    fontSize: scaleFont(18),
    lineHeight: scaleFont(24),
    fontWeight: "600",
    color: "#101828",
    fontFamily: baseFontFamily,
  },
  headerSpacer: {
    width: 32,
  },
  captureButton: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
  },
  scrollContentContainer: {
    flexGrow: 1,
  },
  scrollContent: {
    paddingHorizontal: 16,
    paddingTop: 20,
  },
  captureOffscreen: {
    position: "absolute",
    top: 0,
    overflow: "hidden",
  },
  captureBackground: {
    backgroundColor: "#F9FAFB",
  },
  /** 캡처본에서만 상단 여백을 넉넉히, 하단 여백은 줄임 */
  captureContentPadding: {
    paddingTop: 72,
    paddingBottom: 24,
  },
  // 유저 메시지 - 오른쪽 정렬
  userMessageContainer: {
    alignItems: "flex-end",
    marginBottom: 24,
  },
  userMessageBubble: {
    backgroundColor: "#4A90E2",
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
    color: "#101828",
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
    fontSize: scaleFont(16),
    color: "#6A7282",
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
    color: "#6A7282",
    marginBottom: 4,
    fontFamily: baseFontFamily,
    textAlign: "center",
  },
  errorDescription: {
    fontSize: scaleFont(16),
    color: "#6A7282",
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
    color: "#4A90E2",
    fontWeight: "600",
  },
  // 레퍼런스
  verseReference: {
    fontSize: scaleFont(14),
    fontWeight: "600",
    color: "#4A90E2",
    fontFamily: baseFontFamily,
    marginBottom: 6,
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
    color: "#6A7282",
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
    backgroundColor: "#4A90E2",
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
