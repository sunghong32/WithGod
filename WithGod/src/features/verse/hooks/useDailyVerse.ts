import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { AppState } from "react-native";
import { verseToday } from "@/shared/lib/localDate";
import { verseApi, ApiError } from "../api";
import { verseKeys } from "./keys";

export function useDailyVerse() {
  // i18n.language 를 구독해 설정에서 언어를 바꾸면 말씀도 새 언어로 다시 불러온다.
  const { t, i18n } = useTranslation();
  const [today, setToday] = useState(() => verseToday());

  // 백그라운드에 있다가 돌아왔을 때 날짜가 바뀌었으면 쿼리 키가 바뀌어 새로 불러온다.
  useEffect(() => {
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active") {
        setToday(verseToday());
      }
    });
    return () => subscription.remove();
  }, []);

  const query = useQuery({
    queryKey: verseKeys.daily(today, i18n.language),
    // 이 기기의 말씀 날짜(현지 또는 한국 — localDate.ts)를 보내 그날 말씀을 받는다(#69).
    queryFn: () => verseApi.getDailyVerse(today),
    retry: (failureCount, error) => {
      // ApiError인 경우 retryable 체크
      if (error instanceof ApiError) {
        return error.isRetryable && failureCount < 2;
      }
      // 그 외 에러는 2회까지 재시도
      return failureCount < 2;
    },
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 10000),
  });

  // 에러 메시지 추출 헬퍼
  const errorMessage =
    query.error instanceof ApiError
      ? query.error.userMessage
      : t("errors.unknown");

  return {
    ...query,
    errorMessage,
  };
}
