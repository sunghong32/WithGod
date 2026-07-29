import Constants from 'expo-constants';
import { Platform } from 'react-native';

import { getAppLanguage } from '@/shared/lib/i18n';

import { parseError, logError } from './errors';
import { apiClient } from './client';

export interface RegisterPushDeviceInput {
  token: string;
  timezone?: string;
  deviceId?: string;
  appVersion?: string;
  osVersion?: string;
  enabled?: boolean;
  scheduleHour?: number;
  scheduleMinute?: number;
}

export interface RegisterPushDevicePayload {
  token: string;
  platform: 'ios' | 'android';
  timezone: string;
  enabled: boolean;
  // 앱 표시 언어 — 오늘의 말씀 푸시 제목·본문 현지화용(이슈 #12)
  language: string;
  // 공유 API 규약(snake_case)
  device_id?: string;
  schedule_hour?: number;
  schedule_minute?: number;
  app_version?: string;
  os_version?: string;
  // 현재 배포된 백엔드(camelCase)와의 하위호환을 위해 함께 전송
  deviceId?: string;
  appVersion?: string;
  osVersion?: string;
}

const getPlatform = (): RegisterPushDevicePayload['platform'] =>
  Platform.OS === 'ios' ? 'ios' : 'android';

const getTimezone = (): string => {
  try {
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    return timezone || 'Asia/Seoul';
  } catch {
    return 'Asia/Seoul';
  }
};

const getAppVersion = (): string | undefined =>
  Constants.expoConfig?.version ||
  Constants.nativeAppVersion ||
  undefined;

const getOsVersion = (): string | undefined => {
  const version = Platform.Version;
  if (typeof version === 'string') return version;
  if (typeof version === 'number') return String(version);
  return undefined;
};

const clampInt = (
  value: number | undefined,
  min: number,
  max: number,
): number | undefined => {
  if (value === undefined || !Number.isFinite(value)) return undefined;
  const rounded = Math.round(value);
  if (rounded < min) return min;
  if (rounded > max) return max;
  return rounded;
};

export const pushApi = {
  registerDevice: async ({
    token,
    timezone,
    deviceId,
    appVersion,
    osVersion,
    enabled = true,
    scheduleHour,
    scheduleMinute,
  }: RegisterPushDeviceInput): Promise<void> => {
    const resolvedAppVersion = appVersion || getAppVersion();
    const resolvedOsVersion = osVersion || getOsVersion();
    const resolvedHour = clampInt(scheduleHour, 0, 23);
    const resolvedMinute = clampInt(scheduleMinute, 0, 59);

    const payload: RegisterPushDevicePayload = {
      token,
      platform: getPlatform(),
      timezone: timezone || getTimezone(),
      enabled,
      language: getAppLanguage(),
      // 공유 규약(snake_case)
      device_id: deviceId,
      schedule_hour: resolvedHour,
      schedule_minute: resolvedMinute,
      app_version: resolvedAppVersion,
      os_version: resolvedOsVersion,
      // 하위호환(camelCase)
      deviceId,
      appVersion: resolvedAppVersion,
      osVersion: resolvedOsVersion,
    };

    try {
      await apiClient.post('/push/devices', payload);
    } catch (error) {
      const apiError = parseError(error);
      logError(apiError, 'registerPushDevice');
      throw apiError;
    }
  },
};
