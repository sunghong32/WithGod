"use client";

import { useRouter } from "next/navigation";
import { useRef, useState, type FormEvent, type KeyboardEvent } from "react";

export default function AdminLoginPage() {
  const router = useRouter();
  const passwordRef = useRef<HTMLInputElement>(null);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  const handleSubmit = async (submitEvent?: FormEvent) => {
    submitEvent?.preventDefault();
    if (pending) return;

    // 브라우저 비밀번호 자동완성이 React state(onChange)에 반영되지 않는 경우가
    // 있어, 제출 시점의 DOM 값을 진실로 사용한다.
    const submitted = passwordRef.current?.value ?? password;
    if (!submitted) {
      setError("비밀번호를 입력해주세요.");
      return;
    }

    setPending(true);
    setError("");

    try {
      const response = await fetch("/api/admin/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: submitted }),
      });

      // 429 는 비밀번호가 맞아도 나온다(15분 내 10회 실패 시 IP 잠금). 이걸
      // '비밀번호 오류'로 뭉뚱그리면 맞는 비밀번호를 계속 다시 치게 되므로 구분한다.
      if (response.status === 429) {
        setError("시도 횟수가 너무 많습니다. 15분 후 다시 시도해주세요.");
        return;
      }

      if (!response.ok) {
        setError("비밀번호가 올바르지 않습니다.");
        // 자동완성 값이 state 에 없을 수 있어 DOM 도 함께 비운다 — 안 그러면
        // 다음 제출이 방금 실패한 값을 그대로 다시 보낸다.
        setPassword("");
        if (passwordRef.current) passwordRef.current.value = "";
        return;
      }

      router.replace("/admin");
      router.refresh();
    } catch {
      setError("로그인에 실패했습니다. 잠시 후 다시 시도해주세요.");
    } finally {
      setPending(false);
    }
  };

  // Enter 로 로그인: 폼 암묵 제출은 기본 제출 버튼이 disabled 면 무시되는 등
  // 환경에 따라 동작이 갈려서, 키 입력을 직접 받아 명시적으로 제출한다.
  const handleKeyDown = (keyEvent: KeyboardEvent<HTMLInputElement>) => {
    if (keyEvent.key !== "Enter" || keyEvent.nativeEvent.isComposing) return;
    keyEvent.preventDefault();
    void handleSubmit();
  };

  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm rounded-2xl border border-black/10 p-8 dark:border-white/15"
      >
        <h1 className="text-xl font-semibold tracking-tight">WithGod 어드민</h1>
        <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
          사용자 지표 대시보드
        </p>

        <label htmlFor="password" className="mt-8 block text-sm font-medium">
          비밀번호
        </label>
        <input
          ref={passwordRef}
          id="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(changeEvent) => setPassword(changeEvent.target.value)}
          onKeyDown={handleKeyDown}
          className="mt-2 w-full rounded-lg border border-black/15 bg-transparent px-3 py-2 text-sm outline-none focus:border-black/40 dark:border-white/20 dark:focus:border-white/50"
          autoFocus
        />

        {error && (
          <p className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>
        )}

        <button
          type="submit"
          disabled={pending}
          className="mt-6 w-full rounded-lg bg-foreground px-4 py-2.5 text-sm font-medium text-background disabled:opacity-40"
        >
          {pending ? "확인 중..." : "로그인"}
        </button>
      </form>
    </main>
  );
}
