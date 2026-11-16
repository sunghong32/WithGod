"use client";

import type { LinkClicks as LinkClicksData } from "@/lib/analytics";

import { formatNumber } from "./chartPrimitives";

// 자주 쓰는 src 값의 이름. 없는 값은 src 그대로 보여 준다.
const SOURCE_LABELS: Record<string, string> = {
  instagram: "인스타 프로필 (/ig)",
  "ig-dm": "인스타 DM",
  direct: "src 없음",
};

const PLATFORM_LABELS: Record<string, string> = {
  ios: "iPhone",
  android: "Android",
  other: "PC·iPad·기타",
};

const sourceLabel = (source: string): string => SOURCE_LABELS[source] ?? source;

const formatAt = (iso: string): string => {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return iso;
  return parsed.toLocaleString("ko-KR", {
    timeZone: "Asia/Seoul",
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
};

/**
 * 앱 받기 링크(/get?src=…) 클릭.
 *
 * 스토어 통계는 늦고 작은 숫자를 숨겨서, 링크를 눌렀는지는 여기서 본다.
 * 설치까지 했는지는 알 수 없다 — 스토어로 넘어간 뒤의 일이다.
 */
export function LinkClicks({ data }: { data: LinkClicksData | null }) {
  if (!data) {
    return (
      <p className="py-6 text-center text-xs text-[var(--text-muted)]">
        백엔드가 아직 링크 클릭 집계를 지원하지 않습니다.
      </p>
    );
  }
  if (data.sources.length === 0) {
    return (
      <p className="py-6 text-center text-xs text-[var(--text-muted)]">
        이 기간에 링크를 누른 사람이 없습니다.
      </p>
    );
  }

  const max = Math.max(...data.sources.map((item) => item.clicks));

  return (
    <div className="space-y-6">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-[var(--text-secondary)]">
            <th scope="col" className="py-1 text-left font-medium">
              출처
            </th>
            <th scope="col" className="whitespace-nowrap py-1 pl-2 text-right font-medium">
              클릭
            </th>
            <th scope="col" className="whitespace-nowrap py-1 pl-2 text-right font-medium">
              방문자
            </th>
            <th scope="col" className="whitespace-nowrap py-1 pl-3 text-right font-medium">
              iPhone·Android·기타
            </th>
          </tr>
        </thead>
        <tbody>
          {data.sources.map((item) => (
            <tr key={item.source}>
              <td className="py-1.5 pr-3">
                <span className="text-[var(--text-primary)]">
                  {sourceLabel(item.source)}
                </span>
                <span className="ml-1.5 text-[var(--text-muted)]">{item.source}</span>
                <span
                  aria-hidden
                  className="mt-1 block h-1.5 rounded-full bg-[var(--series-1)]"
                  style={{ width: `${Math.max(2, (item.clicks / max) * 100)}%` }}
                />
              </td>
              <td className="py-1.5 text-right align-top tabular-nums text-[var(--text-primary)]">
                {formatNumber(item.clicks)}
              </td>
              <td className="py-1.5 text-right align-top tabular-nums text-[var(--text-secondary)]">
                {formatNumber(item.visitors)}
              </td>
              <td className="whitespace-nowrap py-1.5 pl-3 text-right align-top tabular-nums text-[var(--text-secondary)]">
                {item.ios} · {item.android} · {item.other}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div>
        <h3 className="text-xs font-medium text-[var(--text-secondary)]">최근 클릭</h3>
        <ul className="mt-2 divide-y divide-[var(--border-1)] text-xs">
          {data.recent.map((click, index) => (
            <li
              key={`${click.at}-${index}`}
              className="flex items-baseline justify-between gap-3 py-1.5"
            >
              <span className="tabular-nums text-[var(--text-secondary)]">
                {formatAt(click.at)}
              </span>
              <span className="text-[var(--text-primary)]">
                {sourceLabel(click.source)}
                <span className="ml-1.5 text-[var(--text-muted)]">
                  {PLATFORM_LABELS[click.platform] ?? click.platform}
                </span>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
