"""Daily Verse 게시물 재료 — 영어 본문(앱과 같은 변환)·카피 파일·매니페스트 (이슈 #62).

- 영어 본문은 앱 `/daily-verse?lang=en` 과 같은 `languages.localize_ko_ref` 로 만든다(합본·하반절·절 경계
  차이·따옴표·첫 글자 정리가 거기 있다). 스토어는 git 의 CSV 로 만든다(서버의 parquet 와 같은 행).
- 카피는 `copy_en.json` — 말씀별 카드 라벨·강조 구절·훅·요청 줄·주제 해시태그·팔레트와 캐러셀 안쪽 장
  (장면 설명·그림). 앱 풀이 카드는 풀이 검토본을 그대로 싣는다. 세션에서 손으로 쓴다(API 로 만들지 않는다). 아직 없는 말씀은 게시하지 않고
  실행기가 준비된 다른 말씀을 고른다(dry-run 알림에 남은 준비 일수가 나온다).
- 매니페스트 `daily_posts_en.json` 은 말씀별 완성 재료(본문·캡션 조각·대체 텍스트·S3 키)다. 운영 서버는
  이 파일과 S3 이미지만 보고 게시한다 — 렌더도 임베딩도 하지 않는다.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from instagram.caption import build_alt_text, display_ref
from notifications.verse_provider import CURATED_INTL_PATH, intl_curated_key, text_fingerprint

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
COPY_JSON = HERE / "copy_en.json"
MANIFEST = HERE / "daily_posts_en.json"
DAILY_VERSES = BACKEND / "notifications" / "daily_verses.json"
KO_CSV = BACKEND / "data" / "verses.csv"
EN_CSV = BACKEND / "data" / "langs" / "en" / "verses.csv"
EN_INTL_TSV = BACKEND / "docs" / "verse_picks" / "interpretations_intl" / "en.tsv"
COPY_FIELDS = ("label", "emph", "hook", "cta", "topic", "pal")

_RE_REF = re.compile(r"^(.+?)\s+(\d+):(\d+)(?:-(\d+))?b?$")


def load_daily_verses(path: Path = DAILY_VERSES) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def en_note(verse_id: str, ko_text: str, intl: dict[str, str] | None = None) -> str:
    """앱의 영어 풀이 검토본(daily_interpretations_intl.json). 키는 한국어 카드 지문을 쓴다."""
    if intl is None:
        intl = json.loads(CURATED_INTL_PATH.read_text(encoding="utf-8"))
    return intl.get(intl_curated_key("en", verse_id, ko_text), "").strip()


# ── 영어 본문(앱과 같은 변환) ─────────────────────────────────────

def install_en_store(items: list[dict]) -> None:
    """languages 모듈에 ko·en 스토어를 CSV 로 끼운다(목록이 쓰는 장만 — 정렬에는 장 전체면 된다)."""
    import pandas as pd

    import languages

    chapters = set()
    for item in items:
        m = _RE_REF.match(item["reference"])
        if m:
            chapters.add((m.group(1), int(m.group(2))))
    coded = {(languages.KO_NAME_TO_CODE.get(b), c) for b, c in chapters}

    def read(path: Path, book_col: str, keep: set) -> "pd.DataFrame":
        with open(path, encoding="utf-8", newline="") as f:
            rows = [r for r in csv.DictReader(f) if (r[book_col], int(r["chapter"])) in keep]
        return pd.DataFrame(rows).astype({"chapter": int, "verse": int})

    languages._stores.clear()
    languages._ko_last_verses = None
    languages.register_ko_store(read(KO_CSV, "book", chapters), None)
    languages._stores["en"] = languages.VerseStore("en", read(EN_CSV, "book_code", coded), None)


def recorded_en_refs() -> dict[str, str]:
    """영어 풀이 검토본 TSV 의 {한국어 참조: 영어 참조} — 풀이를 쓸 때 본 절(테스트가 정렬 정답과 맞춰 둔다)."""
    out = {}
    for line in EN_INTL_TSV.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            parts = line.split("\t")
            if len(parts) >= 3:
                out[parts[0]] = parts[2]
    return out


def localize_all(items: list[dict]) -> dict[str, dict]:
    """{verse_id: {"ref": 앱 참조, "text": 앱 본문}}. 실패나 풀이 기록과 어긋남이 있으면 예외.

    임베딩 모델 없이 돈다. 영어에서 장 마지막 절 번호가 한국어와 달라 앱이 임베딩으로 고르는 곳은
    로마서 14:10·요한삼서 1:2·1:11 셋뿐이고, 셋 다 사람이 확인한 정답이 「같은 번호 절」이다
    (tests/test_languages.py REVIEWED_OFFSETS — 실제 모델로도 그 답이 나오는지 REAL_ENCODER_TEST 가 본다).
    임베더가 없으면 localize_ko_ref 가 같은 번호 절을 고르므로 결과가 같다. 혹시 어긋나면 아래 풀이 기록
    대조(같은 정답으로 테스트됨)가 잡는다.
    """
    from languages import localize_ko_ref

    install_en_store(items)
    recorded = recorded_en_refs()
    out, problems = {}, []
    for item in items:
        found = localize_ko_ref("en", item["reference"], item["text"])
        if not found:
            problems.append(f"{item['reference']}: 현지화 실패")
            continue
        want = recorded.get(item["reference"])
        if want and want != found["ref"]:
            problems.append(f"{item['reference']}: {found['ref']} ≠ 풀이 기록 {want}")
        out[item["verse_id"]] = found
    if problems:
        raise RuntimeError("영어 변환 문제:\n  " + "\n  ".join(problems))
    return out


# ── 카피 파일 ─────────────────────────────────────────────────────

def load_copy(path: Path = COPY_JSON) -> dict[str, dict]:
    """copy_en.json — {verse_id: {label, emph, hook, cta, topic, pal, scene?}}."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    for vid, row in data.items():
        missing = [f for f in COPY_FIELDS if not str(row.get(f, "")).strip()]
        if missing:
            raise ValueError(f"{path.name} {vid}: 빈 칸 {missing}")
    return data


