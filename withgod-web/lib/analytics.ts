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
