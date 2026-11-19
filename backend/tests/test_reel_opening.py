"""릴스 첫 장면 검사(render.opening_problems)와 예약 큐 캡션 검사 — 11/19 평균 시청 7~10초 대책."""
import shutil
import sys
import unittest
from pathlib import Path

REELS = Path(__file__).resolve().parents[1] / "instagram" / "reels"
try:  # render.py 는 Pillow 를 쓴다 — 운영 서버 venv 에는 없을 수 있다(렌더는 이 맥에서만)
    import PIL  # noqa: F401
    sys.path.insert(0, str(REELS))
    from render import opening_problems
except ImportError:
    opening_problems = None


def spec(shots, texts, dur=60):
    return {"dur": dur, "shots": shots, "texts": texts}


GOOD_SHOTS = [{"img": "a.png", "t0": 0, "t1": 2.4, "cam": [[0, 500, 500, 528], [1.3, 500, 480, 430]]},
              {"img": "b.png", "t0": 2.4, "t1": 20, "cam": [[2.4, 500, 500, 600]]}]
GOOD_TEXTS = [{"t0": 0, "t1": 2.5, "fi": 0, "html": "<div class='hook'>She prayed so hard, the priest thought she was drunk.</div>"},
              {"t0": 2.45, "t1": 6.4, "html": "<p class='t'>Her name was Hannah.</p>"},
              {"t0": 6.5, "t1": 10, "html": "<p class='t'>Next line.</p>"}]


@unittest.skipIf(opening_problems is None, "Pillow 없음")
class OpeningTest(unittest.TestCase):
    def test_good_opening_passes(self):
        self.assertEqual(opening_problems(spec(GOOD_SHOTS, GOOD_TEXTS)), [])

    def test_posted_hannah_style_is_caught(self):
        """올라간 한나 편: h1 첫 문장, 3.4초짜리 첫 컷에 줌 1.1배, 3.2~3.6초 자막 빈 틈."""
        shots = [{"img": "a.png", "t0": 0, "t1": 3.4, "cam": [[0, 985, 470, 470], [3.4, 985, 470, 530]]}, GOOD_SHOTS[1]]
        texts = [{"t0": 0, "t1": 3.2, "fi": 0, "html": "<div class='h1'>She prayed so hard.</div>"},
                 {"t0": 3.6, "t1": 9, "html": "<p class='t'>Her name was Hannah.</p>"}]
        found = " ".join(opening_problems(spec(shots, texts)))
        for word in ("hook 클래스", "카메라도 거의 안 움직인다", "자막 빈 틈"):
            self.assertIn(word, found)

    def test_push_in_without_cut_is_enough(self):
        shots = [{"img": "a.png", "t0": 0, "t1": 8, "cam": [[0, 500, 500, 600], [2.0, 500, 480, 460]]}]
        self.assertEqual(opening_problems(spec(shots, GOOD_TEXTS)), [])

    def test_hook_must_show_at_first_frame_and_stay_short(self):
        texts = [dict(GOOD_TEXTS[0], fi=0.6)] + GOOD_TEXTS[1:]
        self.assertTrue(any("fi: 0" in p for p in opening_problems(spec(GOOD_SHOTS, texts))))
        long_hook = "<div class='hook'>" + "word " * 13 + "</div>"
        texts = [dict(GOOD_TEXTS[0], html=long_hook)] + GOOD_TEXTS[1:]
        self.assertTrue(any("13단어" in p for p in opening_problems(spec(GOOD_SHOTS, texts))))

    def test_mia_hook_class_counts(self):
        texts = [dict(GOOD_TEXTS[0], html="<p class='m hook'>My body’s exhausted.<br>My brain is wide awake.</p>")] + GOOD_TEXTS[1:]
        self.assertEqual(opening_problems(spec(GOOD_SHOTS, texts)), [])

    def test_trailing_gap_inside_first_seconds(self):
        texts = GOOD_TEXTS[:2]  # 6.4초 뒤 8초까지 자막이 없다
        self.assertTrue(any("자막 빈 틈" in p for p in opening_problems(spec(GOOD_SHOTS, texts))))


@unittest.skipIf(shutil.which("ffprobe") is None, "ffprobe 없음")
class QueueCaptionTest(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(REELS))
        sys.path.insert(0, str(REELS.parent))
        import reel_queue
        self.rq = reel_queue

    def check(self, caption):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "caption.txt").write_text(caption)
            for n in ("reel.mp4", "cover.jpg"):
                (d / n).write_bytes(b"")
            return " ".join(self.rq.check_folder(d))

    def test_hashtag_rules(self):
        self.assertNotIn("해시태그", self.check("Hook.\n\n#bibleverse #prayer #hannah #biblestory #christianencouragement"))
        self.assertIn("해시태그 6개", self.check("Hook.\n\n#bibleverse #a #b #c #d #e"))
        self.assertIn("#bibleverse 없음", self.check("Hook.\n\n#prayer #faith"))
