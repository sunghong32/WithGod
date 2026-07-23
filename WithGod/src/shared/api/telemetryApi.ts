import axios, { isAxiosError } from 'axios';

/**
 * 자체 지표 수집 전송.
 *
 * 공용 apiClient 를 쓰지 않는 이유:
 * - 타임아웃이 60초(AI 응답 대기용)라 통계 전송에는 너무 길다.
 * - 요청/응답 인터셉터가 콘솔을 채우고 실패를 에러로 승격시킨다. 통계는
 *   조용히 실패하고 다음 기회에 다시 보내면 되는 데이터다.
 */

const TELEMETRY_TIMEOUT_MS = 10000;

const telemetryClient = axios.create({
  baseURL: 'https://mincha.co.kr',
  timeout: TELEMETRY_TIMEOUT_MS,
  headers: { 'Content-Type': 'application/json' },
});

export interface TelemetryEventPayload {
  event_id: string;
  name: string;
  ts: string;
  session_id: string;
  params?: Record<string, string | number | boolean>;
}

export interface TelemetryBatchPayload {
  anon_id: string;
  platform: string;
  app_version?: string;
  os_version?: string;
  tz?: string;
  events: TelemetryEventPayload[];
}

export interface TelemetrySendResult {
  /** 서버가 배치를 받아들였는가. false 면 큐에 남겨 다음에 다시 보낸다. */
  delivered: boolean;
  /** 재시도해도 소용없는 거절(4xx). 큐에서 버려야 한다. */
  rejected: boolean;
}

export const sendTelemetryBatch = async (
  payload: TelemetryBatchPayload,
): Promise<TelemetrySendResult> => {
  try {
    await telemetryClient.post('/telemetry/events', payload);
    return { delivered: true, rejected: false };
  } catch (error) {
    const status = isAxiosError(error) ? error.response?.status : undefined;

    // 429(레이트리밋)는 잠시 뒤 다시 보내야 하므로 영구 거절이 아니다.
    // 그 외 4xx 는 같은 배치를 다시 보내도 계속 실패하므로 버린다.
    const rejected = status !== undefined && status >= 400 && status < 500 && status !== 429;

    if (__DEV__) {
      console.warn('[Telemetry] send failed', status ?? error);
    }
    return { delivered: false, rejected };
  }
};
