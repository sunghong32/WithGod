import type { ReactNode } from "react";

interface ChartCardProps {
  title: string;
  subtitle?: string;
  /** 2개 이상 계열이면 범례는 항상 있어야 한다 — 색만으로 구분하게 두지 않는다. */
  legend?: { label: string; color: string }[];
  children: ReactNode;
}

export function ChartCard({ title, subtitle, legend, children }: ChartCardProps) {
  return (
    <section className="rounded-xl border border-[var(--border-1)] bg-[var(--surface-1)] p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">
            {title}
          </h2>
          {subtitle && (
            <p className="mt-1 text-xs text-[var(--text-secondary)]">{subtitle}</p>
          )}
        </div>

        {legend && legend.length > 0 && (
          <ul className="flex flex-wrap items-center gap-4">
            {legend.map((item) => (
              <li
                key={item.label}
                className="flex items-center gap-1.5 text-xs text-[var(--text-secondary)]"
              >
                <span
                  aria-hidden
                  className="inline-block h-2.5 w-2.5 rounded-sm"
                  style={{ background: item.color }}
                />
                {item.label}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="mt-4">{children}</div>
    </section>
  );
}
