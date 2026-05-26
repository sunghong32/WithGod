from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from notifications.models import DailyVerse


class DailyVerseProvider:
    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def get_daily_verse(self, now: datetime | None = None) -> DailyVerse:
        verses = self._load()
        if not verses:
            raise RuntimeError("No daily verses configured")
        current = now or datetime.now()
        index = current.toordinal() % len(verses)
        item = verses[index]
        return DailyVerse(
            verse_id=str(item["verse_id"]),
            reference=str(item["reference"]),
            text=str(item["text"]),
            reflection=str(item.get("reflection", "")),
        )

    def _load(self) -> list[dict[str, str]]:
        if not self.path.exists():
            raise RuntimeError(f"Daily verse store not found: {self.path}")
        return json.loads(self.path.read_text(encoding="utf-8"))
