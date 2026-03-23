import { apiClient } from "@/shared/api/client";
import { parseError, logError, ApiError } from "@/shared/api/errors";
import {
  RandomOutSchema,
  RecommendOutSchema,
  type RandomOut,
  type RecommendIn,
  type RecommendOut,
  type RecommendItem,
} from "./schema";

export interface RecommendStreamMeta {
  mood?: string;
  model?: string;
  style?: string;
  candidates_count?: number;
}

export interface RecommendStreamVerse {
  ref?: string;
  text?: string;
}

export interface RecommendStreamVerseEvent {
  index?: number;
  verse?: RecommendStreamVerse;
}

export interface RecommendStreamHandlers {
  onMeta?: (meta: RecommendStreamMeta) => void;
  onVerses?: (verses: RecommendStreamVerse[]) => void;
  onVerse?: (event: RecommendStreamVerseEvent) => void;
  onToken?: (content: string, index?: number) => void;
  onDone?: (results: RecommendItem[] | unknown) => void;
  onError?: (message: string) => void;
}

export interface RecommendStreamController {
  close: () => void;
}

const drainSseBuffer = (
  buffer: string,
  onData: (payload: string, eventName: string | null) => void
): string => {
  let cursor = 0;
  while (true) {
    const slice = buffer.slice(cursor);
    const match = slice.match(/\r?\n\r?\n/);
    if (!match || match.index === undefined) break;
    const delimiterIndex = cursor + match.index;
    const rawEvent = buffer.slice(cursor, delimiterIndex).trim();
    cursor = delimiterIndex + match[0].length;
    if (!rawEvent) continue;

    let eventName: string | null = null;
    const dataLines = rawEvent
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .reduce<string[]>((acc, line) => {
        if (line.startsWith("event:")) {
          eventName = line.replace(/^event:\s?/, "").trim();
          return acc;
        }
        if (line.startsWith("data:")) {
          acc.push(line.replace(/^data:\s?/, ""));
        }
        return acc;
      }, []);

    if (dataLines.length === 0) continue;
    const payload = dataLines.join("\n").trim();
    if (payload) onData(payload, eventName);
  }

  return buffer.slice(cursor);
};

const handleSsePayload = (
  payload: string,
  eventName: string | null,
  handlers: RecommendStreamHandlers
) => {
  const trimmed = payload.trim();
  if (!trimmed) return;
  if (trimmed === "[DONE]") return;

  try {
    const data = JSON.parse(trimmed);
    const eventType = data?.event ?? eventName;
    if (eventType === "meta") {
      handlers.onMeta?.(data);
    } else if (eventType === "ping") {
      return;
    } else if (eventType === "verses") {
      const verses = Array.isArray(data?.verses) ? data.verses : [];
      handlers.onVerses?.(verses);
    } else if (eventType === "verse") {
      const index = typeof data?.index === "number" ? data.index : undefined;
      const verse =
        data?.verse && typeof data.verse === "object" ? data.verse : undefined;
      handlers.onVerse?.({ index, verse });
    } else if (eventType === "token") {
      const content = typeof data?.content === "string" ? data.content : "";
      const index = typeof data?.index === "number" ? data.index : undefined;
      handlers.onToken?.(content, index);
    } else if (eventType === "done") {
      handlers.onDone?.(data?.results ?? []);
    } else if (eventType === "error") {
      const message =
        typeof data?.message === "string"
          ? data.message
          : "서버 오류가 발생했어요";
      handlers.onError?.(message);
    }
  } catch (error) {
    if (__DEV__) {
      console.warn("[SSE] payload parse failed", error);
    }
    if (eventName === "token") {
      handlers.onToken?.(trimmed);
      return;
    }
    if (eventName === "done") {
      try {
        handlers.onDone?.(JSON.parse(trimmed));
        return;
      } catch {
        // fall through
      }
    }
    handlers.onError?.("응답을 해석하지 못했어요");
  }
};

export const verseApi = {
  // 랜덤 성경 구절 조회
  getRandomVerse: async (): Promise<RandomOut> => {
    try {
      const { data } = await apiClient.get("/random");
      return RandomOutSchema.parse(data);
    } catch (error) {
      const apiError = parseError(error);
      logError(apiError, "getRandomVerse");
      throw apiError;
    }
  },

  // 기분에 맞는 성경 구절 추천
  getRecommendation: async (input: RecommendIn): Promise<RecommendOut> => {
    try {
      const { data } = await apiClient.post("/recommend", input);
      return RecommendOutSchema.parse(data);
    } catch (error) {
      const apiError = parseError(error);
      logError(apiError, "getRecommendation");
      throw apiError;
    }
  },

  // 기분에 맞는 성경 구절 추천 (스트리밍)
  streamRecommendation: (
    input: RecommendIn,
    handlers: RecommendStreamHandlers
  ): RecommendStreamController => {
    const baseUrl = apiClient.defaults.baseURL ?? "";
    const url = `${baseUrl}/recommend/stream`;
    const xhr = new XMLHttpRequest();
    let buffer = "";
    let lastIndex = 0;
    let closed = false;

    const close = () => {
      closed = true;
      xhr.abort();
    };

    const handleChunk = (chunk: string) => {
      if (!chunk) return;
      buffer += chunk;
      buffer = drainSseBuffer(buffer, (payload, eventName) =>
        handleSsePayload(payload, eventName, handlers)
      );
    };

    xhr.onprogress = () => {
      const responseText = xhr.responseText ?? "";
      if (responseText.length <= lastIndex) return;
      const chunk = responseText.slice(lastIndex);
      lastIndex = responseText.length;
      handleChunk(chunk);
    };

    xhr.onreadystatechange = () => {
      if (xhr.readyState === 3 || xhr.readyState === 4) {
        const responseText = xhr.responseText ?? "";
        if (responseText.length <= lastIndex) return;
        const chunk = responseText.slice(lastIndex);
        lastIndex = responseText.length;
        handleChunk(chunk);
      }
    };

    xhr.onload = () => {
      if (closed) return;
      if (xhr.status >= 400) {
        handlers.onError?.(`서버 오류가 발생했어요 (${xhr.status})`);
        return;
      }
      if (buffer.trim()) {
        handleChunk("\n\n");
        buffer = "";
      }
    };

    xhr.onerror = () => {
      if (closed) return;
      handlers.onError?.("인터넷 연결을 확인해주세요");
    };

    xhr.open("POST", url);
    xhr.setRequestHeader("Content-Type", "application/json");
    xhr.setRequestHeader("Accept", "text/event-stream");
    xhr.send(JSON.stringify(input));

    return { close };
  },
};

// 에러 타입 re-export
export { ApiError };
