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

**절 수가 맞지 않는 장은 손대지 않는다.** 처음(9/3)엔 6개 장이 그랬는데, 원인을 절 단위로
따라가 보니 두 가지였다(11/5). 둘 다 아래 표에 적힌 것만 처리한다.

- `INTRUDED` — **다른 곳의 절이 끼어 있었다.** 이사야 27:11 자리의 히스기야 이야기는
  이사야 37:10 이다. 이 문장을 빼면 남은 단위가 정확히 그 장의 절 수가 되고, 그 장의 진짜
  본문은 원본의 대괄호 꼬리에 다 들어 있다 — 새 본문이 필요 없다.
- `MISSING` — **원본에 이 절이 없다.** 그 자리에 다음 절을 한 번 더 적었다(예레미야 25:21 =
  25:22). 이건 원본만으로는 못 고친다. 채우는 본문은 대한성서공회 공식 온라인 개역한글과
  getbible·bolls·위키문헌 4곳이 글자까지 같은 것만 쓴다.

개역한글판(1961)은 저작재산권 보호기간이 2011-12-31 에 끝났다(대한성서공회 저작권 안내 표).

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

# 다른 곳의 절이 끼어든 자리 — 이 문장은 그 장의 절이 아니므로 버린다(주석은 진짜 자리).
INTRUDED: dict[tuple[str, int], str] = {
    ("시편", 10): "주께서 생명의 길로 내게 보이시리니 주의 앞에는 기쁨이 충만하고 "
                  "주의 우편에는 영원한 즐거움이 있나이다",  # 시편 16:11
    ("잠언", 8): "[사37:26]",  # 본문 대신 들어간 교차 참조 표지
    ("이사야", 27): "너희는 유다 왕 히스기야에게 이같이 고하여 이르기를 너는 너의 의뢰하는 하나님이 "
                    "예루살렘이 앗수르 왕의 손에 넘어가지 아니하리라 하는 말에 속지 말라",  # 이사야 37:10
    ("사도행전", 22): "바울이 한 백부장을 청하여 가로되 `이 청년을 천부장에게로 인도하라 "
                      "그에게 무슨 할 말이 있다' 하니",  # 사도행전 23:17
}

# 원본에 없는 절 — 그 자리에 이웃 절이 한 번 더 적혀 있다. 공식·외부 4곳이 같은 본문.
MISSING: dict[tuple[str, int, int], str] = {
    ("예레미야", 25, 21): "에돔과 모압과 암몬 자손과",
    ("잠언", 30, 32): "만일 네가 미련하여 스스로 높은체 하였거나 혹 악한 일을 도모하였거든 "
                      "네 손으로 입을 막으라",
}

# 이슈 #13 이 getbible 로 통째 채운 장에서 구가 빠진 절 — (지금 본문, 고칠 본문).
# 시편 10 에 끼어 있던 문장이 바로 이 절의 온전한 본문이고, 공식 본문과도 같다.
TRUNCATED: dict[tuple[str, int, int], tuple[str, str]] = {
    ("시편", 16, 11): ("주께서 생명의 길로 내게 보이시리니 주의 우편에는 영원한 즐거움이 있나이다",
                     INTRUDED[("시편", 10)]),
}


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
        seen: set[str] = {norm(INTRUDED.get((book, ch), ""))}
        rebuilt: list[str] = []
        for _, vtext in re.findall(r"\\v (\d+) (.*)", chapter_body(kor[code], ch)):
            for u in units(vtext):
                k = norm(u)
                if k and k not in seen:
                    seen.add(k)
                    rebuilt.append(k)
        for (b, c, v), text in sorted(MISSING.items()):
            if (b, c) == (book, ch):
                rebuilt.insert(v - 1, norm(text))
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
        print("\n  아래는 손대지 않는다. 원본에 본문이 없거나 다른 곳의 절이 섞여 있다 —")
        print("  원인을 확인해 INTRUDED·MISSING 에 적기 전에는 고치지 않는다:")
        for book, ch, got, want in skipped:
            why = "본문 누락" if got < want else "다른 본문 혼입"
            print(f"  ❌ {book} {ch:>3d}장 — 복원 {got}절 / 실제 {want}절 ({why})")

    current = {(r["book"], int(r["chapter"]), int(r["verse"])): r["text"] for r in rows}
    restored = {k: new for k, (old, new) in TRUNCATED.items() if current.get(k) == old}
    for (book, ch, v) in restored:
        print(f"  ✅ {book} {ch}:{v} — 빠진 구를 되살린다")

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
        verse_key = (r["book"], int(r["chapter"]), int(r["verse"]))
        if verse_key in restored:
            r = {**r, "text": restored[verse_key]}
        out.append(r)
    with open(CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["book", "chapter", "verse", "text"])
        w.writeheader()
        w.writerows(out)
    print(f"\n{len(fixed)}개 장 · {len(restored)}개 절 반영 완료. 원본은 {backup.name} 에 남겼다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
