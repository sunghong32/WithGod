import { Platform } from "react-native";

/**
 * 안드로이드 좌측 엣지를 시스템 뒤로가기 제스처에서 넘겨받는 브리지.
 *
 * 드로어가 닫혀 있을 때만 가져오고, 열려 있으면 반납해 시스템 뒤로가기가
 * 정상 동작하게 둔다. 네이티브 모듈이 없는 환경(iOS·구 빌드)에서는 조용히
 * 아무 것도 하지 않는다. [[widget-bridge]] 와 같은 방식.
 */
export const setLeftEdgeGestureExclusion = (
  widthDp: number,
  enabled: boolean,
): void => {
  if (Platform.OS !== "android") return;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports -- 모듈 미탑재 환경 폴백
    const { requireNativeModule } = require("expo-modules-core");
    requireNativeModule("GestureExclusion").setLeftEdgeExclusion(
      widthDp,
      enabled,
    );
  } catch {
    // 미탑재 — 다음 네이티브 빌드부터 동작
  }
};
