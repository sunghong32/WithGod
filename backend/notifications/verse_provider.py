from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

from notifications.models import DailyVerse

# 서버 OS 타임존(UTC 등)과 무관하게 '오늘'은 한국 시간 기준으로 계산한다.
# 설정(push_default_timezone)을 쓰는 경로는 manager 가 normalize 된 now 를 넘겨준다.
_DEFAULT_TZ = ZoneInfo("Asia/Seoul")

# ── 절기 고정 배치 ────────────────────────────────────────────────
# 평소에는 배열 순서대로 하루씩 돌지만(아래 index 계산), 아래 날짜에는 정해진 말씀을 낸다.
# 회전 주기가 365일이 아니라서(=말씀 개수) 그냥 두면 성탄절에 축도가, 새해에 문장
# 조각이 나오는 일이 생긴다. 고정한 말씀도 목록에 그대로 남아 있어 제 차례에 또 나온다.
_FIXED_DATES: dict[tuple[int, int], str] = {
    (1, 1): "jer-29-11",    # 새해 — 너희 장래에 소망을 주려 하는 생각이라
    (12, 24): "isa-9-2",    # 성탄 전야 — 흑암에 행하던 백성이 큰 빛을 보고
    (12, 25): "luk-2-14",   # 성탄절 — 땅에서는 기뻐하심을 입은 사람들 중에 평화로다
}

# 부활절은 해마다 옮겨 다녀서 계산한다(서방 교회 그레고리력 계산법).
_EASTER_VERSE_ID = "job-19-25"  # 나의 구속자가 살아 계시니

# 설날·추석은 음력이라 계산 대신 날짜표를 쓴다(`lunar_holidays.json`).
# 표는 한국 음력 라이브러리로 만든다 — 중국 음력으로 계산하면 2027·2028 설날이
# 하루씩 틀린다. 생성·검증: scripts/build_lunar_holidays.py (--check).
_LUNAR_HOLIDAY_VERSES = {
    "seollal": "num-6-24",   # 설날 — 아론의 축복(민수기 6:24-26)
    "chuseok": "psa-128-2",  # 추석 — 네가 네 손이 수고한대로 먹을 것이라
}
_LUNAR_TABLE = Path(__file__).with_name("lunar_holidays.json")


@lru_cache(maxsize=1)
def _lunar_dates() -> dict[date, str]:
    """{양력 날짜: verse_id}. 표가 없거나 깨져도 죽지 않고 빈 표로 넘어간다."""
    try:
        table = json.loads(_LUNAR_TABLE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[date, str] = {}
    for holiday, verse_id in _LUNAR_HOLIDAY_VERSES.items():
        for iso in table.get(holiday, {}).values():
            try:
                out[date.fromisoformat(iso)] = verse_id
            except (TypeError, ValueError):
                continue
    return out


def _easter(year: int) -> date:
    """그레고리력 부활절(익명 계산법). 2024~2028 실제 날짜로 대조 확인했다."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month, day = divmod(h + ell - 7 * m + 114, 31)
    return date(year, month, day + 1)


def fixed_verse_id(day: date) -> str | None:
    """그 날짜에 고정된 말씀 id. 없으면 None."""
    pinned = _lunar_dates().get(day)
    if pinned:
        return pinned
    pinned = _FIXED_DATES.get((day.month, day.day))
    if pinned:
        return pinned
    if day == _easter(day.year):
        return _EASTER_VERSE_ID
    return None


class DailyVerseProvider:
    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def get_daily_verse(self, now: datetime | None = None) -> DailyVerse:
        verses = self._load()
        if not verses:
            raise RuntimeError("No daily verses configured")
        # now 미지정 시 서버 OS 타임존 대신 한국 시간 기준 '오늘'을 사용한다.
        # aware datetime 이 들어오면 그 타임존의 벽시계 날짜를 그대로 쓴다
        # (manager 가 push_default_timezone 으로 normalize 해서 넘겨준다).
        current = now if now is not None else datetime.now(_DEFAULT_TZ)
        # 절기에 고정된 말씀이 있으면 그것을 먼저 쓴다. 목록에서 못 찾으면
        # (말씀 목록이 바뀐 경우) 조용히 평소 회전으로 넘어간다.
        item = None
        pinned = fixed_verse_id(current.date())
        if pinned:
            item = next((v for v in verses if v.get("verse_id") == pinned), None)
        if item is None:
            item = verses[current.toordinal() % len(verses)]
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


def _cache_key(verse: DailyVerse, lang: str) -> str:
    """풀이 캐시 키. verse_id 만으로는 부족하다.

    같은 verse_id 라도 본문이 바뀔 수 있다(합본 범위 조정, 서사 껍데기 제거 규칙 수정
    등). 그때 예전 본문으로 쓴 풀이가 새 본문에 그대로 붙어 나가면 조용히 어긋난다.
    실제로 목록을 457개로 교체할 때 `num-6-24` 가 민수기 6:24 에서 6:24-26(아론의
    축복 전체)으로 바뀌었다. 그래서 본문 지문을 키에 섞어 본문이 달라지면 캐시가
    저절로 무효가 되게 한다.
    """
    fingerprint = hashlib.sha256(verse.text.encode("utf-8")).hexdigest()[:8]
    if lang == "ko":
        return f"{verse.verse_id}:{fingerprint}"
    return f"{verse.verse_id}:{lang}:{fingerprint}"


class VerseInterpreter:
    """'오늘의 말씀 풀이'의 캐시 조회 → LLM 생성 → 폴백을 담당한다.

    generate_fn 은 (reference, text, lang) -> 풀이 문자열 을 반환하는 콜러블로,
    운영에서는 app.py 의 OpenAI 백엔드 함수를 주입한다(테스트에서는 mock 을 주입).
    어떤 경우에도 예외를 밖으로 던지지 않는다 — 풀이가 없어도 말씀은 항상 반환한다.
    """

    def __init__(
        self,
        store: VerseInterpretationStore,
        generate_fn: Callable[[str, str, str], str],
    ) -> None:
        self._store = store
        self._generate = generate_fn

    def interpret(self, verse: DailyVerse, lang: str = "ko") -> str:
        cache_key = _cache_key(verse, lang)
        try:
            cached = self._store.get(cache_key)
        except Exception:
            cached = ""
        if cached:
            return cached

        try:
            generated = self._generate(verse.reference, verse.text, lang)
            text = (generated or "").strip()
        except Exception:
            # 키 없음/네트워크/파싱 등 어떤 예외든 풀이 없이도 말씀은 반환한다.
            text = ""

        if not text:
            # 폴백은 캐시에 저장하지 않는다(다음 요청에서 LLM 을 재시도).
            return verse.reflection or ""

        try:
            self._store.set(cache_key, text)
        except Exception:
            # 캐시 저장 실패해도 생성된 풀이는 그대로 반환한다.
            pass
        return text
