# -*- coding: utf-8 -*-
"""verses.csv 절 번호 밀림 복구 (이슈 #31).

원본 `data_raw/kor_usfm.zip`(eBible) 이 몇몇 장에서 **한 절을 중복 저장**하는 바람에
그 지점부터 장 끝까지 절 번호가 한 칸씩 밀려 있다. 밀려난 꼬리 절은 앞 절 끝에
`[ (Psalms 3:9) … ]` 형태로 뭉쳐 들어가 있다. 장의 절 수는 맞아떨어져서
개수 비교로는 잡히지 않는다(닫힌 이슈 #13 의 repair_ko_verses.py 가 못 잡은 이유).

    시편 3:5  내가 누워 자고 깨었으니 …
    시편 3:6  내가 누워 자고 깨었으니 …        ← 3:5 와 같다
    시편 3:7  천만인이 나를 둘러치려 하여도 …   ← 실제 3:6
    시편 3:8  여호와여, 일어나소서 … [ (Psalms 3:9) 구원은 여호와께 … ]

복구 방법은 단순하다. **본문 단위를 문서 순서대로 모으고(대괄호 안도 한 절이다),
똑같은 것을 걸러낸 뒤, 1번부터 다시 매긴다.** 이것이 옳은지는 확인할 수 있다 —
결과 절 수가 그 장의 실제 절 수와 맞아야 한다. 실제 절 수는 같은 `data_raw/` 의
영어 WEB 원본에서 가져온다(독어·불어·이어까지 5개 언어가 모두 일치함을 확인했다).

**절 수가 맞지 않는 장은 손대지 않는다.** 본문이 원본에서 아예 빠졌거나
(예레미야 25:21, 잠언 30:32) 다른 장의 본문이 섞여 들어온 경우라
(이사야 27 에 히스기야 이야기) 성경 본문을 지어내지 않고는 복구할 수 없다.

    python scripts/repair_verse_numbering.py            # 검사만 (기본)
    python scripts/repair_verse_numbering.py --apply    # verses.csv 에 반영
"""
from __future__ import annotations

import argparse
import csv
import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "data" / "verses.csv"
KOR = ROOT / "data_raw" / "kor_usfm.zip"
ENG = ROOT / "data_raw" / "engwebp_usfm.zip"

# 밀려난 꼬리 절이 앞 절 끝에 이 모양으로 붙어 있다. 책 이름 표기가 제각각이라
# ('Psalms 3:9', 'I Samuel 129', 'Acts 22:31') 느슨하게 잡는다.
BRACKET = re.compile(r"\[\s*\((?:[IVX]+\s+)?[A-Za-z]+\.?\s*\d+:?\d*\)\s*(.*?)\s*\]")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def units(verse_text: str) -> list[str]:
    """한 절 행에서 본문 단위를 뽑는다 — 대괄호 안은 별개의 절이다."""
    inner = [m.group(1).strip() for m in BRACKET.finditer(verse_text)]
    main = BRACKET.sub("", verse_text).strip()
    return ([main] if main else []) + [t for t in inner if t]


def load_usfm(path: Path) -> dict[str, str]:
    z = zipfile.ZipFile(path)
    out = {}
    for n in z.namelist():
        m = re.search(r"\d\d-([A-Z0-9]{3})", n)
        if m:
            out[m.group(1)] = z.read(n).decode("utf-8", "replace")
    return out


def chapter_body(text: str, ch: int) -> str:
    a = re.search(rf"\\c {ch}\b", text)
    if not a:
        return ""
    b = re.search(rf"\\c {ch + 1}\b", text)
    return text[a.start(): b.start() if b else len(text)]


def true_lengths(eng: dict[str, str]) -> dict[tuple[str, int], int]:
    """영어 WEB 원본에서 장별 절 수를 읽는다(정상 판본 기준)."""
    out: dict[tuple[str, int], int] = {}
    for code, text in eng.items():
        ch = None
        for line in text.splitlines():
            if line.startswith("\\c "):
                ch = int(line.split()[1]) if line.split()[1].isdigit() else None
            elif line.startswith("\\v ") and ch:
                head = line.split()[1]
                if head.isdigit():
                    key = (code, ch)
                    out[key] = max(out.get(key, 0), int(head))
    return out


