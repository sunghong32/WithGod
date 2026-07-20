import { Platform } from "react-native";

/**
 * 앱 실행(포그라운드 진입) 시 안드로이드 홈 위젯을 즉시 최신 말씀으로 갱신한다.
 * 시스템 주기 갱신(30분)만 기다리지 않게 하는 보조 동기화 — 실패해도 무해(best-effort).
 * 홈 화면에 위젯이 없으면 아무 일도 하지 않는다.
 */
export const refreshHomeWidgetAsync = async (): Promise<void> => {
  if (Platform.OS !== "android") return;
  try {
    const { requestWidgetUpdate } = await import("react-native-android-widget");
    const { getDailyVerseWithCache } = await import("./widgetTaskHandler");
    const { DailyVerseWidget } = await import("./DailyVerseWidget");

    const verse = await getDailyVerseWithCache();
    if (!verse) return;

    await requestWidgetUpdate({
      widgetName: "DailyVerse",
      renderWidget: () => ({
        light: (
          <DailyVerseWidget reference={verse.reference} text={verse.text} />
        ),
        dark: (
          <DailyVerseWidget reference={verse.reference} text={verse.text} dark />
        ),
      }),
    });
  } catch {
    // 위젯 미설치·모듈 미탑재 등 — 조용히 무시
  }
};
