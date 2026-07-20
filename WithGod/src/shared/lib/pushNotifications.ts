import messaging, { type FirebaseMessagingTypes } from '@react-native-firebase/messaging';
import type { Href } from 'expo-router';
import { Alert, PermissionsAndroid, Platform } from 'react-native';

import { pushApi } from '@/shared/api';

import {
  getNotificationSettings,
  getOrCreateDeviceId,
  type NotificationSettings,
} from './notificationSettings';

type OpenRoute = (href: Href) => void;

export type PushPermissionStatus = 'granted' | 'denied' | 'undetermined';

export interface SetupPushNotificationsOptions {
  openRoute: OpenRoute;
}

const isNativePlatform = Platform.OS === 'ios' || Platform.OS === 'android';

const getStringValue = (value: unknown): string | undefined => {
  if (typeof value !== 'string') return undefined;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
};

const ensureRemoteMessagesRegisteredAsync = async (): Promise<void> => {
  if (!isNativePlatform) return;

  const instance = messaging();
  if (!instance.isDeviceRegisteredForRemoteMessages) {
    await instance.registerDeviceForRemoteMessages();
  }
};

const requestAndroidNotificationPermissionAsync = async (): Promise<boolean> => {
  if (Platform.OS !== 'android') return true;
  if (Platform.Version < 33) return true;

  const permission = PermissionsAndroid.PERMISSIONS.POST_NOTIFICATIONS;
  const granted = await PermissionsAndroid.request(permission);
  return granted === PermissionsAndroid.RESULTS.GRANTED;
};

const requestIosNotificationPermissionAsync = async (): Promise<boolean> => {
  if (Platform.OS !== 'ios') return true;

  const status = await messaging().requestPermission();
  return (
    status === messaging.AuthorizationStatus.AUTHORIZED ||
    status === messaging.AuthorizationStatus.PROVISIONAL
  );
};

export const requestPushPermissionAsync = async (): Promise<boolean> => {
  if (!isNativePlatform) return false;

  try {
    const androidGranted = await requestAndroidNotificationPermissionAsync();
    if (!androidGranted) {
      return false;
    }

    return requestIosNotificationPermissionAsync();
  } catch (error) {
    if (__DEV__) {
      console.warn('[Push] Failed to request notification permission', error);
    }
    return false;
  }
};

/**
 * 현재 알림 권한 상태를 확인한다(요청은 하지 않음).
 * 설정 화면에서 "권한 거부" 안내/시스템 설정 이동 버튼 노출 여부를 판단할 때 사용.
 */
export const getPushPermissionStatusAsync =
  async (): Promise<PushPermissionStatus> => {
    if (!isNativePlatform) return 'denied';

    try {
      if (Platform.OS === 'android') {
        if (Platform.Version < 33) return 'granted';
        const granted = await PermissionsAndroid.check(
          PermissionsAndroid.PERMISSIONS.POST_NOTIFICATIONS,
        );
        return granted ? 'granted' : 'denied';
      }

      const status = await messaging().hasPermission();
      if (
        status === messaging.AuthorizationStatus.AUTHORIZED ||
        status === messaging.AuthorizationStatus.PROVISIONAL
      ) {
        return 'granted';
      }
      if (status === messaging.AuthorizationStatus.NOT_DETERMINED) {
        return 'undetermined';
      }
      return 'denied';
    } catch (error) {
      if (__DEV__) {
        console.warn('[Push] Failed to read permission status', error);
      }
      return 'denied';
    }
  };

export const getFcmTokenAsync = async (): Promise<string | null> => {
  if (!isNativePlatform) return null;

  try {
    await ensureRemoteMessagesRegisteredAsync();
    const token = await messaging().getToken();
    return token || null;
  } catch (error) {
    if (__DEV__) {
      console.warn('[Push] Failed to fetch FCM token', error);
    }
    return null;
  }
};

/**
 * 서버에 기기 토큰·설정을 등록한다. 예외는 던지지 않고 성공 여부만 반환한다(no-throw).
 */
const registerDeviceTokenAsync = async (
  token: string,
  settings?: NotificationSettings,
): Promise<boolean> => {
  try {
    const deviceId = await getOrCreateDeviceId();
    const resolved = settings ?? (await getNotificationSettings());
    await pushApi.registerDevice({
      token,
      deviceId,
      enabled: resolved.enabled,
      scheduleHour: resolved.scheduleHour,
      scheduleMinute: resolved.scheduleMinute,
    });
    if (__DEV__) {
      console.log(
        `[Push] Registered device on server (enabled=${resolved.enabled}, ` +
          `${resolved.scheduleHour}:${String(resolved.scheduleMinute).padStart(2, '0')})`,
      );
    }
    return true;
  } catch (error) {
    if (__DEV__) {
      console.warn('[Push] Failed to register FCM token on server', error);
    }
    return false;
  }
};

/**
 * 프라이밍 안내에서 '알림 받기'를 선택했을 때: 시스템 권한 요청 → 허용 시
 * 저장된 설정(기본 ON·오전 9시)으로 서버에 기기를 등록한다.
 *
 * @returns 권한 허용 여부
 */
export const requestPermissionAndRegisterAsync = async (): Promise<boolean> => {
  if (!isNativePlatform) return false;

  const granted = await requestPushPermissionAsync();
  if (!granted) return false;

  const savedSettings = await getNotificationSettings();
  const token = await getFcmTokenAsync();
  if (token) {
    await registerDeviceTokenAsync(token, savedSettings);
  }
  return true;
};

