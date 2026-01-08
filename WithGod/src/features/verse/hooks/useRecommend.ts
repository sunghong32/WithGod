import { useMutation, useQueryClient } from "@tanstack/react-query";
import { verseApi, ApiError, type RecommendIn } from "../api";
import { verseKeys } from "./useRandomVerse";

interface UseRecommendOptions {
  onSuccess?: () => void;
  onError?: (error: ApiError) => void;
}

export function useRecommend(options?: UseRecommendOptions) {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: (input: RecommendIn) => verseApi.getRecommendation(input),
    retry: (failureCount, error) => {
      // ApiError인 경우 retryable 체크
      if (error instanceof ApiError) {
        return error.isRetryable && failureCount < 1;
      }
      return failureCount < 1;
    },
    retryDelay: 1000,
    onSuccess: (data, variables) => {
      // 캐시에 저장 (동일한 mood로 재요청시 캐시 활용 가능)
      queryClient.setQueryData(verseKeys.recommend(variables.mood), data);
      options?.onSuccess?.();
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        options?.onError?.(error);
      }
    },
  });

  // 에러 메시지 추출 헬퍼
  const errorMessage =
    mutation.error instanceof ApiError
      ? mutation.error.userMessage
      : mutation.error
        ? "알 수 없는 오류가 발생했어요"
        : null;

  return {
    ...mutation,
    errorMessage,
  };
}
