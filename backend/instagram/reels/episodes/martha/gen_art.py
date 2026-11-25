"""마르다 릴스 장면 그림(로컬 Z-Image-Turbo q8). 장면마다 시드 1·2 를 뽑아 고른다(고른 것은 picks.json).

    ~/.local/share/withgod-imagegen/venv/bin/python gen_art.py <작업폴더>/art [장면...]

예수님은 AI 로 그리지 않는다(README) — 예수님이 계신 쪽은 늘 화면 밖 왼쪽, 따뜻한 빛만 들어온다.
이 모델은 negative 를 무시하므로 "다른 사람은 없다"를 장면 프롬프트에 직접 적는다.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'scripts'))
import gen_ig_art as g
g.WIDTH, g.HEIGHT = 1600, 1200
g.NEGATIVE += (", Jesus, bearded man in robe, halo, Virgin Mary, blue veil, statue, candles, wax candle, glass, glass bottle, "
               "eyeglasses, chair, modern table, tablecloth, metal pot, stove, faucet, church, cross")
OUT = Path(sys.argv[1])
# 성화 관습(파란 머릿수건 + 흰 옷 = 성모)과 겹치지 않게, 한나(붉은 수건·올리브 옷)와도 다르게.
MARTHA = ("Martha, a Middle Eastern woman in her thirties with thick dark hair tied back under a saffron-ochre linen head wrap, "
          "a few loose strands on her forehead, wearing a long rust-brown wool robe with the sleeves rolled up and a "
          "flour-dusted undyed beige linen apron")
MARY = ("her younger sister Mary, a Middle Eastern woman in her twenties with long loose dark hair and no head covering, "
        "wearing a plain warm brown robe with a faded orange shawl")
HOUSE = ("a simple first-century stone house in the village of Bethany, rough plastered walls, a low wooden ceiling beam, "
         "clay oil lamps, woven reed mats on a packed earth floor")
NOBODY = "No other people are in the picture."
# 시드 1·2 의 부엌·항의 장면에 근대식 유리 랜턴이 벽에 걸려 나왔다(11/25) — 조명을 본 프롬프트로 못박고 시드 3·4 로 다시 뽑는다.
LIGHT = ("The only light comes from the open wood fire and small open clay oil lamps sitting on wooden shelves; "
         "the plastered walls are bare except for shelves of clay jars.")
SHOTS = {
 "a_doorway": (f"Inside {HOUSE}. In the right foreground, {MARTHA} stands in the kitchen doorway gripping a clay mixing bowl, "
               f"her face tense and exasperated, brows pulled together, lips pressed tight, glaring toward the left. "
               f"In the left background, in the lamp-lit main room, {MARY} sits on a reed mat on the floor, looking up toward "
               f"the far left edge of the picture with calm, rapt attention, as if listening to someone just outside the frame. "
               f"Warm light falls from the left. {NOBODY} Medium shot, Martha's face large and clearly visible."),
 "b_kitchen": (f"A cramped first-century kitchen corner in {HOUSE}: {MARTHA} works alone, kneading a big lump of bread dough "
               f"on a low stone counter while a round clay cooking pot steams over a small wood fire beside her, baskets of "
               f"lentils, onions and figs, a tall clay water jar, flatbreads stacked on a cloth. She glances over her shoulder, "
               f"flushed and hurried, sweat on her brow, overwhelmed by everything still to do. Smoke and warm firelight. "
               f"{LIGHT} {NOBODY} Wide shot."),
 "c_mary": (f"The lamp-lit main room of {HOUSE}. {MARY} sits on a woven reed mat on the floor with her hands resting in her lap, "
            f"looking up toward the left edge of the picture with a peaceful, listening face, soft warm light from the left on "
            f"her face. Behind her on the right, a doorway to a smoky kitchen glows with firelight. {NOBODY} "
            f"Medium wide shot, quiet, still mood."),
 "d_complain": (f"The main room of {HOUSE}. {MARTHA} has marched out of the kitchen and stands with one hand on her hip and the "
                f"other hand pointing down at {MARY}, who sits calmly on a reed mat on the floor. Martha looks toward the left "
                f"edge of the picture, upset, mouth open mid-sentence, speaking to someone outside the frame. Warm light from "
                f"the left. {LIGHT} {NOBODY} Wide shot, both sisters close together in the middle of the picture."),
 "e_listen": (f"Close-up of {MARTHA} in the lamp-lit main room of {HOUSE}, her pointing hand slowly lowering, her eyes wide and "
              f"glistening, her tense face beginning to soften, as if she has just heard her name spoken kindly by someone on "
              f"the left outside the frame. Warm golden light from the left on her face, soft dark background. {NOBODY} "
              f"Emotional, tender mood."),
 "f_rest": (f"Evening outside {HOUSE}. {MARTHA}, her apron folded beside her, sits on the stone doorstep holding a small clay "
            f"cup in both hands, eyes closed, shoulders relaxed, a faint peaceful smile. Soft orange and lilac sunset sky over "
            f"olive trees and the hills of Bethany, a clay oil lamp glowing in the doorway behind her. {NOBODY} "
            f"Medium wide shot, restful, hopeful mood."),
}
args = sys.argv[2:]
seeds = [1, 2]
if "--seeds" in args:  # 예: b_kitchen d_complain --seeds 3 4
    k = args.index("--seeds")
    seeds, args = [int(x) for x in args[k + 1:]], args[:k]
names = args or list(SHOTS)
for name in names:
    g.generate(SHOTS[name], seeds, 9, OUT, name)
    print("done", name, flush=True)
