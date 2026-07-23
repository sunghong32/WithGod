import { NextResponse } from "next/server";

/**
 * 백엔드 분석 API 프록시.
 *
 * 관리 키(X-API-Key)를 브라우저에 내려보내지 않기 위해 서버에서만 붙인다.
 * 이 경로 자체는 미들웨어의 세션 쿠키 검사로 보호된다.
 */

const BACKEND_ORIGIN = process.env.ANALYTICS_API_ORIGIN ?? "https://mincha.co.kr";

// 임의 경로가 백엔드로 전달되지 않도록 허용 목록으로 제한한다.
const ALLOWED_METRICS = new Set([
  "overview",
  "timeseries",
  "retention",
  "events",
  "breakdown",
]);

const ALLOWED_PARAMS = new Set(["days", "cohorts"]);

export async function GET(
  request: Request,
  context: { params: Promise<{ metric: string }> },
) {
  const { metric } = await context.params;
  if (!ALLOWED_METRICS.has(metric)) {
    return NextResponse.json({ error: "unknown_metric" }, { status: 404 });
  }

  const apiKey = process.env.ANALYTICS_ADMIN_API_KEY;
  if (!apiKey) {
    return NextResponse.json(
      { error: "ANALYTICS_ADMIN_API_KEY is not configured" },
      { status: 500 },
    );
  }

  const incoming = new URL(request.url).searchParams;
  const target = new URL(`${BACKEND_ORIGIN}/admin/analytics/${metric}`);
  for (const [key, value] of incoming) {
    if (ALLOWED_PARAMS.has(key)) target.searchParams.set(key, value);
  }

  try {
    const upstream = await fetch(target, {
      headers: { "X-API-Key": apiKey },
      cache: "no-store",
    });
    const body = await upstream.text();
    return new NextResponse(body, {
      status: upstream.status,
      headers: { "content-type": "application/json" },
    });
  } catch {
    // 백엔드가 내려간 것과 인증 실패를 화면에서 구분할 수 있게 502 로 돌려준다.
    return NextResponse.json({ error: "upstream_unreachable" }, { status: 502 });
  }
}
