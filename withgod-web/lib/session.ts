/**
 * 어드민 세션 쿠키.
 *
 * 사용자가 한 명뿐이라 사용자 테이블을 두지 않는다. 환경변수의 비밀번호를
 * 확인한 뒤, 만료시각에 HMAC 서명을 붙인 값을 httpOnly 쿠키로 내려준다.
 * 미들웨어(Edge 런타임)에서도 검증해야 하므로 node:crypto 대신 Web Crypto 만
 * 쓴다.
 */

export const SESSION_COOKIE = "withgod_admin";
export const SESSION_TTL_SECONDS = 60 * 60 * 12;

const encoder = new TextEncoder();

const getSecret = (): string => {
  const secret = process.env.ADMIN_SESSION_SECRET;
  if (!secret) {
    throw new Error("ADMIN_SESSION_SECRET is not set");
  }
  return secret;
};

const toHex = (buffer: ArrayBuffer): string =>
  Array.from(new Uint8Array(buffer))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");

const sign = async (payload: string): Promise<string> => {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(getSecret()),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  return toHex(await crypto.subtle.sign("HMAC", key, encoder.encode(payload)));
};

/** 길이·내용이 달라도 비교 시간이 같도록 — 타이밍 공격 방지. */
export const timingSafeEqual = (a: string, b: string): boolean => {
  const left = encoder.encode(a);
  const right = encoder.encode(b);
  // 길이가 다르면 즉시 false 지만, 그래도 같은 만큼 순회해 시간차를 줄인다.
  let mismatch = left.length === right.length ? 0 : 1;
  const length = Math.max(left.length, right.length);
  for (let i = 0; i < length; i += 1) {
    mismatch |= (left[i] ?? 0) ^ (right[i] ?? 0);
  }
  return mismatch === 0;
};

export const createSessionToken = async (now: number = Date.now()): Promise<string> => {
  const expiresAt = Math.floor(now / 1000) + SESSION_TTL_SECONDS;
  const payload = String(expiresAt);
  return `${payload}.${await sign(payload)}`;
};

export const verifySessionToken = async (
  token: string | undefined,
  now: number = Date.now(),
): Promise<boolean> => {
  if (!token) return false;
  const separator = token.lastIndexOf(".");
  if (separator <= 0) return false;

  const payload = token.slice(0, separator);
  const signature = token.slice(separator + 1);

  const expiresAt = Number(payload);
  if (!Number.isFinite(expiresAt) || expiresAt * 1000 <= now) return false;

  return timingSafeEqual(signature, await sign(payload));
};

export const verifyPassword = (input: string): boolean => {
  const expected = process.env.ADMIN_PASSWORD;
  // 비밀번호가 설정되지 않았으면 잠긴 상태로 둔다(빈 문자열로 뚫리면 안 된다).
  if (!expected) return false;
  return timingSafeEqual(input, expected);
};
