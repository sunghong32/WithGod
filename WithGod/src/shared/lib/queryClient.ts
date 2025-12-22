import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // 기본 staleTime: 5분
      staleTime: 1000 * 60 * 5,
      // 기본 gcTime (구 cacheTime): 10분
      gcTime: 1000 * 60 * 10,
      // 실패시 재시도 횟수
      retry: 2,
      // 윈도우 포커스시 자동 refetch 비활성화
      refetchOnWindowFocus: false,
    },
    mutations: {
      // 에러 발생시 자동 재시도 비활성화
      retry: false,
    },
  },
});
