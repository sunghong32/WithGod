"""수요일 시리즈 「Mia」 공통 — 화풍·인물·방·자막 모양(사용자 결정 11/17).

수요일 편은 앱 광고처럼 보이지 않게, 매주 같은 인물 Mia 가 진짜 고민을 안고 WithGod 앱을 쓰는 짧은 이야기로 만든다.
월요일 인물 이야기(서양 2D 손그림·세리프 자막)와 한눈에 달라 보이도록 3D 애니메이션 화풍과 산세리프 속마음 자막을 쓴다.

    import mia
    mia.generate({"a_ceiling": "...장면..."}, out_dir, ["a_ceiling"])   # 세로 1088×1936, 시드 1·2

장면 프롬프트에는 {MIA}·{ROOM} 을 넣어 인물과 방을 매주 같게 묘사한다. 앱 화면은 그리지 않는다
(휴대폰 화면은 보는 사람 반대쪽) — 실제 앱을 시뮬레이터에서 녹화해 끼운다. 이 모델은 negative 프롬프트를
무시하므로(가이던스 증류) 피할 것은 장면 프롬프트에 직접 적는다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1].parent / 'scripts'))
import gen_ig_art as g  # noqa: E402

STYLE = ("Still from a modern 3D animated feature film, stylized CGI characters with soft rounded features, "
         "cozy cinematic lighting, shallow depth of field.")
MIA = ("Mia, a young woman in her late twenties with curly dark brown hair tied in a messy bun, round tortoiseshell "
       "glasses, wearing an oversized mustard-yellow hoodie")
ROOM = ("a small cozy city apartment bedroom, a window with blinds and blurry city lights outside, a wooden nightstand "
        "with a green-striped mug and a small potted plant, a rumpled blue blanket")
SIZE = (1088, 1936)  # 세로 그대로(9:16, 16의 배수) — 가로 그림을 잘라 쓰면 인물이 답답하게 잘린다

# 속마음 자막 — 인물 이야기의 금색 세리프와 다르게 Inter 산세리프, 왼쪽 정렬. 마지막 말씀만 시리즈 공통 금색 기울임.
CSS = """
.m{font:500 54px/1.28 "I";letter-spacing:-.005em;color:#FFFFFF;text-wrap:pretty}
.m.big{font-weight:600;font-size:64px;line-height:1.16;text-wrap:balance}
.m.hook{font-weight:700;font-size:74px;line-height:1.1;letter-spacing:-.015em;text-wrap:balance}  /* 첫 문장 — 0초부터 크게 */
.m .dim{color:rgba(255,255,255,.72)}
.stamp{position:absolute;left:90px;top:250px;font:600 34px "I";letter-spacing:.14em;color:rgba(255,255,255,.86);
  text-shadow:0 1px 10px rgba(0,0,0,.5)}
"""


def generate(shots: dict, out: Path, names=None, seeds=(1, 2)):
    g.STYLE = STYLE
    g.WIDTH, g.HEIGHT = SIZE
    for name in names or list(shots):
        g.generate(shots[name], list(seeds), 9, Path(out), name)
        print('done', name, flush=True)
