"""성경 절 '위로 추천 적합성' 일괄 분류 (이슈 #11).

감정 쿼리 임베딩 검색은 절 하나의 표면 텍스트만 보므로, 심판 신탁·진멸
명령·족보·악인의 대사·죽음 소원 탄식 같은 구절이 위로 카드로 새어 나온다
(욥 6:10 은 본문에 '위로'가 있지만 실제론 죽음을 구하는 탄식 — 저지 검증으로
확인). 절 텍스트+참조를 LLM 에 주면 정경 문맥을 알기에 정확히 거를 수 있다.

영어(WEB) 기준으로 전 절을 1회 분류해 '부적합' 참조 목록을 만들고,
(book_code, chapter, verse) 좌표로 전 언어(한국어 포함)의 검색 필터에 쓴다.
프랑스어 시편처럼 절번호가 밀리는 장에서는 좌표가 어긋날 수 있으나, 부적합
범주(정복 서사·신탁·족보)는 시편 밖에 몰려 있어 실용적으로 무해하다.

묶음은 성경 순서대로 25절씩이라 한 묶음이 앞뒤 문맥 노릇도 한다.

    # 처음부터 전부(약 1,250회 호출)
    python scripts/classify_verse_suitability.py --out data/langs/unsuitable_refs.json
    # 지금 목록에서 한 절도 안 걸린 묶음만 다시(빈 묶음 메우기)
    python scripts/classify_verse_suitability.py --holes

⚠️ 2026-11-25 까지의 목록(gpt-4o-mini)은 묶음 222개(5,550절)가 비어 있었다. 옛 스크립트가
429 로 실패한 묶음을 '전부 적합'으로 넘겼기 때문이다(에스겔 21:6-30 칼 심판 신탁이 통째로
빠져 「I will cause my wrath to rest」가 가족 걱정 위로 카드로 나갔다). 이제 실패한 묶음은
결과에 넣지 않고 끝에 번호를 출력하며 종료 코드 1 로 끝난다 — `--holes` 로 다시 돌리면 된다.

요구: ANTHROPIC_API_KEY(backend/.env — 운영과 같은 키다. 전부 돌리면 약 1,250회, 수십 센트).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BATCH = 25
LIST_PATH = ROOT / "data" / "langs" / "unsuitable_refs.json"

SYSTEM = """You screen Bible verses for a comfort-recommendation app. \
A later selection step already picks the BEST verses among candidates — your job \
is NOT to judge whether a verse is comforting. Your ONLY job is to remove verses \
that would be actively jarring, dark, or harmful if shown alone on a comfort card \
to a hurting user.

DEFAULT TO SUITABLE. Neutral narrative, creation, dialogue, laws in passing, wisdom, \
mild warnings, honest laments of sorrow or struggle — all suitable.

