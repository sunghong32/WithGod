"use client";

const numberFormat = new Intl.NumberFormat("ko-KR");

export const formatNumber = (value: number): string => numberFormat.format(value);

/** "2026-07-23" → "7/23". 축이 좁아도 읽히도록 짧게 쓴다. */
export const formatDayShort = (day: string): string => {
  const [, month, date] = day.split("-");
  if (!month || !date) return day;
  return `${Number(month)}/${Number(date)}`;
};

export interface TooltipEntry {
  name?: string;
  value?: number;
  color?: string;
  dataKey?: string | number;
}

export interface ChartTooltipProps {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string | number;
  /** 합계를 함께 보여줄지(누적 막대에서 유용). */
  showTotal?: boolean;
}

export function ChartTooltip({
  active,
  payload,
  label,
  showTotal = false,
}: ChartTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;

  const total = payload.reduce((sum, entry) => sum + (entry.value ?? 0), 0);

  return (
    <div className="rounded-lg border border-[var(--border-1)] bg-[var(--surface-1)] px-3 py-2 text-xs shadow-sm">
      <p className="font-medium text-[var(--text-primary)]">{String(label)}</p>
      <ul className="mt-1.5 space-y-1">
        {payload.map((entry) => (
          <li
            key={String(entry.dataKey ?? entry.name)}
            className="flex items-center gap-2 text-[var(--text-secondary)]"
          >
            <span
              aria-hidden
              className="inline-block h-2 w-2 rounded-sm"
              style={{ background: entry.color }}
            />
            <span>{entry.name}</span>
            <span className="ml-auto tabular-nums text-[var(--text-primary)]">
              {formatNumber(entry.value ?? 0)}
            </span>
          </li>
        ))}
        {showTotal && payload.length > 1 && (
          <li className="flex items-center gap-2 border-t border-[var(--border-1)] pt-1 text-[var(--text-secondary)]">
            <span>합계</span>
            <span className="ml-auto tabular-nums text-[var(--text-primary)]">
              {formatNumber(total)}
            </span>
          </li>
        )}
      </ul>
    </div>
  );
}

/** 축·격자 공통 설정 — 데이터보다 뒤로 물러나 있어야 한다. */
export const axisProps = {
  stroke: "var(--text-muted)",
  tick: { fill: "var(--text-secondary)", fontSize: 11 },
  tickLine: false,
  axisLine: false,
} as const;
