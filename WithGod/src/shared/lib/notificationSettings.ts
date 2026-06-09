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
 * 설치별 안정적인 device_id 를 생성한다.
 *
 * crypto/uuid 폴리필(react-native-get-random-values)이 설치돼 있지 않고
 * 신규 네이티브 의존성 추가가 금지돼 있어, 충분히 고유한 랜덤 문자열을
 * timestamp + 다중 Math.random 조합으로 생성한다. 한 번 생성하면 영속화하여
 * 재설치 전까지 동일한 값을 사용한다.
 */
const generateDeviceId = (): string => {
  const random = () => Math.random().toString(36).slice(2, 10);
  return `dev-${Date.now().toString(36)}-${random()}${random()}`;
};

let cachedDeviceId: string | null = null;

export const getOrCreateDeviceId = async (): Promise<string> => {
  if (cachedDeviceId) return cachedDeviceId;

  const existing = await getStorageItem(DEVICE_ID_KEY);
  if (existing) {
    cachedDeviceId = existing;
    return existing;
  }

  const created = generateDeviceId();
  cachedDeviceId = created;
  await setStorageItem(DEVICE_ID_KEY, created);
  return created;
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
