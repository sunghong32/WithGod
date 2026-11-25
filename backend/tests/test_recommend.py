"""위로의 말씀 추천 — 후보 선별(recommend.py)과 위로 부적합 목록(unsuitable_refs.json).

2026-11-25 영어 「I’m dreading Thanksgiving with my family.」에 에스겔 21:17(칼 심판 신탁의 끝
「I will cause my wrath to rest」)과 욥기 31:34(「내가 죄를 숨겼다면」 하는 결백 맹세의 조건절)가
카드로 나갔다. 에스겔 21:6-30 은 분류 스크립트가 실패한 묶음을 '전부 적합'으로 넘겨 목록에
구멍이 나 있었고, 선별은 앞뒤 절 없이 한 절만 보고 골랐다.
"""

import ast
import contextlib
import importlib.util
import io
import json
import re
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

import languages
import recommend
from languages import KO_NAME_TO_CODE, VerseStore, collect_candidates, is_recommendable

BACKEND = Path(__file__).resolve().parent.parent


def cand(ref: str, before: str = "", after: str = "", continues: bool = False) -> dict:
    return {
        "ref": ref, "text": f"text of {ref}", "score": 0.9,
        "context": {"before": before, "after": after, "continues": continues},
    }


class PickFromResponseTest(unittest.TestCase):
    """LLM 이 돌려준 번호를 후보로 바꾸는 규칙."""

    def setUp(self) -> None:
        self.cands = [cand(f"V {n}") for n in range(1, 7)]

    def refs(self, picked) -> list[str]:
        return [c["ref"] for c in picked]

    def test_excluded_pick_is_dropped_and_refilled_without_excluded(self) -> None:
        # 2번을 제외해 놓고 picks 에도 넣은 경우 — 2번은 버리고, 채울 때도 제외 후보(1번)는 건너뛴다
        got = recommend.pick_from_response({"excluded": [1, 2], "picks": [2, 4]}, self.cands, 3)
        self.assertEqual(self.refs(got), ["V 4", "V 3", "V 5"])

    def test_old_shape_without_excluded(self) -> None:
        got = recommend.pick_from_response({"picks": [5, 5, 9, 1]}, self.cands, 3)
        self.assertEqual(self.refs(got), ["V 5", "V 1", "V 2"])

    def test_everything_excluded_returns_nothing(self) -> None:
        got = recommend.pick_from_response({"excluded": [1, 2, 3, 4, 5, 6], "picks": [1]}, self.cands, 3)
        self.assertEqual(got, [])


class SelectVersesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.cands = [cand(f"V {n}") for n in range(1, 7)]
        patcher = mock.patch.object(recommend.llm, "configured", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_uses_llm_picks(self) -> None:
        with mock.patch.object(recommend.llm, "complete_json",
                               return_value='{"excluded": [1], "picks": [3, 1, 6]}') as call:
            got = recommend.select_verses("mood", self.cands, 3)
        self.assertEqual([c["ref"] for c in got], ["V 3", "V 6", "V 2"])
        self.assertIs(call.call_args.kwargs["schema"], recommend.PICKS_SCHEMA)

    def test_all_excluded_falls_back_to_top_similarity(self) -> None:
        with mock.patch.object(recommend.llm, "complete_json",
                               return_value='{"excluded": [1, 2, 3, 4, 5, 6], "picks": []}'), \
                self.assertLogs("with-god", level="WARNING"):
            got = recommend.select_verses("mood", self.cands, 3)
        self.assertEqual([c["ref"] for c in got], ["V 1", "V 2", "V 3"])

    def test_llm_failure_falls_back_to_top_similarity(self) -> None:
        with mock.patch.object(recommend.llm, "complete_json", side_effect=RuntimeError("429")), \
                self.assertLogs("with-god", level="ERROR"):
            got = recommend.select_verses("mood", self.cands, 3)
        self.assertEqual([c["ref"] for c in got], ["V 1", "V 2", "V 3"])

    def test_excluded_comes_before_picks_in_schema(self) -> None:
        # 출력은 스키마 키 순서대로 나온다 — 먼저 걸러 내고 나서 고르게 하려는 순서다
        self.assertEqual(list(recommend.PICKS_SCHEMA["properties"]), ["excluded", "picks"])


class SelectPromptTest(unittest.TestCase):
    def test_candidate_lines_show_neighbors_and_continuation(self) -> None:
        prompt = recommend.build_select_prompt("mood", [
            cand("Job 31:34",
                 before="if like Adam I have covered my transgressions, by hiding my iniquity in my heart,",
                 after="oh that I had one to hear me!", continues=True),
            cand("Psalms 61:1"),
        ], 3)
        self.assertIn("2. Psalms 61:1 :: text of Psalms 61:1\n", prompt + "\n")
        self.assertIn("1. Job 31:34 :: text of Job 31:34 (앞 절에서 이어지는 문장)", prompt)
        self.assertIn("   앞: if like Adam I have covered", prompt)
        self.assertIn("   뒤: oh that I had one to hear me!", prompt)

    def test_long_previous_verse_keeps_its_end(self) -> None:
        # 앞 절은 끝부분이 이음새다
        line = recommend._candidate_line(1, cand("X 1:2", before="a" * 300 + " if I have hidden it,"))
        self.assertTrue(line.split("앞: ")[1].endswith("if I have hidden it,"))

    def test_rules_name_the_failure_cases(self) -> None:
        for phrase in ("심판", "결백 맹세", "욥기 31:33-34", "에스겔 21:17", "책망", "욥의 세 친구"):
            self.assertIn(phrase, recommend.SELECT_SYSTEM)


class CommentPromptTest(unittest.TestCase):
    LIMITS = {"comment_limit": "2문장", "comment_limit_intl": "2 sentences"}
    VERSE = {"ref": "Job 31:34", "text": "Because I feared the great multitude…",
             "context": {"before": "if like Adam I have covered my transgressions,", "after": "", "continues": True}}

    def test_foreign_prompt_warns_about_conditions_and_speakers(self) -> None:
        prompt = recommend.build_single_comment_prompt("mood", self.VERSE, self.LIMITS, "en")
        self.assertIn("never turn a condition into a fact or a confession", prompt)
        self.assertIn("Do not name the speaker", prompt)
        self.assertIn('"Fear"', prompt)

    def test_korean_prompt_warns_about_conditions_and_speakers(self) -> None:
        prompt = recommend.build_single_comment_prompt("마음", self.VERSE, self.LIMITS, "ko")
        self.assertIn("조건을 사실이나 고백으로 바꿔 말하지 마세요", prompt)
        self.assertIn("단정하지 마세요", prompt)

    def test_neighbor_verses_are_not_put_into_the_comment_prompt(self) -> None:
        # 앞 절 「내가 허물을 가리웠다면」을 따로 주면 그것을 고백으로 읽었다(docstring 참고)
        for lang in ("en", "ko"):
            prompt = recommend.build_single_comment_prompt("mood", self.VERSE, self.LIMITS, lang)
            self.assertNotIn("covered my transgressions", prompt)


class CandidateContextTest(unittest.TestCase):
    """collect_candidates 가 후보마다 같은 장의 앞뒤 절을 붙이는지."""

    def en_store(self) -> VerseStore:
        return VerseStore("en", pd.DataFrame([
            ("JOB", "Job", 30, 31, "Therefore my harp has turned to mourning,"),
            ("JOB", "Job", 31, 33, "if like Adam I have covered my transgressions,"),
            ("JOB", "Job", 31, 34, "because I feared the great multitude, so that I kept silence—"),
            ("JOB", "Job", 31, 35, "oh that I had one to hear me!"),
            ("PSA", "Psalms", 1, 1, "Blessed is the man who doesn’t walk in the counsel of the wicked,"),
        ], columns=["book_code", "book", "chapter", "verse", "text"]), None)

    def test_neighbors_in_same_chapter(self) -> None:
        got = collect_candidates(self.en_store(), [0.9], [2], top_k=1)[0]
        self.assertEqual(got["text"], "Because I feared the great multitude, so that I kept silence—")
        self.assertEqual(got["context"], {
            "before": "if like Adam I have covered my transgressions,",
            "after": "oh that I had one to hear me!",
            "continues": True,
        })

    def test_no_neighbor_across_chapter_or_book(self) -> None:
        store = self.en_store()
        first = collect_candidates(store, [0.9], [1], top_k=1)[0]["context"]
        self.assertEqual(first["before"], "")   # 30:31 은 앞 장
        last = collect_candidates(store, [0.9], [3], top_k=1)[0]["context"]
        self.assertEqual(last["after"], "")     # 다음 행은 시편
        self.assertFalse(collect_candidates(store, [0.9], [4], top_k=1)[0]["context"]["continues"])

    def test_placeholder_neighbor_is_skipped_and_korean_never_continues(self) -> None:
        store = VerseStore("ko", pd.DataFrame([
            ("욥기", 31, 33, "내가 언제 다른 사람처럼 내 죄악을 품에 숨기어 허물을 가리웠으며"),
            ("욥기", 31, 34, "(33절과 같음)"),
            ("욥기", 31, 35, "누구든지 나의 변백을 들으라"),
        ], columns=["book", "chapter", "verse", "text"]), None)
        got = collect_candidates(store, [0.9, 0.8], [1, 2], top_k=1)[0]
        self.assertEqual(got["ref"], "욥기 31:35")
        self.assertEqual(got["context"]["before"], "")
        self.assertFalse(got["context"]["continues"])


def _popular_refs() -> list[tuple[str, int, int]]:
    """app.py 의 인기 말씀 목록 — app.py 는 무거워 import 하지 않고 리터럴만 읽는다."""
    src = (BACKEND / "app.py").read_text(encoding="utf-8")
    start = src.index("_POPULAR_VERSE_REFS = [")
    end = src.index("\n]\n", start) + 2
    return ast.literal_eval(ast.parse(src[start:end]).body[0].value)


_RE_KO_REF = re.compile(r"^(.+?)\s+(\d+):(\d+)(?:-(\d+))?b?$")


class UnsuitableListTest(unittest.TestCase):
    """data/langs/unsuitable_refs.json + languages 의 큐레이션 목록."""

    def setUp(self) -> None:
        languages._unsuitable_refs = None  # 다른 테스트가 바꿔 둔 캐시를 버린다

    def test_ezekiel_21_sword_oracle_is_filtered(self) -> None:
        # 분류 실패로 비어 있던 묶음(21:6-30). 21:17 이 가족 걱정 위로 카드로 나갔다.
        for v in (9, 10, 14, 15, 17):
            self.assertFalse(is_recommendable("EZK", 21, v), f"EZK 21:{v}")

    def test_curated_classics_are_recommendable(self) -> None:
        for ref in sorted(languages._CURATED_SUITABLE):
            code, cv = ref.split()
            ch, v = cv.split(":")
            self.assertTrue(is_recommendable(code, ch, v), ref)

    def test_daily_verses_are_recommendable(self) -> None:
        # 사람이 「비신자에게도 와닿는다」고 고른 376개는 추천에서도 빠지면 안 된다
        daily = json.loads((BACKEND / "notifications" / "daily_verses.json").read_text(encoding="utf-8"))
        blocked = []
        for d in daily:
            m = _RE_KO_REF.match(d["reference"])
            code = KO_NAME_TO_CODE[m.group(1)]
            first, last = int(m.group(3)), int(m.group(4) or m.group(3))
            blocked += [f"{d['reference']} ({v}절)" for v in range(first, last + 1)
                        if not is_recommendable(code, m.group(2), v)]
        self.assertEqual(blocked, [])

    def test_popular_verses_are_recommendable(self) -> None:
        refs = _popular_refs()
        self.assertGreater(len(refs), 100)
        blocked = [f"{b} {c}:{v}" for b, c, v in refs if not is_recommendable(KO_NAME_TO_CODE[b], c, v)]
        self.assertEqual(blocked, [])


def _load_classifier():
    spec = importlib.util.spec_from_file_location(
        "classify_verse_suitability", BACKEND / "scripts" / "classify_verse_suitability.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ClassifierScriptTest(unittest.TestCase):
    """scripts/classify_verse_suitability.py — 실패한 묶음을 '전부 적합'으로 넘기지 않는다."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = _load_classifier()

    def batch(self):
        return [{"book_code": "EZK", "book": "Ezekiel", "chapter": "21", "verse": str(v), "text": "…"}
                for v in (16, 17)]

    def test_failed_batch_is_none_not_empty(self) -> None:
        with mock.patch.object(recommend.llm, "client", side_effect=RuntimeError("429")), \
                mock.patch.object(self.mod.time, "sleep"), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertIsNone(self.mod.classify(self.batch()))
        self.assertIn("묶음 실패: Ezekiel 21:16", out.getvalue())

    def test_numbers_become_refs(self) -> None:
        resp = mock.Mock(content=[mock.Mock(type="text", text='{"unsuitable": [2, 9]}')])
        client = mock.Mock()
        client.messages.create.return_value = resp
        with mock.patch.object(recommend.llm, "client", return_value=client):
            self.assertEqual(self.mod.classify(self.batch()), ["EZK 21:17"])

    def test_batches_match_the_list_boundaries(self) -> None:
        # --holes 는 옛 목록과 같은 25절 경계여야 빈 묶음을 정확히 짚는다
        rows = self.mod.load_rows()
        batches = self.mod.make_batches(rows)
        self.assertEqual(len(rows), 31098)
        self.assertEqual([len(b) for b in batches[:2]], [25, 25])
        ezk = next(b for b in batches if self.mod.ref_key(b[0]) == "EZK 21:6")
        self.assertEqual(self.mod.ref_key(ezk[-1]), "EZK 21:30")
        flagged = {"EZK 21:6"}
        self.assertNotIn(batches.index(ezk), self.mod.empty_batches(batches, flagged))


if __name__ == "__main__":
    unittest.main()
