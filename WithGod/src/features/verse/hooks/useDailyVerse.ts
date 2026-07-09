import { useQuery } from "@tanstack/react-query";
import { verseApi, ApiError } from "../api";
import { verseKeys } from "./useRandomVerse";

export function useDailyVerse() {
  const query = useQuery({
    queryKey: verseKeys.daily(),
    queryFn: verseApi.getDailyVerse,
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
      : "알 수 없는 오류가 발생했어요";

  return {
    ...query,
    errorMessage,
  };
}
