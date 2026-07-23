import { NextResponse, type NextRequest } from "next/server";

import { SESSION_COOKIE, verifySessionToken } from "@/lib/session";

/**
 * /admin 과 /api/admin 을 세션 쿠키로 잠근다.
 *
 * 백엔드 API 키는 서버 라우트 핸들러에만 있고 브라우저로 내려가지 않는다.
 * 여기서 막는 것은 대시보드 화면과 그 프록시 경로다.
 */
/** 어드민 경로는 어떤 경우에도 검색엔진에 올라가면 안 된다. */
const noIndex = (response: NextResponse): NextResponse => {
  response.headers.set("X-Robots-Tag", "noindex, nofollow, noarchive");
  return response;
};

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const isLoginPage = pathname === "/admin/login";
  const isLoginApi = pathname === "/api/admin/login";
  if (isLoginPage || isLoginApi) return noIndex(NextResponse.next());

  const token = request.cookies.get(SESSION_COOKIE)?.value;
  if (await verifySessionToken(token)) return noIndex(NextResponse.next());

  // API 는 리다이렉트 대신 401 — 대시보드의 fetch 가 로그인 HTML 을 받으면
  // 파싱에 실패해 원인을 알기 어려워진다.
  if (pathname.startsWith("/api/")) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const loginUrl = new URL("/admin/login", request.url);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ["/admin/:path*", "/api/admin/:path*"],
};
