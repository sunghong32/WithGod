import { apiClient } from "@/shared/api/client";
import { parseError, logError, ApiError } from "@/shared/api/errors";
import { t } from "@/shared/lib/i18n";
import {
  DailyVerseResponseSchema,
  type DailyVerse,
  type RecommendIn,
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
  onError?: (message: string, context?: RecommendStreamErrorContext) => void;
}

export interface RecommendStreamController {
  close: () => void;
}

export interface RecommendStreamErrorContext {
  source: "event" | "parse" | "http" | "network";
  eventName?: string | null;
  payload?: string;
  url?: string;
  status?: number;
  readyState?: number;
  responseText?: string;
  parseErrorMessage?: string;
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
      handlers.onDone?.(data);
    } else if (eventType === "error") {
      const message =
        typeof data?.message === "string"
          ? data.message
          : t("errors.sseServer");
      handlers.onError?.(message, {
        source: "event",
        eventName,
        payload: trimmed,
      });
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
    handlers.onError?.(t("errors.sseParse"), {
      source: "parse",
      eventName,
      payload: trimmed,
      parseErrorMessage: error instanceof Error ? error.message : String(error),
    });
  }
};

export const verseApi = {
  // 오늘의 말씀 조회 (풀이 interpretation 포함)
  getDailyVerse: async (): Promise<DailyVerse> => {
    try {
      const { data } = await apiClient.get("/daily-verse");
      const { daily_verse } = DailyVerseResponseSchema.parse(data);
      return daily_verse;
    } catch (error) {
      const apiError = parseError(error);
      logError(apiError, "getDailyVerse");
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
    let doneReceived = false;

    // done 수신 여부를 추적해, done 없이 스트림이 끝나면 무한 로딩 대신 에러 처리한다.
    const trackedHandlers: RecommendStreamHandlers = {
      ...handlers,
      onDone: (results) => {
        doneReceived = true;
        handlers.onDone?.(results);
      },
    };

    const close = () => {
      closed = true;
      xhr.abort();
    };

    const handleChunk = (chunk: string) => {
      if (!chunk) return;
      buffer += chunk;
      buffer = drainSseBuffer(buffer, (payload, eventName) =>
        handleSsePayload(payload, eventName, trackedHandlers)
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
        handlers.onError?.(t("errors.sseHttp", { status: xhr.status }), {
          source: "http",
          status: xhr.status,
          readyState: xhr.readyState,
          responseText: xhr.responseText?.slice(-500),
          url,
        });
        return;
      }
      if (buffer.trim()) {
        handleChunk("\n\n");
        buffer = "";
      }
      if (!doneReceived) {
        handlers.onError?.(t("errors.sseIncomplete"), {
          source: "parse",
          status: xhr.status,
          readyState: xhr.readyState,
          responseText: xhr.responseText?.slice(-500),
          url,
        });
      }
    };

    xhr.ontimeout = () => {
      if (closed) return;
      handlers.onError?.(t("errors.sseTimeout"), {
        source: "network",
        status: xhr.status,
        readyState: xhr.readyState,
        url,
      });
    };

    xhr.onerror = () => {
      if (closed) return;
      handlers.onError?.(t("errors.network"), {
        source: "network",
        status: xhr.status,
        readyState: xhr.readyState,
        responseText: xhr.responseText?.slice(-500),
        url,
      });
    };

    try {
      xhr.open("POST", url);
      // LLM 스트리밍 전체 소요 상한 (서버가 ping 을 보내도 총 시간 기준으로 끊는다)
      xhr.timeout = 90000;
      xhr.setRequestHeader("Content-Type", "application/json");
      xhr.setRequestHeader("Accept", "text/event-stream");
      xhr.send(JSON.stringify(input));
    } catch (error) {
      handlers.onError?.(t("errors.sseStart"), {
        source: "network",
        readyState: xhr.readyState,
        status: xhr.status,
        url,
        parseErrorMessage: error instanceof Error ? error.message : String(error),
      });
    }

    return { close };
  },
};

// 에러 타입 re-export
export { ApiError };
