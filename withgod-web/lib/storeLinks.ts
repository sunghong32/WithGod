/**
 * 앱 받기 링크(/get)용 스토어 주소와 기기 판별.
 *
 * 스토어 주소는 backend/app_version.py 의 ios_url·android_url 과 같은 앱이다.
 * 인스타 프로필 링크처럼 한 링크로 iOS·Android 를 모두 받아야 하는 곳에 쓴다.
 */

export const APP_STORE_ID = "6757704775";
export const ANDROID_PACKAGE = "kr.co.mincha.withgod";

/**
 * App Store Connect 캠페인 링크의 provider token(pt).
 * 앱 분석 → 유입 경로 → 캠페인 → + 로 만든 링크의 `pt=` 값이다. 공개 링크에
 * 그대로 실리는 값이라 비밀이 아니다. 비우면 캠페인 파라미터 없이 보낸다
 * (앱 분석에서 유입 경로별 집계만 빠지고 링크는 정상 동작한다).
 */
const APP_STORE_PROVIDER_TOKEN = "128437792";

export type Platform = "ios" | "android" | "other";

/**
 * User-Agent 로 기기를 가른다. 인스타·페이스북 인앱 브라우저도 기기 문자열은
 * 그대로 실어 보내서 이것으로 충분하다. iPadOS 13+ 사파리는 Mac 으로 보이므로
 * "other" 로 떨어지고, 안내 페이지의 클라이언트 쪽 검사가 다시 보낸다.
 */
export function detectPlatform(userAgent: string): Platform {
  if (/iPhone|iPad|iPod/i.test(userAgent)) return "ios";
  if (/Android/i.test(userAgent)) return "android";
  return "other";
}

/**
 * `?src=` 값을 유입 경로 이름으로 정리한다. 스토어 파라미터에 그대로 실리므로
 * 소문자·숫자·`_`·`-` 32자까지만 받고, 그 밖에는 "direct" 로 본다.
 */
export function normalizeSource(raw: string | string[] | undefined): string {
  const value = (Array.isArray(raw) ? raw[0] : raw)?.trim().toLowerCase() ?? "";
  return /^[a-z0-9_-]{1,32}$/.test(value) ? value : "direct";
}

export function appStoreUrl(source: string): string {
  // App Store Connect 가 만들어 주는 캠페인 링크와 같은 꼴(`/app/apple-store/id…`).
  const url = new URL(`https://apps.apple.com/app/apple-store/id${APP_STORE_ID}`);
  if (APP_STORE_PROVIDER_TOKEN) {
    url.searchParams.set("pt", APP_STORE_PROVIDER_TOKEN);
    url.searchParams.set("ct", source);
    url.searchParams.set("mt", "8");
  }
  return url.toString();
}

/** Play 는 referrer 의 UTM 값을 Play Console 획득 보고서에 유입 경로로 보여 준다. */
export function playStoreUrl(source: string): string {
  const url = new URL("https://play.google.com/store/apps/details");
  url.searchParams.set("id", ANDROID_PACKAGE);
  url.searchParams.set(
    "referrer",
    `utm_source=${source}&utm_medium=referral&utm_campaign=get`,
  );
  return url.toString();
}
