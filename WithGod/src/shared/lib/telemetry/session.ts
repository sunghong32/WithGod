import { getStorageItem, setStorageItem } from '@/shared/lib/storage';

import { createSessionId } from './ids';

/**
 * 세션 관리.
 *
 * GA4 와 같은 규칙으로 "마지막 활동 후 30분이 지나면 새 세션"으로 본다.
 * 마지막 활동 시각은 백그라운드로 갈 때만 저장한다 — 이벤트마다 파일을 쓰면
 * 낭비이고, 앱이 죽는 시점은 대부분 백그라운드 이후이기 때문이다.
 */

const SESSION_KEY = 'withgod.telemetry.session';
const SESSION_TIMEOUT_MS = 30 * 60 * 1000;

interface SessionState {
  id: string;
  lastActiveAt: number;
}

let current: SessionState | null = null;

/** 앱 시작 시 1회. 직전 세션이 30분 안이면 이어서 쓴다. */
export const restoreSession = async (now: number = Date.now()): Promise<void> => {
  try {
    const raw = await getStorageItem(SESSION_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw) as Partial<SessionState>;
    if (
      typeof parsed.id === 'string' &&
      typeof parsed.lastActiveAt === 'number' &&
      now - parsed.lastActiveAt <= SESSION_TIMEOUT_MS
    ) {
      current = { id: parsed.id, lastActiveAt: parsed.lastActiveAt };
    }
  } catch {
    // 세션 복원 실패는 새 세션으로 시작하면 그만이다.
  }
};

/**
 * 지금 이벤트가 속할 세션을 돌려준다.
 * 새 세션이 시작됐으면 isNew=true — 호출부가 session_start 를 남긴다.
 */
export const touchSession = (now: number = Date.now()): { id: string; isNew: boolean } => {
  if (current && now - current.lastActiveAt <= SESSION_TIMEOUT_MS) {
    current.lastActiveAt = now;
    return { id: current.id, isNew: false };
  }
  current = { id: createSessionId(), lastActiveAt: now };
  return { id: current.id, isNew: true };
};

export const persistSession = async (): Promise<void> => {
  if (!current) return;
  try {
    await setStorageItem(SESSION_KEY, JSON.stringify(current));
  } catch {
    // best-effort
  }
};

/** 테스트용 초기화. */
export const resetSessionForTest = (): void => {
  current = null;
};
