r"""eBible USFM → 언어별 verses.csv 변환 (다국어 파이프라인 1단계, 이슈 #10).

한국어 data/verses.csv 와 같은 스키마로 각 언어의 성경 전문을 뽑는다.
소스는 전부 eBible.org 의 재배포 가능(퍼블릭 도메인/자유 라이선스) 번역본.

    python scripts/build_language_data.py --all          # 7개 언어 생성
    python scripts/build_language_data.py --lang en      # 한 언어만
    python scripts/build_language_data.py --golden-test  # kor 파싱 ↔ 기존 CSV 대조

출력: data/langs/{lang}/verses.csv (book_code,book,chapter,verse,text)
- book_code: USFM 표준 3글자 코드(GEN, PSA, JHN …) — 언어 간 구절 정렬용
- book: 해당 언어의 책 이름(\toc2, 없으면 \h) — 사용자 표시용
"""

from __future__ import annotations

import argparse
import csv
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data_raw"
OUT_DIR = ROOT / "data" / "langs"

# eBible translationId. 선정 기준: 재배포 가능 + 신구약 완역 + 해당 언어권에서
# 신뢰받는 판본(2026-07 translations.csv 로 확인).
LANGS = {
    "en": "engwebp",    # World English Bible (현대 영어, PD)
    "es": "spaRV1909",  # Reina-Valera 1909 (PD)
    "pt": "porbr2018",  # Bíblia Livre (Almeida 계열 현대어, PD)
    "de": "deu1912",    # Lutherbibel 1912 (PD)
    "fr": "fraLSG",     # Louis Segond 1910 (PD)
    "it": "ita1927",    # Riveduta 1927 (PD)
    "pl": "polubg",     # Uwspółcześniona Biblia Gdańska (자유 배포)
}
KOR_ID = "kor"  # 골든 테스트용(기존 data/verses.csv 의 원본)

# 개신교 정경 66권, 정경 순서. USFM 파일 순서가 아니라 이 순서로 출력한다.
CANON = [
    "GEN", "EXO", "LEV", "NUM", "DEU", "JOS", "JDG", "RUT", "1SA", "2SA",
    "1KI", "2KI", "1CH", "2CH", "EZR", "NEH", "EST", "JOB", "PSA", "PRO",
    "ECC", "SNG", "ISA", "JER", "LAM", "EZK", "DAN", "HOS", "JOL", "AMO",
    "OBA", "JON", "MIC", "NAM", "HAB", "ZEP", "HAG", "ZEC", "MAL",
    "MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH",
    "PHP", "COL", "1TH", "2TH", "1TI", "2TI", "TIT", "PHM", "HEB", "JAS",
    "1PE", "2PE", "1JN", "2JN", "3JN", "JUD", "REV",
]

# 절 본문에 포함되는 문단/시가 마커 — 마커만 떼고 텍스트는 잇는다.
_FLOW = {"p", "m", "pi", "mi", "nb", "q", "q1", "q2", "q3", "q4", "qr", "qc",
         "li", "li1", "li2", "li3", "pc", "cls", "pm", "pmo", "pmc", "pmr",
         "ph", "ph1", "ph2", "b"}
# 절 본문이 아닌 라인 마커 — 라인 전체를 버린다(표제·머리말·장식).
_SKIP = {"id", "ide", "usfm", "sts", "rem", "h", "mt", "mt1", "mt2", "mt3",
         "cl", "cp", "cd", "d", "s", "s1", "s2", "s3", "sr", "r", "sp", "ms",
         "ms1", "ms2", "mr", "periph", "ib", "ie", "toc1", "toc2", "toc3",
         "toca1", "toca2", "toca3"}

_RE_LINE = re.compile(r"^\\(\S+)\s*(.*)$")
_RE_NOTE = re.compile(r"\\f\s.*?\\f\*|\\fe\s.*?\\fe\*|\\x\s.*?\\x\*", re.DOTALL)
# \w 단어|속성\w* → 단어 (중첩 \+w 포함)
_RE_WORD = re.compile(r"\\\+?w\s([^\\|]*)(?:\|[^\\]*)?\\\+?w\*")
# 남은 문자 마커(\add \wj \nd \em \+wh … ) 제거, 내용은 유지.
# 닫는 마커(\add*)는 마커만 지워 뒤 공백을 보존하고, 여는 마커(\add )는
# 구분자 공백까지 지운다 — 하나로 합쳐 \s? 를 쓰면 닫는 마커 뒤의 실제
# 단어 사이 공백까지 삼켜 단어가 붙어버린다(pl 23%가 그랬음, 이슈 #10).
_RE_CHAR = re.compile(r"\\\+?[a-z0-9]+\*|\\\+?[a-z0-9]+ ?")

