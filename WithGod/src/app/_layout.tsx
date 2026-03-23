import { DarkTheme, DefaultTheme, ThemeProvider } from '@react-navigation/native';
import { type Href, Stack, useRouter } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import * as Notifications from 'expo-notifications';
import { useEffect } from 'react';
import 'react-native-reanimated';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { useColorScheme } from '@/shared/hooks/use-color-scheme';
import { QueryProvider } from '@/shared/lib/QueryProvider';
import { registerForPushNotificationsAsync } from '@/shared/lib/pushNotifications';

SplashScreen.preventAutoHideAsync();

export const unstable_settings = {
  anchor: '(tabs)',
};

export default function RootLayout() {
  const colorScheme = useColorScheme();
  const router = useRouter();

  useEffect(() => {
    SplashScreen.hideAsync();
  }, []);

  useEffect(() => {
    registerForPushNotificationsAsync()
      .then(({ expoPushToken, reason }) => {
        if (__DEV__) {
          if (expoPushToken) {
            console.log('[Push] Expo push token:', expoPushToken);
          } else {
            console.log('[Push] Expo push token unavailable:', reason ?? 'unknown');
          }
        }
      })
      .catch((error: unknown) => {
        if (__DEV__) {
          console.warn('[Push] Push registration failed', error);
        }
      });

    const notificationListener = Notifications.addNotificationReceivedListener((notification) => {
      if (__DEV__) {
        console.log('[Push] Notification received:', notification.request.identifier);
      }
    });

    const responseListener = Notifications.addNotificationResponseReceivedListener((response) => {
      const data = response.notification.request.content.data;
      const url = data && typeof data === 'object' ? (data as { url?: unknown }).url : null;
      if (typeof url === 'string' && url.length > 0) {
        router.push(url as Href);
      }
    });

    return () => {
      notificationListener.remove();
      responseListener.remove();
    };
  }, [router]);

  return (
    <QueryProvider>
      <SafeAreaProvider>
        <ThemeProvider value={colorScheme === 'dark' ? DarkTheme : DefaultTheme}>
          <Stack screenOptions={{ headerShown: false }}>
            <Stack.Screen name="index" />
            <Stack.Screen name="(tabs)" />
            <Stack.Screen name="result" />
            <Stack.Screen name="modal" options={{ presentation: 'modal', headerShown: true, title: 'Modal' }} />
          </Stack>
          <StatusBar style="auto" />
        </ThemeProvider>
      </SafeAreaProvider>
    </QueryProvider>
  );
}
