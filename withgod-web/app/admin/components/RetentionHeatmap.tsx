"use client";

import type { Retention } from "@/lib/analytics";

import { formatNumber } from "./chartPrimitives";

/**
 * 코호트 리텐션.
 *
 * 값의 크기를 읽는 격자라 색은 순차 램프(한 색, 진할수록 높음)를 쓴다.
 * 아직 도래하지 않은 칸은 0%가 아니라 '—' 다 — 0%로 칠하면 없는 이탈이
 * 있는 것처럼 보인다.
 */

const RAMP_STEPS = 6;

/**
 * 비율 → 램프 단계. 0은 별도 단계(표면에 가까운 색)로 둔다.
 *
 * 글자색은 밝기로 계산하지 않고 단계마다 짝지어 둔 토큰을 쓴다. 램프 방향이
 * 라이트/다크에서 반대라, 비율만 보고 흰색/검은색을 고르면 한쪽 모드에서
 * 반드시 대비가 무너진다.
 */
const cellStep = (rate: number): number =>
  rate <= 0 ? 0 : Math.min(RAMP_STEPS, Math.floor(rate * RAMP_STEPS) + 1);

export function RetentionHeatmap({ data }: { data: Retention }) {
  const rows = [...data.rows].reverse(); // 최근 코호트를 위로

  return (
    // 코호트가 쌓일수록 표가 길어져 페이지를 다 차지한다 — 카드 안에서만 스크롤한다.
    <div className="max-h-[420px] overflow-auto">
      <table className="w-full min-w-[420px] border-separate border-spacing-0.5 text-xs">
        <caption className="sr-only">
          가입일 기준 코호트별 N일차 재방문율
        </caption>
        <thead>
          <tr className="text-[var(--text-secondary)]">
            <th scope="col" className="px-2 py-1 text-left font-medium">
              가입일
            </th>
            <th scope="col" className="px-2 py-1 text-right font-medium">
              인원
            </th>
            {data.day_ns.map((dayN) => (
              <th key={dayN} scope="col" className="px-2 py-1 text-center font-medium">
                {dayN}일
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.cohort_day}>
              <th
                scope="row"
                className="whitespace-nowrap px-2 py-1 text-left font-normal text-[var(--text-secondary)]"
              >
                {row.cohort_day.slice(5)}
              </th>
              <td className="px-2 py-1 text-right tabular-nums text-[var(--text-secondary)]">
                {formatNumber(row.size)}
              </td>

              {row.cells.map((cell) => (
                <td
                  key={cell.day_n}
                  className="px-2 py-1 text-center tabular-nums"
                  style={
                    cell.rate === null
                      ? undefined
                      : {
                          background: `var(--seq-${cellStep(cell.rate)})`,
                          color: `var(--seq-${cellStep(cell.rate)}-ink)`,
                        }
                  }
                  title={
                    cell.rate === null
                      ? "아직 집계 기간이 지나지 않았습니다"
                      : `${row.cohort_day} 가입 ${formatNumber(row.size)}명 중 ${formatNumber(cell.retained ?? 0)}명 재방문`
                  }
                >
                  {cell.rate === null ? (
                    <span className="text-[var(--text-muted)]">—</span>
                  ) : (
                    `${Math.round(cell.rate * 100)}%`
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
