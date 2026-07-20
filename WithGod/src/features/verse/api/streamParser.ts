/**
 * /recommend SSE 스트림의 부분 JSON을 문자 단위로 파싱하는 순수 파서.
 * 화면(result.tsx)과 분리되어 React에 의존하지 않는다.
 */

export type StreamKey = "ref" | "text" | "comment" | "tag";
export type IndexedTokenKey = "comment" | "tag";

const STREAM_KEYS = new Set<StreamKey>(["ref", "text", "comment", "tag"]);

export const decodePartialJsonString = (raw: string) => {
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

export const createRecommendStreamParser = (callbacks: {
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

export const createIndexedTokenParser = (callbacks: {
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
