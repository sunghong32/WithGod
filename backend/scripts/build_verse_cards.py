# -*- coding: utf-8 -*-
"""선정 목록(docs/verse_picks/*.tsv) → 본문이 붙은 검토용 카드.

개역한글은 한 문장을 여러 절로 쪼갠 곳이 많아, 절 하나만 떼면 '…하시나니',
'…입맞추었으며' 처럼 말이 끊긴다. 그래서 끊긴 절은 버리지 않고 **뒤 절을 붙여
문장이 끝날 때까지 확장**한다(최대 3절). 확장해도 안 끝나거나, 끝나도 너무
짧으면 그때 탈락시킨다.

본문은 카드에 그대로 나가므로 원문 잡티(따옴표 잔여, '하리라 !' 공백,
'셀라', 한자 병기)도 여기서 정리한다. 절 본문 자체는 고치지 않는다.

    python scripts/build_verse_cards.py docs/verse_picks/psalms.tsv
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 길이 하한은 두지 않는다. 좋은 문장은 저절로 어느 정도 길이가 되고,
# 짧아도 심금을 울리면 좋은 문장이다. 문장이 완결되었는지만 본다.
MIN_LEN = 0

MAX_LEN = 160         # 카드에 넣기엔 너무 긴 길이(선지서는 한 절이 길다)
MAX_SPAN = 4          # 합본은 최대 4절까지

# 문장이 끊겼다고 볼 연결어미. 개역한글은 종결형이 워낙 다양해서(…하리요, …너희들아!,
# …할렐루야!) '끝났는가'를 나열로 판정하면 멀쩡한 절이 걸린다. 그래서 반대로
# **끊긴 신호만** 본다.
CONNECTIVE = re.compile(
    r"(하며|하고|하니|하사|하되|시되|시며|시고|이며|으며|으니|으로|아서|어서"
    r"|거니와|려니와|은즉|는즉|면|매|므로|인하여|위하여|말미암아|같이"
    r"|노니|(?<!임)이요|것이니"
    r"|오며|이오며|사오며|사오니|오니|시오니"
    r"|에게|에서|보다|과|와|을|를|이|가|은|는|의|도|께)[!?.]*$"
)


# 절 안에 섞인 서사(narration) — 말씀 자체가 아니라 "누가 말했다"는 서술이다.
# 카드에는 말씀만 싣고 이 껍데기는 벗긴다. 말씀 본문은 한 글자도 바꾸지 않는다.
FRAME_HEAD = re.compile(
    r"^.*?(?:가라사대|이르시되|말씀하시되|대답하시되|이르시기를|일러 가라사대"
    r"|외쳐 가라사대|대답하여 가라사대)\s*"
)
# 뒤 절을 붙이다가 이 표지를 만나면 대화가 시작되는 것이므로 거기서 멈춘다
# (마태 14:27 에 14:28 을 붙이면 베드로의 대사가 딸려 들어온다).
DIALOGUE = re.compile(r"가로되|대답하되|대답하여|여짜오되|묻자오되|이르되|말하되")
FRAME_TAIL = re.compile(
    # 앞에 공백을 반드시 요구한다. 그러지 않으면 "족하니라"의 "하니라",
    # "동일하시니라"의 "하시니라"까지 잘라내 본문이 훼손된다.
    r"\s+(?:하시니라|하셨느니라|하셨으니|하셨나이다|하시었더라|하시더라|하시니|하시고|하신대|하시매|하니라"
    r"|하였더라|하더라|하였느니라)[!?.]*$"
)


def strip_frame(text: str) -> tuple[str, bool]:
    """서사 껍데기를 벗기고, 앞부분을 걷어냈는지(=하반절 표기 필요) 함께 돌려준다."""
    head = FRAME_HEAD.match(text)
    body = text[head.end():] if head else text
    body = FRAME_TAIL.sub("", body).strip()
    if not body:
        return text, False
    return body, bool(head)


def clean(text: str) -> str:
    t = re.sub(r"\([^)]*\)", "", text)          # 한자 병기 등 괄호주
    t = re.sub(r"\[[^\]]*\]", "", t)            # 대괄호 이문(異文)
    t = re.sub(r"[`'\"()]", "", t)                # 인용부호 잔여
    t = re.sub(r"\s+([!?,.])", r"\1", t)        # '하리라 !' → '하리라!'
    t = re.sub(r"\s*셀라\s*", " ", t)            # 음악 지시어
    return re.sub(r"\s+", " ", t).strip()


def is_complete(text: str) -> bool:
    core = re.sub(r"[!?.\s]+$", "", text)
    return not CONNECTIVE.search(core)


def load_bible() -> dict[str, str]:
    out = {}
    with open(ROOT / "data" / "verses.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[f"{r['book']} {r['chapter']}:{r['verse']}"] = clean(r["text"])
    return out


def expand(bible: dict[str, str], book: str, ch: int, start: int, end: int):
    """start~end 를 이어붙이되, 문장이 끊기면 뒤 절을 최대 MAX_SPAN 까지 더 붙인다."""
    v = end
    while True:
        parts = [bible.get(f"{book} {ch}:{i}", "") for i in range(start, v + 1)]
        if not parts[0]:
            return None, 0, 0, "본문 없음"
        text = " ".join(p for p in parts if p).strip()
        text, partial = strip_frame(text)
        span = v - start + 1
        if len(text) > MAX_LEN:
            return text, span, partial, "너무 김"
        # 합본은 '문장이 끊겼거나' '하한에도 못 미칠 때'만 한다. 길이를 넉넉히
        # 채우려고 붙이면 시편 119:105 처럼 그 자체로 완결된 명구가 뒤 절에 희석된다.
        if is_complete(text) and len(text) >= MIN_LEN:
            return text, span, partial, ""
        # 앞의 서사를 걷어낸 절은 '인용된 말씀' 자체가 한 단위다. 뒤 절을 더
        # 붙이면 그 절의 서사("하시고 다시 몸을 굽히사")가 도로 딸려 들어온다.
        nxt = bible.get(f"{book} {ch}:{v + 1}", "")
        if partial or span >= MAX_SPAN or not nxt or DIALOGUE.search(nxt):
            why = "말이 끊김" if not is_complete(text) else "너무 짧음"
            return text, span, partial, why
        v += 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tsv")
    ap.add_argument("--out")
    args = ap.parse_args()

    bible = load_bible()
    src = ROOT / args.tsv
    rows = [r for r in csv.reader(open(src, encoding="utf-8"), delimiter="\t")
            if r and not r[0].startswith("#") and r[0] != "ref"]

    cards, dropped = [], []
    for ref, vtype, note in rows:
        m = re.match(r"(.+?) (\d+):(\d+)(?:-(\d+))?$", ref)
        book, ch = m.group(1), int(m.group(2))
        v1 = int(m.group(3))
        v2 = int(m.group(4)) if m.group(4) else v1
        text, span, partial, problem = expand(bible, book, ch, v1, v2)
        final_ref = f"{book} {ch}:{v1}" if span == 1 else f"{book} {ch}:{v1}-{v1 + span - 1}"
        # 앞부분(서사)을 걷어냈으면 하반절 인용임을 표준 표기 b 로 밝힌다.
        if partial:
            final_ref += "b"
        if problem:
            dropped.append((ref, problem, text or ""))
            continue
        cards.append({"reference": final_ref, "type": vtype,
                      "merged": ("합본" if span > 1 else "") + ("·하반절" if partial else ""),
                      "len": len(text),
                      "text": text, "note": note})

    out = ROOT / (args.out or str(src).replace(".tsv", "_cards.csv"))
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["reference", "type", "merged", "len", "text", "note"])
        w.writeheader()
        w.writerows(cards)

    merged = sum(1 for c in cards if c["merged"])
    print(f"{src.name}: 채택 {len(rows)} → 카드 {len(cards)}개 (합본으로 살린 것 {merged}개), 탈락 {len(dropped)}개")
    print(f"  길이 최소 {min(c['len'] for c in cards)}자 · 중앙 "
          f"{sorted(c['len'] for c in cards)[len(cards)//2]}자 · 최대 {max(c['len'] for c in cards)}자")
    if dropped:
        print("\n  탈락:")
        for ref, why, t in dropped:
            print(f"    [{why}] {ref}  {t[:52]}")
    print(f"\n→ {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
