import { Platform } from "react-native";

/**
 * iOS 위젯 언어 동기화 브리지.
 *
 * 위젯 익스텐션은 앱 JS 저장소를 못 읽어 App Group UserDefaults 로 언어
 * 선택을 공유한다. 네이티브 모듈이 없는 환경(구 dev client·Android)에서는
 * 조용히 아무 것도 하지 않는다(no-throw).
 */
export const syncWidgetLanguage = (language: string | null): void => {
  if (Platform.OS !== "ios") return;
  try {
    // eslint-disable-next-line @typescript-eslint/no-require-imports -- 모듈 미탑재 환경 폴백
    const { requireNativeModule } = require("expo-modules-core");
    const bridge = requireNativeModule("WidgetBridge");
    bridge.setSharedLanguage(language);
    bridge.reloadWidgets();
  } catch {
    // 미탑재 — 다음 네이티브 빌드부터 동작
  }
};
