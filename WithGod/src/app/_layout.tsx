import { DarkTheme, DefaultTheme, ThemeProvider } from '@react-navigation/native';
import { type Href, Stack, usePathname, useRouter } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';
import { KeyboardProvider } from 'react-native-keyboard-controller';
import 'react-native-reanimated';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { AppDrawer, useAppDrawer } from '@/shared/components/AppDrawer';
import { HistorySidebar } from '@/shared/components/HistorySidebar';
import { useColorScheme } from '@/shared/hooks/use-color-scheme';
import { logScreenViewEvent } from '@/shared/lib/analytics';
import { QueryProvider } from '@/shared/lib/QueryProvider';
import { getAppLanguageChoice, initAppLanguage } from '@/shared/lib/i18n';
import { setWidgetHomeHandler } from '@/shared/lib/widgetLink';
import { syncWidgetLanguage } from '../../modules/widget-bridge';
import { setupPushNotificationsAsync } from '@/shared/lib/pushNotifications';
import { startTelemetry, stopTelemetry } from '@/shared/lib/telemetry';
import { TelemetryConsentModal } from '@/shared/components/TelemetryConsentModal';
import { UpdatePromptModal } from '@/shared/components/UpdatePromptModal';
import { refreshHomeWidgetAsync } from '@/widgets/refreshHomeWidget';

SplashScreen.preventAutoHideAsync();

/**
 * 스택 위로 밀려 올라오는 화면들. 여기서는 좌측 엣지가 네이티브 뒤로가기
 * 제스처와 겹치므로 드로어 스와이프를 끈다.
 *
 * 홈 경로를 '/' 로 직접 비교하면 안 된다 — 스플래시를 닫는 경로가 플랫폼마다
 * 달라(back 또는 replace) 홈의 pathname 이 '/' 가 아닐 수 있고, 그러면 안드로이드
 * 에서 스와이프가 통째로 죽는다(실측).
 */
const PUSHED_ROUTES = ['/result', '/settings', '/bookmarks'];

/**
 * 드로어 안에서 렌더되는 사이드바. 항목을 고르면 드로어를 닫고 결과 화면으로
 * 이동한다 (드로어 컨텍스트를 쓰려면 AppDrawer 내부여야 해서 별도 컴포넌트).
 */
function HistorySidebarHost() {
  const router = useRouter();
  const { close } = useAppDrawer();
  return (
    <HistorySidebar
      onSelect={(entry) => {
        close();
        router.push({ pathname: '/result', params: { historyId: entry.id } });
      }}
    />
  );
}

export const unstable_settings = {
  anchor: '(tabs)',
};

export default function RootLayout() {
  const colorScheme = useColorScheme();
  const router = useRouter();

  useEffect(() => {
    SplashScreen.hideAsync();
  }, []);

  // 저장된 언어/기기 언어를 반영 (동기 초기화는 ko 로 이미 완료 — 여기선 보정만).
  // 이어서 iOS 위젯의 App Group 공유 언어도 동기화한다(재설치·업데이트 대비).
  useEffect(() => {
    void (async () => {
      await initAppLanguage();
      const choice = await getAppLanguageChoice();
      syncWidgetLanguage(choice === "system" ? null : choice);
    })();
  }, []);

  // 자체 지표 수집 시작. 화면 추적보다 먼저 켜져야 첫 screen_view 가 잡힌다.
  useEffect(() => {
    void startTelemetry();
    return stopTelemetry;
  }, []);

  // 화면 전환 추적 (스플래시와 홈은 둘 다 '/'라 home 으로 1회 기록된다)
  const pathname = usePathname();
  useEffect(() => {
    const screenName = pathname === '/' ? 'home' : pathname.replace(/^\//, '');
    void logScreenViewEvent(screenName);
  }, [pathname]);

  // 앱을 열 때 안드로이드 홈 위젯도 오늘의 말씀으로 즉시 동기화 (best-effort)
  useEffect(() => {
    void refreshHomeWidgetAsync();
  }, []);

  // 위젯 탭(실행 중 딥링크): 화면 전환 애니메이션을 끄고 즉시 홈 탭으로 팝한다.
  // 앱 등장(줌) 아래에서 전환이 끝나 "열리면 이미 홈"으로 보인다(이슈 #16).
  // instantPop 이 켜진 렌더가 커밋된 다음 틱에 팝해야 무애니메이션이 적용된다.
  const [instantPop, setInstantPop] = useState(false);
  useEffect(() => {
    setWidgetHomeHandler(() => setInstantPop(true));
    return () => setWidgetHomeHandler(null);
  }, []);
  useEffect(() => {
    if (!instantPop) return;
    const popId = setTimeout(() => {
      if (router.canGoBack()) {
        router.dismissTo('/(tabs)');
      }
    }, 0);
    const restoreId = setTimeout(() => setInstantPop(false), 400);
    return () => {
      clearTimeout(popId);
      clearTimeout(restoreId);
    };
  }, [instantPop, router]);

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
          {/* 기록 드로어. 스택 전체를 감싸 화면이 통째로 밀리게 한다.
              스와이프로 여는 건 홈에서만 — 다른 화면은 좌측 엣지가 네이티브
              뒤로가기 제스처와 겹친다. */}
          <AppDrawer
            swipeEnabled={!PUSHED_ROUTES.some((route) => pathname.startsWith(route))}
            renderSidebar={() => <HistorySidebarHost />}
          >
          <Stack screenOptions={{ headerShown: false }}>
            {/* 스플래시·메인은 스와이프 백 비활성 (스택 최하단이라 뒤로 갈 곳이 없음) */}
            {/* 스플래시는 router.back()(pop)으로 닫히는데, 네이티브 pop 기본
                애니메이션이 '우측 슬라이드'라 밀려나가듯 보인다. 팝되는 화면의
                animation 설정을 따르므로 fade 로 지정해 자연스럽게 사라지게 한다. */}
            <Stack.Screen
              name="index"
              options={{ gestureEnabled: false, animation: 'fade' }}
            />
            <Stack.Screen name="(tabs)" options={{ gestureEnabled: false }} />
            <Stack.Screen name="result" options={{ animation: instantPop ? 'none' : 'default' }} />
            <Stack.Screen name="settings" options={{ animation: instantPop ? 'none' : 'default' }} />
            <Stack.Screen name="bookmarks" options={{ animation: instantPop ? 'none' : 'default' }} />
          </Stack>
          </AppDrawer>
          {/* 유럽 첫 실행 시 통계 수집 동의창 (그 외 지역은 뜨지 않음) */}
          <TelemetryConsentModal />
          {/* 새 버전이 있으면 업데이트 안내 (서버 미응답 시 뜨지 않음) */}
          <UpdatePromptModal />
          <StatusBar style="auto" />
          </ThemeProvider>
        </KeyboardProvider>
      </SafeAreaProvider>
    </QueryProvider>
  );
}
