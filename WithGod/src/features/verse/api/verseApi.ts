import { apiClient } from "@/shared/api/client";
import {
  RandomOutSchema,
  RecommendOutSchema,
  type RandomOut,
  type RecommendIn,
  type RecommendOut,
} from "./schema";

export const verseApi = {
  // 랜덤 성경 구절 조회
  getRandomVerse: async (): Promise<RandomOut> => {
    const { data } = await apiClient.get("/random");
    return RandomOutSchema.parse(data);
  },

  // 기분에 맞는 성경 구절 추천
  getRecommendation: async (input: RecommendIn): Promise<RecommendOut> => {
    const { data } = await apiClient.post("/recommend", input);
    return RecommendOutSchema.parse(data);
  },
};
