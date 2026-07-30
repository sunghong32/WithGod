import { router } from "expo-router";

/**
 * 시스템 딥링크가 내비게이션에 닿기 전에 경로를 보정한다 (expo-router 공식 훅).
 *
 * 위젯 탭 딥링크(withgod://)는 '/'(스플래시 라우트)로 들어오는데, 실행 중인
 * 앱에서 스플래시 라우트를 다시 마운트하면 마운트-즉시-팝 경합으로 네이티브
 * 스택이 크래시했다(이슈 #16). 실행 중(initial=false)에는 '/'를 홈 탭으로
 * 돌리고, 콜드 스타트(initial=true)는 그대로 둬서 스플래시가 정상 재생된다.
 *
 * 경로만 바꾸면 linking 이 상태를 '리셋'해 덮인 화면이 페이드로 증발한다
 * (표준 pop 이 아님). 그래서 먼저 dismissTo 로 실제 pop 을 디스패치해
 * 오른쪽으로 밀려나는 기본 전환을 태우고, 반환하는 '/(tabs)' 리셋은 이미
 * 같은 상태라 시각적 no-op 이 된다.
 */
export function redirectSystemPath({ path, initial }: { path: string; initial: boolean }) {
  try {
    if (!initial) {
      const normalized = path.replace(/^withgod:\/\//, '/').replace(/\/+$/, '') || '/';
      if (normalized === '/') {
        if (router.canGoBack()) {
          router.dismissTo('/(tabs)');
        }
        return '/(tabs)';
      }
    }
    return path;
  } catch {
    return path;
  }
}
