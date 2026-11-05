"""한국어 verses.csv 와 검색 인덱스(verses_meta.parquet) 데이터 검사 (이슈 #31).

원본 kor_usfm 은 몇몇 장에서 이웃 절을 한 번 더 적거나, 다른 곳의 절을 끼워 넣거나,
밀려난 꼬리 절을 `[ (Psalms 10:19) … ]` 로 앞 절에 붙여 두었다. 그러면 그 지점부터
참조가 틀린 본문이 검색·추천에 나간다. 또 CSV 만 고치고 인덱스를 두면 사용자에게는
옛 본문이 그대로 나간다(2026-09-15 에 실제로 그랬다).

절 안의 누락·오기(잠언 30:19 구 누락, 「여호아」)와 위키문헌 계열의 「침례」는
공식 개역한글과 대조해 고쳤다(#44, scripts/audit_ko_verse_text.py).
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

    def test_verse_text_matches_official(self) -> None:
        # 원본 절 안의 누락·오기를 공식 개역한글로 고쳤다(#44) — scripts/audit_ko_verse_text.py
        self.assertIn("반석 위로 기어다니는 뱀의 자취와", self.text[("잠언", 30, 19)])
        self.assertTrue(self.text[("이사야", 27, 4)].startswith("나는 포도원에"))
        self.assertIn("너의 모든 행할 것을", self.text[("사도행전", 22, 10)])
        self.assertIn("여호와를 찬양하며", self.text[("시편", 117, 1)])
        self.assertIn("거룩함을 좇으라", self.text[("히브리서", 12, 14)])
        self.assertIn("네게 복을 주고", self.text[("창세기", 26, 3)])

    def test_baptism_is_not_immersion(self) -> None:
        # 위키문헌 계열(getbible)은 개역한글의 「세례」를 「침례」로 바꿔 두었다(#13 이 채운 장)
        bad = [f"{r['book']} {r['chapter']}:{r['verse']}" for r in self.rows if "침례" in r["text"]]
        self.assertEqual(bad, [])
        self.assertIn("세례를 받으니", self.text[("사도행전", 8, 12)])

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
