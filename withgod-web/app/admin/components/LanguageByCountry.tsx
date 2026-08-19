"use client";

import type { LanguageBreakdown } from "@/lib/analytics";

interface LanguageByCountryProps {
  data: LanguageBreakdown | null;
  label: (code: string) => string;
}

const LANG_NAMES: Record<string, string> = {
  ko: "한국어",
  en: "English",
  es: "Español",
  pt: "Português",
  de: "Deutsch",
  fr: "Français",
  it: "Italiano",
  pl: "Polski",
};

/**
 * 국가별 앱 언어 설정.
 *
 * 지표(events)에는 언어를 수집하지 않는다 — 개인정보 최소 수집 원칙이다.
 * 대신 푸시 등록 기기에 저장된 발송 언어를 집계하므로, **알림을 켠 사용자만**
 * 잡힌다. 새 언어를 추가할지 판단할 때 이 표를 근거로 쓴다.
 */
export function LanguageByCountry({ data, label }: LanguageByCountryProps) {
  const rows = data?.countries ?? [];

  return (
    <div>
      <h3 className="text-xs font-medium text-[var(--text-secondary)]">
        국가별 앱 언어 설정
        {data?.days ? (
          <span className="ml-1 font-normal text-[var(--text-muted)]">
            (최근 {data.days}일 활동)
          </span>
        ) : null}
      </h3>
      {rows.length === 0 ? (
        <p className="mt-3 text-xs text-[var(--text-muted)]">
          {data?.note ?? "데이터 없음"}
        </p>
      ) : (
        <ul className="mt-3 space-y-2">
          {rows.slice(0, 12).map((row) => (
            <li key={row.key} className="text-xs">
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-[var(--text-primary)]">{label(row.key)}</span>
                <span className="tabular-nums text-[var(--text-secondary)]">
                  {row.devices}대
                </span>
              </div>
              <div className="mt-0.5 text-[11px] text-[var(--text-muted)]">
                {row.languages
                  .map((l) => `${LANG_NAMES[l.key] ?? l.key} ${l.devices}`)
                  .join(" · ")}
              </div>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 text-[11px] leading-relaxed text-[var(--text-muted)]">
        지표에는 언어를 수집하지 않아(개인정보 최소 수집){" "}
        <strong>알림을 켠 기기</strong>만 집계된다. 왼쪽 국가 분포와 같은 기간·같은
        사용자를 세도록 맞췄다
        {typeof data?.inactive_devices === "number" && data.inactive_devices > 0 ? (
          <> — 그 기간에 앱을 열지 않은 등록 기기 {data.inactive_devices}대는 제외했다</>
        ) : null}
        . 그래도 알림을 끈 사용자는 잡히지 않으므로 국가별 사용자 수보다 적을 수 있다.
      </p>
    </div>
  );
}
