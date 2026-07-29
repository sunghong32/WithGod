import { z } from "zod";

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
  // 이 메시지는 현재 parse() 호출처가 없어 사용자에게 노출되지 않는다(타입 추론용).
  // 노출 경로가 생기면 i18n(errors.moodRequired) 로 교체할 것.
  mood: z.string().min(1, "기분을 입력해주세요"),
});

export const RecommendItemSchema = z.object({
  ref: z.string(),
  text: z.string(),
  comment: z.string().optional(),
  tag: z.string().optional(),
});

export type RecommendIn = z.infer<typeof RecommendInSchema>;
export type RecommendItem = z.infer<typeof RecommendItemSchema>;
