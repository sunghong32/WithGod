import messaging, { type FirebaseMessagingTypes } from '@react-native-firebase/messaging';
import type { Href } from 'expo-router';
import { Alert, PermissionsAndroid, Platform } from 'react-native';

import { pushApi } from '@/shared/api';

type OpenRoute = (href: Href) => void;

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

const registerDeviceTokenAsync = async (token: string): Promise<void> => {
  try {
    await pushApi.registerDevice({ token });
    if (__DEV__) {
      console.log('[Push] Registered FCM token on server');
    }
  } catch (error) {
    if (__DEV__) {
      console.warn('[Push] Failed to register FCM token on server', error);
    }
  }
};

const buildVerseDetailHref = (
  remoteMessage: FirebaseMessagingTypes.RemoteMessage,
): Href | null => {
  const data = remoteMessage.data ?? {};
  const url = getStringValue(data.url);

  if (url) {
    return url as Href;
  }

  const ref = getStringValue(data.ref) ?? getStringValue(data.verseRef);
  const text = getStringValue(data.text) ?? getStringValue(data.verseText);
  const comment =
    getStringValue(data.comment) ?? getStringValue(data.commentText);
  const tag = getStringValue(data.tag);
  const title =
    getStringValue(data.title) ??
    getStringValue(remoteMessage.notification?.title);
  const body =
    getStringValue(data.body) ??
    getStringValue(remoteMessage.notification?.body);

  if (!ref && !text && !comment && !tag && !title && !body) {
    return null;
  }

  return {
    pathname: '/verse-detail',
    params: {
      ref,
      text,
      comment,
      tag,
      title,
      body,
    },
  } as unknown as Href;
};

const openRemoteMessage = (
  remoteMessage: FirebaseMessagingTypes.RemoteMessage,
  openRoute: OpenRoute,
): void => {
  const href = buildVerseDetailHref(remoteMessage);
  if (!href) return;
  openRoute(href);
};

const showForegroundAlert = (
  remoteMessage: FirebaseMessagingTypes.RemoteMessage,
  openRoute: OpenRoute,
): void => {
  const href = buildVerseDetailHref(remoteMessage);
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
    const permissionGranted = await requestPushPermissionAsync();

    if (permissionGranted) {
      const token = await getFcmTokenAsync();
      if (token) {
        if (__DEV__) {
          console.log('[Push] FCM token:', token);
        }
        await registerDeviceTokenAsync(token);
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
