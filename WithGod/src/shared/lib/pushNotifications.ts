import Constants from 'expo-constants';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

export const DEFAULT_ANDROID_CHANNEL_ID = 'default';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldPlaySound: true,
    shouldSetBadge: true,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

export interface PushRegistrationResult {
  expoPushToken: string | null;
  reason?: 'physical-device-required' | 'permission-not-granted' | 'missing-project-id' | 'token-fetch-failed';
}

const getProjectId = (): string | null => {
  const projectId = Constants?.expoConfig?.extra?.eas?.projectId ?? Constants?.easConfig?.projectId;
  if (typeof projectId !== 'string' || projectId.length === 0) {
    return null;
  }
  return projectId;
};

const configureAndroidChannelAsync = async (): Promise<void> => {
  if (Platform.OS !== 'android') return;

  await Notifications.setNotificationChannelAsync(DEFAULT_ANDROID_CHANNEL_ID, {
    name: DEFAULT_ANDROID_CHANNEL_ID,
    importance: Notifications.AndroidImportance.MAX,
    vibrationPattern: [0, 250, 250, 250],
    lightColor: '#4A90E2',
  });
};

export const registerForPushNotificationsAsync = async (): Promise<PushRegistrationResult> => {
  await configureAndroidChannelAsync();

  if (!Device.isDevice) {
    return { expoPushToken: null, reason: 'physical-device-required' };
  }

  const { status: existingStatus } = await Notifications.getPermissionsAsync();
  let finalStatus = existingStatus;

  if (existingStatus !== 'granted') {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }

  if (finalStatus !== 'granted') {
    return { expoPushToken: null, reason: 'permission-not-granted' };
  }

  const projectId = getProjectId();
  if (!projectId) {
    return { expoPushToken: null, reason: 'missing-project-id' };
  }

  try {
    const expoPushToken = (await Notifications.getExpoPushTokenAsync({ projectId })).data;
    return { expoPushToken };
  } catch (error) {
    if (__DEV__) {
      console.warn('[Push] Failed to fetch Expo push token', error);
    }
    return { expoPushToken: null, reason: 'token-fetch-failed' };
  }
};
