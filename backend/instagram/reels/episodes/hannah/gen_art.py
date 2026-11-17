"""한나 릴스 장면 그림(로컬 Z-Image-Turbo q8). 장면마다 시드 1·2 를 뽑아 고른다(고른 것은 picks.json).

    ~/.local/share/withgod-imagegen/venv/bin/python gen_art.py <작업폴더>/art [장면...]
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'scripts'))
import gen_ig_art as g
g.WIDTH, g.HEIGHT = 1600, 1200  # 9:16 로 확대해도 덜 흐리게(엘리야는 1344×992)
g.NEGATIVE += (", Virgin Mary, blue veil, statue, animal on rocks, candles, wax candle, glass, glass bottle, eyeglasses, chair, modern table, tablecloth, church, "
               "cathedral, stained glass, cross, crucifix, halo")
OUT = Path(sys.argv[1])
# 파란 머릿수건 + 흰 옷은 성모 마리아로 읽혀서(11/17 첫 장) 흙빛 붉은 수건 + 올리브색 옷으로 고정한다.
HANNAH = ("Hannah, a young Middle Eastern woman in her twenties with long dark brown hair under a muted "
          "terracotta-red linen head covering, wearing a long olive-green wool robe")
ELI = "Eli, a very old priest with a long white beard, wearing a plain white linen robe"
ELKANAH = "her husband Elkanah, a kind bearded Middle Eastern man in his thirties wearing a brown striped wool robe"
SHOTS = {
 "a_temple": (f"Night at the ancient Israelite sanctuary at Shiloh, a stone courtyard in front of a large tent "
              f"tabernacle made of dark goat-hair curtains with heavy wooden doorposts, lit by small clay oil lamps. "
              f"On the right, {HANNAH} kneels on the stone floor, eyes closed, tears on her cheeks, hands pressed "
              f"to her chest, lips parted as if whispering a prayer. On the left, {ELI} sits on a simple stone seat "
              f"beside the wooden doorpost, leaning forward and frowning at her with a stern, suspicious look. Wide shot, both clearly visible, warm lamp "
              f"light and deep blue night shadows, emotional mood."),
 "b_feast": (f"Daytime festival meal outdoors on a hillside at ancient Shiloh, olive trees, a family sitting on woven "
             f"mats on the ground around bread, grapes and roasted meat on clay dishes. In the center a proud woman "
             f"in a rich purple robe with gold jewelry laughs, surrounded by many happy small children. She glances sideways with a "
             f"smirk. Far on the right edge, apart from everyone, {HANNAH} sits alone looking down sadly, her clay "
             f"plate untouched. Wide shot, bright warm light on the family, Hannah in shade."),
 "c_husband": (f"Dusk beside an old stone wall at ancient Shiloh. {HANNAH} sits on the ground weeping into her hands. "
               f"Beside her kneels {ELKANAH}, gently offering her a piece of flat bread, his face worried and loving. "
               f"Soft purple and orange evening sky, quiet tender sad mood, medium wide shot."),
 "d_morning": (f"Early morning sunrise on a winding dirt path through green hills of ancient Israel. {HANNAH} walks "
               f"toward the viewer with a calm, peaceful face and a faint gentle smile, soft golden sunlight on her "
               f"face, her head covering moving in the breeze, a few olive trees. Hopeful, light, restful mood, "
               f"medium shot."),
}
names = sys.argv[2:] or list(SHOTS)
for name in names:
    g.generate(SHOTS[name], [1, 2], 9, OUT, name)
    print("done", name, flush=True)
