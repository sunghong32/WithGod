import { createHmac } from "node:crypto";

import type { Platform } from "./storeLinks";

/**
 * 앱 받기 링크(/get) 클릭을 백엔드 분석 DB 에 남긴다.
 *
 * 스토어 쪽 유입 집계는 하루 넘게 늦고 숫자가 작으면 보여 주지 않아, DM 한 통에
 * 붙인 링크를 눌렀는지 같은 작은 신호는 이걸로 본다(어드민 「앱 받기 링크」 카드).
 *
 * - 관리 키를 붙여 서버에서만 보낸다. 브라우저가 부르는 공개 수집 경로가 아니다.
 * - IP 는 보내지 않는다. IP·User-Agent·KST 날짜를 관리 키로 HMAC 한 하루짜리
 *   방문자 값만 보내, 같은 사람이 같은 날 여러 번 눌러도 방문자는 한 번으로 센다.
 * - 링크 미리보기 봇(인스타 DM 의 facebookexternalhit 등)은 세지 않는다. 링크를
 *   보내기만 해도 미리보기가 한 번 열린다.
 * - 실패해도 리다이렉트에는 영향이 없다(페이지가 `after()` 로 부른다).
 */

const BACKEND_ORIGIN = process.env.ANALYTICS_API_ORIGIN ?? "https://mincha.co.kr";

// 사람이 아닌 요청. 인앱 브라우저(Instagram·FBAN·KAKAOTALK 등)는 여기에 걸리지 않는다.
const BOT_UA =
  /bot\b|bot\/|crawl|spider|slurp|facebookexternalhit|facebookcatalog|meta-externalagent|embedly|kakaotalk-scrap|whatsapp|skypeuripreview|vkshare|bitlybot|preview|headless|lighthouse|curl\/|wget\/|python-|go-http-client|okhttp\/|java\/|node-fetch|axios\//i;

export const isBot = (userAgent: string): boolean =>
  userAgent.trim() === "" || BOT_UA.test(userAgent);

/** 프록시 뒤의 실제 클라이언트 IP(Vercel 은 x-forwarded-for 첫 값). */
export const clientIp = (headerList: Headers): string =>
  headerList.get("x-forwarded-for")?.split(",")[0]?.trim() ||
  headerList.get("x-real-ip")?.trim() ||
  "";

const kstDay = (moment: Date): string =>
  // en-CA 는 YYYY-MM-DD 로 찍힌다.
  new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(moment);

export const visitorHash = (
  secret: string,
  ip: string,
  userAgent: string,
  moment: Date = new Date(),
): string | null => {
  if (!ip) return null;
  return createHmac("sha256", secret)
    .update(`${kstDay(moment)}|${ip}|${userAgent}`)
    .digest("hex")
    .slice(0, 16);
};

interface LinkClick {
  source: string;
  platform: Platform;
  userAgent: string;
  ip: string;
}

export async function recordLinkClick({
  source,
  platform,
  userAgent,
  ip,
}: LinkClick): Promise<void> {
  if (isBot(userAgent)) return;
  const apiKey = process.env.ANALYTICS_ADMIN_API_KEY;
  if (!apiKey) return;

  try {
    const response = await fetch(`${BACKEND_ORIGIN}/admin/analytics/link-clicks`, {
      method: "POST",
      headers: { "X-API-Key": apiKey, "content-type": "application/json" },
      body: JSON.stringify({
        source,
        platform,
        visitor: visitorHash(apiKey, ip, userAgent),
      }),
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });
    if (!response.ok) {
      console.warn(`link click not recorded: ${response.status}`);
    }
  } catch (error) {
    console.warn("link click not recorded:", error);
  }
}
