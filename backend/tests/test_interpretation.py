import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from notifications.interpretation import (
    cache_tag,
    find_habits,
    find_problems,
    generate_interpretation,
    tidy,
)
from notifications.models import DailyVerse
from notifications.verse_provider import (
    VerseInterpretationStore,
    VerseInterpreter,
    curated_key,
    load_curated_interpretations,
)

BACKEND = Path(__file__).resolve().parent.parent

JHN_8_11 = "나도 너를 정죄하지 아니하노니 가서 다시는 죄를 범치 말라!"
GOOD = (
    "간음하다 붙잡혀 온 여인에게 예수님께서 하신 말씀이에요. "
    "정죄하지 않으신다는 말이 먼저 오고, 새 삶으로 부르심이 뒤에 옵니다."
)


class FakeClient:
    """Anthropic messages.create 만 흉내 낸다. 준비한 답을 차례로 돌려준다.

    실제 응답처럼 글 블록 앞에 내용이 빈 생각 블록을 붙인다.
    """

    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.calls: list[dict] = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(content=[
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text=self.replies.pop(0)),
        ])


class FindProblemsTest(unittest.TestCase):
    def test_flags_informal_address(self) -> None:
        # 실제 운영에서 나간 풀이(2026-09-17 요한복음 8:11b)
        self.assertEqual(
            find_problems("너의 잘못을 용서받았다는 말씀이에요."), ["반말 호칭 '너의'"]
        )
        for text in (
            "너희에게 평안을 주신다는 약속이에요.",
            "하나님께서 당신을 붙들어 주세요.",
            "네가 어디로 가든 함께하세요.",
            "네 마음을 지키라는 뜻이에요.",
        ):
            with self.subTest(text=text):
                self.assertTrue(find_problems(text))

    def test_words_that_merely_contain_neo_pass(self) -> None:
        for text in (
            "너무 걱정하지 않아도 돼요.",
            "서로를 너그럽게 대해 보세요.",
            "강을 건너는 날에도 함께하세요.",
            "네 가지 약속이 담겨 있어요.",
            "네, 그렇게 말씀하셨어요.",
        ):
            with self.subTest(text=text):
                self.assertEqual(find_problems(text), [])

    def test_flags_non_polite_ending(self) -> None:
        problems = find_problems("하나님은 가까이 계신다. 오늘도 함께하세요.")
        self.assertEqual(len(problems), 1)
        self.assertIn("존댓말", problems[0])

    def test_punctuation_inside_quotes_does_not_split_sentence(self) -> None:
        self.assertEqual(find_problems("예수님은 “일어나라!”라고 하셨어요."), [])
        self.assertEqual(find_problems("‘없을지라도!’가 쌓인 뒤에 기쁨이 나와요."), [])

    def test_flags_copying_the_verse(self) -> None:
        copied = "나도 너를 정죄하지 아니하노니 가서 다시는 죄를 범치 말라는 말씀이에요."
        self.assertIn("본문을 그대로 옮겨 적음", find_problems(copied, JHN_8_11))
        # 낱말 하나를 짚는 인용은 괜찮다
        self.assertEqual(find_problems("‘가서’라는 말에 새 삶이 담겨 있어요.", JHN_8_11), [])

    def test_habits_are_separate_from_defects(self) -> None:
        text = "사랑이라는 말씀이에요. 놓치기 쉬운 것은 순서예요."
        self.assertEqual(find_problems(text), [])
        self.assertEqual(len(find_habits(text)), 2)


class TidyTest(unittest.TestCase):
    def test_drops_title_and_quoted_verse_lines(self) -> None:
        verse = "말이 많으면 허물을 면키 어려우나 그 입술을 제어하는 자는 지혜가 있느니라"
        raw = (
            "말을 아끼는 지혜\n"
            f"“{verse}”\n"
            "잠언은 멈출 줄 아는 마음을 지혜로 봅니다. 오늘 한 번 숨을 고르세요."
        )
        self.assertEqual(
            tidy(raw, verse), "잠언은 멈출 줄 아는 마음을 지혜로 봅니다. 오늘 한 번 숨을 고르세요."
        )

    def test_keeps_single_paragraph(self) -> None:
        self.assertEqual(tidy(f"풀이: {GOOD}\n"), GOOD)
        self.assertEqual(tidy("제목만 있는 줄"), "제목만 있는 줄")


