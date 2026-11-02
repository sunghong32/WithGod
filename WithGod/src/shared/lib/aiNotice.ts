import { getStorageItem, setStorageItem } from './storage';

/**
 * AI 장애 사과 안내(1회성 팝업)의 노출 여부 플래그.
 *
 * 2026-09-18 ~ 11-02 동안 생성 AI 가 멈춰 위로의 말씀이 첫 카드에서 끊기고
 * 오늘의 말씀 풀이가 한 줄로 나갔다. 그 기간을 겪은 기존 사용자에게만 한 번
 * 사과하고, 확인을 누르면 다시 띄우지 않는다. 장애 뒤에 설치한 사용자는 겪은
 * 적이 없으므로 홈 첫 진입 때 본 것으로 기록해 띄우지 않는다(홈 화면에서 판단).
 */

const AI_NOTICE_SEEN_KEY = 'withgod.notice.aiOutage2026.seen';

// 이 시각이 지나면 아무에게도 띄우지 않는다 — 몇 달 뒤 처음 연 사람에게는 맥락 없는 사과다.
const AI_NOTICE_UNTIL = Date.UTC(2027, 0, 1);

export const shouldShowAiNotice = async (): Promise<boolean> => {
  if (Date.now() >= AI_NOTICE_UNTIL) return false;
  return (await getStorageItem(AI_NOTICE_SEEN_KEY)) !== 'true';
};

export const markAiNoticeSeen = async (): Promise<void> => {
  await setStorageItem(AI_NOTICE_SEEN_KEY, 'true');
};