# eBible 원본의 표기 결함/비일관 교정 (검증 워크플로 2026-07-29 발견).
BOOK_NAME_OVERRIDES = {
    "de": {"1CH": "1. Chronik"},  # 원본 오타 '1. Chonik'
    "it": {"JOS": "Giosuè"},  # 원본 'Giosué' — 본문 표기와 통일
    "es": {"MAT": "Mateo", "LUK": "Lucas"},  # 'San Mateo'만 San이 붙는 비일관
    "pl": {"JDG": "Sędziów", "DEU": "Powtórzonego Prawa"},  # 소유격 단독형으로 통일
}

# deu1912 는 독일식 대체 절번호를 본문에 [1:5]/[1b] 로 병기한다 — 표시 노이즈.
_RE_DE_ALTVERSE = re.compile(r"\[\d+[ab]?(?::\d+[ab]?)?\]\s*")


def _fix_pt(text: str) -> str:
    """porbr2018 원본의 조판 결함 교정 — 공백 누락이 원본에 그대로 있다.

    예: "senhor,o rei", "seguinte.O que", "sobrenomeTadeu" (전부 원본 확인).
    포르투갈어 단어는 어중 대문자가 없고 본문에 소수점·약어가 없어 안전하다.
    """
    text = re.sub(r"([,;:!?])([A-Za-zÀ-ÿ])", r"\1 \2", text)  # 쉼표류 뒤 공백
    text = re.sub(r"(\.)([A-ZÀ-Ö])", r"\1 \2", text)  # 문장 마침표 뒤 공백
    return re.sub(r"([a-zà-ÿ])([A-ZÀ-Ö])", r"\1 \2", text)  # 붙은 고유명사 분리


TEXT_OVERRIDES = {
    "de": lambda t: _RE_DE_ALTVERSE.sub("", t),
    "pt": _fix_pt,
}


def _clean(text: str) -> str:
    # 노트는 공백으로 치환 — LSG 등은 \x 상호참조가 앞뒤 공백 없이 끼어 있어
    # 빈 문자열로 지우면 단어가 붙는다("mal,\x…\x*à" → "mal,à"). 생긴 잉여
    # 공백은 마지막 정규화가 걷어내고, 노트가 구두점 바로 앞에 오는 경우만
    # 별도로 붙여준다(" ," → ",").
    text = _RE_NOTE.sub(" ", text)
    text = _RE_WORD.sub(r"\1", text)
    text = _RE_CHAR.sub("", text)
    text = " ".join(text.split())
    return re.sub(r" ([,.])", r"\1", text)


def parse_usfm(raw: str) -> tuple[str, str, list[tuple[int, int, str]]]:
    """USFM 한 파일(책 한 권) → (book_code, book_name, [(장, 절, 본문)])."""
    book_code = ""
    names: dict[str, str] = {}
    chapter = 0
    verse = 0
    buf: list[str] = []
    verses: list[tuple[int, int, str]] = []

    def flush() -> None:
        nonlocal buf
        if verse and buf:
            text = _clean(" ".join(buf))
            if text:
                verses.append((chapter, verse, text))
        buf = []

    for line in raw.splitlines():
        m = _RE_LINE.match(line.strip())
        if not m:
            if verse and line.strip():
                buf.append(line.strip())
            continue
        marker, rest = m.group(1), m.group(2)

        if marker == "id":
            book_code = rest.split()[0].upper() if rest.split() else ""
        elif marker in ("h", "toc2"):
            names[marker] = rest.strip()
        elif marker == "c":
            flush()
            verse = 0
            num = re.match(r"\d+", rest)
            chapter = int(num.group()) if num else chapter + 1
        elif marker == "v":
            flush()
            # "17" 또는 "17-18"(합절) — 합절은 첫 번호로 한 행을 만든다.
            num = re.match(r"(\d+)", rest)
            if not num:
                continue
            verse = int(num.group(1))
            buf.append(rest[num.end() :].lstrip("-0123456789").strip())
        elif marker in _FLOW:
            if verse and rest.strip():
                buf.append(rest.strip())
        elif marker in _SKIP:
            continue
        # 그 외 미지의 라인 마커는 본문 아님으로 간주하고 버린다.

    flush()
    return book_code, names.get("toc2") or names.get("h", book_code), verses


