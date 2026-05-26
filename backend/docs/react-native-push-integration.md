# React Native Push Integration

이 문서는 `with-god-rag` 서버의 오늘의 말씀 푸시를 Android / iOS 앱에 붙일 때 React Native 개발자에게 전달하는 코드입니다.

## 서버 API

- `POST /push/devices`
- `DELETE /push/devices?token=...`
- `GET /daily-verse`
- `POST /push/send/daily-verse`

서버에는 반드시 `FCM registration token` 을 등록해야 합니다.

## 패키지 설치

```bash
yarn add @react-native-firebase/app @react-native-firebase/messaging
```

iOS는 아래도 필요합니다.

```bash
cd ios && pod install
```

## API 유틸

```ts
// src/api/pushApi.ts
const API_BASE_URL = 'https://your-api.example.com';

export type PushPlatform = 'ios' | 'android';

export async function registerPushDevice(input: {
  token: string;
  platform: PushPlatform;
  timezone: string;
  enabled?: boolean;
}) {
  const response = await fetch(`${API_BASE_URL}/push/devices`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      token: input.token,
      platform: input.platform,
      timezone: input.timezone,
      enabled: input.enabled ?? true,
    }),
  });

  if (!response.ok) {
    throw new Error(`registerPushDevice failed: ${response.status}`);
  }

  return response.json();
}

export async function unregisterPushDevice(token: string) {
  const response = await fetch(
    `${API_BASE_URL}/push/devices?token=${encodeURIComponent(token)}`,
    {method: 'DELETE'},
  );

  if (!response.ok && response.status !== 404) {
    throw new Error(`unregisterPushDevice failed: ${response.status}`);
  }
}
```

## 푸시 초기화 훅

```ts
// src/features/push/useDailyVersePush.ts
import {useEffect} from 'react';
import {AppState, PermissionsAndroid, Platform} from 'react-native';
import messaging from '@react-native-firebase/messaging';
import {registerPushDevice} from '../../api/pushApi';

async function requestAndroid13Permission() {
  if (Platform.OS !== 'android' || Platform.Version < 33) {
    return true;
  }
  const result = await PermissionsAndroid.request(
    PermissionsAndroid.PERMISSIONS.POST_NOTIFICATIONS,
  );
  return result === PermissionsAndroid.RESULTS.GRANTED;
}

async function requestPushPermission() {
  if (Platform.OS === 'ios') {
    const authStatus = await messaging().requestPermission();
    return (
      authStatus === messaging.AuthorizationStatus.AUTHORIZED ||
      authStatus === messaging.AuthorizationStatus.PROVISIONAL
    );
  }
  return requestAndroid13Permission();
}

async function syncPushToken() {
  const permitted = await requestPushPermission();
  if (!permitted) {
    return;
  }

  await messaging().registerDeviceForRemoteMessages();
  const token = await messaging().getToken();
  if (!token) {
    return;
  }

  await registerPushDevice({
    token,
    platform: Platform.OS === 'ios' ? 'ios' : 'android',
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Seoul',
    enabled: true,
  });
}

export function useDailyVersePush() {
  useEffect(() => {
    void syncPushToken();

    const unsubscribeRefresh = messaging().onTokenRefresh(nextToken => {
      void registerPushDevice({
        token: nextToken,
        platform: Platform.OS === 'ios' ? 'ios' : 'android',
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Seoul',
        enabled: true,
      });
    });

    const subscription = AppState.addEventListener('change', state => {
      if (state === 'active') {
        void syncPushToken();
      }
    });

    return () => {
      unsubscribeRefresh();
      subscription.remove();
    };
  }, []);
}
```

## 앱 진입점 연결

```ts
// App.tsx
import React from 'react';
import {useDailyVersePush} from './src/features/push/useDailyVersePush';

export default function App() {
  useDailyVersePush();
  return null;
}
```

실제 앱에서는 기존 루트 컴포넌트를 그대로 렌더링하면 됩니다.

## 백그라운드 메시지 핸들러

```ts
// index.js
import {AppRegistry} from 'react-native';
import messaging from '@react-native-firebase/messaging';
import App from './App';
import {name as appName} from './app.json';

messaging().setBackgroundMessageHandler(async remoteMessage => {
  console.log('Background push handled', remoteMessage);
});

AppRegistry.registerComponent(appName, () => App);
```

## RN 개발자 전달 메모

- iOS도 APNs 토큰이 아니라 FCM 토큰을 서버에 등록해야 합니다.
- 앱 시작 시 1회 등록하고 `onTokenRefresh` 때 다시 등록해야 합니다.
- 서버는 각 기기 타임존 기준 오전 9시에 하루 한 번만 발송합니다.
- payload `data.type` 은 `daily_verse` 입니다.
