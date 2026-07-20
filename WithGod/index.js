import messaging from '@react-native-firebase/messaging';
import { Platform } from 'react-native';

import { handleBackgroundRemoteMessage } from './src/shared/lib/pushNotifications';

try {
  messaging().setBackgroundMessageHandler(handleBackgroundRemoteMessage);
} catch (error) {
  if (__DEV__) {
    console.warn('[Push] Failed to register background message handler', error);
  }
}

// 안드로이드 홈 화면 위젯: 헤드리스 기동 시에도 실행되는 엔트리에서 등록해야 한다
if (Platform.OS === 'android') {
  try {
    const { registerWidgetTaskHandler } = require('react-native-android-widget');
    const { widgetTaskHandler } = require('./src/widgets/widgetTaskHandler');
    registerWidgetTaskHandler(widgetTaskHandler);
  } catch (error) {
    if (__DEV__) {
      console.warn('[Widget] Failed to register widget task handler', error);
    }
  }
}

require('expo-router/entry');
