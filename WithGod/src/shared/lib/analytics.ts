import { Platform } from "react-native";

/**
 * Firebase Analytics 래퍼.
 *
 * - 네이티브(iOS/Android)에서만 동작하고 웹은 no-op.
 * - 분석 실패가 앱 흐름을 깨지 않도록 모든 호출을 삼킨다.
 * - 사용자가 입력한 마음 텍스트 같은 개인 내용은 절대 파라미터로 보내지 않는다.
 */

type AnalyticsParams = Record<string, string | number | boolean>;

const isNative = Platform.OS === "ios" || Platform.OS === "android";

// require 를 호출 시점으로 미뤄 웹 런타임에서 네이티브 모듈 초기화를 피한다
// (정적 import 는 웹에서 모듈 로드 시점에 NativeModules 접근으로 터질 수 있음)
const getAnalyticsApi = () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { getApp } = require("@react-native-firebase/app");
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const analyticsModule = require("@react-native-firebase/analytics");
  return {
    analytics: analyticsModule.getAnalytics(getApp()),
    module: analyticsModule,
  };
};

export const logAnalyticsEvent = async (
  name: string,
  params?: AnalyticsParams,
): Promise<void> => {
  if (!isNative) return;
  try {
    const { analytics, module } = getAnalyticsApi();
    await module.logEvent(analytics, name, params);
  } catch (error) {
    if (__DEV__) console.warn("[Analytics] logEvent failed:", name, error);
  }
};

export const logScreenViewEvent = async (screenName: string): Promise<void> => {
  if (!isNative) return;
  try {
    const { analytics, module } = getAnalyticsApi();
    await module.logScreenView(analytics, {
      screen_name: screenName,
      screen_class: screenName,
    });
  } catch (error) {
    if (__DEV__) {
      console.warn("[Analytics] screenView failed:", screenName, error);
    }
  }
};