def tidy_copy(text: str) -> str:
    """곧은 따옴표를 둥근 것으로(런칭 카드 표기), 공백 정리."""
    text = " ".join((text or "").split())
    text = re.sub(r"(?<=\w)'(?=\w)", "’", text)
    text = re.sub(r"(^|[\s(])'", r"\1‘", text).replace("'", "’")
    text = re.sub(r'(^|[\s(])"', r"\1“", text).replace('"', "”")
    return text


# ── 매니페스트 ────────────────────────────────────────────────────

def image_key(name: str, digest: str) -> str:
    """S3 키. 내용 지문을 붙여 다시 렌더하면 새 키가 된다(받는 쪽 캐시에 옛 카드가 남지 않게).
    name 은 「{verse_id}-{장 번호}」 또는 「app」."""
    return f"cards/{name}-{digest[:10]}.jpg"


def card_text(text: str) -> str:
    """카드·캡션에 싣는 본문. 낱말은 WEB 그대로이고, 절이 문장 중간에서 끝나 쉼표·세미콜론으로 끝나면
    (목록 376개 중 11개, 예: 마태 6:28 「…neither do they spin,」) 그 부호만 말줄임표로 바꿔 문장이 이어짐을
    보인다 — 인용의 관례다. 카드가 쉼표로 끝나면 잘린 것처럼 보인다.
    """
    return re.sub(r"\s*[,;:]\s*$", "…", text.strip())


def manifest_entry(item: dict, en: dict, copy: dict, note: str) -> dict:
    ref = display_ref(en["ref"])
    text = card_text(en["text"])
    return {
        "ko_reference": item["reference"],
        "ko_fp": text_fingerprint(item["text"]),
        "ref": en["ref"],
        "display_ref": ref,
        "text": text,
        "kicker": copy["label"],
        "hook": copy["hook"],
        "cta": copy["cta"],
        "topic": copy["topic"],
        "note": note,
        "alt_text": build_alt_text(kicker=copy["label"], verse_text=text, ref=ref),
    }


def load_manifest(path: Path = MANIFEST) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
