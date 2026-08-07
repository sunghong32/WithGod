import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  clearHistory,
  loadHistory,
  removeHistoryEntry,
  renameHistoryEntry,
  type HistoryEntry,
} from "../lib/historyStorage";
import { historyKeys } from "./keys";

/**
 * 지나온 마음(고민 기록) 목록.
 *
 * 로컬 파일이 단일 진실 공급원이고 모든 변경을 setQueryData 로 캐시에 반영하므로
 * staleTime 은 무한. 기록은 사이드바를 열 때 처음 읽힌다(앱 시작 비용에 얹지 않음).
 */
export function useHistory(enabled = true) {
  return useQuery({
    queryKey: historyKeys.all,
    queryFn: loadHistory,
    staleTime: Infinity,
    enabled,
  });
}

export function useRemoveHistoryEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => removeHistoryEntry(id),
    onSuccess: (entries) => {
      queryClient.setQueryData<HistoryEntry[]>(historyKeys.all, entries);
    },
  });
}

export function useRenameHistoryEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      renameHistoryEntry(id, title),
    onSuccess: (entries) => {
      queryClient.setQueryData<HistoryEntry[]>(historyKeys.all, entries);
    },
  });
}

export function useClearHistory() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => clearHistory(),
    onSuccess: (entries) => {
      queryClient.setQueryData<HistoryEntry[]>(historyKeys.all, entries);
    },
  });
}
