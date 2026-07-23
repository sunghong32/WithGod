"use client";

import type { EventCount } from "@/lib/analytics";

import { formatNumber } from "./chartPrimitives";

/**
 * 이벤트별 발생량.
 *
 * 계열이 하나(발생 건수)라 범례가 없다 — 제목이 무엇을 재는지 말해준다.
 * 막대는 크기를 읽는 보조 장치이고 정확한 값은 옆의 숫자가 담당한다.
 */
export function EventTable({ events }: { events: EventCount[] }) {
  if (events.length === 0) {
    return (
      <p className="py-6 text-center text-xs text-[var(--text-muted)]">
        아직 수집된 이벤트가 없습니다.
      </p>
    );
  }

  const max = Math.max(...events.map((item) => item.total));

  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="text-[var(--text-secondary)]">
          <th scope="col" className="py-1 text-left font-medium">
            이벤트
          </th>
          <th scope="col" className="py-1 text-right font-medium">
            발생
          </th>
          <th scope="col" className="py-1 text-right font-medium">
            사용자
          </th>
        </tr>
      </thead>
      <tbody>
        {events.map((item) => (
          <tr key={item.name}>
            <td className="py-1.5 pr-3">
              <span className="text-[var(--text-primary)]">{item.name}</span>
              <span
                aria-hidden
                className="mt-1 block h-1.5 rounded-full bg-[var(--series-1)]"
                style={{ width: `${Math.max(2, (item.total / max) * 100)}%` }}
              />
            </td>
            <td className="py-1.5 text-right align-top tabular-nums text-[var(--text-primary)]">
              {formatNumber(item.total)}
            </td>
            <td className="py-1.5 text-right align-top tabular-nums text-[var(--text-secondary)]">
              {formatNumber(item.users)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