/**
 * 설정 화면에서 토글/시각을 바꾼 뒤 호출하여 백엔드에 즉시 반영한다.
 * 토큰을 다시 받아 device_id 와 함께 enabled/schedule 을 전송한다.
 *
 * @returns 서버 반영 성공 여부(토큰을 못 받으면 false)
 */
export const syncNotificationSettingsAsync = async (
  settings: NotificationSettings,
): Promise<boolean> => {
  if (!isNativePlatform) return false;
  const token = await getFcmTokenAsync();
  if (!token) return false;
  return registerDeviceTokenAsync(token, settings);
};

// 오늘의 말씀 알림은 홈에 이미 같은 내용(말씀+풀이)이 있으므로 별도 상세 화면 없이
// 홈으로 보낸다. 서버가 data.url 로 명시적 경로를 주면 그 경로를 우선한다.
const buildNotificationHref = (
  remoteMessage: FirebaseMessagingTypes.RemoteMessage,
): Href => {
  const url = getStringValue(remoteMessage.data?.url);
  return (url ?? '/(tabs)') as Href;
};

const openRemoteMessage = (
  remoteMessage: FirebaseMessagingTypes.RemoteMessage,
  openRoute: OpenRoute,
): void => {
  openRoute(buildNotificationHref(remoteMessage));
};

const showForegroundAlert = (
  remoteMessage: FirebaseMessagingTypes.RemoteMessage,
  openRoute: OpenRoute,
): void => {
  const href = buildNotificationHref(remoteMessage);
  const title =
    getStringValue(remoteMessage.notification?.title) ??
    getStringValue(remoteMessage.data?.title) ??
    '새로운 말씀 알림';
  const body =
    getStringValue(remoteMessage.notification?.body) ??
    getStringValue(remoteMessage.data?.body) ??
    '말씀을 확인해보세요';

  const buttons = href
    ? [
        { text: '닫기', style: 'cancel' as const },
        { text: '말씀 보기', onPress: () => openRoute(href) },
      ]
    : [{ text: '확인', style: 'default' as const }];

  Alert.alert(title, body, buttons);
};

export const handleBackgroundRemoteMessage = async (
  remoteMessage: FirebaseMessagingTypes.RemoteMessage,
): Promise<void> => {
  if (__DEV__) {
    console.log(
      '[Push] Background message received:',
      JSON.stringify(
        {
          messageId: remoteMessage.messageId,
          data: remoteMessage.data,
          notification: remoteMessage.notification,
        },
        null,
        2,
      ),
    );
  }
};

export const setupPushNotificationsAsync = async ({
  openRoute,
}: SetupPushNotificationsOptions): Promise<() => void> => {
  if (!isNativePlatform) {
    return () => undefined;
  }

  let unsubscribeForeground: () => void = () => {};
  let unsubscribeOpened: () => void = () => {};
  let unsubscribeTokenRefresh: () => void = () => {};

  try {
    // 앱 시작 시 시스템 권한 팝업을 바로 띄우지 않는다(맥락 없는 요청 방지).
    // 미결정(undetermined) 상태면 홈의 프라이밍 안내를 거쳐
    // requestPermissionAndRegisterAsync 로 요청한다.
    const permission = await getPushPermissionStatusAsync();
    const permissionGranted = permission === 'granted';

    // 저장된 사용자 설정(알림 on/off, 시각)을 함께 보내서
    // 앱 재시작 시 OFF 가 기본값 true 로 덮어써지지 않도록 한다.
    const savedSettings = await getNotificationSettings();

    if (permissionGranted) {
      const token = await getFcmTokenAsync();
      if (token) {
        if (__DEV__) {
          console.log('[Push] FCM token:', token);
        }
        await registerDeviceTokenAsync(token, savedSettings);
      } else if (__DEV__) {
        console.log('[Push] FCM token unavailable');
      }
    } else if (__DEV__) {
      console.log('[Push] Notification permission denied');
    }

    unsubscribeForeground = messaging().onMessage(
      async (remoteMessage: FirebaseMessagingTypes.RemoteMessage) => {
        if (__DEV__) {
          console.log(
            '[Push] Foreground message received:',
            JSON.stringify(
              {
                messageId: remoteMessage.messageId,
                data: remoteMessage.data,
                notification: remoteMessage.notification,
              },
              null,
              2,
            ),
          );
        }

        showForegroundAlert(remoteMessage, openRoute);
      },
    );

    unsubscribeOpened = messaging().onNotificationOpenedApp(
      (remoteMessage: FirebaseMessagingTypes.RemoteMessage) => {
        if (__DEV__) {
          console.log(
            '[Push] Notification opened from background:',
            JSON.stringify(remoteMessage.data, null, 2),
          );
        }
        openRemoteMessage(remoteMessage, openRoute);
      },
    );

    unsubscribeTokenRefresh = messaging().onTokenRefresh(
      async (token: string) => {
        if (__DEV__) {
          console.log('[Push] FCM token refreshed:', token);
        }
        await registerDeviceTokenAsync(token);
      },
    );

    const initialNotification = await messaging().getInitialNotification();
    if (initialNotification) {
      if (__DEV__) {
        console.log(
          '[Push] Notification opened from quit state:',
          JSON.stringify(initialNotification.data, null, 2),
        );
      }
      openRemoteMessage(initialNotification, openRoute);
    }
  } catch (error) {
    if (__DEV__) {
      console.warn('[Push] Failed to initialize push notifications', error);
    }
  }

  return () => {
    unsubscribeForeground();
    unsubscribeOpened();
    unsubscribeTokenRefresh();
  };
};
