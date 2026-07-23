import { NextResponse } from "next/server";

import {
  SESSION_COOKIE,
  SESSION_TTL_SECONDS,
  createSessionToken,
  verifyPassword,
} from "@/lib/session";

/** 로그인 무차별 대입을 늦추는 최소 지연(프로세스 로컬). */
const FAILURE_DELAY_MS = 700;

/**
 * IP 당 실패 횟수 제한.
 *
 * 서버리스라 인스턴스가 바뀌면 카운터가 초기화되므로 완전한 방어는 아니다.
 * 실제 방어선은 비밀번호 자체의 길이이고, 이건 한 인스턴스로 몰아치는
 * 시도를 끊는 용도다.
 */
const MAX_ATTEMPTS = 10;
const WINDOW_MS = 15 * 60 * 1000;
const attempts = new Map<string, number[]>();

const tooManyAttempts = (ip: string, now: number): boolean => {
  const recent = (attempts.get(ip) ?? []).filter((at) => now - at < WINDOW_MS);
  attempts.set(ip, recent);
  if (attempts.size > 1000) attempts.clear();
  return recent.length >= MAX_ATTEMPTS;
};

const recordFailure = (ip: string, now: number): void => {
  attempts.set(ip, [...(attempts.get(ip) ?? []), now]);
};

export async function POST(request: Request) {
  const now = Date.now();
  const ip =
    request.headers.get("x-forwarded-for")?.split(",")[0].trim() ?? "unknown";

  if (tooManyAttempts(ip, now)) {
    return NextResponse.json({ error: "too_many_attempts" }, { status: 429 });
  }

  let password = "";
  try {
    const body = (await request.json()) as { password?: unknown };
    password = typeof body.password === "string" ? body.password : "";
  } catch {
    password = "";
  }

  if (!verifyPassword(password)) {
    recordFailure(ip, now);
    await new Promise((resolve) => setTimeout(resolve, FAILURE_DELAY_MS));
    return NextResponse.json({ error: "invalid_password" }, { status: 401 });
  }

  // 성공하면 카운터를 비워 정상 사용자가 이전 오타에 발목 잡히지 않게 한다.
  attempts.delete(ip);
  const response = NextResponse.json({ ok: true });
  response.cookies.set({
    name: SESSION_COOKIE,
    value: await createSessionToken(),
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: SESSION_TTL_SECONDS,
  });
  return response;
}
