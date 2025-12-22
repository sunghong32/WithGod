import { useQuery } from "@tanstack/react-query";
import { verseApi } from "../api";

export const verseKeys = {
  all: ["verse"] as const,
  random: () => [...verseKeys.all, "random"] as const,
  recommend: (mood: string) => [...verseKeys.all, "recommend", mood] as const,
};

export function useRandomVerse() {
  return useQuery({
    queryKey: verseKeys.random(),
    queryFn: verseApi.getRandomVerse,
    // 컴포넌트 마운트시 자동 fetch 하지 않음 (버튼 클릭시 수동 fetch)
    enabled: false,
  });
}