Mark UNSUITABLE ONLY for (use your knowledge of the canonical context of the reference; \
the items are consecutive verses, so read each one with its neighbours):
- judgment / vengeance / destruction oracles (wrath pronounced or executed) — including \
a verse that sounds calm on its own but closes or belongs to such an oracle \
(e.g. "I will cause my wrath to rest" at the end of the sword oracle of Ezekiel 21)
- commands to destroy peoples; battle slaughter and gore
- genealogies, name lists, censuses (verses that are mostly proper names)
- words spoken by villains or tempters (e.g. the adulteress of Proverbs 7)
- laments wishing for death (e.g. Job 3; Job 6:8-10)
- curses and imprecations against people
Return the item numbers of the UNSUITABLE verses only (an empty list if none)."""

_SCHEMA = {
    "type": "object",
    "properties": {"unsuitable": {"type": "array", "items": {"type": "integer"}}},
    "required": ["unsuitable"],
    "additionalProperties": False,
}


def ref_key(row: dict) -> str:
    return f"{row['book_code']} {int(row['chapter'])}:{int(row['verse'])}"


def load_rows() -> list[dict]:
    with open(ROOT / "data" / "langs" / "en" / "verses.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def make_batches(rows: list[dict]) -> list[list[dict]]:
    # 옛 목록과 같은 경계(성경 순서 25절씩)여야 --holes 가 빈 묶음을 정확히 짚는다.
    return [rows[i : i + BATCH] for i in range(0, len(rows), BATCH)]


def empty_batches(batches: list[list[dict]], flagged: set[str]) -> list[int]:
    """한 절도 부적합으로 안 걸린 묶음 번호. 실패해서 비었을 수도, 정말 다 괜찮을 수도 있다."""
    return [i for i, b in enumerate(batches) if not any(ref_key(r) in flagged for r in b)]


def classify(batch: list[dict]) -> list[str] | None:
    """부적합 절의 참조 목록. 끝내 실패하면 None — '전부 적합'으로 착각하지 않게 구분한다."""
    import llm

    listing = "\n".join(
        f"{n + 1}. {r['book']} {r['chapter']}:{r['verse']} — {r['text'][:220]}"
        for n, r in enumerate(batch)
    )
    for attempt in range(4):
        try:
            # 문맥을 따져야 하는 분류라 생각을 켠다(Haiku 5.5 기본 medium). 생각 토큰도 상한에 든다.
            resp = llm.client().messages.create(
                model=llm.LLM_MODEL,
                max_tokens=6000,
                system=SYSTEM,
                messages=[{"role": "user", "content": listing}],
                output_config={"effort": "medium", **llm.json_format(_SCHEMA)},
            )
            nums = json.loads(llm.response_text(resp))["unsuitable"]
            return [ref_key(batch[n - 1]) for n in nums if 1 <= int(n) <= len(batch)]
        except Exception as e:  # 429·과부하는 물러났다 다시
            if attempt == 3:
                print(f"묶음 실패: {batch[0]['book']} {batch[0]['chapter']}:{batch[0]['verse']} — {e}")
                return None
            time.sleep(5 * (attempt + 1))
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(LIST_PATH))
    ap.add_argument("--holes", action="store_true", help="지금 목록에서 비어 있는 묶음만 다시 분류해 합친다")
    ap.add_argument("--limit", type=int, help="앞쪽 N개 묶음만(시험 실행용)")
    ap.add_argument("--dry-run", action="store_true", help="파일을 쓰지 않고 결과만 출력")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    from settings import load_dotenv

    load_dotenv()
    import llm

    if not llm.configured():
        sys.exit("ANTHROPIC_API_KEY 가 없다")

    rows = load_rows()
    batches = make_batches(rows)
    current = json.loads(LIST_PATH.read_text(encoding="utf-8")) if args.holes else {}
    flagged: set[str] = set(current.get("unsuitable", []))
    targets = empty_batches(batches, flagged) if args.holes else list(range(len(batches)))
    if args.limit:
        targets = targets[: args.limit]
    print(f"{len(rows)}절, 묶음 {len(batches)}개 중 {len(targets)}개 분류")

    found: list[str] = []
    failed: list[int] = []
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for bi, bad in zip(targets, pool.map(lambda i: classify(batches[i]), targets)):
            if bad is None:
                failed.append(bi)
            else:
                found.extend(bad)
            done += 1
            if done % 25 == 0:
                print(f"{done}/{len(targets)} 묶음, 부적합 {len(found)}, 실패 {len(failed)}", flush=True)

    result = (flagged | set(found)) if args.holes else set(found)
    model = llm.LLM_MODEL
    if args.holes:
        model = f"{current.get('model', '?')} + {llm.LLM_MODEL}(빈 묶음 {len(targets) - len(failed)}개)"
    print(f"새로 걸린 절 {len(found)}개 · 전체 부적합 {len(result)}/{len(rows)} ({100 * len(result) / len(rows):.1f}%)")
    if args.dry_run:
        for ref in sorted(found):
            print(" ", ref)
    else:
        Path(args.out).write_text(
            json.dumps({"model": model, "total": len(rows), "unsuitable": sorted(result)},
                       ensure_ascii=False, indent=0) + "\n",
            encoding="utf-8",
        )
        print(f"→ {args.out}")
    if failed:
        print(f"⚠️ 실패한 묶음 {len(failed)}개(목록에 안 들어감) — --holes 로 다시 돌릴 것: {failed}")
        sys.exit(1)


if __name__ == "__main__":
    main()
