/** 백엔드 /admin/analytics/* 응답 타입과 조회 헬퍼. */

export interface Overview {
  day: string;
  dau: number;
  dau_prev: number;
  wau: number;
  mau: number;
  new_users: number;
  new_users_prev: number;
  returning_users: number;
  total_users: number;
  sessions: number;
  events: number;
  stickiness: number;
  last_event_at: string | null;
}

export interface DailyPoint {
  day: string;
  dau: number;
  new_users: number;
  returning_users: number;
  wau: number;
  mau: number;
  sessions: number;
  events: number;
}

export interface RetentionCell {
  day_n: number;
  rate: number | null;
  retained: number | null;
}

export interface RetentionRow {
  cohort_day: string;
  size: number;
  cells: RetentionCell[];
}

export interface Retention {
  day_ns: number[];
  rows: RetentionRow[];
}

export interface EventCount {
  name: string;
  total: number;
  users: number;
}

export interface Breakdown {
  platforms: { key: string; users: number }[];
  app_versions: { key: string; users: number }[];
  // 기기 타임존으로 추정한 국가(ISO 3166-1 alpha-2, 모르면 "unknown").
  // 백엔드가 구버전이면 빠져 있을 수 있다.
  countries?: { key: string; users: number }[];
  /** 국가별 퍼널 — 앱을 연 사용자 중 상담을 시작한 비율. 구버전 백엔드는 없다. */
  country_funnel?: {
    key: string;
    users: number;
    home: number;
    mood: number;
    rate: number;
  }[];
}

/** 국가별 앱 언어 설정. 지표에 언어가 없어 **푸시 등록 기기**로만 집계된다. */
export interface LanguageBreakdown {
  countries: {
    key: string;
    devices: number;
    languages: { key: string; devices: number }[];
  }[];
  source?: string;
  note?: string;
  /** 집계 기간(일). 국가 분포 카드와 같은 창을 쓴다. */
  days?: number;
  /** 그 기간에 앱을 열지 않아 제외된 등록 기기 수 */
  inactive_devices?: number;
}

export class UnauthorizedError extends Error {}

const request = async <T>(path: string): Promise<T> => {
  const response = await fetch(`/api/admin/analytics/${path}`, {
    cache: "no-store",
  });
  if (response.status === 401) {
    throw new UnauthorizedError("세션이 만료되었습니다.");
  }
  if (!response.ok) {
    throw new Error(`지표를 불러오지 못했습니다 (${response.status})`);
  }
  return (await response.json()) as T;
};

export const fetchOverview = () => request<Overview>("overview");

export const fetchTimeseries = (days: number) =>
  request<{ days: number; series: DailyPoint[] }>(`timeseries?days=${days}`);

export const fetchRetention = (cohorts: number) =>
  request<Retention>(`retention?cohorts=${cohorts}`);

export const fetchEvents = (days: number) =>
  request<{ days: number; events: EventCount[] }>(`events?days=${days}`);

export const fetchBreakdown = (days: number) =>
  request<Breakdown>(`breakdown?days=${days}`);

export const fetchLanguages = (days: number) =>
  request<LanguageBreakdown>(`languages?days=${days}`);
