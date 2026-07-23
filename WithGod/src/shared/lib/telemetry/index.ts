import Constants from 'expo-constants';
import { AppState, Platform, type AppStateStatus } from 'react-native';

import type { TelemetryBatchPayload } from '@/shared/api/telemetryApi';
import { getOrCreateDeviceId } from '@/shared/lib/notificationSettings';
import { getStorageItem, setStorageItem } from '@/shared/lib/storage';

import { createEventId } from './ids';
import { clearQueue, flush, loadQueue, enqueue, shouldFlush } from './queue';
import { persistSession, restoreSession, touchSession } from './session';

/**
 * 자체 지표 수집 SDK.
 *
 * Firebase Analytics 와 병행한다(analytics.ts 가 양쪽으로 보낸다). Firebase 는
 * 집계가 하루 늦고 원시 데이터를 꺼내기 번거로워 어드민 대시보드에 쓸 수
 * 없기 때문이지, Firebase 가 틀려서가 아니다. 한동안 두 수치를 대조한다.
 *
 * 사용자가 입력한 마음 같은 개인 내용은 여기로도 절대 보내지 않는다.
 * 서버에서 파라미터 키를 한 번 더 화이트리스트로 거른다.
 */

const ENABLED_KEY = 'withgod.telemetry.enabled';
const FLUSH_INTERVAL_MS = 30_000;

type TelemetryParams = Record<string, string | number | boolean>;

const isNative = Platform.OS === 'ios' || Platform.OS === 'android';

let anonId = '';
let enabled = true;
let started = false;
let flushTimer: ReturnType<typeof setInterval> | null = null;
let appStateSubscription: { remove: () => void } | null = null;

const getTimezone = (): string => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Seoul';
  } catch {
    return 'Asia/Seoul';
  }
};

const getOsVersion = (): string | undefined => {
  const version = Platform.Version;
  return typeof version === 'number' ? String(version) : version;
};

const getMeta = (): Omit<TelemetryBatchPayload, 'events'> => ({
  anon_id: anonId,
  platform: Platform.OS,
  app_version:
    Constants.expoConfig?.version || Constants.nativeAppVersion || undefined,
  os_version: getOsVersion(),
  tz: getTimezone(),
});

const flushNow = (): void => {
  if (!enabled || !anonId) return;
  void flush(getMeta);
};

let lastAppState: AppStateStatus = AppState.currentState;

/**
 * 포그라운드 복귀와 백그라운드 전환을 잡는다.
 *
 * iOS 는 제어센터를 내리기만 해도 active↔inactive 를 오간다. 직전 상태가
 * background 였을 때만 앱을 다시 연 것으로 본다.
 */
const handleAppStateChange = (state: AppStateStatus): void => {
  const previous = lastAppState;
  lastAppState = state;

  if (state === 'active') {
    if (previous === 'background') trackEvent('app_open');
    return;
  }
  if (state !== 'background') return;

  // 백그라운드로 갈 때가 사실상 마지막 기회다 — 세션 시각을 남기고 큐를 비운다.
  void persistSession();
  flushNow();
};

export const isTelemetryEnabled = (): boolean => enabled;

export const setTelemetryEnabled = async (next: boolean): Promise<void> => {
  enabled = next;
  await setStorageItem(ENABLED_KEY, next ? '1' : '0');
  if (next) {
    flushNow();
    return;
  }
  // 껐는데 큐에 남은 이벤트가 나중에 나가면 끈 의미가 없다.
  await clearQueue();
};

/**
 * 앱 시작 시 1회 호출. 실패해도 앱 흐름을 막지 않는다.
 */
export const startTelemetry = async (): Promise<void> => {
  if (!isNative || started) return;
  started = true;

  try {
    const stored = await getStorageItem(ENABLED_KEY);
    enabled = stored !== '0';
    if (!enabled) {
      // 초기화가 끝나기 전 짧은 순간에 담긴 이벤트까지 정리한다.
      await clearQueue();
      return;
    }

    anonId = await getOrCreateDeviceId();
    await restoreSession();
    await loadQueue();

    appStateSubscription = AppState.addEventListener('change', handleAppStateChange);
    flushTimer = setInterval(flushNow, FLUSH_INTERVAL_MS);

    trackEvent('app_open');
    flushNow();
  } catch (error) {
    if (__DEV__) console.warn('[Telemetry] start failed', error);
  }
};

export const stopTelemetry = (): void => {
  if (flushTimer) {
    clearInterval(flushTimer);
    flushTimer = null;
  }
  appStateSubscription?.remove();
  appStateSubscription = null;
  started = false;
};

export const trackEvent = (name: string, params?: TelemetryParams): void => {
  // anonId 를 기다리지 않는다 — 익명 ID 는 전송할 때만 필요하고, 여기서 막으면
  // 초기화(비동기)보다 먼저 일어나는 첫 화면의 screen_view 를 놓친다.
  if (!isNative || !enabled) return;

  const now = Date.now();
  const session = touchSession(now);
  if (session.isNew) {
    // 세션 경계는 서버가 알 수 없으므로 앱이 명시적으로 남긴다.
    enqueue({
      event_id: createEventId(),
      name: 'session_start',
      ts: new Date(now).toISOString(),
      session_id: session.id,
    });
  }

  enqueue({
    event_id: createEventId(),
    name,
    ts: new Date(now).toISOString(),
    session_id: session.id,
    params,
  });

  if (shouldFlush()) flushNow();
};

export const trackScreen = (screenName: string): void => {
  trackEvent('screen_view', { screen_name: screenName });
};
