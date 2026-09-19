"""오늘의 말씀 참조(단일·합본·하반절)를 다른 언어의 같은 구절로 바꾸는 localize_ko_ref.

파싱에 실패하면 호출측이 한국어 본문으로 폴백해, 외국어 사용자에게 그날 카드와
푸시가 한국어로 나간다. 2026-09-17(요한복음 8:11b)에 실제로 그랬다.
"""

import csv
import importlib.util
import json
import os
import re
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

import embedding
import languages
from languages import VerseStore, localize_ko_ref

BACKEND = Path(__file__).resolve().parent.parent
DAILY_VERSES = BACKEND / "notifications" / "daily_verses.json"
FOREIGN_LANGS = [lang for lang in languages.SUPPORTED_LANGUAGES if lang != "ko"]


class LanguageStoreTestBase(unittest.TestCase):
    """languages 모듈 전역(스토어·한국어 절수 캐시·임베더)을 테스트마다 갈아 끼운다."""

    def setUp(self) -> None:
        self._saved = (
            dict(languages._stores), languages._ko_chapter_counts, languages._encoder
        )
        languages._stores.clear()
        languages._ko_chapter_counts = None
        languages._encoder = None

    def tearDown(self) -> None:
        stores, counts, encoder = self._saved
        languages._stores.clear()
        languages._stores.update(stores)
        languages._ko_chapter_counts = counts
        languages._encoder = encoder

    def install(self, ko_df: pd.DataFrame, lang_dfs: dict[str, pd.DataFrame]) -> None:
        languages.register_ko_store(ko_df, None)
        for lang, df in lang_dfs.items():
            languages._stores[lang] = VerseStore(lang, df, None)


def ko_rows(*rows) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["book", "chapter", "verse", "text"])


def lang_rows(*rows) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["book_code", "book", "chapter", "verse", "text"])


# 가짜 임베더 — 단어를 개념 축에 올린 단위 벡터. 한국어 단어와 대응 외국어 단어가
# 같은 축이라 '같은 내용'이면 코사인이 높다. TITLE 은 fr 시편 표제(절 번호를 차지).
_CONCEPTS = {"기다림": 0, "WAIT": 0, "웅덩이": 1, "PIT": 1, "노래": 2, "SONG": 2, "TITLE": 3}


def fake_encode(texts: list[str]) -> np.ndarray:
    out = np.zeros((len(texts), len(set(_CONCEPTS.values()))), dtype="float32")
    for i, text in enumerate(texts):
        for word in text.split(": ", 1)[1].split():
            out[i, _CONCEPTS[word]] += 1
    return out / np.linalg.norm(out, axis=1, keepdims=True)


