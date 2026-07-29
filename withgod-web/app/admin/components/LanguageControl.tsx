"use client";

import { useEffect, useState } from "react";

import { ChartCard } from "./ChartCard";

/**
 * 서비스 언어 스위치.
 *
 * 언어를 켜면 앱/API 가 해당 언어의 성경 검색·구절 제공을 시작한다(이슈 #10).
 * 한국어는 기본 언어라 끌 수 없다. 서버에 해당 언어 데이터가 없으면 백엔드가
 * 저장을 거부한다(422).
 *
 * ⚠️ 켜기 전에 해당 언어의 AI 코멘트 품질(이슈 #11)까지 준비됐는지 확인할 것.
 */

interface LanguagesConfig {
  supported: string[];
  enabled: string[];
}

const LANGUAGE_LABELS: Record<string, string> = {
  ko: "한국어",
  en: "영어",
  es: "스페인어",
  pt: "포르투갈어",
  de: "독일어",
  fr: "프랑스어",
  it: "이탈리아어",
  pl: "폴란드어",
};

export function LanguageControl() {
  const [config, setConfig] = useState<LanguagesConfig | null>(null);
  const [enabled, setEnabled] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(
    null,
  );

  useEffect(() => {
    void fetch("/api/admin/languages", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((data: LanguagesConfig) => {
        // 백엔드 다운(502)·세션 만료(401) 등은 {error} JSON 이 온다 — 형태 검증
        // 없이 캐스팅하면 아래 배열 연산에서 카드가(경계가 없어 대시보드 전체가)
        // 죽는다.
        if (!Array.isArray(data.enabled) || !Array.isArray(data.supported)) {
          throw new Error("invalid_shape");
        }
        setConfig(data);
        setEnabled(data.enabled);
      })
      .catch(() => setMessage({ kind: "error", text: "현재 값을 불러오지 못했어요." }));
  }, []);

  const dirty =
    config !== null &&
    (enabled.length !== config.enabled.length ||
      enabled.some((l) => !config.enabled.includes(l)));

  const toggle = (lang: string) => {
    if (lang === "ko") return;
    setEnabled((prev) =>
      prev.includes(lang) ? prev.filter((l) => l !== lang) : [...prev, lang],
    );
  };

  const handleSave = async () => {
    setMessage(null);
    setSaving(true);
    try {
      const response = await fetch("/api/admin/languages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      });
      if (!response.ok) {
        const detail = (await response.json().catch(() => null)) as {
          detail?: string;
        } | null;
        setMessage({
          kind: "error",
          text:
            typeof detail?.detail === "string"
              ? detail.detail
              : `저장 실패 (${response.status})`,
        });
        return;
      }
      const data = (await response.json()) as LanguagesConfig;
      setConfig(data);
      setEnabled(data.enabled);
      setMessage({ kind: "ok", text: "저장했어요. API에 바로 반영됩니다." });
    } catch {
      setMessage({ kind: "error", text: "저장 중 오류가 발생했어요." });
    } finally {
      setSaving(false);
    }
  };

  return (
    <ChartCard
      title="서비스 언어"
      subtitle="켠 언어만 앱에서 해당 언어의 성경 검색·구절 제공이 활성화됩니다"
    >
      <div className="flex flex-wrap gap-2">
        {(config?.supported ?? Object.keys(LANGUAGE_LABELS)).map((lang) => {
          const on = enabled.includes(lang);
          const isKo = lang === "ko";
          return (
            <button
              key={lang}
              type="button"
              onClick={() => toggle(lang)}
              disabled={isKo}
              aria-pressed={on}
              className={`rounded-full border px-3 py-1.5 text-xs transition-colors ${
                on
                  ? "border-transparent bg-[var(--text-primary)] text-[var(--surface-1)]"
                  : "border-[var(--border-1)] text-[var(--text-secondary)]"
              } ${isKo ? "opacity-70" : ""}`}
            >
              {LANGUAGE_LABELS[lang] ?? lang}
              <span className="ml-1 uppercase opacity-60">{lang}</span>
            </button>
          );
        })}
      </div>

      <div className="mt-4 flex items-center gap-3">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving || !dirty}
          className="rounded-lg bg-[var(--text-primary)] px-4 py-2 text-xs font-medium text-[var(--surface-1)] disabled:opacity-40"
        >
          {saving ? "저장 중..." : "저장"}
        </button>
        {message && (
          <span
            className={`text-xs ${
              message.kind === "ok" ? "text-[var(--text-secondary)]" : "text-red-500"
            }`}
          >
            {message.text}
          </span>
        )}
      </div>
    </ChartCard>
  );
}
