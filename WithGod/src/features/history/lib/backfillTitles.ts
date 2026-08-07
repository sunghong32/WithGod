import { apiClient } from "@/shared/api/client";
import { getAppLanguage } from "@/shared/lib/i18n";
import { setHistoryTitle, type HistoryEntry } from "./historyStorage";

/**
 * 제목이 비어 있는 기록에 요약 제목을 나중에 채워 넣는다.
 *
 * 제목은 보통 상담이 끝날 때 서버가 함께 내려준다. 다만 그때 생성이 실패했거나
 * (OpenAI 오류·타임아웃) 서버가 이 기능을 갖기 전에 만들어진 기록은 제목이 없고,
 * 목록에 고민 원문이 그대로 노출된다. 그걸 뒤늦게라도 메우는 경로다.
 *
 * - 실패해도 조용히 넘어간다. 목록은 원문으로 계속 폴백하므로 사용자는 못 느낀다.
 * - 한 번에 조금씩만 처리해 사이드바를 열 때마다 서버를 몰아치지 않는다.
 */

/** 한 번 열 때 채울 최대 개수 */
const MAX_PER_RUN = 3;
const TIMEOUT_MS = 8000;

let running = false;
/** 이번 실행에서 실패한 항목은 다시 시도하지 않는다(무한 재시도 방지) */
const failed = new Set<string>();

const fetchTitle = async (mood: string): Promise<string> => {
  const { data } = await apiClient.post<{ title?: string }>(
    "/history/title",
    { mood, lang: getAppLanguage() },
    { timeout: TIMEOUT_MS },
  );
  return typeof data?.title === "string" ? data.title.trim() : "";
};

/**
 * @returns 하나라도 채웠으면 true (호출부에서 목록을 새로고침하면 된다)
 */
export const backfillMissingTitles = async (
  entries: HistoryEntry[],
): Promise<boolean> => {
  if (running) return false;
  const targets = entries
    .filter((entry) => !entry.title?.trim() && !!entry.mood.trim())
    .filter((entry) => !failed.has(entry.id))
    .slice(0, MAX_PER_RUN);
  if (targets.length === 0) return false;

  running = true;
  let filled = false;
  try {
    for (const entry of targets) {
      try {
        const title = await fetchTitle(entry.mood);
        if (!title) {
          failed.add(entry.id);
          continue;
        }
        await setHistoryTitle(entry.id, title);
        filled = true;
      } catch {
        // 네트워크·서버 오류 — 이번 실행에서는 포기하고 원문 폴백을 유지한다
        failed.add(entry.id);
      }
    }
  } finally {
    running = false;
  }
  return filled;
};
