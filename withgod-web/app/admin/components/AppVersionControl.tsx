"use client";

import { useEffect, useState } from "react";

import { ChartCard } from "./ChartCard";

/**
 * 앱 버전 관리.
 *
 * - latest: 스토어 최신 버전. 올리면 그보다 낮은 사용자에게 '선택 업데이트' 팝업.
 *   **App Store 라이브 버전을 백엔드가 자동 추적**한다 — 새 버전이 스토어에
 *   릴리즈되면 자동으로 올라가므로 평소엔 손댈 필요가 없다. 수동으로 더 높게
 *   올리는 것은 그대로 존중되고, 자동은 절대 값을 내리지 않는다.
 * - min_supported: 최소 지원 버전(강제 업데이트). 어드민 수동 전용 — 비상시만.
 */

interface VersionConfig {
  latest: string;
  min_supported: string;
  ios_url: string;
  android_url: string;
  /** 백엔드가 감지한 App Store 라이브 버전(자동 추적 소스). 조회 전엔 없음. */
  store_latest?: string;
}

const VERSION_RE = /^\d+(\.\d+){1,3}$/;

export function AppVersionControl() {
  const [config, setConfig] = useState<VersionConfig | null>(null);
  const [latest, setLatest] = useState("");
  const [minSupported, setMinSupported] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(
    null,
  );

  useEffect(() => {
    void fetch("/api/admin/app-version", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((data: VersionConfig) => {
        // 502/401 시 {error} JSON 이 그대로 캐스팅되지 않도록 형태를 검증한다.
        if (typeof data.latest !== "string" || typeof data.min_supported !== "string") {
          throw new Error("invalid_shape");
        }
        setConfig(data);
        setLatest(data.latest);
        setMinSupported(data.min_supported);
      })
      .catch(() => setMessage({ kind: "error", text: "현재 값을 불러오지 못했어요." }));
  }, []);

  const dirty =
    config !== null && (latest !== config.latest || minSupported !== config.min_supported);

  const handleSave = async () => {
    setMessage(null);
    if (!VERSION_RE.test(latest) || !VERSION_RE.test(minSupported)) {
      setMessage({ kind: "error", text: "버전 형식이 올바르지 않아요 (예: 1.3.0)." });
      return;
    }
    setSaving(true);
    try {
      const response = await fetch("/api/admin/app-version", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ latest, min_supported: minSupported }),
      });
      if (!response.ok) {
        setMessage({ kind: "error", text: `저장 실패 (${response.status})` });
        return;
      }
      const data = (await response.json()) as VersionConfig;
      setConfig(data);
      setLatest(data.latest);
      setMinSupported(data.min_supported);
      setMessage({ kind: "ok", text: "저장했어요. 앱에 바로 반영됩니다." });
    } catch {
      setMessage({ kind: "error", text: "저장 중 오류가 발생했어요." });
    } finally {
      setSaving(false);
    }
  };

  return (
    <ChartCard
      title="앱 버전 관리"
      subtitle="최신 버전은 App Store 릴리즈를 자동 추적합니다 — 강제 업데이트(최소 지원)만 수동으로 관리하세요"
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="text-xs">
          <span className="text-[var(--text-secondary)]">최신 버전 (latest)</span>
          <input
            value={latest}
            onChange={(e) => setLatest(e.target.value.trim())}
            placeholder="1.3.0"
            inputMode="decimal"
            className="mt-1 w-full rounded-lg border border-[var(--border-1)] bg-transparent px-3 py-2 tabular-nums text-[var(--text-primary)] outline-none focus:border-[var(--text-muted)]"
          />
          <span className="mt-1 block text-[var(--text-muted)]">
            {config?.store_latest
              ? `App Store 라이브 ${config.store_latest} 자동 추적 중 · 수동은 올리기만 유효`
              : "그보다 낮은 사용자 → 선택 업데이트 팝업 (스토어 릴리즈 시 자동 갱신)"}
          </span>
        </label>

        <label className="text-xs">
          <span className="text-[var(--text-secondary)]">
            최소 지원 버전 (min_supported)
          </span>
          <input
            value={minSupported}
            onChange={(e) => setMinSupported(e.target.value.trim())}
            placeholder="1.0.0"
            inputMode="decimal"
            className="mt-1 w-full rounded-lg border border-[var(--border-1)] bg-transparent px-3 py-2 tabular-nums text-[var(--text-primary)] outline-none focus:border-[var(--text-muted)]"
          />
          <span className="mt-1 block text-[var(--text-muted)]">
            그보다 낮은 사용자 → 강제 업데이트 (비상시만)
          </span>
        </label>
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
