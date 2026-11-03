# -*- coding: utf-8 -*-
"""오늘의 말씀 풀이 사전 생성 → `docs/verse_picks/interpretations.tsv`.

카드마다 풀이 한 단락을 만들어 TSV 에 채운다. **이미 있는 행은 건드리지 않는다** —
사람이 고친 풀이를 덮어쓰지 않기 위해서다. 빠진 행, 카드 본문이 바뀐 행, `--redo` 로
지정한 행만 새로 만든다. 만든 뒤에는 사람이 읽고 고친 다음 빌드로 반영한다.

    python scripts/generate_verse_interpretations.py                  # 빠진 것만 생성
    python scripts/generate_verse_interpretations.py --redo "요한복음 8:11b"
    python scripts/generate_verse_interpretations.py --check          # 생성 없이 검수표만
    python scripts/build_daily_verses.py --apply                      # 운영 파일로 반영

TSV 형식은 `reference<TAB>본문<TAB>풀이`. 본문 열은 풀이를 쓸 때의 카드 본문이라,
카드 본문이 나중에 바뀌면 빌드가 알아채고 멈춘다(예전 본문에 쓴 풀이가 조용히 붙는 것을 막는다).

`--check` 는 결함(반말·반말 어미·본문 되옮기기), 말버릇, 길이, 여러 풀이에 되풀이되는
표현을 보여 준다. 한 장씩 읽으면 괜찮아도 매일 보면 같은 말이 거슬린다.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from build_daily_verses import INTERPRETATIONS as TSV  # noqa: E402  (같은 scripts/ 폴더)
from build_daily_verses import load_cards, load_interpretations  # noqa: E402
from notifications.interpretation import (  # noqa: E402
    find_habits,
    find_problems,
    generate_interpretation,
)

HEADER = (
    "# 오늘의 말씀 풀이(검토본) — reference<TAB>본문<TAB>풀이\n"
    "# 생성: scripts/generate_verse_interpretations.py → 사람이 읽고 고친다. 고친 행은 다시 생성하지 않는다.\n"
    "# 본문 열은 풀이를 쓸 때의 카드 본문이다. 카드 본문이 바뀌면 build_daily_verses.py 가 멈춘다.\n"
    "# 반영: python scripts/build_daily_verses.py --apply → notifications/daily_interpretations.json\n"
)
LEN_RANGE = (110, 260)

# 풀이가 한 틀로 굳지 않도록 카드마다 첫머리와 끝맺음을 나눠 준다. 형식 없이 한 벌을
# 돌렸더니 68%가 「오늘 ~해 보세요.」로 끝났고, 팔복 7장이 모두 「예수님은 산 위에서」로
# 시작했다. 한 장씩 읽으면 괜찮아도 매일 보면 같은 글로 읽힌다.
# 참조의 해시로 고르므로 다시 돌려도 같은 카드에는 같은 형식이 간다. 값은 (비율%, 지시).
# 기도 끝맺음(15%)은 2026-11-03 뺐다 — 교회에 다니지 않는 사람에게는 기도를 시키는 셈이다.
OPENINGS = [
    (50, "첫 문장은 말씀의 핵심을 곧바로 짚습니다. 배경이 필요하면 뒤에서 짧게 덧붙입니다."),
    (50, "배경이 뜻을 살리는 구절이면 첫 문장에서 누가 누구에게 어떤 자리에서 한 말인지 알려 줍니다. "
         "배경이 없어도 되는 구절이면 핵심부터 씁니다."),
]
ENDINGS = [
    (45, "마지막 문장은 오늘 해 볼 만한 구체적인 행동이나 태도를 권합니다."),
    (35, "마지막 문장은 권유('~해 보세요') 없이, 이 말씀이 오늘의 삶에 건네는 확신이나 위로를 평서문으로 맺습니다."),
    (20, "마지막 문장은 오늘 스스로에게 물어볼 짧은 질문으로 맺습니다."),
]


def _weighted(options: list[tuple[int, str]], roll: int) -> str:
    for weight, text in options:
        if roll < weight:
            return text
        roll -= weight
    return options[-1][1]


def pick_form(reference: str) -> str:
    h = int(hashlib.sha256(reference.encode("utf-8")).hexdigest(), 16)
    return f"{_weighted(OPENINGS, h % 100)} {_weighted(ENDINGS, (h // 100) % 100)}"


def _one_line(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def save_tsv(rows: dict[str, tuple[str, str]], order: list[str]) -> None:
    lines = [HEADER.rstrip("\n")]
    # 카드 순서(책별)로 쓴다. 카드에서 빠진 행은 지우지 않고 뒤에 남긴다.
    for ref in order + [r for r in rows if r not in set(order)]:
        if ref in rows:
            text, interp = rows[ref]
            lines.append(f"{ref}\t{_one_line(text)}\t{_one_line(interp)}")
    TSV.write_text("\n".join(lines) + "\n", encoding="utf-8")


def report(cards: list[dict], rows: dict[str, tuple[str, str]]) -> None:
    missing = [c["reference"] for c in cards if c["reference"] not in rows]
    stale = [c["reference"] for c in cards
             if c["reference"] in rows and rows[c["reference"]][0] != c["text"]]
    print(f"카드 {len(cards)}개 · 풀이 {len(rows)}개 · 빠짐 {len(missing)} · 본문 바뀜 {len(stale)}")
    for r in stale:
        print(f"  본문 바뀜: {r}")

    texts = {c["reference"]: c["text"] for c in cards}
    flagged = 0
    for ref, (text, interp) in rows.items():
        notes = find_problems(interp, texts.get(ref, text)) + find_habits(interp)
        if not LEN_RANGE[0] <= len(interp) <= LEN_RANGE[1]:
            notes.append(f"길이 {len(interp)}자")
        if notes:
            flagged += 1
            print(f"  [{ref}] {', '.join(notes)}\n      {interp}")
    print(f"걸린 풀이 {flagged}개")

    interps = [i for _, i in rows.values()]
    if not interps:
        return
    lengths = sorted(len(i) for i in interps)
    print(f"\n길이 — 최소 {lengths[0]} · 중앙 {lengths[len(lengths) // 2]} · 최대 {lengths[-1]}")

    # 여러 풀이에 되풀이되는 어절(문서 빈도). 5% 넘게 나오면 버릇일 가능성이 크다.
    df = Counter()
    for i in interps:
        words = {re.sub(r"[^가-힣]", "", w) for w in i.split()}
        df.update(w for w in words if len(w) >= 2)
    common = [(w, n) for w, n in df.most_common(60) if n / len(interps) >= 0.05]
    print("자주 쓰인 어절(5% 이상):", " · ".join(f"{w} {n}" for w, n in common))

    openings = Counter(" ".join(i.split()[:2]) for i in interps)
    print("첫머리:", " · ".join(f"{w} {n}" for w, n in openings.most_common(8)))
    endings = Counter(i.split()[-1] for i in interps)
    print("끝말:", " · ".join(f"{w} {n}" for w, n in endings.most_common(10)))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="생성하지 않고 검수표만 본다")
    ap.add_argument("--redo", nargs="+", default=[], metavar="REF", help="이 참조들은 다시 만든다")
    ap.add_argument("--redo-all", action="store_true", help="검토 전 초안을 통째로 다시 만든다(고친 행도 덮어쓴다)")
    ap.add_argument("--limit", type=int, default=0, help="이번에 만들 최대 개수(0=전부)")
    ap.add_argument("--model", default="claude-haiku-5-5")
    ap.add_argument("--effort", default="medium", help="생각 강도(low/medium/high)")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    cards = load_cards()
    order = [c["reference"] for c in cards]
    rows = load_interpretations()

    unknown = [r for r in args.redo if r not in order]
    if unknown:
        raise SystemExit(f"카드에 없는 참조: {unknown}")

    if args.check:
        report(cards, rows)
        return 0

    todo = [c for c in cards
            if c["reference"] not in rows
            or rows[c["reference"]][0] != c["text"]
            or c["reference"] in args.redo
            or args.redo_all]
    if args.limit:
        todo = todo[: args.limit]
    if not todo:
        print("만들 풀이가 없다.")
        report(cards, rows)
        return 0

    import anthropic  # 검수만 할 때는 anthropic 이 없어도 되게 여기서 부른다

    from settings import load_dotenv

    load_dotenv()
    # ⚠️ 운영 서버와 같은 키다(backend/.env). 대량 생성은 운영 잔액을 같이 쓴다 —
    # 2026-09-17 이 스크립트가 OpenAI 크레딧을 바닥내 운영 AI 기능이 전부 멈췄다.
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    print(f"{len(todo)}개 생성 — {args.model} (생각 {args.effort}), 동시 {args.workers}")

    def work(card: dict) -> tuple[str, str, str]:
        interp = generate_interpretation(
            client, args.model, card["reference"], card["text"],
            kind=card.get("type"), reasoning_effort=args.effort, check_habits=True,
            form=pick_form(card["reference"]),
        )
        return card["reference"], card["text"], interp

    started, done, failed = time.time(), 0, []
    with ThreadPoolExecutor(args.workers) as pool:
        futures = {pool.submit(work, c): c["reference"] for c in todo}
        for fut in as_completed(futures):
            ref = futures[fut]
            try:
                ref, text, interp = fut.result()
            except Exception as exc:  # noqa: BLE001 — 한 장이 실패해도 나머지는 계속 만든다
                failed.append(ref)
                print(f"  실패 {ref}: {exc}")
                continue
            rows[ref] = (text, interp)
            done += 1
            if done % 20 == 0:
                save_tsv(rows, order)  # 중간에 끊겨도 만든 것은 남긴다
                print(f"  {done}/{len(todo)} ({time.time() - started:.0f}초)")
    save_tsv(rows, order)
    print(f"완료 {done} · 실패 {len(failed)} ({time.time() - started:.0f}초) → {TSV}")
    for ref in failed:
        print(f"  다시 돌릴 것: {ref}")
    report(cards, rows)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
