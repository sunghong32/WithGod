const numberFormat = new Intl.NumberFormat("ko-KR");

interface StatTileProps {
  label: string;
  value: number | string;
  /** 직전 기간 값. 주면 변화량을 함께 보여준다. */
  previous?: number;
  suffix?: string;
  hint?: string;
  /** 대시보드가 이끄는 대표 숫자 하나만 true. */
  hero?: boolean;
}

const formatValue = (value: number | string): string =>
  typeof value === "number" ? numberFormat.format(value) : value;

export function StatTile({
  label,
  value,
  previous,
  suffix,
  hint,
  hero = false,
}: StatTileProps) {
  const delta =
    typeof value === "number" && previous !== undefined ? value - previous : null;

  return (
    <div className="rounded-xl border border-[var(--border-1)] bg-[var(--surface-1)] p-4">
      <p className="text-xs font-medium text-[var(--text-secondary)]">{label}</p>
      <p
        className={`mt-2 font-semibold tabular-nums text-[var(--text-primary)] ${
          hero ? "text-5xl" : "text-3xl"
        }`}
      >
        {formatValue(value)}
        {suffix && (
          <span className="ml-1 text-base font-normal text-[var(--text-secondary)]">
            {suffix}
          </span>
        )}
      </p>

      {delta !== null && (
        // 색만으로 방향을 알리지 않도록 화살표 기호를 함께 쓴다.
        <p className="mt-1 text-xs tabular-nums text-[var(--text-secondary)]">
          {delta === 0
            ? "어제와 같음"
            : `어제 대비 ${delta > 0 ? "▲" : "▼"} ${numberFormat.format(Math.abs(delta))}`}
        </p>
      )}
      {hint && <p className="mt-1 text-xs text-[var(--text-muted)]">{hint}</p>}
    </div>
  );
}
