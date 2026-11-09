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
from languages import VerseStore, collect_candidates, localize_ko_ref

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


class CollectCandidatesTest(unittest.TestCase):
    """검색 결과(FAISS 점수·행 번호)에서 추천 후보를 만드는 collect_candidates."""

    def store(self, *rows) -> VerseStore:
        return VerseStore("ko", ko_rows(*rows), None)

    def test_drops_placeholder_rows(self) -> None:
        # 본문 대신 「(앞절과 동일)」·「(없 음)」이 든 행이 검색에 걸려도 후보로 나가면 안 된다
        store = self.store(
            ("시편", 92, 2, "(앞절과 동일)"),
            ("시편", 92, 1, "지존자여 십현금과 비파와 수금의 정숙한 소리로 여호와께 감사하며"),
            ("마태복음", 17, 21, "(없 음)"),
            ("시편", 23, 1, "여호와는 나의 목자시니 내가 부족함이 없으리로다"),
        )
        got = collect_candidates(store, [0.9, 0.8, 0.7, 0.6], [0, 1, 2, 3], top_k=3)
        self.assertEqual([c["ref"] for c in got], ["시편 92:1", "시편 23:1"])

    def test_fallback_still_drops_placeholder_rows(self) -> None:
        # 부적합 절만 걸려 필터 없이 폴백할 때도 자리표시는 뺀다(잠언 7:14 는 큐레이션 부적합)
        store = self.store(
            ("신명기", 6, 19, "(18절과 같음)"),
            ("잠언", 7, 14, "내가 화목제를 드려서 서원한 것을 오늘날 갚았노라"),
        )
        got = collect_candidates(store, [0.9, 0.8], [0, 1], top_k=3)
        self.assertEqual([c["ref"] for c in got], ["잠언 7:14"])


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


# 원래 전부 대문자인 낱말 — 신명 JAH(시편 130:3), 벽에 쓰인 글자(다니엘 5:27-28).
_ES_CAPS_WORDS = {"JAH", "TEKEL", "PERES"}
# 시편 표제의 머리 — 「Salmo de David」「Al Músico principal」「Cántico gradual」 …
_RE_ES_PSALM_TITLE = re.compile(
    r"^(?:Salmo|Al Músico|Cántico gradual|Canción|Masquil|Michta?h?m|Sigaión|Oración del?|Para Salomón|A los hijos)\b"
)


@unittest.skipUnless((languages.LANG_DIR / "es" / "verses.csv").exists(), "es verses.csv 없음")
class SpanishCleanupDataTest(unittest.TestCase):
    """es(RV1909) 인쇄본 조판 흔적이 본문에 다시 들어오지 않는지 (이슈 #35).

    원본 spaRV1909 는 시편 표제를 1절 본문에 넣었고(「Salmo de David: Masquil. BIENAVENTURADO…」),
    장 첫 낱말을 드롭캡 대문자로 남겼다(「NO juzguéis」). 오늘의 말씀 15개가 그대로 나갔다.
    `scripts/build_language_data.py` 를 다시 돌려도 이 정리가 빠지지 않아야 한다.
    """

    @classmethod
    def setUpClass(cls) -> None:
        with open(languages.LANG_DIR / "es" / "verses.csv", encoding="utf-8", newline="") as f:
            cls.rows = {
                (r["book_code"], int(r["chapter"]), int(r["verse"])): r["text"]
                for r in csv.DictReader(f)
            }

    @staticmethod
    def _caps(tok: str) -> bool:
        w = re.sub(r"[\W\d_]", "", tok)
        return len(w) >= 2 and w.isupper()

    def test_no_dropcap_or_psalm119_letter_at_verse_start(self) -> None:
        bad = []
        for key, text in self.rows.items():
            toks = text.split()
            first = re.sub(r"[\W\d_]", "", toks[0])
            # 「NO juzguéis」「ALEPH.」, 한 글자 드롭캡 「Y FUERON」「A TODOS」
            if (self._caps(toks[0]) and first not in _ES_CAPS_WORDS) or (
                len(first) == 1 and len(toks) > 1 and self._caps(toks[1])
            ):
                bad.append((key, text[:40]))
        self.assertEqual(bad, [], f"드롭캡 대문자가 남은 절 {len(bad)}개")

    def test_psalm_titles_are_not_in_verse_one(self) -> None:
        bad = []
        for ch in range(1, 151):
            text = self.rows[("PSA", ch, 1)]
            # 표제 뒤 드롭캡은 절 중간에 대문자로 남는다 — 「Cántico gradual. ALZARÉ」
            caps = [t for t in text.split() if self._caps(t) and re.sub(r"\W", "", t) not in _ES_CAPS_WORDS]
            if _RE_ES_PSALM_TITLE.match(text) or caps:
                bad.append((ch, text[:50]))
        self.assertEqual(bad, [], f"표제가 남은 시편 {len(bad)}개")

    def test_known_verses(self) -> None:
        self.assertEqual(
            self.rows[("PSA", 32, 1)],
            "Bienaventurado aquel cuyas iniquidades son perdonadas, y borrados sus pecados.",
        )
        self.assertTrue(self.rows[("MAT", 7, 1)].startswith("No juzguéis,"))
        self.assertTrue(self.rows[("ISA", 55, 1)].startswith("A todos los sedientos:"))
        # 「Aleluya.」는 표제가 아니라 1절 본문이다
        self.assertTrue(self.rows[("PSA", 111, 1)].startswith("Aleluya. Alabaré á Jehová"))
        # 드롭캡 둘째 낱말이 고유명사면 첫 글자를 살린다
        self.assertTrue(self.rows[("GEN", 7, 1)].startswith("Y Jehová dijo á Noé"))
        self.assertTrue(self.rows[("1KI", 19, 1)].startswith("Y Achab dió"))
        self.assertTrue(self.rows[("PSA", 147, 1)].startswith("Alabad á JAH,"))
        self.assertTrue(self.rows[("PSA", 119, 105)].startswith("Lámpara es á mis pies"))
        # 잠언 10:1 의 「Las sentencias de Salomón.」은 표제가 아니라 본문이다(시편만 뗀다)
        self.assertTrue(self.rows[("PRO", 10, 1)].startswith("Las sentencias de Salomón. El hijo sabio"))


if __name__ == "__main__":
    unittest.main()
