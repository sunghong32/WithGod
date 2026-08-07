import * as Updates from 'expo-updates';

/**
 * OTA(무선 업데이트) 즉시 적용 게이트.
 *
 * 기본 동작은 "캐시로 먼저 뜨고, 새 번들은 백그라운드로 받아 **다음 실행**에
 * 반영"이라 사용자가 앱을 껐다 켜야 새 버전을 본다. 여기서는 스플래시가 이미
 * 기다리는 시간 안에 확인·내려받기를 마치고 곧바로 재시작해, 사용자가 아무것도
 * 하지 않아도 새 버전 화면으로 들어가게 한다.
 *
 * 원칙:
 * - **실패하면 그냥 넘어간다(fail-open).** 업데이트 서버 문제로 앱이 안 열리는
 *   일은 절대 없어야 한다. appUpdate.ts 와 같은 방침.
 * - 확인은 스플래시 대기시간(3초) 안에서 끝낸다. 초과하면 포기하고 진행한다.
 * - 실제로 받을 게 있을 때만 조금 더 기다리고, 그동안 안내 문구를 띄운다.
 */

/** 업데이트 확인에 허용하는 시간. 스플래시 대기(3초)를 넘기지 않는 선. */
const CHECK_TIMEOUT_MS = 2000;
/** 받을 게 있다고 확인된 뒤 내려받기에 허용하는 시간. */
const FETCH_TIMEOUT_MS = 8000;

export type OtaPhase = 'idle' | 'downloading';

const withTimeout = async <T,>(
  promise: Promise<T>,
  ms: number,
): Promise<T | null> => {
  let timer: ReturnType<typeof setTimeout> | null = null;
  const timeout = new Promise<null>((resolve) => {
    timer = setTimeout(() => resolve(null), ms);
  });
  try {
    return await Promise.race([promise, timeout]);
  } catch {
    return null;
  } finally {
    if (timer) clearTimeout(timer);
  }
};

/**
 * 새 번들이 있으면 받아서 즉시 재시작한다.
 *
 * @param onPhase 내려받기 시작 시 안내 문구를 띄우기 위한 콜백
 * @returns 재시작을 시작했으면 true (이 경우 호출자는 화면 전환을 하지 말 것 —
 *          곧 앱이 새 번들로 다시 뜬다). 받을 게 없거나 실패하면 false.
 */
export const applyPendingUpdateAsync = async (
  onPhase?: (phase: OtaPhase) => void,
): Promise<boolean> => {
  // 개발 빌드·Expo Go 에서는 비활성. __DEV__ 에서도 돌지 않는다.
  if (!Updates.isEnabled || __DEV__) return false;

  try {
    const check = await withTimeout(Updates.checkForUpdateAsync(), CHECK_TIMEOUT_MS);
    if (!check?.isAvailable) return false;

    onPhase?.('downloading');
    const fetched = await withTimeout(Updates.fetchUpdateAsync(), FETCH_TIMEOUT_MS);
    if (!fetched?.isNew) {
      onPhase?.('idle');
      return false;
    }

    // 여기서 앱이 새 번들로 재시작한다(이 함수는 사실상 반환하지 않는다).
    await Updates.reloadAsync();
    return true;
  } catch (error) {
    if (__DEV__) console.warn('[OTA] update gate failed', error);
    onPhase?.('idle');
    return false;
  }
};
