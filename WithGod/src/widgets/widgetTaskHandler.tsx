import type { WidgetTaskHandlerProps } from "react-native-android-widget";

import { getAppLanguage, initAppLanguage, t } from "@/shared/lib/i18n";
import { getStorageItem, removeStorageItem, setStorageItem } from "@/shared/lib/storage";

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
  lang: string;
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
    // 구버전 캐시(lang 없음)는 무효 처리해 새 언어로 받아오게 한다.
    if (typeof parsed.lang !== "string") {
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
    // 언어 파라미터 — 서버가 미지원/비활성 언어는 ko 로 폴백한다(이슈 #12)
    const response = await fetch(
      `${API_URL}?lang=${encodeURIComponent(getAppLanguage())}`,
      { signal: controller.signal },
    );
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

/** 언어 변경 시 등 캐시를 강제로 비운다 — 다음 조회가 새 언어로 받아온다. */
export const clearDailyVerseCache = async (): Promise<void> => {
  try {
    await removeStorageItem(CACHE_KEY);
  } catch {
    // 캐시 삭제 실패는 무해 — 다음 날 갱신 시 자연 교체된다.
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
  // 헤드리스 컨텍스트(앱 프로세스 없이 위젯 주기 갱신)에서는 _layout 의
  // initAppLanguage() 가 돈 적이 없어 i18n 이 초기값(ko)에 머문다 — 저장된
  // 선택/기기 언어를 먼저 반영해야 fetch 언어가 맞는다(리뷰 발견, v1.4.0).
  await initAppLanguage();
  const cached = await readCache();
  const today = kstToday();
  const lang = getAppLanguage();
  if (cached && cached.day === today && cached.lang === lang) {
    return { reference: cached.reference, text: cached.text };
  }

  try {
    const verse = await fetchDailyVerse();
    await setStorageItem(
      CACHE_KEY,
      JSON.stringify({ day: today, lang, ...verse } satisfies CachedVerse),
    );
    return verse;
  } catch {
    return cached
      ? { reference: cached.reference, text: cached.text }
      : null;
  }
};

const getPlaceholder = () => ({
  reference: t("widget.placeholderRef"),
  text: t("widget.placeholderText"),
});

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
      const verse = (await getDailyVerseWithCache()) ?? getPlaceholder();
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