class GenerateInterpretationTest(unittest.TestCase):
    def test_returns_clean_answer_with_one_call(self) -> None:
        client = FakeClient(GOOD)
        self.assertEqual(generate_interpretation(client, "claude-haiku-5-5", "요한복음 8:11b", JHN_8_11), GOOD)
        self.assertEqual(len(client.calls), 1)

    def test_rewrites_once_when_reader_is_called_neo(self) -> None:
        bad = "너의 잘못을 용서받았다는 말씀이에요. 새롭게 시작해 보세요."
        client = FakeClient(bad, GOOD)
        result = generate_interpretation(client, "claude-haiku-5-5", "요한복음 8:11b", JHN_8_11)
        self.assertEqual(result, GOOD)
        # 고쳐 쓸 때는 방금 쓴 답과 무엇이 문제인지를 함께 보여 준다
        retry = client.calls[1]["messages"]
        self.assertEqual(retry[1], {"role": "assistant", "content": bad})
        self.assertIn("반말 호칭 '너의'", retry[2]["content"])
        self.assertEqual(retry[-1]["role"], "user")  # 미리 채우기(prefill)는 400 이다

    def test_raises_when_rewrite_still_has_defects(self) -> None:
        bad = "너의 잘못을 용서받았다는 말씀이에요."
        client = FakeClient(bad, bad)
        with self.assertRaises(ValueError):
            generate_interpretation(client, "claude-haiku-5-5", "요한복음 8:11b", JHN_8_11)

    def test_keeps_first_answer_when_only_habit_and_rewrite_is_worse(self) -> None:
        habit_only = "놓치기 쉬운 것은 순서예요. 용서가 먼저 옵니다."
        client = FakeClient(habit_only, "너의 잘못을 용서받았어요.")
        result = generate_interpretation(
            client, "claude-haiku-5-5", "요한복음 8:11b", JHN_8_11, check_habits=True
        )
        self.assertEqual(result, habit_only)

    def test_other_languages_skip_korean_checks(self) -> None:
        client = FakeClient("Title\nJesus does not condemn her. Grace comes first.")
        result = generate_interpretation(
            client, "claude-haiku-5-5", "John 8:11", "Neither do I condemn you.", lang="en", lang_name="English"
        )
        self.assertEqual(result, "Jesus does not condemn her. Grace comes first.")
        self.assertIn("ONLY in English", client.calls[0]["system"])

    def test_model_parameters(self) -> None:
        client = FakeClient(GOOD)
        generate_interpretation(client, "claude-haiku-5-5", "r", "t", reasoning_effort="medium")
        call = client.calls[0]
        # system 은 messages 가 아니라 따로 간다
        self.assertTrue(call["system"])
        self.assertEqual([m["role"] for m in call["messages"]], ["user"])
        # 생각 강도는 effort 로 정하고, Haiku 5.5 가 400 을 내는 temperature 는 보내지 않는다
        self.assertEqual(call["output_config"], {"effort": "medium"})
        self.assertEqual(call["thinking"], {"type": "adaptive"})
        self.assertNotIn("temperature", call)

    def test_cache_tag_follows_model(self) -> None:
        self.assertEqual(cache_tag("claude-haiku-5-5"), cache_tag("claude-haiku-5-5"))
        self.assertNotEqual(cache_tag("claude-haiku-5-5"), cache_tag("gpt-4o-mini"))


class CuratedInterpretationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = VerseInterpretationStore(str(Path(self.temp_dir.name) / "cache.json"))
        self.verse = DailyVerse(
            verse_id="jhn-8-11", reference="요한복음 8:11b", text=JHN_8_11, reflection="적용문"
        )
        self.curated = {curated_key("jhn-8-11", JHN_8_11): "검토한 풀이예요."}

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_korean_uses_reviewed_text_without_llm(self) -> None:
        generate = Mock(return_value="불리면 안 됨")
        interpreter = VerseInterpreter(self.store, generate, curated=self.curated)
        self.assertEqual(interpreter.interpret(self.verse), "검토한 풀이예요.")
        generate.assert_not_called()

    def test_reviewed_text_ignored_when_verse_text_changed(self) -> None:
        changed = DailyVerse(verse_id="jhn-8-11", reference="요한복음 8:11", text="다른 본문", reflection="r")
        generate = Mock(return_value="새 본문 풀이예요.")
        interpreter = VerseInterpreter(self.store, generate, curated=self.curated)
        self.assertEqual(interpreter.interpret(changed), "새 본문 풀이예요.")
        generate.assert_called_once()

    def test_other_languages_ignore_korean_review(self) -> None:
        generate = Mock(return_value="An English note.")
        interpreter = VerseInterpreter(self.store, generate, curated=self.curated)
        self.assertEqual(interpreter.interpret(self.verse, "en"), "An English note.")
        generate.assert_called_once_with(self.verse.reference, self.verse.text, "en")

    def test_changing_generation_method_regenerates_cache(self) -> None:
        # 모델·프롬프트를 바꾼 뒤에도 예전 풀이가 캐시에서 나가면 안 된다
        VerseInterpreter(self.store, Mock(return_value="old"), cache_tag="aaaaaa").interpret(self.verse, "en")
        regenerate = Mock(return_value="new")
        interpreter = VerseInterpreter(self.store, regenerate, cache_tag="bbbbbb")
        self.assertEqual(interpreter.interpret(self.verse, "en"), "new")
        regenerate.assert_called_once()

    def test_missing_or_broken_file_gives_empty_table(self) -> None:
        broken = Path(self.temp_dir.name) / "broken.json"
        broken.write_text("{not json", encoding="utf-8")
        self.assertEqual(load_curated_interpretations(broken), {})
        self.assertEqual(load_curated_interpretations(Path(self.temp_dir.name) / "none.json"), {})


class ShippedInterpretationsTest(unittest.TestCase):
    """배포 파일끼리 맞물리는지 본다. 말씀 목록을 바꾸고 풀이를 안 채우면 여기서 걸린다."""

    def test_every_daily_verse_has_a_clean_reviewed_interpretation(self) -> None:
        verses = json.loads((BACKEND / "notifications" / "daily_verses.json").read_text(encoding="utf-8"))
        curated = load_curated_interpretations()
        self.assertEqual(len(curated), len(verses))
        for v in verses:
            with self.subTest(reference=v["reference"]):
                interp = curated.get(curated_key(v["verse_id"], v["text"]))
                self.assertTrue(interp)
                self.assertEqual(find_problems(interp, v["text"]), [])


if __name__ == "__main__":
    unittest.main()
