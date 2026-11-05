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


class IntlLangsTest(unittest.TestCase):
    def test_interpretation_langs_match_supported_languages(self) -> None:
        # interpretation.py 는 languages 를 import 하지 않아 목록을 따로 둔다 — 둘이 어긋나면 검토본이 빠진다
        from notifications.interpretation import INTL_LANGS

        self.assertEqual(list(INTL_LANGS), FOREIGN_LANGS)


class LanguageStoreTestBase(unittest.TestCase):
    """languages 모듈 전역(스토어·한국어 절수 캐시·임베더)을 테스트마다 갈아 끼운다."""

    def setUp(self) -> None:
        self._saved = (
            dict(languages._stores), languages._ko_last_verses, languages._encoder
        )
        languages._stores.clear()
        languages._ko_last_verses = None
        languages._encoder = None

    def tearDown(self) -> None:
        stores, counts, encoder = self._saved
        languages._stores.clear()
        languages._stores.update(stores)
        languages._ko_last_verses = counts
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
_CONCEPTS = {
    "기다림": 0, "WAIT": 0, "웅덩이": 1, "PIT": 1, "노래": 2, "SONG": 2, "TITLE": 3,
    "기도": 4, "PRAY": 4, "조롱": 5, "MOCK": 5, "낙망": 6, "DESPAIR": 6, "소망": 7, "HOPE": 7,
    "PRAISE": 8,
}


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


class AlignWithContextTest(LanguageStoreTestBase):
    """절 번호가 밀린 장에서 후보를 앞뒤 절까지 묶어 고르는지(#33)."""

    def test_neighbours_outvote_a_lookalike_verse(self) -> None:
        # fr(LSG) 시편 42 처럼 표제가 1절을 차지해 한국어 42:11 = fr 42:12. fr 42:11(원수의
        # 조롱)이 후렴과 단어를 많이 나눠 카드 한 절만 비교하면 이긴다(0.94 > 0.82) — 실제로
        # 그렇게 나갔다. 앞 절들은 한 절 밀린 쪽에서만 맞아 떨어져 정답을 끌어온다.
        self.install(
            ko_rows(("시편", 42, 9, "기도"), ("시편", 42, 10, "조롱"), ("시편", 42, 11, "낙망 소망")),
            {"fr": lang_rows(
                ("PSA", "Psaumes", 42, 1, "TITLE"),
                ("PSA", "Psaumes", 42, 9, "SONG"),
                ("PSA", "Psaumes", 42, 10, "PRAY"),
                ("PSA", "Psaumes", 42, 11, "MOCK DESPAIR DESPAIR HOPE HOPE"),
                ("PSA", "Psaumes", 42, 12, "DESPAIR HOPE PRAISE"),
            )},
        )
        languages.set_encoder(fake_encode)
        self.assertEqual(
            localize_ko_ref("fr", "시편 42:11", "낙망 소망"),
            {"ref": "Psaumes 42:12", "text": "DESPAIR HOPE PRAISE"},
        )

    def test_missing_korean_verse_number_keeps_same_number(self) -> None:
        # 개역한글은 사본에 없는 절을 번호째 비운다(눅 17:36 등). 절 수는 한 절 적어도 마지막
        # 절 번호가 같으면 밀린 게 아니다 — 임베딩으로 고르지 않고 같은 번호 절을 낸다.
        self.install(
            ko_rows(("누가복음", 17, 35, "기다림"), ("누가복음", 17, 37, "웅덩이")),
            {"en": lang_rows(
                ("LUK", "Luke", 17, 35, "WAIT"),
                ("LUK", "Luke", 17, 36, "SONG"),
                ("LUK", "Luke", 17, 37, "PIT"),
            )},
        )
        calls = []
        languages.set_encoder(lambda texts: calls.append(texts) or fake_encode(texts))
        self.assertEqual(localize_ko_ref("en", "누가복음 17:35", "기다림")["ref"], "Luke 17:35")
        self.assertEqual(calls, [])

    def test_korean_context_drops_psalm_title(self) -> None:
        # 한국어 시편 1절은 본문 앞에 표제를 괄호로 붙여 둔다. LSG 는 표제를 따로 세므로
        # 문맥으로 비교할 때 붙여 두면 표제 절(fr 52:2)과 엮인다.
        self.install(ko_rows(("시편", 52, 1, "(다윗의 마스길. 영장으로 한 노래) 강포한 자여")), {})
        self.assertEqual(languages._ko_chapter_texts("PSA", 52), {1: "강포한 자여"})


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


INTL_DIR = BACKEND / "docs" / "verse_picks" / "interpretations_intl"