def ko_book_codes() -> dict[str, str]:
    src = (ROOT / "languages.py").read_text(encoding="utf-8")

    def grab(name: str) -> list[str]:
        body = re.search(rf"{name} = \[(.*?)\]", src, re.S).group(1)
        return re.findall(r'"([^"]+)"', body)

    return dict(zip(grab("_KO_BOOKS"), grab("_CANON_CODES")))


def find_broken(rows: list[dict]) -> set[tuple[str, int]]:
    """중복 절이나 대괄호 꼬리가 있는 장을 찾는다."""
    by: dict[tuple[str, int], dict[int, str]] = {}
    for r in rows:
        by.setdefault((r["book"], int(r["chapter"])), {})[int(r["verse"])] = r["text"]
    bad = set()
    for key, vs in by.items():
        for v, t in vs.items():
            if BRACKET.search(t):
                bad.add(key)
            nxt = vs.get(v + 1)
            if nxt and len(t.strip()) > 10 and norm(t) == norm(nxt):
                bad.add(key)
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="verses.csv 를 실제로 고친다")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(CSV, encoding="utf-8")))
    kor, eng = load_usfm(KOR), load_usfm(ENG)
    truth, code_of = true_lengths(eng), ko_book_codes()

    fixed: dict[tuple[str, int], list[str]] = {}
    skipped: list[tuple[str, int, int, int]] = []

    for book, ch in sorted(find_broken(rows)):
        code = code_of.get(book)
        if not code or code not in kor:
            continue
        seen: set[str] = set()
        rebuilt: list[str] = []
        for _, vtext in re.findall(r"\\v (\d+) (.*)", chapter_body(kor[code], ch)):
            for u in units(vtext):
                k = norm(u)
                if k not in seen:
                    seen.add(k)
                    rebuilt.append(k)
        want = truth.get((code, ch), 0)
        if want and len(rebuilt) == want:
            fixed[(book, ch)] = rebuilt
        else:
            skipped.append((book, ch, len(rebuilt), want))

    print(f"손상된 장 {len(fixed) + len(skipped)}개 — 복구 가능 {len(fixed)} · 불가 {len(skipped)}\n")
    for (book, ch), new in sorted(fixed.items()):
        old = {int(r["verse"]): r["text"] for r in rows
               if r["book"] == book and int(r["chapter"]) == ch}
        moved = sum(1 for i, t in enumerate(new, 1) if norm(old.get(i, "")) != t)
        print(f"  ✅ {book} {ch:>3d}장 — {len(new)}절 · 본문이 바뀌는 절 {moved}개")
    if skipped:
        print("\n  아래는 손대지 않는다. 원본에 본문이 없거나 다른 장이 섞여 있어")
        print("  성경 본문을 지어내지 않고는 복구할 수 없다:")
        for book, ch, got, want in skipped:
            why = "본문 누락" if got < want else "다른 본문 혼입"
            print(f"  ❌ {book} {ch:>3d}장 — 복원 {got}절 / 실제 {want}절 ({why})")

    if not args.apply:
        print("\n(검사만 했다. 반영하려면 --apply)")
        return 0

    backup = CSV.with_suffix(".csv.bak")
    shutil.copy2(CSV, backup)
    out = []
    for r in rows:
        key = (r["book"], int(r["chapter"]))
        if key in fixed:
            v = int(r["verse"])
            new = fixed[key]
            if v <= len(new):
                r = {**r, "text": new[v - 1]}
        out.append(r)
    with open(CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["book", "chapter", "verse", "text"])
        w.writeheader()
        w.writerows(out)
    print(f"\n{len(fixed)}개 장 반영 완료. 원본은 {backup.name} 에 남겼다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
