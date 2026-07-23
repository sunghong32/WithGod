import { DarkTheme, DefaultTheme, ThemeProvider } from '@react-navigation/native';
import { type Href, Stack, useRouter } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { KeyboardProvider } from 'react-native-keyboard-controller';
import 'react-native-reanimated';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { useColorScheme } from '@/shared/hooks/use-color-scheme';
import { QueryProvider } from '@/shared/lib/QueryProvider';
import { setupPushNotificationsAsync } from '@/shared/lib/pushNotifications';
import { refreshHomeWidgetAsync } from '@/widgets/refreshHomeWidget';

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

  // 앱을 열 때 안드로이드 홈 위젯도 오늘의 말씀으로 즉시 동기화 (best-effort)
  useEffect(() => {
    void refreshHomeWidgetAsync();
  }, []);

  useEffect(() => {
    let unsubscribe: () => void = () => {};
    let isMounted = true;

    setupPushNotificationsAsync({
      // 홈은 스택 최하단 앵커이므로 push 로 중복 생성하지 않고 dismissTo 로 되돌아간다.
      openRoute: (href: Href) =>
        href === '/(tabs)' ? router.dismissTo(href) : router.push(href),
    })
      .then((cleanup) => {
        if (!isMounted) {
          cleanup();
          return;
        }
        unsubscribe = cleanup;
      })
      .catch((error: unknown) => {
        if (__DEV__) {
          console.warn('[Push] Push setup failed', error);
        }
      });

    return () => {
      isMounted = false;
      unsubscribe();
    };
  }, [router]);

  return (
    <QueryProvider>
      <SafeAreaProvider>
        <KeyboardProvider>
          <ThemeProvider value={colorScheme === 'dark' ? DarkTheme : DefaultTheme}>
          <Stack screenOptions={{ headerShown: false }}>
            {/* 스플래시·메인은 스와이프 백 비활성 (스택 최하단이라 뒤로 갈 곳이 없음) */}
            <Stack.Screen name="index" options={{ gestureEnabled: false }} />
            <Stack.Screen name="(tabs)" options={{ gestureEnabled: false }} />
            <Stack.Screen name="result" />
            <Stack.Screen name="settings" />
            <Stack.Screen name="bookmarks" />
          </Stack>
          <StatusBar style="auto" />
          </ThemeProvider>
        </KeyboardProvider>
      </SafeAreaProvider>
    </QueryProvider>
  );
}
