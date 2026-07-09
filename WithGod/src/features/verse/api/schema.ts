import { z } from "zod";

// ==================== Random Verse ====================

export const RandomOutSchema = z.object({
  ref: z.string(),
  text: z.string(),
});

export const RandomErrorSchema = z.object({
  error: z.string(),
});

export const RandomResponseSchema = z.union([RandomOutSchema, RandomErrorSchema]);

export type RandomOut = z.infer<typeof RandomOutSchema>;
export type RandomResponse = z.infer<typeof RandomResponseSchema>;

// ==================== Daily Verse ====================

// GET /daily-verse 응답의 내부 객체
// interpretation = LLM이 생성한 "풀이"(구절당 최대 1회 호출, 파일 캐시).
//   실패 시 reflection → 빈 문자열 순으로 폴백될 수 있음.
// reflection = 푸시 알림에서 사용하는 기존 필드(그대로 유지).
export const DailyVerseSchema = z.object({
  verse_id: z.string().optional().default(""),
  reference: z.string(),
  text: z.string(),
  reflection: z.string().optional().default(""),
  interpretation: z.string().optional().default(""),
});

export const DailyVerseResponseSchema = z.object({
  daily_verse: DailyVerseSchema,
});

export type DailyVerse = z.infer<typeof DailyVerseSchema>;
export type DailyVerseResponse = z.infer<typeof DailyVerseResponseSchema>;

// ==================== Recommend ====================

export const RecommendInSchema = z.object({
  mood: z.string().min(1, "기분을 입력해주세요"),
});

export const RecommendItemSchema = z.object({
  ref: z.string(),
  text: z.string(),
  comment: z.string().optional(),
  tag: z.string().optional(),
});

export const VerseCandidateSchema = z.object({
  ref: z.string(),
  text: z.string(),
  score: z.number().optional(),
});

export const RecommendOutSchema = z.object({
  mood: z.string(),
  model: z.string().optional(),
  style: z.string().optional(),
  results: z.array(RecommendItemSchema),
  error: z.string().nullable().optional(),
  candidates: z.array(VerseCandidateSchema).nullable().optional(),
});

export const RecommendErrorSchema = z.object({
  error: z.string(),
});

export const RecommendResponseSchema = z.union([RecommendOutSchema, RecommendErrorSchema]);

export type RecommendIn = z.infer<typeof RecommendInSchema>;
export type RecommendItem = z.infer<typeof RecommendItemSchema>;
export type RecommendOut = z.infer<typeof RecommendOutSchema>;
export type RecommendResponse = z.infer<typeof RecommendResponseSchema>;