class LocalizeKoRefTest(LanguageStoreTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.install(
            ko_rows(
                ("시편", 40, 1, "기다림"),
                ("시편", 40, 2, "웅덩이"),
                ("시편", 40, 3, "노래"),
                ("요한복음", 8, 11, "가로되 주여 없나이다 예수께서 가라사대 나도 너를 정죄하지 아니하노니"),
                ("로마서", 5, 3, "환난중에도 즐거워하나니"),
                ("로마서", 5, 4, "인내는 연단을"),
                ("로마서", 5, 5, "소망이 부끄럽게 아니함은"),
            ),
            {
                "en": lang_rows(
                    ("PSA", "Psalms", 40, 1, "WAIT"),
                    ("PSA", "Psalms", 40, 2, "PIT"),
                    ("PSA", "Psalms", 40, 3, "SONG"),
                    ("JHN", "John", 8, 11, "She said, “No one, Lord.” Jesus said, “Neither do I condemn you.”"),
                    ("ROM", "Romans", 5, 3, "we also rejoice in our sufferings,"),
                    ("ROM", "Romans", 5, 4, "and perseverance, proven character;"),
                    # 5:5 가 빠진 판본 — 합본 3:5 는 반쪽이 되므로 실패해야 한다.
                ),
                # LSG 시편처럼 표제가 1절을 차지해 한국어보다 한 절씩 밀린 판본.
                "fr": lang_rows(
                    ("PSA", "Psaumes", 40, 1, "TITLE"),
                    ("PSA", "Psaumes", 40, 2, "WAIT"),
                    ("PSA", "Psaumes", 40, 3, "PIT"),
                    ("PSA", "Psaumes", 40, 4, "SONG"),
                ),
            },
        )

    def test_single_verse(self) -> None:
        self.assertEqual(
            localize_ko_ref("en", "시편 40:1", "기다림"),
            {"ref": "Psalms 40:1", "text": "WAIT"},
        )

    def test_range_joins_verses_and_keeps_range_ref(self) -> None:
        self.assertEqual(
            localize_ko_ref("en", "시편 40:1-2", "기다림 웅덩이"),
            {"ref": "Psalms 40:1-2", "text": "WAIT PIT"},
        )

    def test_partial_verse_uses_whole_verse_without_b(self) -> None:
        # 한국어 카드는 서사를 벗긴 하반절이지만 외국어는 절 전체를 싣는다.
        found = localize_ko_ref("en", "요한복음 8:11b", "나도 너를 정죄하지 아니하노니")
        self.assertEqual(found["ref"], "John 8:11")
        self.assertEqual(
            found["text"],
            "She said, “No one, Lord.” Jesus said, “Neither do I condemn you.”",
        )

    def test_range_with_partial_suffix(self) -> None:
        self.assertEqual(
            localize_ko_ref("en", "로마서 5:3-4b", "즐거워하나니 인내는 연단을")["ref"],
            "Romans 5:3-4",
        )

    def test_range_with_missing_verse_fails_instead_of_half_passage(self) -> None:
        self.assertIsNone(localize_ko_ref("en", "로마서 5:3-5", "…"))

    def test_malformed_refs_fail(self) -> None:
        for ref in ("시편 40:2-1", "시편 40:1a", "시편 40", "없는책 1:1", "시편 40:1-2-3"):
            with self.subTest(ref=ref):
                self.assertIsNone(localize_ko_ref("en", ref, "기다림"))

    def test_range_aligns_as_one_window(self) -> None:
        # fr 은 한 절 밀려 있어 임베딩으로 오프셋을 고른다. 합본 전체(ko_text)를
        # 절마다 따로 비교하면 40:2 를 두 번 고르게 된다 — 창 단위로 골라야 40:2-3.
        languages.set_encoder(fake_encode)
        self.assertEqual(
            localize_ko_ref("fr", "시편 40:1-2", "기다림 웅덩이"),
            {"ref": "Psaumes 40:2-3", "text": "WAIT PIT"},
        )
        self.assertEqual(localize_ko_ref("fr", "시편 40:3", "노래")["ref"], "Psaumes 40:4")

    def test_range_below_align_threshold_fails(self) -> None:
        languages.set_encoder(fake_encode)
        self.assertIsNone(localize_ko_ref("fr", "시편 40:1-2", "노래"))


_RE_DAILY_REF = re.compile(r"^(.+?)\s+(\d+):(\d+)(?:-(\d+))?b?$")


def _read_chapters(path: Path, book_col: str, chapters: set) -> pd.DataFrame:
    """CSV 를 한 줄씩 읽어 필요한 장만 남긴다. 테스트는 운영 서버(1GB)에서도 도니
    pd.read_csv 로 통째로 올리지 않는다(언어당 수십 MB)."""
    with open(path, encoding="utf-8", newline="") as f:
        rows = [
            r for r in csv.DictReader(f) if (r[book_col], int(r["chapter"])) in chapters
        ]
    df = pd.DataFrame(rows)
    return df.astype({"chapter": int, "verse": int})


def _real_encoder_requested() -> bool:
    """REAL_ENCODER_TEST=1 이고 int8 ONNX 모델(gitignore)과 런타임이 있는가.

    기본은 끈다 — 모델을 올리면 테스트 프로세스가 +130MB 라, 앱이 떠 있는 운영
    서버(1GB)에서 스위트를 돌릴 때 부담이 된다. 목록이나 정렬 코드를 바꿀 때 켠다.
    """
    return (
        os.environ.get("REAL_ENCODER_TEST") == "1"
        and (embedding.ONNX_DIR / "model_int8_noemb.onnx").exists()
        and (embedding.ONNX_DIR / "word_embeddings_uint8.npy").exists()
        and importlib.util.find_spec("onnxruntime") is not None
        and importlib.util.find_spec("sentencepiece") is not None
    )


@unittest.skipUnless(
    all((languages.LANG_DIR / lang / "verses.csv").exists() for lang in FOREIGN_LANGS),
    "언어별 verses.csv 없음",
)
class DailyVersesLocalizationDataTest(LanguageStoreTestBase):
    """운영 목록 daily_verses.json 전부가 7개 언어로 현지화되는지(데이터 회귀 방지).

    스토어는 git 의 verses.csv 로 만든다(서버의 verses_meta.parquet 과 같은 행).
    목록이 쓰는 장만 올려 메모리를 아낀다 — 장 절수 비교에는 장 전체면 충분하다.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.items = json.loads(DAILY_VERSES.read_text(encoding="utf-8"))
        chapters = set()
        for item in cls.items:
            m = _RE_DAILY_REF.match(item["reference"])
            if m:
                chapters.add((m.group(1), int(m.group(2))))
        coded = {(languages.KO_NAME_TO_CODE.get(b), c) for b, c in chapters}
        cls.ko_df = _read_chapters(BACKEND / "data" / "verses.csv", "book", chapters)
        cls.lang_dfs = {
            lang: _read_chapters(languages.LANG_DIR / lang / "verses.csv", "book_code", coded)
            for lang in FOREIGN_LANGS
        }

    def setUp(self) -> None:
        super().setUp()
        self.install(self.ko_df, self.lang_dfs)

    def assert_all_localize(self) -> None:
        failed = []
        for item in self.items:
            m = _RE_DAILY_REF.match(item["reference"])
            span = int(m.group(4)) - int(m.group(3)) if m and m.group(4) else 0
            for lang in FOREIGN_LANGS:
                found = localize_ko_ref(lang, item["reference"], item["text"])
                if found is None:
                    failed.append((item["reference"], lang))
                    continue
                # 하반절 b 는 떼고, 합본은 같은 길이의 범위로 나와야 한다.
                got = re.search(r"(\d+):(\d+)(?:-(\d+))?$", found["ref"])
                got_span = int(got.group(3)) - int(got.group(2)) if got and got.group(3) else 0
                if got is None or got_span != span:
                    failed.append((item["reference"], lang, found["ref"]))
        self.assertEqual(failed, [], f"현지화 실패 {len(failed)}건")

    def test_every_daily_verse_localizes(self) -> None:
        self.assert_all_localize()

    @unittest.skipUnless(
        _real_encoder_requested(), "REAL_ENCODER_TEST=1 + backend/models/e5-small-int8 필요"
    )
    def test_every_daily_verse_localizes_with_real_encoder(self) -> None:
        # 장 절수가 다른 곳은 임베딩으로 절을 고르고 코사인 0.7 미만이면 실패한다.
        languages.set_encoder(embedding.load_query_embedder().encode)
        self.assert_all_localize()


if __name__ == "__main__":
    unittest.main()
