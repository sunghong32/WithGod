from __future__ import annotations

import time
from collections import deque
from threading import Lock


class SlidingWindowLimiter:
    """프로세스 로컬 슬라이딩 윈도우 제한기.

    수집 엔드포인트는 인증이 없어 누구나 때릴 수 있다. gunicorn 워커마다
    카운터가 따로 놀지만, 목적이 정밀한 쿼터가 아니라 폭주 차단이라 충분하다.
    """

    def __init__(self, limit: int, window_seconds: float, max_keys: int = 10_000) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()

    def allow(self, key: str, now: float | None = None) -> bool:
        now = now if now is not None else time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            hits = self._hits.get(key)
            if hits is None:
                # 키가 무한정 늘어나면 메모리 1GB 인스턴스에서 문제가 된다.
                if len(self._hits) >= self.max_keys:
                    self._evict(cutoff)
                hits = deque()
                self._hits[key] = hits

            while hits and hits[0] < cutoff:
                hits.popleft()

            if len(hits) >= self.limit:
                return False

            hits.append(now)
            return True

    def _evict(self, cutoff: float) -> None:
        stale = [key for key, hits in self._hits.items() if not hits or hits[-1] < cutoff]
        for key in stale:
            del self._hits[key]
        if len(self._hits) >= self.max_keys:
            self._hits.clear()
