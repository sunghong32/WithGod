"""그날 올릴 말씀 고르기 (이슈 #62).

**앱의 오늘의 말씀과 같은 말씀**을 올린다. 게시 시각(미국 동부 07:00)은 한국 20~21시라 한국 날짜와
미국 동부 날짜가 같다 — 앱(`/daily-verse`, 한국 날짜 기준)이 그날 보여 주는 말씀과 같다.
같은 `DailyVerseProvider` 를 쓰므로 절기 고정(새해·부활절·성탄·설날·추석)과 성탄 전용 말씀
(`_HOLIDAY_ONLY`, 눅 2:14 는 12/25 에만)도 앱 규칙 그대로 따른다.

예외 하나 — 절기 고정 말씀은 제 회전 차례에도 또 나온다(앱은 그대로 둔다). 인스타 그리드에서
같은 카드가 몇 주 사이 두 번 보이면 어색하므로, 최근 `REPEAT_WINDOW_DAYS` 안에 올린 말씀이면
그날만 **회전의 반대편**(반 바퀴 떨어진) 말씀을 올린다. 바로 다음 말씀으로 넘기면 이튿날 앱 말씀이
「어제 올린 말씀」이 되어 그 뒤로 매일 한 칸씩 밀린다. 반대편 말씀은 지난 차례와 다음 차례가 모두
반 바퀴(약 6개월) 떨어져 있어 다시 부딪히지 않는다.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from notifications.verse_provider import _HOLIDAY_ONLY, DailyVerseProvider

DAILY_VERSES = Path(__file__).resolve().parent.parent / "notifications" / "daily_verses.json"
APP_TZ = ZoneInfo("Asia/Seoul")  # 앱 오늘의 말씀의 날짜 기준(push_default_timezone)
REPEAT_WINDOW_DAYS = 90


def app_verse_for(day: date, path: Path = DAILY_VERSES):
    """앱이 그 날짜(한국)에 내는 오늘의 말씀(DailyVerse, 한국어 카드)."""
    noon = datetime.combine(day, time(12, 0), tzinfo=APP_TZ)
    return DailyVerseProvider(str(path)).get_daily_verse(now=noon)


def pick_verse_id(day: date, posted: dict[str, str], available: set[str],
                  path: Path = DAILY_VERSES) -> tuple[str, str]:
    """(verse_id, 고른 이유). posted 는 {verse_id: 마지막으로 올린 날짜 ISO}.

    available 은 이미지·캡션이 준비된 verse_id(매니페스트). 앱 말씀이 최근에 올라갔거나 준비가
    안 됐으면 회전의 반대편에서 찾는다. 이유: "app" | "recent:<앱 말씀>" | "missing:<앱 말씀>".
    """
    verse = app_verse_for(day, path)
    if verse.verse_id in available and _fresh(verse.verse_id, day, posted):
        return verse.verse_id, "app"

    provider = DailyVerseProvider(str(path))
    rotation = [v["verse_id"] for v in provider._load() if v.get("verse_id") not in _HOLIDAY_ONLY]
    n = len(rotation)
    start = rotation.index(verse.verse_id) if verse.verse_id in rotation else day.toordinal() % n
    reason = "recent" if verse.verse_id in available else "missing"
    for step in range(n):
        candidate = rotation[(start + n // 2 + step) % n]
        if candidate in available and _fresh(candidate, day, posted):
            return candidate, f"{reason}:{verse.verse_id}"
    raise RuntimeError("올릴 수 있는 말씀이 없다(매니페스트가 비었거나 전부 최근에 올림)")


def _fresh(verse_id: str, day: date, posted: dict[str, str]) -> bool:
    last = posted.get(verse_id)
    if not last:
        return True
    return (day - date.fromisoformat(last)) > timedelta(days=REPEAT_WINDOW_DAYS)
