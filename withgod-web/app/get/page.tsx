import type { Metadata } from "next";
import { headers } from "next/headers";
import { redirect } from "next/navigation";

import {
  appStoreUrl,
  detectPlatform,
  normalizeSource,
  playStoreUrl,
} from "@/lib/storeLinks";

import IpadRedirect from "./IpadRedirect";

/**
 * 앱 받기 링크. 인스타 프로필처럼 링크를 하나만 걸 수 있는 곳에 쓴다
 * (예: /get?src=instagram).
 *
 * 휴대폰이면 기기에 맞는 스토어로 바로 보내고, PC·링크 미리보기 봇처럼
 * 기기를 알 수 없으면 두 스토어 버튼이 있는 안내 페이지를 보여 준다.
 * `src` 는 스토어 쪽 유입 경로 집계(App Store 캠페인·Play UTM)에 실린다.
 */

const TITLE = "WithGod — Daily Bible Verses";
const TAGLINE = "Whatever you're going through, there's a verse for it.";

export const metadata: Metadata = {
  title: TITLE,
  description: TAGLINE,
  openGraph: { title: TITLE, description: TAGLINE, type: "website" },
};

type PageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

export default async function GetAppPage({ searchParams }: PageProps) {
  const source = normalizeSource((await searchParams).src);
  const userAgent = (await headers()).get("user-agent") ?? "";
  const platform = detectPlatform(userAgent);

  const ios = appStoreUrl(source);
  const android = playStoreUrl(source);
  if (platform === "ios") redirect(ios);
  if (platform === "android") redirect(android);

  return (
    <main
      lang="en"
      className="flex min-h-screen flex-col items-center justify-center bg-[#F9FAFB] px-6 py-16 text-center text-[#101828] dark:bg-[#0a0a0a] dark:text-[#ededed]"
    >
      <IpadRedirect href={ios} />
      <p className="text-sm font-semibold tracking-wide text-[#4A90E2]">
        WithGod
      </p>
      <h1 className="mt-3 max-w-md text-3xl font-semibold leading-tight tracking-tight">
        {TAGLINE}
      </h1>
      <p className="mt-4 max-w-md text-base text-[#6A7282] dark:text-zinc-400">
        Tell the app how you feel and get Bible verses for that moment, with a
        gentle reflection. A new verse every morning.
      </p>
      <div className="mt-10 flex w-full max-w-xs flex-col gap-3">
        <a
          href={ios}
          className="rounded-xl bg-[#4A90E2] px-6 py-3.5 text-base font-semibold text-white transition-colors hover:bg-[#3A7BC8]"
        >
          Download on the App Store
        </a>
        <a
          href={android}
          className="rounded-xl border border-[#E5E7EB] bg-white px-6 py-3.5 text-base font-semibold text-[#101828] transition-colors hover:bg-[#F3F4F6] dark:border-zinc-700 dark:bg-zinc-900 dark:text-[#ededed] dark:hover:bg-zinc-800"
        >
          Get it on Google Play
        </a>
      </div>
      <p className="mt-6 text-sm text-[#6A7282] dark:text-zinc-500">
        Free · iPhone, iPad &amp; Android
      </p>
    </main>
  );
}
