import { recallDeviceId, rememberDeviceId } from './deviceIdentity';
import { getStorageItem, setStorageItem } from './storage';

/**
 * 알림 설정(수신 여부 / 알림 시각)과 설치별 안정적인 device_id 를 영속화한다.
 *
 * 저장 위치는 storage.ts (expo-file-system 기반) 를 사용한다.
 */

const DEVICE_ID_KEY = 'withgod.deviceId';
const ENABLED_KEY = 'withgod.notifications.enabled';
const HOUR_KEY = 'withgod.notifications.scheduleHour';
const MINUTE_KEY = 'withgod.notifications.scheduleMinute';
const PRIMING_SEEN_KEY = 'withgod.notifications.primingSeen';

export const DEFAULT_SCHEDULE_HOUR = 9;
export const DEFAULT_SCHEDULE_MINUTE = 0;

export interface NotificationSettings {
  enabled: boolean;
  scheduleHour: number;
  scheduleMinute: number;
}

export const DEFAULT_NOTIFICATION_SETTINGS: NotificationSettings = {
  enabled: true,
  scheduleHour: DEFAULT_SCHEDULE_HOUR,
  scheduleMinute: DEFAULT_SCHEDULE_MINUTE,
};

/**
 * 처음 쓰는 기기의 device_id 를 만든다.
 *
 * crypto/uuid 폴리필(react-native-get-random-values)이 설치돼 있지 않아, 충분히
 * 고유한 랜덤 문자열을 timestamp + 다중 Math.random 조합으로 만든다.
 */
const generateDeviceId = (): string => {
  const random = () => Math.random().toString(36).slice(2, 10);
  return `dev-${Date.now().toString(36)}-${random()}${random()}`;
};

let deviceIdPromise: Promise<string> | null = null;

const loadDeviceId = async (): Promise<string> => {
  const existing = await getStorageItem(DEVICE_ID_KEY);
  if (existing) {
    void rememberDeviceId(existing);
    return existing;
  }

  // 파일이 없다 = 새로 깔았거나 다시 깔았다. 앱을 지워도 남는 곳에서 먼저 찾는다(#79).
  const id = (await recallDeviceId()) ?? generateDeviceId();
  await setStorageItem(DEVICE_ID_KEY, id);
  void rememberDeviceId(id);
  return id;
};

/**
 * 기기의 익명 ID. 지표(anon_id)와 푸시 기기 등록이 같이 쓴다.
 *
 * 앱 시작 때 지표와 푸시가 동시에 부르므로 한 번만 만든다 — 따로 만들면 새 기기에서
 * 서로 다른 ID 가 생길 수 있다.
 */
export const getOrCreateDeviceId = (): Promise<string> => {
  if (!deviceIdPromise) {
    deviceIdPromise = loadDeviceId().catch((error: unknown) => {
      deviceIdPromise = null;
      throw error;
    });
  }
  return deviceIdPromise;
};

const clampInt = (value: number, min: number, max: number): number => {
  if (!Number.isFinite(value)) return min;
  const rounded = Math.round(value);
  if (rounded < min) return min;
  if (rounded > max) return max;
  return rounded;
};

export const getNotificationSettings =
  async (): Promise<NotificationSettings> => {
    const [enabledRaw, hourRaw, minuteRaw] = await Promise.all([
      getStorageItem(ENABLED_KEY),
      getStorageItem(HOUR_KEY),
      getStorageItem(MINUTE_KEY),
    ]);

    return {
      // 저장된 값이 없으면(최초 실행) 기본 ON
      enabled: enabledRaw === null ? true : enabledRaw === 'true',
      scheduleHour:
        hourRaw === null
          ? DEFAULT_SCHEDULE_HOUR
          : clampInt(Number(hourRaw), 0, 23),
      scheduleMinute:
        minuteRaw === null
          ? DEFAULT_SCHEDULE_MINUTE
          : clampInt(Number(minuteRaw), 0, 59),
    };
  };

/**
 * 알림 프라이밍(사전 안내) 화면을 이미 보여줬는지 여부.
 * 시스템 권한 팝업은 iOS에서 한 번뿐이라, 맥락을 설명하는 안내를 먼저 보여주고
 * 사용자가 응답한 뒤에는 다시 노출하지 않는다.
 */
export const hasSeenNotificationPriming = async (): Promise<boolean> => {
  return (await getStorageItem(PRIMING_SEEN_KEY)) === 'true';
};

export const markNotificationPrimingSeen = async (): Promise<void> => {
  await setStorageItem(PRIMING_SEEN_KEY, 'true');
};

export const saveNotificationSettings = async (
  settings: NotificationSettings,
): Promise<void> => {
  await Promise.all([
    setStorageItem(ENABLED_KEY, settings.enabled ? 'true' : 'false'),
    setStorageItem(HOUR_KEY, String(clampInt(settings.scheduleHour, 0, 23))),
    setStorageItem(
      MINUTE_KEY,
      String(clampInt(settings.scheduleMinute, 0, 59)),
    ),
  ]);
};
