import { Platform } from "react-native";
import {
  documentDirectory,
  getInfoAsync,
  readAsStringAsync,
  writeAsStringAsync,
} from "expo-file-system/legacy";

/**
 * 고민 기록(지나온 마음) 로컬 저장소.
 *
 * 설정값 저장소(withgod-storage.json)와 **파일을 분리**한다. 그쪽은 알림 설정
 * 처럼 작고 자주 읽는 값을 위해 "전체를 메모리에 올려두고 매 쓰기마다 통째로
 * 직렬화"하는 구조라, 기록처럼 계속 늘어나는 데이터를 얹으면 알림 토글 한 번에
 * 수백 KB를 다시 쓰게 된다.
 *
 * 용량 관리:
 * - 최근 MAX_ENTRIES 건만 유지하고 오래된 것부터 버린다(항목당 대략 1~2KB이므로
 *   상한선에서도 파일이 200KB를 넘지 않는다).
 * - 기록 화면에 들어갈 때만 읽는다. 앱 시작 비용에 얹지 않는다.
 * - 서버에 계정 체계가 없어 기기 로컬에만 저장한다. [[bookmarkStorage]] 와 같은 원칙.
 */

const HISTORY_FILE = "withgod-history.json";
const MAX_ENTRIES = 100;
const isWeb = Platform.OS === "web";

export interface HistoryVerse {
  ref: string;
  text: string;
  /** AI 코멘트. 스트리밍이 중간에 끊겼으면 비어 있을 수 있다 */
  comment?: string;
  tag?: string;
}

export interface HistoryEntry {
  id: string;
  /** 사용자가 입력한 마음 (다시보기에서 그대로 보여준다) */
  mood: string;
  /**
   * 목록 표시용 요약 제목. 서버가 만들어 준다 —
   * 원문을 목록에 그대로 띄우면 적나라하고 어깨너머로도 읽히기 때문이다.
   * 구버전 서버·생성 실패 시 비어 있고, 그때는 화면이 mood 로 폴백한다.
   */
  title?: string;
  verses: HistoryVerse[];
  createdAt: string;
}

export type HistoryEntryInput = Omit<HistoryEntry, "id" | "createdAt">;

const isHistoryVerse = (value: unknown): value is HistoryVerse => {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return typeof record.ref === "string" && typeof record.text === "string";
};

const isHistoryEntry = (value: unknown): value is HistoryEntry => {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return (
    typeof record.id === "string" &&
    record.id.length > 0 &&
    typeof record.mood === "string" &&
    typeof record.createdAt === "string" &&
    Array.isArray(record.verses) &&
    record.verses.every(isHistoryVerse)
  );
};

// 동시 쓰기가 서로의 read-modify-write 를 덮어쓰지 않도록 직렬화
let opChain: Promise<unknown> = Promise.resolve();
const enqueue = <T,>(op: () => Promise<T>): Promise<T> => {
  const next = opChain.then(op, op);
  opChain = next.catch(() => {});
  return next;
};

const getFileUri = (): string | null =>
  documentDirectory ? `${documentDirectory}${HISTORY_FILE}` : null;

const readAll = async (): Promise<HistoryEntry[]> => {
  try {
    let raw: string | null = null;
    if (isWeb) {
      raw =
        typeof localStorage !== "undefined"
          ? localStorage.getItem(HISTORY_FILE)
          : null;
    } else {
      const uri = getFileUri();
      if (!uri) return [];
      const info = await getInfoAsync(uri);
      if (!info.exists) return [];
      raw = await readAsStringAsync(uri);
    }
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isHistoryEntry);
  } catch (error) {
    if (__DEV__) console.warn("[History] Failed to load", error);
    return [];
  }
};

const writeAll = async (entries: HistoryEntry[]): Promise<void> => {
  const serialized = JSON.stringify(entries);
  try {
    if (isWeb) {
      if (typeof localStorage !== "undefined") {
        localStorage.setItem(HISTORY_FILE, serialized);
      }
      return;
    }
    const uri = getFileUri();
    if (!uri) return;
    await writeAsStringAsync(uri, serialized);
  } catch (error) {
    if (__DEV__) console.warn("[History] Failed to persist", error);
  }
};

const makeId = (): string =>
  `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;

/** 최신순 기록 목록. */
export const loadHistory = (): Promise<HistoryEntry[]> => enqueue(readAll);

/** 기록을 맨 앞에 추가하고 상한을 넘은 오래된 항목은 버린다. */
export const appendHistory = (
  input: HistoryEntryInput,
): Promise<HistoryEntry[]> =>
  enqueue(async () => {
    const current = await readAll();
    const entry: HistoryEntry = {
      ...input,
      id: makeId(),
      createdAt: new Date().toISOString(),
    };
    const entries = [entry, ...current].slice(0, MAX_ENTRIES);
    await writeAll(entries);
    return entries;
  });

/** 나중에 만들어진 요약 제목을 해당 기록에 채워 넣는다. */
export const setHistoryTitle = (
  id: string,
  title: string,
): Promise<HistoryEntry[]> =>
  enqueue(async () => {
    const current = await readAll();
    let changed = false;
    const entries = current.map((item) => {
      if (item.id !== id || item.title) return item;
      changed = true;
      return { ...item, title };
    });
    if (changed) await writeAll(entries);
    return entries;
  });

/** 사용자가 직접 붙인 이름으로 바꾼다(자동 생성 제목을 덮어쓴다). */
export const renameHistoryEntry = (
  id: string,
  title: string,
): Promise<HistoryEntry[]> =>
  enqueue(async () => {
    const next = title.trim();
    if (!next) return readAll();
    const current = await readAll();
    const entries = current.map((item) =>
      item.id === id ? { ...item, title: next } : item,
    );
    await writeAll(entries);
    return entries;
  });

export const removeHistoryEntry = (id: string): Promise<HistoryEntry[]> =>
  enqueue(async () => {
    const current = await readAll();
    const entries = current.filter((item) => item.id !== id);
    if (entries.length !== current.length) await writeAll(entries);
    return entries;
  });

export const clearHistory = (): Promise<HistoryEntry[]> =>
  enqueue(async () => {
    await writeAll([]);
    return [];
  });
