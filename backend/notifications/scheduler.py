from __future__ import annotations

import logging
from datetime import datetime
from threading import Event, Thread

from notifications.manager import DailyVerseNotificationManager

log = logging.getLogger("with-god.push")


class DailyVerseScheduler:
    def __init__(self, manager: DailyVerseNotificationManager, poll_seconds: int = 30) -> None:
        self.manager = manager
        self.poll_seconds = poll_seconds
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._last_error = ""

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(target=self._run, name="daily-verse-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)

    def run_once(self, now: datetime | None = None) -> dict[str, object]:
        return self.manager.send_due_notifications(now=now)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.manager.send_due_notifications()
                self._last_error = ""
            except Exception as exc:
                # 같은 오류가 30초마다 되풀이되면 로그가 넘치므로 내용이 바뀔 때만 남긴다.
                error = f"{type(exc).__name__}: {exc}"
                if error != self._last_error:
                    log.exception("push scheduler: send_due_notifications failed")
                    self._last_error = error
            self._stop_event.wait(self.poll_seconds)
