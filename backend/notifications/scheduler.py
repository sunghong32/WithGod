from __future__ import annotations

from datetime import datetime
from threading import Event, Thread

from notifications.manager import DailyVerseNotificationManager


class DailyVerseScheduler:
    def __init__(self, manager: DailyVerseNotificationManager, poll_seconds: int = 30) -> None:
        self.manager = manager
        self.poll_seconds = poll_seconds
        self._stop_event = Event()
        self._thread: Thread | None = None

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
            except Exception:
                pass
            self._stop_event.wait(self.poll_seconds)
