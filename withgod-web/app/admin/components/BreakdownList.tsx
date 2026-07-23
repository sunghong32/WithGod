"use client";

import { formatNumber } from "./chartPrimitives";

interface BreakdownListProps {
  title: string;
  items: { key: string; users: number }[];
}

/** 플랫폼·앱 버전 분포. 항목이 적고 값이 중요해 막대+숫자 목록으로 둔다. */
export function BreakdownList({ title, items }: BreakdownListProps) {
  const total = items.reduce((sum, item) => sum + item.users, 0);

  return (
    <div>
      <h3 className="text-xs font-medium text-[var(--text-secondary)]">{title}</h3>
      {items.length === 0 ? (
        <p className="mt-3 text-xs text-[var(--text-muted)]">데이터 없음</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {items.map((item) => (
            <li key={item.key} className="text-xs">
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-[var(--text-primary)]">{item.key}</span>
                <span className="tabular-nums text-[var(--text-secondary)]">
                  {formatNumber(item.users)}명
                  {total > 0 && ` · ${Math.round((item.users / total) * 100)}%`}
                </span>
              </div>
              <span
                aria-hidden
                className="mt-1 block h-1.5 rounded-full bg-[var(--series-1)]"
                style={{
                  width: total > 0 ? `${Math.max(2, (item.users / total) * 100)}%` : "2%",
                }}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
