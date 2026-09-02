# -*- coding: utf-8 -*-
"""오늘의 말씀 카드 재검토 — 진행분을 파일에 남겨 세션이 끊겨도 이어간다.

전수 재검토는 사람이 카드를 한 장씩 읽고 판정하는 일이라 오래 걸린다. 세션이
바뀌면 처음부터 다시 읽게 되므로, 판정을 그때그때 `docs/verse_picks/recheck.tsv`
에 적어 두고 남은 것만 다시 읽는다.

    # 1. 아직 안 본 것 중 앞에서 200개 보여주기
    python scripts/recheck_verse_cards.py next --limit 200

    # 2. 읽고 판정을 기록 (keep 은 생략 가능 — drop 만 적어도 된다)
    python scripts/recheck_verse_cards.py mark --drop "마태복음 5:23" "누가복음 10:20" \\
        --reason "끊김"
    python scripts/recheck_verse_cards.py mark --keep-rest    # 그 배치의 나머지는 통과 처리

    # 3. 진행 상황
    python scripts/recheck_verse_cards.py status

    # 4. 다 끝나면 drop 을 선정 목록(*.tsv)에 반영
    python scripts/recheck_verse_cards.py apply

`recheck.tsv` 형식: reference / verdict(keep|drop) / reason
"""
from __future__ import annotations

import argparse
import csv
import glob
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PICKS = ROOT / "docs" / "verse_picks"
LOG = PICKS / "recheck.tsv"
FIELDS = ["reference", "verdict", "reason"]


def load_cards() -> list[dict]:
    out = []
    for f in sorted(glob.glob(str(PICKS / "*_cards.csv"))):
        with open(f, encoding="utf-8-sig") as fh:
            out += list(csv.DictReader(fh))
    return out


def load_log() -> dict[str, dict]:
    if not LOG.exists():
        return {}
    with open(LOG, encoding="utf-8") as fh:
        return {r["reference"]: r for r in csv.DictReader(fh, delimiter="\t")}


def save_log(rows: dict[str, dict]) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, delimiter="\t")
        w.writeheader()
        for ref in rows:
            w.writerow(rows[ref])


def cmd_next(args) -> int:
    done = load_log()
    left = [c for c in load_cards() if c["reference"] not in done]
    for c in left[: args.limit]:
        print(f"{c['reference']}\t{c['type'][0]}\t{c['text']}")
    print(f"\n# 남은 {len(left)}개 중 {min(args.limit, len(left))}개 표시", flush=True)
    return 0


def cmd_mark(args) -> int:
    rows = load_log()
    for ref in args.drop:
        rows[ref] = {"reference": ref, "verdict": "drop", "reason": args.reason}
    for ref in args.keep:
        rows[ref] = {"reference": ref, "verdict": "keep", "reason": ""}
    if args.keep_rest:
        # 이번 배치에서 drop 으로 찍지 않은 앞쪽 카드를 통과 처리한다.
        cards = load_cards()
        marked = set(rows)
        n = 0
        for c in cards:
            if c["reference"] in marked:
                continue
            rows[c["reference"]] = {"reference": c["reference"], "verdict": "keep", "reason": ""}
            n += 1
            if n >= args.keep_rest:
                break
        print(f"{n}개 통과 처리")
    save_log(rows)
    return cmd_status(args)


def cmd_status(args) -> int:
    cards = load_cards()
    log = load_log()
    keep = sum(1 for r in log.values() if r["verdict"] == "keep")
    drop = sum(1 for r in log.values() if r["verdict"] == "drop")
    left = len(cards) - len(log)
    pct = len(log) / len(cards) * 100 if cards else 0
    print(f"재검토 {len(log)}/{len(cards)} ({pct:.0f}%) — 통과 {keep} · 탈락 {drop} · 남음 {left}")
    if drop:
        reasons = {}
        for r in log.values():
            if r["verdict"] == "drop":
                reasons[r["reason"] or "(사유없음)"] = reasons.get(r["reason"] or "(사유없음)", 0) + 1
        print("  탈락 사유: " + " · ".join(f"{k} {v}" for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])))
    return 0


def cmd_apply(args) -> int:
    """drop 판정을 선정 목록(*.tsv)에서 실제로 제거한다."""
    log = load_log()
    drops = {r["reference"] for r in log.values() if r["verdict"] == "drop"}
    # 카드 표기(b·합본)를 선정 목록의 시작 절 표기로 되돌린다
    starts = set()
    for ref in drops:
        base = ref.rstrip("b")
        starts.add(base.split("-")[0])
    total = 0
    for f in sorted(glob.glob(str(PICKS / "*.tsv"))):
        p = Path(f)
        if p.name == LOG.name:
            continue
        lines = p.read_text(encoding="utf-8").splitlines(True)
        out = []
        for l in lines:
            ref = l.split("\t")[0]
            if l.startswith("#") or ref == "ref":
                out.append(l)
                continue
            if ref in drops or ref.split("-")[0] in starts:
                total += 1
                continue
            out.append(l)
        p.write_text("".join(out), encoding="utf-8")
    print(f"선정 목록에서 {total}개 제거. 이제 build_verse_cards.py 로 카드를 다시 만들 것:")
    print("  for f in psalms proverbs isaiah gospels paul general; do "
          "python scripts/build_verse_cards.py docs/verse_picks/$f.tsv; done")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("next", help="아직 안 본 카드를 보여준다")
    p.add_argument("--limit", type=int, default=200)
    p.set_defaults(fn=cmd_next)

    p = sub.add_parser("mark", help="판정을 기록한다")
    p.add_argument("--drop", nargs="*", default=[])
    p.add_argument("--keep", nargs="*", default=[])
    p.add_argument("--keep-rest", type=int, default=0,
                   help="아직 안 찍은 앞쪽 N개를 통과 처리")
    p.add_argument("--reason", default="")
    p.set_defaults(fn=cmd_mark)

    p = sub.add_parser("status", help="진행 상황")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("apply", help="drop 판정을 *.tsv 에 반영")
    p.set_defaults(fn=cmd_apply)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
