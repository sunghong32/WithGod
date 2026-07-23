import { logAnalyticsEvent } from "@/shared/lib/analytics";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  loadBookmarks,
  removeBookmark,
  toggleBookmark,
  type Bookmark,
  type BookmarkInput,
  type BookmarkSource,
} from "../lib/bookmarkStorage";
import { bookmarkKeys } from "./keys";

/**
 * 저장한 말씀 목록. 로컬 파일이 단일 진실 공급원이고 모든 변경이
 * setQueryData 로 캐시에 반영되므로 staleTime 은 무한으로 둔다.
 */
export function useBookmarks() {
  return useQuery({
    queryKey: bookmarkKeys.all,
    queryFn: loadBookmarks,
    staleTime: Infinity,
  });
}

export function useToggleBookmark() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: BookmarkInput) => toggleBookmark(input),
    onSuccess: ({ bookmarks, added }, input) => {
      queryClient.setQueryData<Bookmark[]>(bookmarkKeys.all, bookmarks);
      void logAnalyticsEvent(added ? "verse_save" : "verse_unsave", {
        source: input.source,
        reference: input.reference,
      });
    },
  });
}

export function useRemoveBookmark() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      reference,
      source,
    }: {
      reference: string;
      source: BookmarkSource;
    }) => removeBookmark(reference, source),
    onSuccess: (bookmarks, { reference, source }) => {
      queryClient.setQueryData<Bookmark[]>(bookmarkKeys.all, bookmarks);
      void logAnalyticsEvent("verse_unsave", {
        source,
        reference,
        from: "bookmarks_screen",
      });
    },
  });
}

/** (reference, source)가 저장돼 있는지. 목록 로딩 전에는 false */
export function useIsBookmarked(
  reference: string | undefined,
  source: BookmarkSource,
): boolean {
  const { data } = useBookmarks();
  if (!reference || !data) return false;
  return data.some(
    (item) => item.reference === reference && item.source === source,
  );
}
