import { Platform } from "react-native";

import { isTelemetryEnabled, trackEvent, trackScreen } from "./telemetry";

/**
 * 분석 이벤트 래퍼.
 *
 * - 네이티브(iOS/Android)에서만 동작하고 웹은 no-op.
 * - 분석 실패가 앱 흐름을 깨지 않도록 모든 호출을 삼킨다.
 * - 사용자가 입력한 마음 텍스트 같은 개인 내용은 절대 파라미터로 보내지 않는다.
 *
 * Firebase 와 자체 수집(telemetry) 양쪽으로 같은 이벤트를 보낸다. 호출부는
 * 이 파일만 알면 되므로 화면 코드는 어디로 가는지 신경 쓰지 않는다.
 * 자체 수집은 어드민 대시보드용이고, Firebase 는 수치 대조용으로 남긴다.
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
  // 사용자가 통계 수집을 끄면 자체 수집뿐 아니라 Firebase 로도 보내지 않는다.
  // (자동 수집 자체는 setFirebaseAnalyticsCollectionEnabled 로 중단한다)
  if (!isNative || !isTelemetryEnabled()) return;
  trackEvent(name, params);
  try {
    const { analytics, module } = getAnalyticsApi();
    await module.logEvent(analytics, name, params);
  } catch (error) {
    if (__DEV__) console.warn("[Analytics] logEvent failed:", name, error);
  }
};

/**
 * Firebase 의 자동 수집(세션, 앱 최초 실행, IP 기반 대략적 위치 등)을 켜고 끈다.
 *
 * 명시적 logEvent 만 막으면 Firebase 가 뒤에서 자동 수집하는 데이터는 계속
 * 흐른다. 개인정보 신고에서 '사용자가 수집을 끌 수 있음'으로 선언하려면 이
 * 자동 수집까지 멈춰야 한다. 이 설정은 네이티브에 영속되어 앱을 다시 켜도 유지된다.
 */
export const setFirebaseAnalyticsCollectionEnabled = async (
  collectionEnabled: boolean,
): Promise<void> => {
  if (!isNative) return;
  try {
    const { analytics, module } = getAnalyticsApi();
    await module.setAnalyticsCollectionEnabled(analytics, collectionEnabled);
  } catch (error) {
    if (__DEV__) {
      console.warn("[Analytics] setCollectionEnabled failed:", error);
    }
  }
};

export const logScreenViewEvent = async (screenName: string): Promise<void> => {
  if (!isNative || !isTelemetryEnabled()) return;
  trackScreen(screenName);
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
