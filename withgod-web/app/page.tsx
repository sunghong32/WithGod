import Link from "next/link";

/**
 * 공개 홈. 아직 소개 페이지가 없어 비워두고 어드민 입구만 둔다.
 * (대시보드는 /admin — 미들웨어가 세션 쿠키로 막는다)
 */
export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center">
      <h1 className="text-2xl font-semibold tracking-tight">WithGod</h1>
      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        매일의 말씀을 전하는 앱
      </p>
      <Link
        href="/admin"
        className="mt-2 text-sm text-zinc-500 underline underline-offset-4 dark:text-zinc-400"
      >
        어드민
      </Link>
    </main>
  );
}
