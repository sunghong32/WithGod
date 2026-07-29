"""성경 절 '위로 추천 적합성' 일괄 분류 (이슈 #11).

감정 쿼리 임베딩 검색은 절 하나의 표면 텍스트만 보므로, 심판 신탁·진멸
명령·족보·악인의 대사·죽음 소원 탄식 같은 구절이 위로 카드로 새어 나온다
(욥 6:10 은 본문에 '위로'가 있지만 실제론 죽음을 구하는 탄식 — 저지 검증으로
확인). 절 텍스트+참조를 LLM 에 주면 정경 문맥을 알기에 정확히 거를 수 있다.

영어(WEB) 기준으로 전 절을 1회 분류해 '부적합' 참조 목록을 만들고,
(book_code, chapter, verse) 좌표로 전 언어(한국어 포함)의 검색 필터에 쓴다.
프랑스어 시편처럼 절번호가 밀리는 장에서는 좌표가 어긋날 수 있으나, 부적합
범주(정복 서사·신탁·족보)는 시편 밖에 몰려 있어 실용적으로 무해하다.

    python scripts/classify_verse_suitability.py \
        --out data/langs/unsuitable_refs.json [--limit 500]

요구: OPENAI_API_KEY(backend/.env). 약 1,250회 호출(gpt-4o-mini, ~$1).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BATCH = 25

SYSTEM = """You screen Bible verses for a comfort-recommendation app. \
A later selection step already picks the BEST verses among candidates — your job \
is NOT to judge whether a verse is comforting. Your ONLY job is to remove verses \
that would be actively jarring, dark, or harmful if shown alone on a comfort card \
to a hurting user.

DEFAULT TO true. Neutral narrative, creation, dialogue, laws in passing, wisdom, \
mild warnings, honest laments of sorrow or struggle — all true.

Mark false ONLY for (use your knowledge of the canonical context of the reference):
- judgment / vengeance / destruction oracles (wrath pronounced or executed)
- commands to destroy peoples; battle slaughter and gore
- genealogies, name lists, censuses (verses that are mostly proper names)
- words spoken by villains or tempters (e.g. the adulteress of Proverbs 7)
- laments wishing for death (e.g. Job 3; Job 6:8-10)
- curses and imprecations against people
Return ONLY a JSON object mapping each item number to true/false."""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/langs/unsuitable_refs.json")
    ap.add_argument("--limit", type=int, help="앞쪽 N개 절만(시험 실행용)")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    from settings import load_dotenv

    load_dotenv()
    from openai import OpenAI
    import os

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    root = Path(__file__).resolve().parent.parent
    rows = list(csv.DictReader(open(root / "data" / "langs" / "en" / "verses.csv")))
    if args.limit:
        rows = rows[: args.limit]
    batches = [rows[i : i + BATCH] for i in range(0, len(rows), BATCH)]
    print(f"{len(rows)}절, {len(batches)}배치")

    def classify(batch):
        listing = "\n".join(
            f"{n + 1}. {r['book']} {r['chapter']}:{r['verse']} — {r['text'][:220]}"
            for n, r in enumerate(batch)
        )
        verdicts = None
        for attempt in range(4):  # 429(분당 토큰 한도)는 짧게 물러났다 재시도
            try:
                resp = client.chat.completions.create(
                    model=model,
                    temperature=0,
                    max_tokens=400,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": SYSTEM},
                        {"role": "user", "content": listing},
                    ],
                )
                verdicts = json.loads(resp.choices[0].message.content)
                break
            except Exception as e:
                if attempt == 3:
                    print("배치 실패:", e)
                    return []  # '전부 적합'으로 두고 넘어간다
                time.sleep(5 * (attempt + 1))
        bad = []
        for n, r in enumerate(batch):
            if verdicts.get(str(n + 1)) is False:
                bad.append(f"{r['book_code']} {int(r['chapter'])}:{int(r['verse'])}")
        return bad

    unsuitable: list[str] = []
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for bad in pool.map(classify, batches):
            unsuitable.extend(bad)
            done += 1
            if done % 100 == 0:
                print(f"{done}/{len(batches)} 배치, 부적합 {len(unsuitable)}")

    out = root / args.out
    out.write_text(
        json.dumps({"model": model, "total": len(rows), "unsuitable": sorted(unsuitable)},
                   ensure_ascii=False, indent=0) + "\n",
        encoding="utf-8",
    )
    print(f"완료: 부적합 {len(unsuitable)}/{len(rows)} ({100*len(unsuitable)/len(rows):.1f}%) → {out}")


if __name__ == "__main__":
    main()
