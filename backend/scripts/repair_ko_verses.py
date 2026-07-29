"""한국어 verses.csv 결손 보수 (이슈 #13).

기존 데이터(eBible/bible4u 계열 디지털화)는 49개 장에서 절이 누락되거나
중간 결손 후 재번호돼 있다(베드로전서 5장 통째, 시편 118편 9/29절 등).
완전한 개역한글 소스(getbible, 퍼블릭 도메인, 표기 계열이 기존과 동일한
현대화 표기)에서 **절 번호 집합이 다른 장만** 통째로 교체(splice)한다 —
정상 장의 본문은 1바이트도 바꾸지 않는다.

    python scripts/repair_ko_verses.py --source /path/to/getbible_korean.json
    # 소스가 없으면: curl -o korean.json https://api.getbible.net/v2/korean.json

교체 후 scripts/../index.py 로 재인덱싱하고 verify_quantized_model.py 게이트를
다시 통과시켜야 한다.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BOOKS = [
    "창세기", "출애굽기", "레위기", "민수기", "신명기", "여호수아", "사사기",
    "룻기", "사무엘상", "사무엘하", "열왕기상", "열왕기하", "역대상", "역대하",
    "에스라", "느헤미야", "에스더", "욥기", "시편", "잠언", "전도서", "아가",
    "이사야", "예레미야", "예레미야애가", "에스겔", "다니엘", "호세아", "요엘",
    "아모스", "오바댜", "요나", "미가", "나훔", "하박국", "스바냐", "학개",
    "스가랴", "말라기", "마태복음", "마가복음", "누가복음", "요한복음",
    "사도행전", "로마서", "고린도전서", "고린도후서", "갈라디아서", "에베소서",
    "빌립보서", "골로새서", "데살로니가전서", "데살로니가후서", "디모데전서",
    "디모데후서", "디도서", "빌레몬서", "히브리서", "야고보서", "베드로전서",
    "베드로후서", "요한일서", "요한이서", "요한삼서", "유다서", "요한계시록",
]


def load_getbible(path: Path) -> dict[tuple[str, int], dict[int, str]]:
    """getbible korean.json → {(책, 장): {절: 본문}}."""
    data = json.loads(path.read_text(encoding="utf-8"))
    chapters: dict[tuple[str, int], dict[int, str]] = {}
    for book in data["books"]:
        name = BOOKS[int(book["nr"]) - 1]
        for ch in book["chapters"]:
            verses = {
                int(v["verse"]): " ".join(str(v["text"]).split())
                for v in ch["verses"]
                if str(v["text"]).strip()
            }
            chapters[(name, int(ch["chapter"]))] = verses
    return chapters


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="getbible korean.json 경로")
    ap.add_argument("--csv", default=str(ROOT / "data" / "verses.csv"))
    args = ap.parse_args()

    src = load_getbible(Path(args.source))

    rows = list(csv.DictReader(open(args.csv, encoding="utf-8")))
    cur: dict[tuple[str, int], dict[int, str]] = {}
    for r in rows:
        cur.setdefault((r["book"], int(r["chapter"])), {})[int(r["verse"])] = r["text"]

    # 소스에만 있는 장(예: 벧전 5)과 절 집합이 다른 장을 교체 대상으로 삼는다.
    to_replace = sorted(
        key for key in src
        if key not in cur or set(cur[key]) != set(src[key])
    )
    only_ours = sorted(k for k in cur if k not in src)
    if only_ours:
        raise SystemExit(f"소스에 없는 장이 있음(소스 불완전?): {only_ours[:5]}")

    print(f"교체 대상 장: {len(to_replace)}")
    added = removed = 0
    for key in to_replace:
        old = cur.get(key, {})
        new = src[key]
        added += len(set(new) - set(old))
        removed += len(set(old) - set(new))
        print(
            f"  {key[0]} {key[1]}: {len(old)}절 → {len(new)}절"
            + (f" (+{len(set(new)-set(old))})" if set(new) - set(old) else "")
        )
        cur[key] = dict(new)

    # 정경 순서·장·절 순서로 재조립
    out_rows = []
    order = {b: i for i, b in enumerate(BOOKS)}
    for (book, chapter) in sorted(cur, key=lambda k: (order[k[0]], k[1])):
        for verse in sorted(cur[(book, chapter)]):
            out_rows.append(
                {"book": book, "chapter": chapter, "verse": verse,
                 "text": cur[(book, chapter)][verse]}
            )

    with open(args.csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["book", "chapter", "verse", "text"])
        w.writeheader()
        w.writerows(out_rows)

    print(f"완료: {len(rows)} → {len(out_rows)}절 (+{added} 추가, {removed} 절번호 정정)")


if __name__ == "__main__":
    main()
