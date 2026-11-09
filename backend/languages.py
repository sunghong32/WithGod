"""다국어 지원 — 언어별 성경 스토어 + 서버 언어 스위치 (이슈 #10 3단계).

언어별 데이터(data/langs/{lang}/)는 scripts/build_language_data.py 와
scripts/build_language_index.py 로 만든다. 서버에는 활성 언어만 lazy 로드하며,
FAISS 는 mmap 이라 메모리 압박 시 OS 가 페이지를 회수할 수 있다.

활성 언어 목록은 data/language_config.json 에 저장한다(app_version.json 과
같은 패턴 — gitignore 로 서버가 관리, 요청마다 읽어 재시작 없이 반영, 값 변경은
어드민 대시보드 POST /admin/languages).
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from analytics.routes import require_analytics_admin

log = logging.getLogger("with-god.languages")

router = APIRouter()

ROOT = Path(__file__).parent
LANG_DIR = ROOT / "data" / "langs"
CONFIG_PATH = ROOT / "data" / "language_config.json"

# 앱 i18n(WithGod/src/shared/lib/i18n)과 같은 8개. ko 는 항상 활성.
SUPPORTED_LANGUAGES = ("ko", "en", "es", "pt", "de", "fr", "it", "pl")
DEFAULT_ENABLED = ["ko"]

# 프롬프트 지시문용 언어 이름(영어) — 지시는 영어, 출력은 대상 언어가
# 소형 모델에서 언어 준수가 가장 안정적이다(이슈 #11).
LANGUAGE_NAMES_EN = {
    "ko": "Korean", "en": "English", "es": "Spanish", "pt": "Portuguese",
    "de": "German", "fr": "French", "it": "Italian", "pl": "Polish",
}

# '오늘의 말씀' — 푸시 제목·태그용. 앱 로케일(home.dailyVerseTitle)과 동일 문구.
DAILY_VERSE_TITLES = {
    "ko": "오늘의 말씀", "en": "Today's Verse", "es": "Versículo del día",
    "pt": "Versículo do dia", "de": "Vers des Tages", "fr": "Verset du jour",
    "it": "Versetto del giorno", "pl": "Werset dnia",
}

# 한국어 책 이름(운영 data/verses.csv 기준) ↔ USFM 3글자 코드.
# 언어 간 구절 정렬(/random 의 '오늘의 말씀' 동일 구절 제공)에 쓴다.
_KO_BOOKS = [
    "창세기", "출애굽기", "레위기", "민수기", "신명기", "여호수아", "사사기",
    "룻기", "사무엘상", "사무엘하", "열왕기상", "열왕기하", "역대상", "역대하",
    "에스라", "느헤미야", "에스더", "욥기", "시편", "잠언", "전도서", "아가",
    "이사야", "예레미야", "예레미야애가", "에스겔", "다니엘", "호세아", "요엘",
    "아모스", "오바댜", "요나", "미가", "나훔", "하박국", "스바냐", "학개",
    "스가랴", "말라기", "마태복음", "마가복음", "누가복음", "요한복음",
    "사도행전", "로마서", "고린도전서", "고린도후서", "갈라디아서", "에베소서",
    "빌립보서", "골로새서", "데살로니가전서", "데살로니가후서", "디모데전서",
    "디모데후서", "디도서", "빌레몬서", "히브리서", "야고보서", "베드로전서",
    "베드로후서", "요한일서", "요한이서", "요한삼서", "유다서", "요한계시록",
]
_CANON_CODES = [
    "GEN", "EXO", "LEV", "NUM", "DEU", "JOS", "JDG", "RUT", "1SA", "2SA",
    "1KI", "2KI", "1CH", "2CH", "EZR", "NEH", "EST", "JOB", "PSA", "PRO",
    "ECC", "SNG", "ISA", "JER", "LAM", "EZK", "DAN", "HOS", "JOL", "AMO",
    "OBA", "JON", "MIC", "NAM", "HAB", "ZEP", "HAG", "ZEC", "MAL",
    "MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH",
    "PHP", "COL", "1TH", "2TH", "1TI", "2TI", "TIT", "PHM", "HEB", "JAS",
    "1PE", "2PE", "1JN", "2JN", "3JN", "JUD", "REV",
]
KO_NAME_TO_CODE = dict(zip(_KO_BOOKS, _CANON_CODES))
_CODE_TO_KO_NAME = dict(zip(_CANON_CODES, _KO_BOOKS))


# ---------- 활성 언어 스위치 ----------

def get_enabled_languages() -> list[str]:
    enabled = list(DEFAULT_ENABLED)
    try:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            raw = data.get("enabled")
            if isinstance(raw, list):
                enabled = [l for l in raw if l in SUPPORTED_LANGUAGES]
    except Exception:
        log.exception("language_config.json 읽기 실패 — 기본값(ko) 사용")
    if "ko" not in enabled:
        enabled.insert(0, "ko")
    return enabled


def normalize_lang(raw: str | None) -> str:
    """지원 언어의 기본 서브태그로 정규화한다(활성 여부는 안 봄 — 저장용).

    기기 등록처럼 '사용자 의도'를 보존해야 하는 곳에 쓴다. 실제 서빙 시점에
    resolve_lang 으로 활성 여부를 다시 거른다(비활성이면 ko 폴백).
    """
    if not raw:
        return "ko"
    lang = raw.strip().lower().split("-")[0]
    return lang if lang in SUPPORTED_LANGUAGES else "ko"


def resolve_lang(raw: str | None) -> str:
    """요청 lang 을 활성 언어로 정규화한다. 미지원/비활성은 ko 로 폴백."""
    lang = normalize_lang(raw)
    if lang != "ko" and lang not in get_enabled_languages():
        return "ko"
    return lang


# ---------- 언어별 스토어 (lazy) ----------

class VerseStore:
    """언어 하나의 성경 데이터(df)와 FAISS 인덱스. 행 번호가 서로 1:1 대응."""

    def __init__(self, lang: str, df, index) -> None:
        self.lang = lang
        self.df = df
        self.index = index
        self._last_verses: dict[tuple[str, int], int] | None = None

    def chapter_last_verse(self, book_code: str, chapter: int) -> int | None:
        """(책, 장)의 마지막 절 번호 — 번역본 간 절번호 오프셋 계산용(캐시)."""
        if self._last_verses is None:
            self._last_verses = _last_verse_numbers(
                self.df["book_code"].tolist(), self.df["chapter"].tolist(),
                self.df["verse"].tolist(),
            )
        return self._last_verses.get((book_code, int(chapter)))

    def chapter_texts(self, book_code: str, chapter: int) -> dict[int, str]:
        """(책, 장)의 {절 번호: 본문} — 구절 정렬의 앞뒤 문맥용."""
        df = self.df
        m = df[(df["book_code"] == book_code) & (df["chapter"].astype(int) == int(chapter))]
        return {int(v): str(t) for v, t in zip(m["verse"], m["text"])}

    def find_verse(self, book_code: str, chapter: int, verse: int) -> dict | None:
        df = self.df
        m = df[
            (df["book_code"] == book_code)
            & (df["chapter"].astype(int) == int(chapter))
            & (df["verse"].astype(int) == int(verse))
        ]
        if m.empty:
            return None
        r = m.iloc[0]
        return {
            "book": str(r["book"]),
            "chapter": int(r["chapter"]),
            "verse": int(r["verse"]),
            "text": str(r["text"]),
        }

    def find_passage(
        self, book_code: str, chapter: int, first: int, last: int
    ) -> dict | None:
        """같은 장 first~last 절을 이어 붙인다. 한 절이라도 없으면 None(반쪽 합본 방지)."""
        verses = [self.find_verse(book_code, chapter, v) for v in range(first, last + 1)]
        if not verses or not all(verses):
            return None
        return {
            **verses[0],
            "last_verse": verses[-1]["verse"],
            "text": " ".join(v["text"] for v in verses),
        }


_stores: dict[str, VerseStore] = {}
_store_lock = Lock()
_store_failed_at: dict[str, float] = {}  # 로드 실패 부정 캐시(요청마다 디스크 재시도 방지)
_STORE_RETRY_SECONDS = 60.0
_ko_last_verses: dict[tuple[str, int], int] | None = None
_encoder = None  # app.py 가 주입하는 다국어 쿼리 임베더(model.encode)


def register_ko_store(df, index) -> None:
    """app.py 가 이미 로드한 한국어 df/인덱스를 스토어로 등록한다(중복 로드 방지)."""
    _stores["ko"] = VerseStore("ko", df, index)


def set_encoder(encode_fn) -> None:
    """구절 정렬의 내용 검증에 쓸 다국어 임베더를 주입한다(app.py 의 model.encode)."""
    global _encoder
    _encoder = encode_fn


def _load_lang_store(lang: str) -> VerseStore:
    import faiss
    import pandas as pd

    d = LANG_DIR / lang
    df = pd.read_parquet(
        d / "verses_meta.parquet",
        columns=["book_code", "book", "chapter", "verse", "text"],
    )
    try:
        index = faiss.read_index(
            str(d / "verses.faiss"), faiss.IO_FLAG_MMAP | faiss.IO_FLAG_READ_ONLY
        )
    except Exception:
        index = faiss.read_index(str(d / "verses.faiss"))
    log.info("verse store 로드: %s (%d절)", lang, len(df))
    return VerseStore(lang, df, index)


def get_store(lang: str) -> VerseStore:
    """언어 스토어 반환. 미로드면 lazy 로드, 실패하면 ko 로 폴백.

    로드 실패는 잠시 부정 캐시해(_STORE_RETRY_SECONDS) 데이터가 깨진 언어가
    켜져 있어도 요청마다 락+디스크 재시도로 서버가 느려지지 않게 한다.
    """
    store = _stores.get(lang)
    if store is not None:
        return store
    failed_at = _store_failed_at.get(lang)
    if failed_at is not None and time.monotonic() - failed_at < _STORE_RETRY_SECONDS:
        return _stores["ko"]
    with _store_lock:
        store = _stores.get(lang)
        if store is not None:
            return store
        try:
            store = _load_lang_store(lang)
            _stores[lang] = store
            _store_failed_at.pop(lang, None)
            return store
        except Exception:
            log.exception("verse store 로드 실패(%s) — ko 폴백", lang)
            _store_failed_at[lang] = time.monotonic()
            return _stores["ko"]


def _last_verse_numbers(codes, chapters, verses) -> dict[tuple[str, int], int]:
    last: dict[tuple[str, int], int] = {}
    for code, ch, v in zip(codes, chapters, verses):
        if code:
            key = (str(code), int(ch))
            last[key] = max(last.get(key, 0), int(v))
    return last


def _ko_last_verse_numbers() -> dict[tuple[str, int], int]:
    """한국어(≈KJV 절번호 체계) 기준 (책코드, 장) → 마지막 절 번호. 오프셋 기준점.

    절 수가 아니라 마지막 절 번호를 쓴다. 개역한글은 사본에 없는 절을 번호째 비워 둔다
    (막 9:44·46, 눅 17:36 의 「(없음)」, 앞 절에 합친 사 30:2 의 「(1절에 포함)」 등 15개 장). 절 수로 재면 이런 장이
    모든 언어에서 1~2절 밀린 것처럼 보여 임베딩으로 고르게 되지만, 번호는 그대로
    같다 — 같은 번호 절이 정답이다.
    """
    global _ko_last_verses
    if _ko_last_verses is None:
        ko = _stores["ko"].df
        _ko_last_verses = _last_verse_numbers(
            [KO_NAME_TO_CODE.get(str(b)) for b in ko["book"].tolist()],
            ko["chapter"].tolist(), ko["verse"].tolist(),
        )
    return _ko_last_verses


# 한국어 시편 1절 본문 앞의 표제 「(다윗의 시. 영장으로 한 노래)」. LSG 는 표제를 따로
# 1~2절로 세므로, 문맥으로 비교할 때 붙여 두면 표제 절과 엮여 오프셋을 잘못 고른다.
_RE_KO_TITLE = re.compile(r"^\([^)]*\)\s*")


def _ko_chapter_texts(book_code: str, chapter: int) -> dict[int, str]:
    """한국어 (책코드, 장)의 {절 번호: 본문}(표제 제외) — 구절 정렬의 앞뒤 문맥용."""
    ko = _stores["ko"].df
    name = _CODE_TO_KO_NAME.get(book_code)
    m = ko[(ko["book"] == name) & (ko["chapter"].astype(int) == int(chapter))]
    return {int(v): _RE_KO_TITLE.sub("", str(t)) for v, t in zip(m["verse"], m["text"])}


# 임베딩 내용 검증에서 이 코사인 미만이면 정렬 실패로 본다(전혀 다른 구절 방지).
# e5 계열의 언어 간 동일-구절 유사도는 통상 0.8 이상이다.
_ALIGN_MIN_SCORE = 0.7

# 후보를 고를 때 오늘의 말씀 앞뒤로 함께 비교하는 절 수(한쪽).
_ALIGN_CONTEXT = 2

# 한국어 한 절이 외국어 두 절에 걸치는 곳(#53) — (언어, 책, 장, 한국어 절) → 외국어에서 뒤로 더
# 붙일 절 수. 언어 None 은 모든 외국어. 정렬로 오프셋을 정한 뒤 그 창의 끝을 늘린다.
# 한 절만 고르면 뒤 절 내용이 빠진다(fr 막 9:50 은 카드의 요점 「서로 화목하라」가 9:51 에 있다).
_KO_VERSE_SPANS: dict[tuple[str | None, str, int, int], int] = {
    # 개역한글이 두 절을 한 절로 합친 곳. 공식 본문도 뒤 절은 「(1절에 포함되어 있음)」이라
    # verses.csv 에 그 행이 없다(공회 본문 대조, 7개 언어 모두 뒤 절이 이어지는 내용).
    (None, "PSA", 72, 19): 1,  # 20절 「이새의 아들 다윗의 기도가 필하다」
    (None, "ISA", 30, 1): 1,
    (None, "ISA", 48, 1): 1,
    (None, "JER", 21, 1): 1,
    (None, "EZK", 24, 4): 1,
    (None, "ACT", 15, 25): 1,
    (None, "ROM", 9, 1): 1,
    # 개역한글 고후 13:11 끝 「거룩하게 입맞춤으로 서로 문안하라」= 영어식 절 체계의 13:12.
    # es·fr 는 그 말이 「모든 성도가 문안하느니라」(한국어 13:12)와 한 절이라 늘리지 않는다.
    **{(lang, "2CO", 13, 11): 1 for lang in ("en", "pt", "de", "it", "pl")},
    # fr(LSG)가 한국어 한 절을 두 절로 나눈 곳
    ("fr", "MRK", 9, 50): 1,   # 9:51 「Ayez du sel en vous-mêmes, et soyez en paix…」
    ("fr", "1KI", 22, 43): 1,  # 22:44 「Seulement, les hauts lieux ne disparurent point…」
}


def ko_verse_span(lang: str, book_code: str, chapter: int, verse: int) -> int:
    """한국어 절 하나가 lang 에서 뒤로 몇 절 더 걸치는지(대개 0)."""
    key = (book_code, int(chapter), int(verse))
    return _KO_VERSE_SPANS.get((lang, *key), _KO_VERSE_SPANS.get((None, *key), 0))


def find_aligned_verse(
    lang: str,
    book_code: str,
    chapter: int,
    verse: int,
    ko_text: str | None = None,
    last_verse: int | None = None,
) -> dict | None:
    """한국어 기준 (책, 장, 절)에 해당하는 다른 언어 구절을 찾는다.

    장 마지막 절 번호 차이(±1~3)는 두 가지 상반된 원인이 있어 번호만으로는 판별 불가:
    - LSG(fr) 시편처럼 표제가 절 번호를 차지 → 그만큼 밀어야 맞음 (30:5→30:6)
    - 장 끝에서 절을 나눈 번역본(fr 전도서 4:17 = 한국어 5:1) → 밀면 엉뚱한 구절이 됨
    그래서 후보(verse+0 … verse+차이, 차이가 음수면 verse+차이 … verse+0)를 모두 뽑아
    **다국어 임베딩으로 내용을 대조**한다. 한국어 한 절이 그 언어 두 절에 걸치는 곳은
    `_KO_VERSE_SPANS` 로 창 끝을 늘린다(#53).
    이 함수는 '오늘의 말씀' 현지화에만 쓰이고(/random 은 하루·언어당 1회 캐시, /daily-verse
    ·푸시는 부를 때마다) 한 번에 짧은 절 10여 개를 임베딩하므로 비용은 작다.

    대조는 **앞뒤 _ALIGN_CONTEXT 절까지 묶어서** 한다. 오프셋 k 후보의 점수는 「카드 ↔
    후보」와 「한국어 앞뒤 절 n ↔ 그 언어 n+k 절」 코사인의 평균이다. 카드 한 절만 비교하면
    e5 의 언어 간 코사인이 0.8 언저리에 몰려 이웃 절과 0.01 안쪽으로 붙는다 — fr 시편
    42:11 이 42:11(0.843, 원수의 조롱)을 골랐다(정답 42:12, 0.834, #33). 마지막 절 번호가
    다른 92개 장(언어·장 쌍)의 모든 절 1,614개를 정답과 맞춰 보면 한 절 비교는 114개(7%)를
    틀리고 앞뒤 2절 창은 2개(고후 13:12 — 그 절에서 오프셋이 바뀌는 데다 두 후보가 모두
    「문안」)만 틀린다. 접두어는 양쪽 모두 「query: 」(e5 안내: 대칭 과제는 query 끼리) —
    같은 비교에서 query↔passage 보다 오답이 적다(7 → 2).

    last_verse 를 주면 같은 장 verse~last_verse 합본을 **한 덩어리로** 찾는다.
    후보도 같은 오프셋의 창(verse+k ~ last_verse+k)을 이어 붙여 만든다. 절마다
    따로 정렬하면 합본 전체인 ko_text 를 한 절과 비교하게 돼 점수가 뒤집힌다 —
    fr 시편 40:1-2 가 40:2 를 두 번 고른다(정답은 40:2-3). 반환 dict 의
    verse·last_verse 는 그 언어의 절 번호, text 는 이어 붙인 본문이다.
    """
    last = int(verse) if last_verse is None else int(last_verse)
    store = get_store(lang)
    if store.lang != lang:  # 로드 실패로 ko 폴백된 경우
        return None
    # 마지막 한국어 절이 그 언어 두 절에 걸치면 창 끝을 늘린다(#53).
    extra = ko_verse_span(lang, book_code, chapter, last)
    diff = 0
    ref_last = _ko_last_verse_numbers().get((book_code, int(chapter)))
    lang_last = store.chapter_last_verse(book_code, int(chapter))
    if ref_last and lang_last:
        diff = lang_last - ref_last

    # 그 언어의 장이 더 짧아도(diff < 0) 앞 장 끝으로 절이 넘어간 판본이 있다 — fr(LSG) 이사야 8:23 =
    # 한국어 9:1, 전도서 4:17 = 한국어 5:1 이라 한국어 9:2·5:2 는 그 언어 9:1·5:1 이다. 번호로만
    # 찾으면 한 절 뒤 내용이 나간다. 그래서 양쪽 모두 후보(0 … diff)를 뽑아 내용으로 고른다.
    if diff == 0 or abs(diff) > 3 or not ko_text or _encoder is None:
        return store.find_passage(book_code, chapter, verse, last + extra)

    candidates = {}
    for off in range(min(0, diff), max(0, diff) + 1):
        found = store.find_passage(book_code, chapter, verse + off, last + off + extra)
        if found:
            candidates[off] = found
    if not candidates:
        return None
    if len(candidates) == 1:
        return next(iter(candidates.values()))

    try:
        ko_verses = _ko_chapter_texts(book_code, chapter)
        lang_verses = store.chapter_texts(book_code, chapter)
        around = [
            *range(int(verse) - _ALIGN_CONTEXT, int(verse)),
            *range(last + 1, last + 1 + _ALIGN_CONTEXT),
        ]
        # 오프셋마다 비교할 (한국어, 그 언어) 쌍 — 첫 쌍이 카드 ↔ 후보. 뒤 문맥은 늘린 창(extra) 다음부터.
        def lang_n(n: int, off: int) -> int:
            return n + off + (extra if n > last else 0)

        pairs = {
            off: [(_RE_KO_TITLE.sub("", ko_text), found["text"])]
            + [(ko_verses[n], lang_verses[lang_n(n, off)])
               for n in around if n in ko_verses and lang_n(n, off) in lang_verses]
            for off, found in candidates.items()
        }
        texts = list(dict.fromkeys(t for ps in pairs.values() for pair in ps for t in pair))
        vecs = _encoder([f"query: {t}" for t in texts])
        row = {t: i for i, t in enumerate(texts)}

        def cos(a: str, b: str) -> float:  # 임베딩이 정규화돼 있어 내적 = 코사인
            return float(vecs[row[a]] @ vecs[row[b]])

        scores = {off: sum(cos(a, b) for a, b in ps) / len(ps) for off, ps in pairs.items()}
        ranked = sorted(scores, key=scores.get, reverse=True)
        best, runner_up = ranked[0], ranked[1]
        score = cos(*pairs[best][0])
        log.info(
            "verse align %s %s %s:%s → +%d (창 %.3f, 차점 +%d %.3f, cos=%.3f)",
            lang, book_code, chapter,
            verse if last == int(verse) else f"{verse}-{last}",
            best, scores[best], runner_up, scores[runner_up], score,
        )
        if score < _ALIGN_MIN_SCORE:
            return None  # 내용이 안 맞으면 호출측이 ko 본문으로 폴백한다
        return candidates[best]
    except Exception:
        log.exception("verse align 실패(%s) — 같은 번호 절로 폴백", lang)
        return store.find_passage(book_code, chapter, verse, last)


# ---------- 외국어 절 표시 정리 (#51·#52) ----------
#
# 외국어 판본은 문장·인용이 절을 넘나든다. 「God said, “Let there be lights …」(창 1:14)의
# 인용은 1:15 에서 닫히고, 이탈리아어 이사야 29:24 는 29:23 의 문장을 이어 소문자로 시작한다.
# 절 하나(또는 합본)만 떼어 카드·푸시·위젯·검색 결과로 보여 주면 짝 없는 따옴표와 소문자
# 첫 글자가 그대로 나간다. 원본 CSV·인덱스는 그대로 두고(검색·정렬은 원문으로) 내보내는
# 곳에서만 정리한다. 한국어(개역한글)는 대소문자가 없고 이 따옴표 체계도 아니라 건드리지 않는다.

# 큰따옴표 여는 것 → 닫는 것. 이 데이터의 en·pt·de·it 는 “ ”, pl 은 „ ” 를 쓴다(지금 de 도 „ “ 가
# 아니라 “ ” 지만, 독일어 표기 „ “ 가 들어와도 짝이 맞게 de 의 „ 는 “ 로 닫는다). 홑따옴표 ‘ ’ 는
# 닫는 ’ 가 아포스트로피와 같은 글자라 짝을 셀 수 없어 두고, 따옴표를 쓰지 않는 es·fr 는 그대로 나간다.
_QUOTE_CLOSE_OF = {"“": "”", "„": "”", "«": "»"}
_QUOTE_CLOSE_OF_DE = {**_QUOTE_CLOSE_OF, "„": "“"}
_QUOTE_CLOSERS = frozenset({"”", "»"})
# 첫 글자를 찾을 때 건너뛰는 앞쪽 문장부호
_LEADING_PUNCT = frozenset(" \t\"'“„«‘(¿¡[")
# 이탈리아어 본문은 닫는 따옴표를 끝 문장부호 앞에 둔다(「…quello che t’ho detto”.」).
_CLOSE_BEFORE_FINAL_PUNCT = frozenset({"it"})


def _balance_quotes(text: str, lang: str) -> str:
    """앞 절에서 열린 인용을 닫는 따옴표는 떼고, 다음 절로 이어지는 인용은 끝에서 닫는다."""
    close_of = _QUOTE_CLOSE_OF_DE if lang == "de" else _QUOTE_CLOSE_OF
    kept: list[str] = []
    # 아직 안 닫힌 인용 — (닫는 따옴표, kept 안의 여는 따옴표 위치), 안쪽이 뒤
    pending: list[tuple[str, int]] = []
    removed = False
    i = 0
    while i < len(text):
        ch = text[i]
        i += 1
        if pending and ch == pending[-1][0]:
            pending.pop()
        elif ch in close_of:
            pending.append((close_of[ch], len(kept)))
        elif ch in _QUOTE_CLOSERS:
            if pending:  # 짝이 다른 닫는 따옴표 — 열린 인용을 닫는 것으로 본다
                pending.pop()
            else:  # 앞 절에서 열린 인용을 닫는 따옴표 — 뗀다
                removed = True
                # 겹인용을 함께 닫던 ’ 도 뗀다 — 안쪽(「…bury her.’” Then」)이든 바깥쪽
                # (「…all that you have.”’」)이든. 문장부호 바로 뒤의 ’ 는 아포스트로피일 수 없다.
                if len(kept) >= 2 and kept[-1] == "’" and kept[-2] in ".,;:!?":
                    kept.pop()
                elif text[i:i + 1] == "’" and kept and kept[-1] in ".,;:!?" and text[i + 1:i + 2] in ("", " "):
                    i += 1
                continue
        kept.append(ch)

    def rstrip_kept() -> None:
        while kept and kept[-1].isspace():
            kept.pop()

    # 끝에서 막 연 인용 — 빈 따옴표 대신 뗀다. 다음 절로 넘어가는 겹인용의 ‘ 도
    # (「…will not change his mind, ‘」) 닫는 따옴표 앞에 매달리지 않게 뗀다.
    rstrip_kept()
    while kept and (kept[-1] == "‘" or (pending and pending[-1][1] == len(kept) - 1)):
        if pending and pending[-1][1] == len(kept) - 1:
            pending.pop()
        kept.pop()
        rstrip_kept()
    out = "".join(kept)
    if removed:
        out = re.sub(r" {2,}", " ", out).strip()
    if pending:
        closers = "".join(c for c, _ in reversed(pending))
        if lang in _CLOSE_BEFORE_FINAL_PUNCT and out and out[-1] in ".;:,":
            out = out[:-1] + closers + out[-1]
        else:
            out += closers
    return out


def _capitalize_first(text: str) -> str:
    for i, ch in enumerate(text):
        if ch in _LEADING_PUNCT:
            continue
        up = ch.upper()
        if ch.islower() and len(up) == 1:
            return text[:i] + up + text[i + 1:]
        return text
    return text


def tidy_verse_text(text: str, lang: str) -> str:
    """외국어 절을 한 장의 카드로 내보낼 때의 표시 정리 — 짝 없는 따옴표(#51)·소문자 첫 글자(#52)."""
    if lang == "ko" or not text:
        return text
    return _capitalize_first(_balance_quotes(str(text), lang))


# 「시편 23:1」 · 합본 「시편 40:1-2」(같은 장) · 하반절 「요한복음 8:11b」.
# 둘이 겹친 「…:1-2b」도 받는다(scripts/build_verse_cards.py 가 만들 수 있는 꼴).
_RE_KO_REF = re.compile(r"^(.+?)\s+(\d+):(\d+)(?:-(\d+))?b?$")


def localize_ko_ref(lang: str, ko_ref: str, ko_text: str) -> dict | None:
    """'시편 23:1' 같은 한국어 ref 를 해당 언어의 같은 구절로 바꾼다.

    /random 오늘의 말씀·푸시·위젯이 공용으로 쓴다. 실패(파싱 불가·판본 차이로
    정렬 불가) 시 None — 호출측은 한국어 본문으로 폴백한다.

    합본(40:1-2)은 범위의 절을 이어 붙이고 ref 도 그 언어 절 번호로 「장:시작-끝」.
    하반절(8:11b)은 **절 전체**를 싣고 ref 에서 b 를 뗀다. 한국어의 b 는 「예수께서
    가라사대」 같은 서사만 벗긴 표기인데(docs/오늘의말씀_재선정.md), 번역본마다
    인용 표기가 달라(따옴표·콜론·표기 없음) 같은 자르기를 규칙으로 옮길 수 없다.
    """
    m = _RE_KO_REF.match(ko_ref.strip())
    if not m:
        return None
    code = KO_NAME_TO_CODE.get(m.group(1))
    if not code:
        return None
    first = int(m.group(3))
    last = int(m.group(4)) if m.group(4) else first
    if last < first:
        return None
    found = find_aligned_verse(
        lang, code, int(m.group(2)), first, ko_text, last_verse=last
    )
    if not found:
        return None
    ref = f"{found['book']} {found['chapter']}:{found['verse']}"
    if found["last_verse"] != found["verse"]:
        ref += f"-{found['last_verse']}"
    return {"ref": ref, "text": tidy_verse_text(found["text"], lang)}


# ---------- 추천 적합성 필터 ----------

# 저지 검증(이슈 #11)이 확정했지만 자동 분류가 놓친 구절 + 같은 단락의 명백한
# 이웃 절. 분류기를 재실행해도 유지되도록 코드에 둔다.
_CURATED_UNSUITABLE = {
    # 잠언 7:13-21 — 유혹하는 여인의 대사(경건해 보이는 7:14 포함)
    *(f"PRO 7:{v}" for v in range(13, 22)),
    # 이사야 63:1-6 — 포도주틀 심판 신탁
    *(f"ISA 63:{v}" for v in range(1, 7)),
    # 이사야 43:22-28 — 언약 소송의 책망(43:24 가 위로 카드로 검색된 사례)
    *(f"ISA 43:{v}" for v in range(22, 29)),
    # 예레미야 8:10-12 — 거짓 평강 규탄
    *(f"JER 8:{v}" for v in range(10, 13)),
    "GEN 27:7",    # 야곱의 속임 서사 중 한 절
    "PRO 24:33", "PRO 24:34",  # 게으름뱅이 경고(빈궁이 강도같이 오리라)
    "PHP 1:23",    # '떠나는 것이 더 낫다' — 우울·고립 사용자에게 위험
}

_unsuitable_refs: set[str] | None = None


def _load_unsuitable() -> set[str]:
    """scripts/classify_verse_suitability.py 산출물. 없으면 필터 없이 동작."""
    global _unsuitable_refs
    if _unsuitable_refs is None:
        try:
            data = json.loads(
                (LANG_DIR / "unsuitable_refs.json").read_text(encoding="utf-8")
            )
            _unsuitable_refs = set(data.get("unsuitable", [])) | _CURATED_UNSUITABLE
            log.info("추천 부적합 절 %d개 로드", len(_unsuitable_refs))
        except FileNotFoundError:
            _unsuitable_refs = set(_CURATED_UNSUITABLE)
        except Exception:
            log.exception("unsuitable_refs.json 로드 실패 — 큐레이션 목록만 사용")
            _unsuitable_refs = set(_CURATED_UNSUITABLE)
    return _unsuitable_refs


def is_recommendable(book_code: str | None, chapter, verse) -> bool:
    """위로 카드로 부적합한 절(심판 신탁·족보·악인의 대사 등)인지 검사.

    좌표는 KJV식(영어 기준). 절번호가 밀리는 일부 장(fr 시편)에서는 어긋날 수
    있으나 부적합 범주는 시편 밖에 몰려 있어 실용적으로 무해하다(이슈 #11).
    """
    if not book_code:
        return True
    return f"{book_code} {int(chapter)}:{int(verse)}" not in _load_unsuitable()


# 본문 대신 자리표시만 든 절. 공회가 앞 절에 묶은 절(신명기 6:18-19 → 6:19 「(18절과 같음)」,
# 시편 92:1-3 → 92:2·3 「(앞절과 동일)」)과 사본에 없는 절(마태복음 17:21 「(없 음)」)이다.
# 행에 벡터가 있어 질문에 따라 검색 후보로 걸린다. 괄호로 감싼 진짜 본문(요한복음 4:2)은 아니다.
_PLACEHOLDER = re.compile(r"\(\s*(?:\d+\s*절과\s*같음|앞\s*절과\s*동일|없\s*음)\s*\)")


def is_placeholder_text(text) -> bool:
    """「(18절과 같음)」·「(앞절과 동일)」·「(없음)」처럼 본문이 없는 절인지."""
    return bool(_PLACEHOLDER.fullmatch(str(text).strip()))


def collect_candidates(store: VerseStore, scores, ids, top_k: int) -> list[dict]:
    """FAISS 결과에서 위로 부적합 절(심판 신탁·족보·악인의 대사 등)을 걸러
    상위 top_k 후보를 만든다. 전부 걸러지는 극단엔 부적합 필터 없이 폴백한다.
    본문이 없는 자리표시 절은 폴백에서도 뺀다. 외국어 본문은 표시용으로 정리한다(#51·#52)."""
    def card(s, r) -> dict:
        return {
            "ref": f"{r['book']} {int(r['chapter'])}:{int(r['verse'])}",
            "text": tidy_verse_text(str(r["text"]), store.lang),
            "score": float(s),
        }

    cands: list[dict] = []
    dropped = 0
    for s, i in zip(scores, ids):
        r = store.df.iloc[int(i)]
        if is_placeholder_text(r["text"]):
            dropped += 1
            continue
        code = (
            str(r["book_code"]) if "book_code" in r.index
            else KO_NAME_TO_CODE.get(str(r["book"]))
        )
        if not is_recommendable(code, r["chapter"], r["verse"]):
            dropped += 1
            continue
        cands.append(card(s, r))
        if len(cands) >= top_k:
            break
    if dropped:
        log.info("추천 후보에서 부적합 절 %d개 제외", dropped)
    if not cands:
        for s, i in zip(scores, ids):
            r = store.df.iloc[int(i)]
            if is_placeholder_text(r["text"]):
                continue
            cands.append(card(s, r))
            if len(cands) >= top_k:
                break
    return cands


# ---------- 라우터 ----------

@router.get("/languages", tags=["app"])
def get_languages() -> dict[str, list[str]]:
    """클라이언트 언어 게이트용 — 서버가 켜 둔 언어 목록."""
    return {"supported": list(SUPPORTED_LANGUAGES), "enabled": get_enabled_languages()}


class LanguagesUpdate(BaseModel):
    enabled: list[str] = Field(..., examples=[["ko", "en", "es", "pt"]])


@router.post(
    "/admin/languages",
    dependencies=[Depends(require_analytics_admin)],
    tags=["app"],
)
def update_languages(payload: LanguagesUpdate) -> dict[str, list[str]]:
    """어드민 대시보드에서 활성 언어를 갱신한다. ko 는 항상 포함된다."""
    unknown = [l for l in payload.enabled if l not in SUPPORTED_LANGUAGES]
    if unknown:
        raise HTTPException(status_code=422, detail=f"지원하지 않는 언어: {unknown}")
    enabled = [l for l in SUPPORTED_LANGUAGES if l in payload.enabled or l == "ko"]
    missing = [
        l for l in enabled
        if l != "ko" and not (
            (LANG_DIR / l / "verses.faiss").exists()
            and (LANG_DIR / l / "verses_meta.parquet").exists()
        )
    ]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"서버에 인덱스가 없는 언어: {missing} — 먼저 데이터를 업로드하세요",
        )
    # 원자적 쓰기 — 갱신 순간 다른 요청이 잘린 JSON 을 읽지 않도록 한다.
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps({"enabled": enabled}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, CONFIG_PATH)
    return {"supported": list(SUPPORTED_LANGUAGES), "enabled": enabled}
