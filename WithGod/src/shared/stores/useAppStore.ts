import { create } from "zustand";
import type { RecommendItem } from "@/features/verse";

interface AppState {
  // 현재 표시 중인 말씀
  currentVerse: {
    ref: string;
    text: string;
    comment?: string;
  } | null;

  // 추천 결과 목록
  recommendations: RecommendItem[];

  // 로딩 상태 (UI용)
  isLoading: boolean;

  // Actions
  setCurrentVerse: (verse: AppState["currentVerse"]) => void;
  setRecommendations: (items: RecommendItem[]) => void;
  setLoading: (loading: boolean) => void;
  clearRecommendations: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  currentVerse: null,
  recommendations: [],
  isLoading: false,

  setCurrentVerse: (verse) => set({ currentVerse: verse }),
  setRecommendations: (items) => set({ recommendations: items }),
  setLoading: (loading) => set({ isLoading: loading }),
  clearRecommendations: () => set({ recommendations: [] }),
}));
