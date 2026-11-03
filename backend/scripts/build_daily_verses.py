# -*- coding: utf-8 -*-
"""선정된 카드 → 운영용 `notifications/daily_verses.json`.

카드(`docs/verse_picks/*_cards.csv`)와 한 줄 적용문(`docs/verse_picks/reflections.tsv`)을
합쳐 배포 파일을 만든다. 여기서 하는 일은 셋이다.

1. **verse_id 생성** — `languages.py` 의 정경 코드로 `psa-4-8` 처럼 만든다.
   기존 파일은 표기가 섞여 있었다(`proverbs-3-5` 하나만 세 글자 코드가 아니었다).
   verse_id 는 풀이 캐시(`data/verse_interpretations.json`)의 키이므로 한번 정하면 바꾸지 않는다.

2. **날짜 편중 해소** — 배포 파일의 배열 순서가 곧 달력이다
   (`verse_provider`: `index = 날짜.toordinal() % N`). 그래서 책별로 모아 두면
   시편만 72일 연속으로 나온다. 각 책을 전체 길이에 고르게 펴서 섞는다
   (버킷 안 위치를 0~1 로 정규화해 정렬 — 큰 버킷일수록 촘촘히 박힌다).

3. **검증** — 같은 책이 연달아 나오지 않는지, 위안/교훈이 한쪽으로 몰리지 않는지 본다.

4. **풀이 검토본 반영** — `docs/verse_picks/interpretations.tsv`(사람이 검토한 풀이)를
   `notifications/daily_interpretations.json` 으로 낸다. 풀이가 빠졌거나, 풀이를 쓸 때와
   카드 본문이 달라졌거나, 반말·본문 되옮기기 같은 결함이 있으면 반영하지 않는다.
   풀이는 `scripts/generate_verse_interpretations.py` 로 만든다.
   외국어 검토본(`docs/verse_picks/interpretations_intl/<lang>.tsv`)은
   `notifications/daily_interpretations_intl.json` 으로 낸다. 바탕으로 삼은 한국어 카드·풀이가
   바뀌었거나 결함이 있는 행은 빼고 낸다(빠진 말씀은 운영에서 즉석 생성으로 채운다).
   외국어 풀이는 `scripts/generate_intl_interpretations.py` 로 만든다.

    python scripts/build_daily_verses.py            # 검사만
    python scripts/build_daily_verses.py --apply
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PICKS = ROOT / "docs" / "verse_picks"
REFLECTIONS = PICKS / "reflections.tsv"
INTERPRETATIONS = PICKS / "interpretations.tsv"
OUT = ROOT / "notifications" / "daily_verses.json"
OUT_INTERPRETATIONS = ROOT / "notifications" / "daily_interpretations.json"
INTL_DIR = PICKS / "interpretations_intl"
OUT_INTERPRETATIONS_INTL = ROOT / "notifications" / "daily_interpretations_intl.json"

# notifications 의 두 모듈은 표준 라이브러리만 쓴다(fastapi 가 없어도 된다).
sys.path.insert(0, str(ROOT))
from notifications.interpretation import INTL_LANGS, find_intl_problems, find_problems  # noqa: E402
from notifications.verse_provider import (  # noqa: E402
    curated_key,
    intl_curated_key,
    intl_source_fingerprint,
)


def canon_codes() -> dict[str, str]:
    src = (ROOT / "languages.py").read_text(encoding="utf-8")

    def grab(name: str) -> list[str]:
        body = re.search(rf"{name} = \[(.*?)\]", src, re.S).group(1)
        return re.findall(r'"([^"]+)"', body)

    return dict(zip(grab("_KO_BOOKS"), grab("_CANON_CODES")))


def verse_id(reference: str, codes: dict[str, str]) -> str:
    """'시편 40:1-2' → 'psa-40-1'. 합본·하반절(b)은 시작 절로 잡는다."""
    book, rest = reference.rsplit(" ", 1)
    chapter, verses = rest.split(":")
    start = re.match(r"\d+", verses).group(0)
    code = codes.get(book)
    if not code:
        raise KeyError(f"정경 코드를 모르는 책: {book}")
    return f"{code.lower()}-{chapter}-{start}"


def load_cards() -> list[dict]:
    """카드를 파일별 버킷과 함께 읽는다(버킷이 곧 섞는 단위다)."""
    out = []
    for path in sorted(glob.glob(str(PICKS / "*_cards.csv"))):
        bucket = Path(path).name.replace("_cards.csv", "")
        for row in csv.DictReader(open(path, encoding="utf-8-sig")):
            out.append({**row, "bucket": bucket})
    return out


def load_reflections() -> dict[str, str]:
    if not REFLECTIONS.exists():
        return {}
    out = {}
    for line in REFLECTIONS.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        ref, _, text = line.partition("\t")
        if text.strip():
            out[ref.strip()] = text.strip()
    return out


def load_interpretations() -> dict[str, tuple[str, str]]:
    """{reference: (풀이를 쓸 때의 카드 본문, 풀이)}"""
    if not INTERPRETATIONS.exists():
        return {}
    out = {}
    for line in INTERPRETATIONS.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            raise SystemExit(f"{INTERPRETATIONS.name}: 열이 3개가 아닌 행 → {line[:60]}")
        ref, text, interp = (p.strip() for p in parts)
        out[ref] = (text, interp)
    return out


def curate_interpretations(entries: list[dict], interps: dict[str, tuple[str, str]]):
    """배포할 {curated_key: 풀이} 와 반영을 막는 문제 목록을 만든다."""
    curated, missing, stale, defects = {}, [], [], []
    for e in entries:
        got = interps.get(e["reference"])
        if not got:
            missing.append(e["reference"])
            continue
        text, interp = got
        if text != e["text"]:
            stale.append(e["reference"])
            continue
        problems = find_problems(interp, e["text"])
        if problems:
            defects.append(f"{e['reference']}: {', '.join(problems)}")
            continue
        curated[curated_key(e["verse_id"], e["text"])] = interp
    return curated, missing, stale, defects


def load_intl_interpretations(lang: str) -> dict[str, tuple[str, str, str]]:
    """{reference: (바탕 지문, 현지 참조, 풀이)}"""
    path = INTL_DIR / f"{lang}.tsv"
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 4:
            raise SystemExit(f"{path.name}: 열이 4개가 아닌 행 → {line[:60]}")
        ref, fp, local_ref, note = (p.strip() for p in parts)
        out[ref] = (fp, local_ref, note)
    return out


def curate_intl_interpretations(entries: list[dict], interps: dict[str, tuple[str, str]]):
    """배포할 {intl_curated_key: 풀이} 와 언어별 (빠짐, 낡음, 결함) 목록."""
    curated, problems = {}, {}
    for lang in INTL_LANGS:
        rows = load_intl_interpretations(lang)
        missing, stale, defects = [], [], []
        for e in entries:
            got, ko = rows.get(e["reference"]), interps.get(e["reference"])
            if not got:
                missing.append(e["reference"])
                continue
            fp, _, note = got
            if not ko or fp != intl_source_fingerprint(e["text"], ko[1]):
                stale.append(e["reference"])
                continue
            found = find_intl_problems(note, lang)
            if found:
                defects.append(f"{e['reference']}: {', '.join(found)}")
                continue
            curated[intl_curated_key(lang, e["verse_id"], e["text"])] = note
        problems[lang] = (missing, stale, defects)
    return curated, problems


def interleave(cards: list[dict]) -> list[dict]:
    """책이 뭉치지 않도록 전체 길이에 고르게 편다.

    각 카드에 '갈래 안 위치 / 갈래 크기' 를 매겨 그 값으로 정렬한다. 큰 갈래는
    촘촘히, 작은 갈래는 드문드문 박혀서 어느 구간을 잘라 봐도 비율이 비슷해진다.
    갈래는 (책 묶음 × 위안/교훈)이라 책과 유형이 함께 퍼진다.
    """
    # 책만으로 나누면 위안/교훈이 한쪽으로 몰려 아흐레씩 교훈만 나오는 구간이 생긴다.
    # 그래서 (책 묶음 × 유형)을 한 갈래로 잡아 유형까지 같이 퍼지게 한다.
    by_bucket: dict[str, list[dict]] = {}
    for c in cards:
        by_bucket.setdefault(f"{c['bucket']}:{c['type']}", []).append(c)
    keyed = []
    for name, items in by_bucket.items():
        n = len(items)
        for i, c in enumerate(items):
            keyed.append(((i + 0.5) / n, -n, name, c))
    keyed.sort(key=lambda t: (t[0], t[1], t[2]))
    return [t[3] for t in keyed]


def longest_run(seq: list[str]) -> tuple[int, str]:
    best, best_key, run, prev = 1, seq[0], 1, seq[0]
    for x in seq[1:]:
        run = run + 1 if x == prev else 1
        if run > best:
            best, best_key = run, x
        prev = x
    return best, best_key


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    codes = canon_codes()
    cards = load_cards()
    reflections = load_reflections()

    missing = [c["reference"] for c in cards if c["reference"] not in reflections]
    ordered = interleave(cards)

    seen: dict[str, str] = {}
    entries = []
    for c in ordered:
        vid = verse_id(c["reference"], codes)
        if vid in seen:
            raise SystemExit(f"verse_id 충돌: {vid} ← {seen[vid]} / {c['reference']}")
        seen[vid] = c["reference"]
        entries.append({
            "verse_id": vid,
            "reference": c["reference"],
            "text": c["text"],
            "reflection": reflections.get(c["reference"], ""),
        })

    books = [e["reference"].rsplit(" ", 1)[0] for e in entries]
    types = [c["type"] for c in ordered]
    run_book, which = longest_run(books)
    run_type, _ = longest_run(types)

    print(f"카드 {len(entries)}개 · 적용문 없음 {len(missing)}개")
    print(f"같은 책 최대 연속 {run_book}일 ({which}) · 같은 유형 최대 연속 {run_type}일")
    print("  유형 분포:", dict(Counter(types)))
    # 앞 30일이 한쪽으로 쏠리지 않는지 눈으로 본다
    print("  첫 12일:", " · ".join(f"{b}" for b in books[:12]))
    if missing:
        print(f"\n  적용문이 없는 카드 {len(missing)}개 (앞 10개):")
        for r in missing[:10]:
            print(f"    {r}")

    curated, no_interp, stale, defects = curate_interpretations(entries, load_interpretations())
    print(f"풀이 검토본 {len(curated)}개 · 없음 {len(no_interp)} · 본문 바뀜 {len(stale)} · 결함 {len(defects)}")
    for label, items in (("풀이 없음", no_interp), ("본문 바뀜 — 풀이 다시 볼 것", stale), ("결함", defects)):
        for r in items[:10]:
            print(f"    {label}: {r}")
    curated_intl, intl_problems = curate_intl_interpretations(entries, load_interpretations())
    print(f"외국어 검토본 {len(curated_intl)}개")
    for lang, (i_missing, i_stale, i_defects) in intl_problems.items():
        if i_missing or i_stale or i_defects:
            print(f"  {lang}: 없음 {len(i_missing)} · 바탕 바뀜 {len(i_stale)} · 결함 {len(i_defects)}"
                  " → scripts/generate_intl_interpretations.py (--submit / --fix)")
            for r in i_defects[:3]:
                print(f"    결함: {r}")

    if not args.apply:
        print("\n(검사만 했다. 반영하려면 --apply)")
        return 0
    if missing:
        print("\n적용문이 빠진 카드가 있어 반영하지 않는다.")
        return 1
    if no_interp or stale or defects:
        print("\n풀이 검토본에 문제가 있어 반영하지 않는다 → scripts/generate_verse_interpretations.py")
        return 1

    OUT.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_INTERPRETATIONS.write_text(
        json.dumps(curated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\n→ {OUT} ({len(entries)}개)")
    print(f"→ {OUT_INTERPRETATIONS} ({len(curated)}개)")
    OUT_INTERPRETATIONS_INTL.write_text(
        json.dumps(curated_intl, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"→ {OUT_INTERPRETATIONS_INTL} ({len(curated_intl)}개)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
