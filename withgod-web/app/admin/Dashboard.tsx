"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  UnauthorizedError,
  fetchBreakdown,
  fetchEvents,
  fetchOverview,
  fetchRetention,
  fetchTimeseries,
  type Breakdown,
  type DailyPoint,
  type EventCount,
  type Overview,
  type Retention,
} from "@/lib/analytics";

import { ActiveUsersChart } from "./components/ActiveUsersChart";
import { AppVersionControl } from "./components/AppVersionControl";
import { LanguageControl } from "./components/LanguageControl";
import { BreakdownList } from "./components/BreakdownList";
import { ChartCard } from "./components/ChartCard";
import { EventTable } from "./components/EventTable";
import { ReachChart } from "./components/ReachChart";
import { RetentionHeatmap } from "./components/RetentionHeatmap";
import { StatTile } from "./components/StatTile";

const RANGES = [7, 30, 90] as const;
type Range = (typeof RANGES)[number];

interface DashboardData {
  overview: Overview;
  series: DailyPoint[];
  retention: Retention;
  events: EventCount[];
  breakdown: Breakdown;
}

// 국가 코드(ISO 3166-1 alpha-2) → "🇰🇷 대한민국". 이름은 브라우저 로케일
// 데이터에 맡긴다 — 국가 이름 표를 우리가 들고 있을 이유가 없다.
const REGION_NAMES =
  typeof Intl !== "undefined" && "DisplayNames" in Intl
    ? new Intl.DisplayNames(["ko"], { type: "region" })
    : null;

const countryLabel = (code: string): string => {
  if (!/^[A-Z]{2}$/.test(code)) return "🌐 알 수 없음";
  const flag = String.fromCodePoint(
    ...[...code].map((ch) => 0x1f1a5 + ch.charCodeAt(0)),
  );
  let name = code;
  try {
    name = REGION_NAMES?.of(code) ?? code;
  } catch {
    // 로케일 데이터에 없는 코드는 코드 그대로 보여준다.
  }
  return `${flag} ${name}`;
};

const formatUpdatedAt = (iso: string | null): string => {
  if (!iso) return "아직 수집된 이벤트가 없습니다";
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return "알 수 없음";
  return `마지막 수집 ${parsed.toLocaleString("ko-KR", { timeZone: "Asia/Seoul" })}`;
};

