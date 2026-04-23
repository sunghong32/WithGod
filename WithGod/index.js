import messaging from '@react-native-firebase/messaging';

import { handleBackgroundRemoteMessage } from './src/shared/lib/pushNotifications';

try {
  messaging().setBackgroundMessageHandler(handleBackgroundRemoteMessage);
} catch (error) {
  if (__DEV__) {
    console.warn('[Push] Failed to register background message handler', error);
  }
}

require('expo-router/entry');