# 장 마지막 절 번호가 한국어와 1~3 달라 임베딩으로 절을 고르는 결정 — 한국어와 그 언어
# 본문을 나란히 놓고 사람이 확인한 정답(2026-11-05, #33). 목록이 바뀌어 이런 결정이 새로
# 생기면 test_offset_decisions_are_reviewed 가 실패한다 → 본문을 보고 여기에 더한다.
REVIEWED_OFFSETS = {
    # fr(LSG) 시편은 표제가 1절(51편은 1~2절)을 차지한다.
    ("시편 4:8", "fr"): "Psaumes 4:9",
    ("시편 18:28", "fr"): "Psaumes 18:29",
    ("시편 20:4", "fr"): "Psaumes 20:5",
    ("시편 30:11", "fr"): "Psaumes 30:12",
    ("시편 34:4", "fr"): "Psaumes 34:5",
    ("시편 34:14", "fr"): "Psaumes 34:15",
    ("시편 34:18", "fr"): "Psaumes 34:19",
    ("시편 34:19", "fr"): "Psaumes 34:20",
    ("시편 40:1-2", "fr"): "Psaumes 40:2-3",
    ("시편 42:11", "fr"): "Psaumes 42:12",  # 42:11 은 원수의 조롱 — 한 절 비교 때 나가던 오답
    ("시편 51:10", "fr"): "Psaumes 51:12",
    ("시편 51:17", "fr"): "Psaumes 51:19",
    ("시편 55:22", "fr"): "Psaumes 55:23",
    ("시편 61:2", "fr"): "Psaumes 61:3",
    ("시편 62:8", "fr"): "Psaumes 62:9",
    ("시편 102:17", "fr"): "Psaumes 102:18",
    ("시편 140:12", "fr"): "Psaumes 140:13",
    # 장 끝에서 절을 더 세는 판본 — 밀지 않는다(fr 전도서 4:17 = 한국어 5:1, en 로마서 14:24-26 = 16:25-27).
    ("전도서 4:10", "fr"): "Ecclésiaste 4:10",
    ("전도서 4:12", "fr"): "Ecclésiaste 4:12",
    ("로마서 14:10", "en"): "Romans 14:10",
    # LSG 는 한국어 9:50 을 50·51 두 절로 나눴다. 한 절만 고르는 지금 정렬로는 9:51
    # (「서로 화목하라」)이 빠진다 — 절 분할 대응은 따로 다룬다.
    ("마가복음 9:50", "fr"): "Marc 9:50",
}


def _read_intl_local_refs(lang: str) -> dict[str, str]:
    """외국어 풀이 검토본 TSV 의 {한국어 참조: 현지 참조}(3열)."""
    out = {}
    for line in (INTL_DIR / f"{lang}.tsv").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            parts = line.split("\t")
            out[parts[0]] = parts[2]
    return out


@unittest.skipUnless(
    all((languages.LANG_DIR / lang / "verses.csv").exists() for lang in FOREIGN_LANGS),
    "언어별 verses.csv 없음",
)
class DailyVersesLocalizationDataTest(LanguageStoreTestBase):
    """운영 목록 daily_verses.json 전부가 7개 언어로 현지화되는지(데이터 회귀 방지).

    스토어는 git 의 verses.csv 로 만든다(서버의 verses_meta.parquet 과 같은 행).
    목록이 쓰는 장만 올려 메모리를 아낀다 — 장 절 번호 비교와 앞뒤 문맥에는 장 전체면 충분하다.
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

    def test_offset_decisions_are_reviewed(self) -> None:
        # 임베딩을 부르는 결정만 모은다 — 가짜 임베더라 무엇을 고르는지는 상관없다.
        asked = set()
        for item in self.items:
            for lang in FOREIGN_LANGS:
                key = (item["reference"], lang)
                languages.set_encoder(
                    lambda texts, key=key: asked.add(key) or np.ones((len(texts), 1), "float32")
                )
                localize_ko_ref(lang, item["reference"], item["text"])
        self.assertEqual(sorted(asked - REVIEWED_OFFSETS.keys()), [], "사람이 확인하지 않은 결정")
        self.assertEqual(sorted(REVIEWED_OFFSETS.keys() - asked), [], "목록에서 빠진 결정")

    def test_intl_interpretations_record_localized_refs(self) -> None:
        # 외국어 풀이 검토본은 현지 본문을 보고 썼다(TSV 3열 = 현지 참조). 정렬이 바뀌면 다른
        # 절을 보고 쓴 풀이가 붙어 나가므로, 기록이 현지화 결과와 같은지 본다(fr 42:11 이
        # 어긋나 있었다). 임베딩 결정은 사람이 확인한 정답, 나머지는 번호대로 찾은 절과 맞춘다.
        mismatched = []
        for lang in FOREIGN_LANGS:
            recorded = _read_intl_local_refs(lang)
            for item in self.items:
                ref = item["reference"]
                if ref not in recorded:
                    continue  # 아직 만들지 않은 풀이 — 빌드가 따로 알린다
                want = REVIEWED_OFFSETS.get((ref, lang)) or localize_ko_ref(lang, ref, item["text"])["ref"]
                if recorded[ref] != want:
                    mismatched.append((ref, lang, recorded[ref], want))
        self.assertEqual(mismatched, [])

    @unittest.skipUnless(
        _real_encoder_requested(), "REAL_ENCODER_TEST=1 + backend/models/e5-small-int8 필요"
    )
    def test_every_daily_verse_localizes_with_real_encoder(self) -> None:
        # 장 마지막 절 번호가 다른 곳은 임베딩으로 절을 고르고 코사인 0.7 미만이면 실패한다.
        languages.set_encoder(embedding.load_query_embedder().encode)
        self.assert_all_localize()
        wrong = []
        for (ref, lang), want in REVIEWED_OFFSETS.items():
            text = next(item["text"] for item in self.items if item["reference"] == ref)
            got = localize_ko_ref(lang, ref, text)["ref"]
            if got != want:
                wrong.append((ref, lang, got, want))
        self.assertEqual(wrong, [], "사람이 확인한 정답과 다른 정렬")


if __name__ == "__main__":
    unittest.main()
