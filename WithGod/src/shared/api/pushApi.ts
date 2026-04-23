import Constants from 'expo-constants';
import { Platform } from 'react-native';

import { parseError, logError } from './errors';
import { apiClient } from './client';

export interface RegisterPushDeviceInput {
  token: string;
  timezone?: string;
  deviceId?: string;
  appVersion?: string;
  osVersion?: string;
  enabled?: boolean;
}

export interface RegisterPushDevicePayload {
  token: string;
  platform: 'ios' | 'android';
  timezone: string;
  enabled: boolean;
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

export const pushApi = {
  registerDevice: async ({
    token,
    timezone,
    deviceId,
    appVersion,
    osVersion,
    enabled = true,
  }: RegisterPushDeviceInput): Promise<void> => {
    const payload: RegisterPushDevicePayload = {
      token,
      platform: getPlatform(),
      timezone: timezone || getTimezone(),
      enabled,
      deviceId,
      appVersion: appVersion || getAppVersion(),
      osVersion: osVersion || getOsVersion(),
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
