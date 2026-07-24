import { NextResponse } from "next/server";

/**
 * 앱 버전 설정 프록시 (GET 조회 / POST 갱신).
 *
 * 관리 키(X-API-Key)를 브라우저에 노출하지 않기 위해 서버에서만 붙인다.
 * 이 경로는 미들웨어의 세션 쿠키 검사로 보호된다.
 */

const BACKEND_ORIGIN = process.env.ANALYTICS_API_ORIGIN ?? "https://mincha.co.kr";

export async function GET() {
  try {
    const upstream = await fetch(`${BACKEND_ORIGIN}/app-version`, {
      cache: "no-store",
    });
    const body = await upstream.text();
    return new NextResponse(body, {
      status: upstream.status,
      headers: { "content-type": "application/json" },
    });
  } catch {
    return NextResponse.json({ error: "upstream_unreachable" }, { status: 502 });
  }
}

export async function POST(request: Request) {
  const apiKey = process.env.ANALYTICS_ADMIN_API_KEY;
  if (!apiKey) {
    return NextResponse.json(
      { error: "ANALYTICS_ADMIN_API_KEY is not configured" },
      { status: 500 },
    );
  }

  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ error: "invalid_body" }, { status: 400 });
  }

  try {
    const upstream = await fetch(`${BACKEND_ORIGIN}/admin/app-version`, {
      method: "POST",
      headers: { "X-API-Key": apiKey, "content-type": "application/json" },
      body: JSON.stringify(payload),
      cache: "no-store",
    });
    const body = await upstream.text();
    return new NextResponse(body, {
      status: upstream.status,
      headers: { "content-type": "application/json" },
    });
  } catch {
    return NextResponse.json({ error: "upstream_unreachable" }, { status: 502 });
  }
}
