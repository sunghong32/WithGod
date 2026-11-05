"""한국어 verses.csv 와 검색 인덱스(verses_meta.parquet) 데이터 검사 (이슈 #31).

원본 kor_usfm 은 몇몇 장에서 이웃 절을 한 번 더 적거나, 다른 곳의 절을 끼워 넣거나,
밀려난 꼬리 절을 `[ (Psalms 10:19) … ]` 로 앞 절에 붙여 두었다. 그러면 그 지점부터
참조가 틀린 본문이 검색·추천에 나간다. 또 CSV 만 고치고 인덱스를 두면 사용자에게는
옛 본문이 그대로 나간다(2026-09-15 에 실제로 그랬다).
"""

import csv
import re
import unittest
from pathlib import Path

import pandas as pd

BACKEND = Path(__file__).resolve().parent.parent
CSV = BACKEND / "data" / "verses.csv"
META = BACKEND / "data" / "verses_meta.parquet"

# 밀려난 꼬리 절을 붙여 둔 모양과, 본문 대신 들어간 교차 참조 표지('[사37:26]')
LEFTOVER = re.compile(r"\[\s*\(|\[[가-힣]{1,3}\d+:\d+\]")


def ws(s: str) -> str:
    return " ".join(s.split())


class KoVersesDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with open(CSV, encoding="utf-8") as f:
            cls.rows = list(csv.DictReader(f))
        cls.text = {(r["book"], int(r["chapter"]), int(r["verse"])): r["text"] for r in cls.rows}

    def test_no_leftover_source_markers(self) -> None:
        bad = [f"{r['book']} {r['chapter']}:{r['verse']}" for r in self.rows
               if LEFTOVER.search(r["text"])]
        self.assertEqual(bad, [])

    def test_no_verse_repeats_the_next_one(self) -> None:
        # 원본은 빠진 절 자리에 이웃 절을 한 번 더 적었다(예레미야 25:21 = 25:22)
        bad = [
            f"{a['book']} {a['chapter']}:{a['verse']}"
            for a, b in zip(self.rows, self.rows[1:])
            if (a["book"], a["chapter"]) == (b["book"], b["chapter"])
            and len(a["text"].strip()) > 10 and ws(a["text"]) == ws(b["text"])
        ]
        self.assertEqual(bad, [])

    def test_restored_verses(self) -> None:
        # 원본에 없던 절, 다른 곳의 절이 빠진 자리, 그 절의 제자리
        self.assertEqual(self.text[("예레미야", 25, 21)], "에돔과 모압과 암몬 자손과")
        self.assertTrue(self.text[("잠언", 30, 32)].startswith("만일 네가 미련하여"))
        self.assertTrue(self.text[("이사야", 27, 11)].startswith("가지가 마르면 꺾이나니"))
        self.assertTrue(self.text[("시편", 10, 12)].startswith("여호와여, 일어나옵소서"))
        self.assertIn("주의 앞에는 기쁨이 충만하고", self.text[("시편", 16, 11)])

    def test_search_index_matches_csv(self) -> None:
        # 앱은 CSV 가 아니라 parquet·faiss 를 읽는다 — 고친 뒤엔 sync_index_with_csv.py 를 돌릴 것
        meta = pd.read_parquet(META, columns=["book", "chapter", "verse", "text"])
        self.assertEqual(len(meta), len(self.rows))
        stale = [
            f"{b} {c}:{v}"
            for (b, c, v, t), r in zip(meta.itertuples(index=False), self.rows)
            if (b, str(c), str(v), t) != (r["book"], r["chapter"], r["verse"], r["text"])
        ]
        self.assertEqual(stale[:5], [])


if __name__ == "__main__":
    unittest.main()
