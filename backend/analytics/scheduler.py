from __future__ import annotations

import logging
from datetime import datetime
from threading import Event, Thread
from zoneinfo import ZoneInfo

from analytics.db import SERVICE_TIMEZONE, service_day, utc_now
from analytics.rollup import claim_job, run_rollup

log = logging.getLogger("with-god.analytics")

JOB_NAME = "daily_rollup"


class AnalyticsRollupScheduler:
    """매일 새벽 한 번 롤업을 돌린다.

    gunicorn 워커마다 이 스레드가 뜨지만, job_lock 을 선점한 워커 하나만
    실제로 실행한다(푸시 스케줄러와 달리 집계는 중복 실행 시 값이 흔들린다).
    """

    def __init__(
        self,
        db_path: str,
        hour: int = 3,
        raw_retention_days: int = 90,
        poll_seconds: int = 300,
    ) -> None:
        self.db_path = db_path
        self.hour = hour
        self.raw_retention_days = raw_retention_days
        self.poll_seconds = poll_seconds
        self._stop_event = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(target=self._run, name="analytics-rollup", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)

    def run_if_due(self, now: datetime | None = None) -> dict[str, object] | None:
        now = now or utc_now()
        local = now.astimezone(ZoneInfo(SERVICE_TIMEZONE))
        if local.hour < self.hour:
            return None

        day = service_day(now)
        if not claim_job(self.db_path, JOB_NAME, day):
            return None

        result = run_rollup(
            self.db_path,
            now=now,
            raw_retention_days=self.raw_retention_days,
        )
        log.info("analytics rollup done: %s", result)
        return result

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_if_due()
            except Exception:
                log.exception("analytics rollup failed")
            self._stop_event.wait(self.poll_seconds)
