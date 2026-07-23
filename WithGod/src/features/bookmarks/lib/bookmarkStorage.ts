import { getStorageItem, setStorageItem } from "@/shared/lib/storage";

/**
 * 북마크(저장한 말씀) 로컬 저장소.
 *
 * 서버에 계정 체계가 없어 기기 로컬(withgod-storage.json)에만 저장한다.
 * 키는 (reference, source) 복합키다 — 같은 구절이라도 오늘의 말씀(풀이)과
 * 위로의 말씀(그 세션에서만 생성되는 AI 코멘트)은 내용이 달라 별개 항목으로
 * 취급해야, 한쪽 하트 토글이 다른 쪽 저장본을 지우는 사고를 막을 수 있다.
 */

const BOOKMARKS_KEY = "withgod.bookmarks";

export type BookmarkSource = "daily" | "recommend";

export interface Bookmark {
  /** "이사야 41:10" 형태. 북마크 식별 키 */
  reference: string;
  text: string;
  /** daily: 풀이(interpretation), recommend: AI 코멘트 */
  note?: string;
  tag?: string;
  /** recommend일 때 사용자가 입력했던 마음 */
  mood?: string;
  source: BookmarkSource;
  createdAt: string;
}

export type BookmarkInput = Omit<Bookmark, "createdAt">;

const isBookmark = (value: unknown): value is Bookmark => {
  if (!value || typeof value !== "object") return false;
  const record = value as Record<string, unknown>;
  return (
    typeof record.reference === "string" &&
    record.reference.length > 0 &&
    typeof record.text === "string" &&
    (record.source === "daily" || record.source === "recommend") &&
    typeof record.createdAt === "string"
  );
};

// 동시 토글이 서로의 read-modify-write 를 덮어쓰지 않도록 저장 작업을 직렬화
let opChain: Promise<unknown> = Promise.resolve();
const enqueue = <T,>(op: () => Promise<T>): Promise<T> => {
  const next = opChain.then(op, op);
  opChain = next.catch(() => {});
  return next;
};

const readBookmarks = async (): Promise<Bookmark[]> => {
  try {
    const raw = await getStorageItem(BOOKMARKS_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isBookmark);
  } catch (error) {
    if (__DEV__) console.warn("[Bookmarks] Failed to load", error);
    return [];
  }
};

const writeBookmarks = async (bookmarks: Bookmark[]): Promise<void> => {
  await setStorageItem(BOOKMARKS_KEY, JSON.stringify(bookmarks));
};

export const loadBookmarks = (): Promise<Bookmark[]> =>
  enqueue(readBookmarks);

const matches = (item: Bookmark, reference: string, source: BookmarkSource) =>
  item.reference === reference && item.source === source;

/** (reference, source)로 저장돼 있으면 해제, 없으면 최신순 맨 앞에 추가한다. */
export const toggleBookmark = (
  input: BookmarkInput,
): Promise<{ bookmarks: Bookmark[]; added: boolean }> =>
  enqueue(async () => {
    const current = await readBookmarks();
    const exists = current.some((item) =>
      matches(item, input.reference, input.source),
    );
    const bookmarks = exists
      ? current.filter((item) => !matches(item, input.reference, input.source))
      : [{ ...input, createdAt: new Date().toISOString() }, ...current];
    await writeBookmarks(bookmarks);
    return { bookmarks, added: !exists };
  });

export const removeBookmark = (
  reference: string,
  source: BookmarkSource,
): Promise<Bookmark[]> =>
  enqueue(async () => {
    const current = await readBookmarks();
    const bookmarks = current.filter(
      (item) => !matches(item, reference, source),
    );
    if (bookmarks.length !== current.length) {
      await writeBookmarks(bookmarks);
    }
    return bookmarks;
  });
