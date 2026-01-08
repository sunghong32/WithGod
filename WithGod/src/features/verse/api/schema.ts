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
