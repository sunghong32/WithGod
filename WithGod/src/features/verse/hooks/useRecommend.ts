import { useMutation, useQueryClient } from "@tanstack/react-query";
import { verseApi, type RecommendIn } from "../api";
import { verseKeys } from "./useRandomVerse";

export function useRecommend() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (input: RecommendIn) => verseApi.getRecommendation(input),
    onSuccess: (data, variables) => {
      // 캐시에 저장 (동일한 mood로 재요청시 캐시 활용 가능)
      queryClient.setQueryData(verseKeys.recommend(variables.mood), data);
    },
  });
}
