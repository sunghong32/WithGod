"""한국어 verses.csv 와 검색 인덱스(verses_meta.parquet) 데이터 검사 (이슈 #31).

원본 kor_usfm 은 몇몇 장에서 이웃 절을 한 번 더 적거나, 다른 곳의 절을 끼워 넣거나,
밀려난 꼬리 절을 `[ (Psalms 10:19) … ]` 로 앞 절에 붙여 두었다. 그러면 그 지점부터
참조가 틀린 본문이 검색·추천에 나간다. 또 CSV 만 고치고 인덱스를 두면 사용자에게는
옛 본문이 그대로 나간다(2026-09-15 에 실제로 그랬다).

절 안의 누락·오기(잠언 30:19 구 누락, 「여호아」)와 위키문헌 계열의 「침례」는
공식 개역한글과 대조해 고쳤다(#44, scripts/audit_ko_verse_text.py).

원본에서 통째로 빠졌던 아가 6:14 는 행을 새로 넣었다. 행이 하나 들어가면 그 뒤 인덱스
행 번호가 모두 밀리므로 parquet 뿐 아니라 npy·faiss 의 행 수도 CSV 와 같아야 한다.
"""

import csv
import importlib.util
import re
import unittest
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from languages import is_placeholder_text

BACKEND = Path(__file__).resolve().parent.parent
CSV = BACKEND / "data" / "verses.csv"
META = BACKEND / "data" / "verses_meta.parquet"
NPY = BACKEND / "data" / "verses.npy"
IDX = BACKEND / "data" / "verses.faiss"

# 밀려난 꼬리 절을 붙여 둔 모양과, 본문 대신 들어간 교차 참조 표지('[사37:26]')
LEFTOVER = re.compile(r"\[\s*\(|\[[가-힣]{1,3}\d+:\d+\]")

# 장 중간에 행이 없는 절 — 공회 개역한글이 「(없음)」으로 두거나 앞 절에 묶은 절이다
# (bolls 도 「(없음)」·「(1절에 포함되어 있음)」). 장 끝에서 빠진 절(아가 6:14)은 이 검사로
# 못 잡아 따로 본다.
ABSENT_IN_CHAPTER = {
    "이사야 30:2", "이사야 48:2", "예레미야 21:2", "에스겔 24:5",
    "마태복음 18:11", "마가복음 9:44", "마가복음 9:46", "마가복음 11:26", "마가복음 15:28",
    "누가복음 17:36", "누가복음 23:17", "사도행전 8:37", "사도행전 15:26", "사도행전 15:34",
    "사도행전 28:29", "로마서 9:2", "로마서 16:24",
}

# 본문 대신 자리표시가 든 행 — 검색·추천 후보에서 뺀다(languages.is_placeholder_text)
PLACEHOLDER_ROWS = {
    "신명기 6:19", "신명기 15:5", "여호수아 2:13", "사무엘상 30:31", "역대상 16:13",
    "욥기 31:34", "시편 92:2", "시편 92:3", "시편 105:6", "이사야 7:9", "예레미야 32:5",
    "에스겔 25:3", "마태복음 17:21", "마태복음 23:14",
}


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

    def test_song_6_14_restored(self) -> None:
        # 원본(eBible kor)에 없던 절 — 공회·bolls 는 6:14, getbible 은 6:13 에 합쳐 둠
        self.assertEqual(
            self.text[("아가", 6, 14)],
            "너희가 어찌하여 마하나임의 춤추는 것을 보는 것처럼 술람미 여자를 보려느냐",
        )
        refs = [(r["book"], r["chapter"], r["verse"]) for r in self.rows]
        at = refs.index(("아가", "6", "14"))
        self.assertEqual(refs[at - 1:at + 2], [("아가", "6", "13"), ("아가", "6", "14"), ("아가", "7", "1")])

    def test_no_missing_verse_inside_chapter(self) -> None:
        verses = defaultdict(list)
        for r in self.rows:
            verses[(r["book"], int(r["chapter"]))].append(int(r["verse"]))
        unsorted = [f"{b} {c}장" for (b, c), vs in verses.items() if vs != sorted(vs)]
        self.assertEqual(unsorted, [])
        holes = {f"{b} {c}:{v}" for (b, c), vs in verses.items()
                 for v in range(1, max(vs) + 1) if v not in vs}
        self.assertEqual(holes, ABSENT_IN_CHAPTER)

    def test_placeholder_rows(self) -> None:
        # 「(18절과 같음)」·「(앞절과 동일)」·「(없음)」만 든 행. 늘면 검색 후보에 새는지 볼 것
        found = {f"{r['book']} {r['chapter']}:{r['verse']}" for r in self.rows
                 if is_placeholder_text(r["text"])}
        self.assertEqual(found, PLACEHOLDER_ROWS)
        # 괄호로 감싼 진짜 본문은 자리표시가 아니다
        for k in [("신명기", 3, 9), ("사무엘상", 30, 5), ("요한복음", 4, 2), ("시편", 67, 1)]:
            self.assertFalse(is_placeholder_text(self.text[k]), k)

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

    def test_search_vectors_match_csv_rows(self) -> None:
        # FAISS 가 돌려주는 번호로 parquet 행을 읽는다 — 행을 넣거나 빼면 셋이 같이 바뀌어야 한다
        self.assertEqual(np.load(NPY, mmap_mode="r").shape[0], len(self.rows))

    @unittest.skipUnless(importlib.util.find_spec("faiss"), "faiss 없음")
    def test_faiss_matches_npy(self) -> None:
        import faiss

        vecs = np.load(NPY, mmap_mode="r")
        index = faiss.read_index(str(IDX), faiss.IO_FLAG_MMAP | faiss.IO_FLAG_READ_ONLY)
        self.assertEqual(index.ntotal, len(self.rows))
        song = [i for i, r in enumerate(self.rows) if (r["book"], r["chapter"]) == ("아가", "6")][-1]
        for i in (0, song, song + 1, len(self.rows) - 1):
            np.testing.assert_array_equal(index.reconstruct(i), vecs[i])


if __name__ == "__main__":
    unittest.main()
