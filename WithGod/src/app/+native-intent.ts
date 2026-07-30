import { emitWidgetHome } from "@/shared/lib/widgetLink";

/**
 * 시스템 딥링크가 내비게이션에 닿기 전에 경로를 보정한다 (expo-router 공식 훅).
 *
 * 위젯 탭 딥링크(withgod://)는 '/'(스플래시 라우트)로 들어오는데, 실행 중인
 * 앱에서 스플래시 라우트를 다시 마운트하면 마운트-즉시-팝 경합으로 네이티브
 * 스택이 크래시했다(이슈 #16). 실행 중(initial=false)에는 루트 레이아웃에
 * 위임해 '애니메이션 없는 즉시 팝'으로 홈 탭에 보내고(앱 등장 줌 아래에서
 * 끝나 다른 앱들처럼 "열리면 이미 홈"으로 보인다), '/(tabs)' 반환은 이미
 * 같은 상태라 시각적 no-op 안전망이 된다. 콜드 스타트(initial=true)는
 * 그대로 둬서 스플래시가 정상 재생된다.
 */
export async function redirectSystemPath({ path, initial }: { path: string; initial: boolean }) {
  try {
    if (!initial) {
      const normalized = path.replace(/^withgod:\/\//, '/').replace(/\/+$/, '') || '/';
      if (normalized === '/') {
        if (emitWidgetHome()) {
          // 무애니메이션 팝이 커밋될 시간(두어 프레임)을 준 뒤 안전망 경로 반환
          await new Promise((resolve) => setTimeout(resolve, 150));
        }
        return '/(tabs)';
      }
    }
    return path;
  } catch {
    return path;
  }
}
