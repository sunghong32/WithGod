from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Callable

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


class VerseInterpretationStore:
    """verse_id -> interpretation 파일 캐시.

    gunicorn worker=1 로 운영하므로 동시성 부담이 낮아 단순 파일(JSON)로 영속화한다.
    말씀 개수가 적고 verse_id 기준으로 캐시하므로 말씀당 최대 1회만 LLM 을 호출한다.
    """

    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def get(self, verse_id: str) -> str:
        return self._load().get(verse_id, "")

    def set(self, verse_id: str, interpretation: str) -> None:
        data = self._load()
        data[verse_id] = interpretation
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # 손상/읽기 실패 시에도 죽지 않고 빈 캐시로 취급(풀이는 재생성).
            return {}


class VerseInterpreter:
    """'오늘의 말씀 풀이'의 캐시 조회 → LLM 생성 → 폴백을 담당한다.

    generate_fn 은 (reference, text) -> 풀이 문자열 을 반환하는 콜러블로,
    운영에서는 app.py 의 OpenAI 백엔드 함수를 주입한다(테스트에서는 mock 을 주입).
    어떤 경우에도 예외를 밖으로 던지지 않는다 — 풀이가 없어도 말씀은 항상 반환한다.
    """

    def __init__(
        self,
        store: VerseInterpretationStore,
        generate_fn: Callable[[str, str], str],
    ) -> None:
        self._store = store
        self._generate = generate_fn

    def interpret(self, verse: DailyVerse) -> str:
        try:
            cached = self._store.get(verse.verse_id)
        except Exception:
            cached = ""
        if cached:
            return cached

        try:
            generated = self._generate(verse.reference, verse.text)
            text = (generated or "").strip()
        except Exception:
            # 키 없음/네트워크/파싱 등 어떤 예외든 풀이 없이도 말씀은 반환한다.
            text = ""

        if not text:
            # 폴백은 캐시에 저장하지 않는다(다음 요청에서 LLM 을 재시도).
            return verse.reflection or ""

        try:
            self._store.set(verse.verse_id, text)
        except Exception:
            # 캐시 저장 실패해도 생성된 풀이는 그대로 반환한다.
            pass
        return text
