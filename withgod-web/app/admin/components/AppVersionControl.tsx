"use client";

import { useEffect, useState } from "react";

import { ChartCard } from "./ChartCard";

/**
 * 앱 버전 관리.
 *
 * - latest: 스토어 최신 버전. 올리면 그보다 낮은 사용자에게 '선택 업데이트' 팝업.
 * - min_supported: 최소 지원 버전. 올리면 그보다 낮은 사용자에게 '강제 업데이트' 팝업.
 *
 * ⚠️ latest 는 새 버전이 스토어에 실제로 올라간 뒤 올려야 한다(아직 없는 버전으로
 * 업데이트하라고 안내하지 않도록).
 */

interface VersionConfig {
  latest: string;
  min_supported: string;
  ios_url: string;
  android_url: string;
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
      subtitle="새 버전 출시 후 최신 버전을 올리면 구버전 사용자에게 업데이트 안내가 뜹니다"
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
            그보다 낮은 사용자 → 선택 업데이트 팝업
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