export function Dashboard() {
  const router = useRouter();
  const [range, setRange] = useState<Range>(30);
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(
    async (days: Range) => {
      setLoading(true);
      setError("");
      try {
        const [overview, timeseries, retention, events, breakdown] =
          await Promise.all([
            fetchOverview(),
            fetchTimeseries(days),
            // 30일차 칸이 채워지려면 코호트가 그만큼 더 오래돼야 한다.
            // 조회 기간만큼만 가져오면 마지막 열이 항상 비어 고장난 것처럼 보인다.
            fetchRetention(Math.min(90, days + 31)),
            fetchEvents(days),
            fetchBreakdown(days),
          ]);
        setData({
          overview,
          series: timeseries.series,
          retention,
          events: events.events,
          breakdown,
        });
      } catch (caught) {
        if (caught instanceof UnauthorizedError) {
          router.replace("/admin/login");
          return;
        }
        setError(
          caught instanceof Error ? caught.message : "지표를 불러오지 못했습니다.",
        );
      } finally {
        setLoading(false);
      }
    },
    [router],
  );

  useEffect(() => {
    void load(range);
  }, [load, range]);

  const handleLogout = async () => {
    await fetch("/api/admin/logout", { method: "POST" });
    router.replace("/admin/login");
    router.refresh();
  };

  return (
    <div className="viz-root min-h-screen bg-[var(--surface-2)] text-[var(--text-primary)]">
      <header className="border-b border-[var(--border-1)] bg-[var(--surface-1)]">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-4">
          <div>
            <h1 className="text-base font-semibold">WithGod 지표</h1>
            <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
              {data ? formatUpdatedAt(data.overview.last_event_at) : "불러오는 중..."}
              {" · 날짜 기준 Asia/Seoul"}
            </p>
          </div>

          {/* 필터는 차트 위 한 줄에 모아둔다 */}
          <div className="flex items-center gap-2">
            <div
              className="flex rounded-lg border border-[var(--border-1)] p-0.5"
              role="group"
              aria-label="조회 기간"
            >
              {RANGES.map((days) => (
                <button
                  key={days}
                  type="button"
                  onClick={() => setRange(days)}
                  aria-pressed={range === days}
                  className={`rounded-md px-3 py-1 text-xs font-medium ${
                    range === days
                      ? "bg-[var(--text-primary)] text-[var(--surface-1)]"
                      : "text-[var(--text-secondary)]"
                  }`}
                >
                  {days}일
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={handleLogout}
              className="rounded-lg border border-[var(--border-1)] px-3 py-1.5 text-xs text-[var(--text-secondary)]"
            >
              로그아웃
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-6">
        {error && (
          <div className="mb-6 rounded-lg border border-[var(--border-1)] bg-[var(--surface-1)] p-4 text-sm">
            <p className="text-[var(--text-primary)]">{error}</p>
            <button
              type="button"
              onClick={() => void load(range)}
              className="mt-2 text-xs underline"
            >
              다시 시도
            </button>
          </div>
        )}

        {loading && !data ? (
          <p className="py-20 text-center text-sm text-[var(--text-secondary)]">
            불러오는 중...
          </p>
        ) : data ? (
          <div className="space-y-6">
            <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <StatTile
                label="오늘 방문자 (DAU)"
                value={data.overview.dau}
                previous={data.overview.dau_prev}
                hero
              />
              <StatTile
                label="오늘 신규"
                value={data.overview.new_users}
                previous={data.overview.new_users_prev}
              />
              <StatTile label="주간 활성 (WAU)" value={data.overview.wau} />
              <StatTile label="월간 활성 (MAU)" value={data.overview.mau} />
              <StatTile
                label="총 사용자"
                value={data.overview.total_users}
                hint="기기 기준 · 재설치하면 새 사용자로 잡힙니다"
              />
              <StatTile label="오늘 재방문" value={data.overview.returning_users} />
              <StatTile
                label="고착도 (DAU/MAU)"
                value={`${Math.round(data.overview.stickiness * 100)}`}
                suffix="%"
                hint="월간 사용자가 얼마나 자주 오는지"
              />
              <StatTile
                label="오늘 이벤트"
                value={data.overview.events}
                hint={`세션 ${data.overview.sessions}회`}
              />
            </section>

            <ChartCard
              title="일별 활성 사용자"
              subtitle="신규 + 재방문 = 그날의 DAU"
              legend={[
                { label: "재방문", color: "var(--series-1)" },
                { label: "신규", color: "var(--series-2)" },
              ]}
            >
              <ActiveUsersChart data={data.series} />
            </ChartCard>

            <ChartCard
              title="주간 · 월간 활성 사용자"
              subtitle="각 날짜 기준 최근 7일 / 30일 동안의 순 사용자 수"
              legend={[
                { label: "주간(WAU)", color: "var(--series-1)" },
                { label: "월간(MAU)", color: "var(--series-2)" },
              ]}
            >
              <ReachChart data={data.series} />
            </ChartCard>

            <ChartCard
              title="리텐션"
              subtitle="첫 방문일 기준, N일 뒤에 다시 온 비율 (진할수록 높음)"
            >
              <RetentionHeatmap data={data.retention} />
            </ChartCard>

            <div className="grid gap-6 lg:grid-cols-2">
              <ChartCard title="이벤트" subtitle={`최근 ${range}일 발생 건수`}>
                <EventTable events={data.events} />
              </ChartCard>

              <ChartCard title="사용 환경" subtitle={`최근 ${range}일 활동 사용자`}>
                <div className="grid gap-6 sm:grid-cols-2">
                  <BreakdownList
                    title="플랫폼"
                    items={data.breakdown.platforms}
                  />
                  <BreakdownList
                    title="앱 버전"
                    items={data.breakdown.app_versions}
                  />
                  <BreakdownList
                    title="국가 (타임존 추정)"
                    items={(data.breakdown.countries ?? []).map((item) => ({
                      key: countryLabel(item.key),
                      users: item.users,
                    }))}
                  />
                </div>
              </ChartCard>
            </div>

            <AppVersionControl />

            <LanguageControl />
          </div>
        ) : null}
      </main>
    </div>
  );
}
