import type { WidgetTaskHandlerProps } from "react-native-android-widget";

import { getStorageItem, setStorageItem } from "@/shared/lib/storage";

import { DailyVerseWidget } from "./DailyVerseWidget";

/**
 * 안드로이드 위젯 갱신 핸들러.
 *
 * updatePeriodMillis(30분)마다 헤드리스 JS 로 깨어나지만, 오늘의 말씀은 KST
 * 날짜 기준으로만 바뀌므로 캐시 날짜가 오늘과 같으면 네트워크를 건너뛴다
 * (실제 API 호출은 하루 1회). 헤드리스 태스크 전체 타임아웃이 30초라
 * fetch 타임아웃을 10초로 짧게 잡는다.
 */

const CACHE_KEY = "withgod.widget.dailyVerse";
const API_URL = "https://mincha.co.kr/daily-verse";
const FETCH_TIMEOUT_MS = 10_000;

interface CachedVerse {
  day: string;
  reference: string;
  text: string;
}

// KST(UTC+9) 기준 오늘 날짜. useDailyVerse 의 kstToday 와 동일한 규칙.
const kstToday = (): string =>
  new Date(Date.now() + 9 * 60 * 60 * 1000).toISOString().slice(0, 10);

const readCache = async (): Promise<CachedVerse | null> => {
  try {
    const raw = await getStorageItem(CACHE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<CachedVerse>;
    if (
      typeof parsed.day !== "string" ||
      typeof parsed.reference !== "string" ||
      typeof parsed.text !== "string"
    ) {
      return null;
    }
    return parsed as CachedVerse;
  } catch {
    return null;
  }
};

const fetchDailyVerse = async (): Promise<{
  reference: string;
  text: string;
}> => {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const response = await fetch(API_URL, { signal: controller.signal });
    if (!response.ok) {
      throw new Error(`daily-verse HTTP ${response.status}`);
    }
    const json = (await response.json()) as {
      daily_verse?: { reference?: string; text?: string };
    };
    const reference = json.daily_verse?.reference;
    const text = json.daily_verse?.text;
    if (!reference || !text) {
      throw new Error("daily-verse: malformed payload");
    }
    return { reference, text };
  } finally {
    clearTimeout(timer);
  }
};

/**
 * 오늘의 말씀을 캐시 우선으로 가져온다.
 * 실패 시 지난 캐시라도 반환하고, 그것도 없으면 null.
 */
export const getDailyVerseWithCache = async (): Promise<{
  reference: string;
  text: string;
} | null> => {
  const cached = await readCache();
  const today = kstToday();
  if (cached && cached.day === today) {
    return { reference: cached.reference, text: cached.text };
  }

  try {
    const verse = await fetchDailyVerse();
    await setStorageItem(
      CACHE_KEY,
      JSON.stringify({ day: today, ...verse } satisfies CachedVerse),
    );
    return verse;
  } catch {
    return cached
      ? { reference: cached.reference, text: cached.text }
      : null;
  }
};

const PLACEHOLDER = {
  reference: "신과함께",
  text: "앱을 열어 오늘의 말씀을 받아보세요.",
};

export async function widgetTaskHandler(
  props: WidgetTaskHandlerProps,
): Promise<void> {
  if (__DEV__) {
    console.log(
      `[Widget] task: ${props.widgetAction} (${props.widgetInfo.widgetName}#${props.widgetInfo.widgetId})`,
    );
  }
  switch (props.widgetAction) {
    case "WIDGET_ADDED":
    case "WIDGET_UPDATE":
    case "WIDGET_RESIZED": {
      const verse = (await getDailyVerseWithCache()) ?? PLACEHOLDER;
      props.renderWidget({
        light: <DailyVerseWidget reference={verse.reference} text={verse.text} />,
        dark: (
          <DailyVerseWidget reference={verse.reference} text={verse.text} dark />
        ),
      });
      break;
    }
    default:
      // WIDGET_DELETED / WIDGET_CLICK(OPEN_APP 은 네이티브에서 처리) — 할 일 없음
      break;
  }
}
