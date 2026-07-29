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


def resolve_lang(raw: str | None) -> str:
    """요청 lang 을 활성 언어로 정규화한다. 미지원/비활성은 ko 로 폴백."""
    if not raw:
        return "ko"
    lang = raw.strip().lower().split("-")[0]
    if lang in SUPPORTED_LANGUAGES and lang in get_enabled_languages():
        return lang
    return "ko"


# ---------- 언어별 스토어 (lazy) ----------

class VerseStore:
    """언어 하나의 성경 데이터(df)와 FAISS 인덱스. 행 번호가 서로 1:1 대응."""

    def __init__(self, lang: str, df, index) -> None:
        self.lang = lang
        self.df = df
        self.index = index
        self._chapter_counts: dict[tuple[str, int], int] | None = None

    def chapter_verse_count(self, book_code: str, chapter: int) -> int | None:
        """(책, 장)의 절 수 — 번역본 간 절번호 오프셋 계산용(캐시)."""
        if self._chapter_counts is None:
            counts: dict[tuple[str, int], int] = {}
            codes = self.df["book_code"].tolist()
            chapters = self.df["chapter"].tolist()
            for code, ch in zip(codes, chapters):
                key = (str(code), int(ch))
                counts[key] = counts.get(key, 0) + 1
            self._chapter_counts = counts
        return self._chapter_counts.get((book_code, int(chapter)))

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


_stores: dict[str, VerseStore] = {}
_store_lock = Lock()
_store_failed_at: dict[str, float] = {}  # 로드 실패 부정 캐시(요청마다 디스크 재시도 방지)
_STORE_RETRY_SECONDS = 60.0
_ko_chapter_counts: dict[tuple[str, int], int] | None = None
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


def _ko_counts() -> dict[tuple[str, int], int]:
    """한국어(≈KJV 절번호 체계) 기준 (책코드, 장) → 절 수. 오프셋 기준점."""
    global _ko_chapter_counts
    if _ko_chapter_counts is None:
        ko = _stores["ko"].df
        counts: dict[tuple[str, int], int] = {}
        books = ko["book"].tolist()
        chapters = ko["chapter"].tolist()
        for book, ch in zip(books, chapters):
            code = KO_NAME_TO_CODE.get(str(book))
            if code:
                key = (code, int(ch))
                counts[key] = counts.get(key, 0) + 1
        _ko_chapter_counts = counts
    return _ko_chapter_counts


# 임베딩 내용 검증에서 이 코사인 미만이면 정렬 실패로 본다(전혀 다른 구절 방지).
# e5 계열의 언어 간 동일-구절 유사도는 통상 0.8 이상이다.
_ALIGN_MIN_SCORE = 0.7


def find_aligned_verse(
    lang: str, book_code: str, chapter: int, verse: int, ko_text: str | None = None
) -> dict | None:
    """한국어 기준 (책, 장, 절)에 해당하는 다른 언어 구절을 찾는다.

    장 절수 차이(1~3)는 두 가지 상반된 원인이 있어 번호만으로는 판별 불가:
    - LSG(fr) 시편처럼 표제가 절 번호를 차지 → 그만큼 밀어야 맞음 (30:5→30:6)
    - 장 끝 차이/한국어 데이터 결손(시편 16 등) → 밀면 엉뚱한 구절이 됨
    그래서 후보(verse+0 … verse+차이)를 모두 뽑아 **다국어 임베딩으로 한국어
    본문과 내용을 대조**해 가장 유사한 절을 고른다. 이 함수는 '오늘의 말씀'
    현지화(하루·언어당 1회, 캐시됨)에만 쓰여 임베딩 비용은 무시할 수준이다.
    """
    store = get_store(lang)
    if store.lang != lang:  # 로드 실패로 ko 폴백된 경우
        return None
    diff = 0
    ref_count = _ko_counts().get((book_code, int(chapter)))
    lang_count = store.chapter_verse_count(book_code, int(chapter))
    if ref_count and lang_count:
        diff = lang_count - ref_count

    if diff <= 0 or diff > 3 or not ko_text or _encoder is None:
        return store.find_verse(book_code, chapter, verse)

    candidates = []
    for off in range(diff + 1):
        found = store.find_verse(book_code, chapter, verse + off)
        if found:
            candidates.append(found)
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    try:
        q = _encoder([f"query: {ko_text}"])
        p = _encoder([f"passage: {c['text']}" for c in candidates])
        sims = (q @ p.T)[0]  # 임베딩이 정규화돼 있어 내적 = 코사인
        best = int(sims.argmax())
        score = float(sims[best])
        log.info(
            "verse align %s %s %s:%s → +%d (cos=%.3f)",
            lang, book_code, chapter, verse,
            candidates[best]["verse"] - int(verse), score,
        )
        if score < _ALIGN_MIN_SCORE:
            return None  # 내용이 안 맞으면 호출측이 ko 본문으로 폴백한다
        return candidates[best]
    except Exception:
        log.exception("verse align 실패(%s) — 같은 번호 절로 폴백", lang)
        return store.find_verse(book_code, chapter, verse)


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
