"use client";

import { formatNumber } from "./chartPrimitives";

interface Row {
  key: string;
  users: number;
  home: number;
  mood: number;
  rate: number;
}

interface CountryFunnelProps {
  title: string;
  rows: Row[];
  label: (code: string) => string;
}

/**
 * 국가별 퍼널 — 앱을 연 사람 중 실제로 상담을 시작한 비율.
 *
 * "어느 나라 사용자가 들어왔다가 그냥 나가는가"를 보는 지표다. 전환율이 유독
 * 낮은 국가는 언어 장벽이나 네트워크 문제를 의심할 단서가 된다.
 */
export function CountryFunnel({ title, rows, label }: CountryFunnelProps) {
  if (rows.length === 0) {
    return (
      <div>
        <h3 className="text-xs font-medium text-[var(--text-secondary)]">{title}</h3>
        <p className="mt-3 text-xs text-[var(--text-muted)]">데이터 없음</p>
      </div>
    );
  }

  return (
    <div>
      <h3 className="text-xs font-medium text-[var(--text-secondary)]">{title}</h3>
      <table className="mt-3 w-full text-xs">
        <thead>
          <tr className="text-[var(--text-muted)]">
            <th className="pb-1 text-left font-normal">국가</th>
            <th className="pb-1 text-right font-normal">사용자</th>
            <th className="pb-1 text-right font-normal">홈 진입</th>
            <th className="pb-1 text-right font-normal">상담 시작</th>
            <th className="pb-1 text-right font-normal">전환율</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            // 사용자가 있는데 상담이 0이면 눈에 띄게 표시한다 — 조사 대상이다.
            const stuck = row.users >= 3 && row.mood === 0;
            return (
              <tr key={row.key} className="border-t border-[var(--border)]">
                <td className="py-1.5 text-[var(--text-primary)]">{label(row.key)}</td>
                <td className="py-1.5 text-right tabular-nums text-[var(--text-secondary)]">
                  {formatNumber(row.users)}
                </td>
                <td className="py-1.5 text-right tabular-nums text-[var(--text-secondary)]">
                  {formatNumber(row.home)}
                </td>
                <td className="py-1.5 text-right tabular-nums text-[var(--text-secondary)]">
                  {formatNumber(row.mood)}
                </td>
                <td
                  className={`py-1.5 text-right tabular-nums ${
                    stuck ? "font-semibold text-[var(--danger,#dc2626)]" : "text-[var(--text-primary)]"
                  }`}
                >
                  {row.rate}%
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="mt-2 text-[11px] leading-relaxed text-[var(--text-muted)]">
        전환율 = 상담 시작 ÷ 사용자. 사용자가 3명 이상인데 상담이 0건이면 빨갛게
        표시된다 — 언어 장벽이나 네트워크 문제를 의심해 볼 신호다.
      </p>
    </div>
  );
}
