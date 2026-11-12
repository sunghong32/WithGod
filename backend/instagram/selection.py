"""그날 올릴 말씀 고르기 (이슈 #62).

**앱의 오늘의 말씀과 같은 말씀**을 올린다. 게시 시각(미국 동부 07:00)은 한국 20~21시라 한국 날짜와
미국 동부 날짜가 같다 — 앱(`/daily-verse`, 한국 날짜 기준)이 그날 보여 주는 말씀과 같다.
같은 `DailyVerseProvider` 를 쓰므로 절기 고정(새해·부활절·성탄·설날·추석)과 성탄 전용 말씀
(`_HOLIDAY_ONLY`, 눅 2:14 는 12/25 에만)도 앱 규칙 그대로 따른다.

최근에 올린 말씀이어도 **앱 말씀을 그대로 올린다**(11/12 사용자 결정 — 런칭 게시물과 겹쳐도 스타일이
달라 괜찮다). 회전은 한 바퀴가 약 1년이라 겹치는 건 손으로 고른 게시물·절기 고정 말씀 정도다.

예외는 그 말씀의 캐러셀이 아직 준비되지 않았을 때뿐이다 — 그날만 **회전의 반대편**(반 바퀴 떨어진)
준비된 말씀을 올린다. 바로 다음 말씀으로 넘기면 이튿날 앱 말씀이 「어제 올린 말씀」이 되어 그 뒤로
매일 한 칸씩 밀린다. 대신 올릴 말씀은 최근 `REPEAT_WINDOW_DAYS` 안에 올린 것과, 앞으로 그만큼 안에 앱 차례가
돌아올 것(곧 그날 말씀으로 다시 올라간다)을 피한다. 그런 말씀이 없으면 그날은 올리지 않는다(실패 알림).
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

    available 은 이미지·캡션이 준비된 verse_id(매니페스트). 앱 말씀이 준비됐으면 최근에 올렸어도
    그대로, 준비가 안 됐으면 회전의 반대편에서 찾는다. 이유: "app" | "missing:<앱 말씀>".
    """
    verse = app_verse_for(day, path)
    if verse.verse_id in available:
        return verse.verse_id, "app"

    provider = DailyVerseProvider(str(path))
    rotation = [v["verse_id"] for v in provider._load() if v.get("verse_id") not in _HOLIDAY_ONLY]
    n = len(rotation)
    start = rotation.index(verse.verse_id) if verse.verse_id in rotation else day.toordinal() % n
    for step in range(n):
        pos = (start + n // 2 + step) % n
        candidate = rotation[pos]
        upcoming = (pos - start) % n <= REPEAT_WINDOW_DAYS  # 곧 앱 차례로 다시 올라갈 말씀
        if candidate in available and not upcoming and _fresh(candidate, day, posted):
            return candidate, f"missing:{verse.verse_id}"
    raise RuntimeError(f"{verse.verse_id} 캐러셀이 준비되지 않았고 대신 올릴 말씀도 없다 — 카피·그림을 만들 때")


def _fresh(verse_id: str, day: date, posted: dict[str, str]) -> bool:
    last = posted.get(verse_id)
    if not last:
        return True
    return (day - date.fromisoformat(last)) > timedelta(days=REPEAT_WINDOW_DAYS)
