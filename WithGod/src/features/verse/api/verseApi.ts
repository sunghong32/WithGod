import { apiClient } from "@/shared/api/client";
import { parseError, logError, ApiError } from "@/shared/api/errors";
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
    try {
      const { data } = await apiClient.get("/random");
      return RandomOutSchema.parse(data);
    } catch (error) {
      const apiError = parseError(error);
      logError(apiError, "getRandomVerse");
      throw apiError;
    }
  },

  // 기분에 맞는 성경 구절 추천
  getRecommendation: async (input: RecommendIn): Promise<RecommendOut> => {
    try {
      const { data } = await apiClient.post("/recommend", input);
      return RecommendOutSchema.parse(data);
    } catch (error) {
      const apiError = parseError(error);
      logError(apiError, "getRecommendation");
      throw apiError;
    }
  },
};

// 에러 타입 re-export
export { ApiError };
