import Constants from "expo-constants";
import { Platform } from "react-native";

import { compareVersions } from "./appUpdate";

/**
 * 오늘의 말씀 날짜(#69).
 *
 * 홈·위젯·푸시가 늘 같은 말씀을 보여 주도록 기기마다 날짜 기준을 하나로 정한다.
 * - 현지 날짜(각자의 자정에 바뀜): 안드로이드(위젯도 JS 라 OTA 로 함께 바뀜), iOS 1.6.1 이상
 * - 한국 날짜(한국 자정에 바뀜): iOS 1.6.0 이하 — iOS 위젯(Swift)이 한국 날짜로 요청·갱신하고
 *   스토어 빌드로만 바뀌므로, 홈·푸시도 위젯에 맞춘다.
 * 푸시는 서버가 보내므로 기기 등록 때 이 기준(`verseDateMode`)을 함께 알린다.
 */

/** iOS 위젯이 현지 날짜를 쓰기 시작한 앱 버전. */
const IOS_LOCAL_DATE_SINCE = "1.6.1";

const nativeVersion = (): string =>
  Constants.nativeAppVersion || Constants.expoConfig?.version || "0.0.0";

export type VerseDateMode = "local" | "kst";

export function verseDateMode(): VerseDateMode {
  if (Platform.OS !== "ios") return "local";
  return compareVersions(nativeVersion(), IOS_LOCAL_DATE_SINCE) >= 0 ? "local" : "kst";
}

/** 기기 현지 날짜(YYYY-MM-DD). */
export function localToday(now: Date = new Date()): string {
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

/** 한국 날짜(YYYY-MM-DD). 한국은 DST 가 없어 고정 오프셋으로 충분하다. */
export function kstToday(now: Date = new Date()): string {
  return new Date(now.getTime() + 9 * 60 * 60 * 1000).toISOString().slice(0, 10);
}

/** 이 기기의 오늘의 말씀 날짜 — 서버 `/daily-verse?date=` 에 그대로 보낸다. */
export function verseToday(now: Date = new Date()): string {
  return verseDateMode() === "local" ? localToday(now) : kstToday(now);
}