def build_language(lang: str, ebible_id: str) -> list[dict]:
    zip_path = RAW_DIR / f"{ebible_id}_usfm.zip"
    if not zip_path.exists():
        raise SystemExit(
            f"{zip_path} 없음 — 먼저 내려받으세요: "
            f"curl -o {zip_path} https://ebible.org/Scriptures/{ebible_id}_usfm.zip"
        )

    books: dict[str, tuple[str, list[tuple[int, int, str]]]] = {}
    with zipfile.ZipFile(zip_path) as zf:
        for name in sorted(zf.namelist()):
            if not name.lower().endswith((".usfm", ".sfm")):
                continue
            code, book_name, verses = parse_usfm(
                zf.read(name).decode("utf-8", errors="ignore")
            )
            if code in CANON and verses:
                books[code] = (book_name, verses)

    missing = [c for c in CANON if c not in books]
    if missing:
        raise SystemExit(f"[{lang}] 누락된 책: {missing}")

    name_fix = BOOK_NAME_OVERRIDES.get(lang, {})
    text_fix = TEXT_OVERRIDES.get(lang)
    rows = []
    for code in CANON:
        book_name, verses = books[code]
        book_name = name_fix.get(code, book_name)
        for chapter, verse, text in verses:
            if text_fix:
                text = " ".join(text_fix(text).split())
            rows.append(
                {"book_code": code, "book": book_name, "chapter": chapter,
                 "verse": verse, "text": text}
            )
    return rows


def write_csv(lang: str, rows: list[dict]) -> Path:
    out = OUT_DIR / lang / "verses.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["book_code", "book", "chapter", "verse", "text"])
        w.writeheader()
        w.writerows(rows)
    return out


def golden_test() -> None:
    """kor USFM을 이 파서로 돌려 기존 data/verses.csv 와 대조한다."""
    rows = build_language("ko", KOR_ID)
    old_path = ROOT / "data" / "verses.csv"
    with open(old_path, encoding="utf-8") as f:
        old = list(csv.DictReader(f))

    print(f"파서 결과 {len(rows)}절 vs 기존 {len(old)}절")
    old_map = {(r["book"], int(r["chapter"]), int(r["verse"])): r["text"] for r in old}
    new_map = {(r["book"], r["chapter"], r["verse"]): r["text"] for r in rows}

    only_old = set(old_map) - set(new_map)
    only_new = set(new_map) - set(old_map)
    print(f"기존에만 있는 절: {len(only_old)}  파서에만 있는 절: {len(only_new)}")
    for k in sorted(only_old)[:5]:
        print("  기존에만:", k, old_map[k][:40])
    for k in sorted(only_new)[:5]:
        print("  파서에만:", k, new_map[k][:40])

    diff = 0
    for k in set(old_map) & set(new_map):
        if " ".join(old_map[k].split()) != new_map[k]:
            diff += 1
            if diff <= 5:
                print(f"  본문 차이 {k}\n    기존: {old_map[k][:60]}\n    파서: {new_map[k][:60]}")
    total = len(set(old_map) & set(new_map))
    print(f"본문 차이: {diff}/{total} ({100 * (total - diff) / total:.2f}% 일치)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=sorted(LANGS))
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--golden-test", action="store_true")
    args = ap.parse_args()

    if args.golden_test:
        golden_test()
        return
    targets = sorted(LANGS) if args.all else [args.lang] if args.lang else []
    if not targets:
        ap.error("--lang, --all, --golden-test 중 하나가 필요합니다")
    for lang in targets:
        rows = build_language(lang, LANGS[lang])
        out = write_csv(lang, rows)
        n_books = len({r["book_code"] for r in rows})
        print(f"[{lang}] {LANGS[lang]}: {len(rows)}절, {n_books}권 → {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
