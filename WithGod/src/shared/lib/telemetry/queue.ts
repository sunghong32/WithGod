import {
  sendTelemetryBatch,
  type TelemetryBatchPayload,
  type TelemetryEventPayload,
} from '@/shared/api/telemetryApi';
import { getStorageItem, setStorageItem } from '@/shared/lib/storage';

/**
 * 이벤트 큐.
 *
 * 앱이 짧게 쓰이는 서비스라 이벤트를 즉시 보내면 요청만 잦아지고 배터리를
 * 먹는다. 모아서 보내되 다음을 지킨다.
 * - 오프라인/실패 시 잃지 않는다(파일에 영속화).
 * - 무한히 쌓이지 않는다(상한 초과 시 오래된 것부터 버린다).
 * - 재전송이 중복 집계되지 않는다(서버가 event_id 로 멱등 처리).
 */

const QUEUE_KEY = 'withgod.telemetry.queue';

/** 이 개수가 차면 즉시 보낸다. */
export const FLUSH_THRESHOLD = 20;
/** 한 번에 보낼 최대 개수(서버 배치 상한과 맞춘다). */
export const MAX_BATCH_SIZE = 50;
/** 큐 상한. 넘으면 가장 오래된 이벤트부터 버린다. */
export const MAX_QUEUE_SIZE = 500;

type MetaProvider = () => Omit<TelemetryBatchPayload, 'events'>;

let queue: TelemetryEventPayload[] = [];
let flushing: Promise<void> | null = null;
let persistChain: Promise<void> = Promise.resolve();

export const loadQueue = async (): Promise<void> => {
  try {
    const raw = await getStorageItem(QUEUE_KEY);
    if (!raw) return;
    const parsed: unknown = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      // 덮어쓰지 않고 앞에 붙인다. 초기화(비동기)가 끝나기 전에 이미 담긴
      // 이벤트가 있을 수 있고, 지난 실행의 이벤트가 시간상 더 앞선다.
      queue = [...parsed.filter(isQueuedEvent), ...queue].slice(-MAX_QUEUE_SIZE);
    }
  } catch {
    // 큐 파일이 깨졌으면 지난 이벤트만 잃고 이번 실행분은 그대로 살린다.
  }
};

const isQueuedEvent = (value: unknown): value is TelemetryEventPayload => {
  if (!value || typeof value !== 'object') return false;
  const record = value as Record<string, unknown>;
  return typeof record.event_id === 'string' && typeof record.name === 'string';
};

/** 파일 쓰기를 직렬화해 동시 저장이 서로를 덮어쓰지 않게 한다. */
const persist = (): Promise<void> => {
  persistChain = persistChain
    .then(() => setStorageItem(QUEUE_KEY, JSON.stringify(queue)))
    .catch(() => {
      // best-effort
    });
  return persistChain;
};

export const enqueue = (event: TelemetryEventPayload): void => {
  queue.push(event);
  if (queue.length > MAX_QUEUE_SIZE) {
    queue = queue.slice(-MAX_QUEUE_SIZE);
  }
  void persist();
};

export const queueSize = (): number => queue.length;

export const shouldFlush = (): boolean => queue.length >= FLUSH_THRESHOLD;

/**
 * 큐를 서버로 보낸다.
 *
 * 전송 중에 들어온 새 이벤트를 잃지 않도록, 보낸 이벤트를 인덱스가 아니라
 * event_id 로 찾아 제거한다.
 */
export const flush = async (getMeta: MetaProvider): Promise<void> => {
  if (flushing) return flushing;
  if (queue.length === 0) return;
  // 익명 ID 가 아직 없으면 보낼 수 없다. 큐는 그대로 두고 다음 기회를 기다린다.
  if (!getMeta().anon_id) return;

  // 진행 중 표시는 반드시 실행 밖에서 걸고 푼다. 안쪽 finally 에서 풀면 첫
  // await 전에 return 하는 경로에서 대입보다 해제가 먼저 일어나, 이후 모든
  // flush 가 이미 끝난 프로미스만 돌려주고 영영 전송되지 않는다.
  const run = (async () => {
    while (queue.length > 0) {
      const batch = queue.slice(0, MAX_BATCH_SIZE);
      const result = await sendTelemetryBatch({ ...getMeta(), events: batch });

      if (!result.delivered && !result.rejected) {
        // 네트워크 실패 — 큐에 남겨두고 다음 기회에 다시 보낸다.
        return;
      }

      // 전송 중에 들어온 새 이벤트를 건드리지 않도록 인덱스가 아니라 id 로 지운다.
      const sent = new Set(batch.map((event) => event.event_id));
      queue = queue.filter((event) => !sent.has(event.event_id));
      await persist();
    }
  })();

  flushing = run;
  try {
    await run;
  } finally {
    flushing = null;
  }
};

/** 테스트/로그아웃용 초기화. */
export const clearQueue = async (): Promise<void> => {
  queue = [];
  await persist();
};
