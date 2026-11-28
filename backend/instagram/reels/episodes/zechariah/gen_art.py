"""사가랴와 엘리사벳 릴스 장면 그림(로컬 Z-Image-Turbo q8). 장면마다 시드 1·2 를 뽑아 고른다(고른 것은 picks.json).

    ~/.local/share/withgod-imagegen/venv/bin/python gen_art.py <작업폴더>/art [장면...] [--seeds 3 4]

누가복음 1장, 헤롯 때 유대 산골 마을과 예루살렘 성전. 천사(가브리엘)는 그리지 않는다 — 화면 밖 오른쪽에서 들어오는 흰 금빛으로만
(날개 달린 인물을 AI 로 그리면 이상한 모양이 자주 나오고, 빛으로 두면 사가랴의 얼굴이 주인공이 된다).
엘리사벳 색은 성모 관습(파란 머릿수건 + 흰 옷)·한나(붉은 수건·올리브 옷)·마르다(사프란 수건·녹슨 갈색 옷)와 겹치지 않게
자두색 머릿수건 + 테라코타 옷. 사가랴는 흰 옷 + 흰 수염이 '하나님 아버지' 그림으로 읽히지 않게 제사장 모자·줄무늬 띠를 단다.

시드 1·2 의 a_temple 은 빛이 코에 꽂히는 광선처럼 나와(11/28) "광선 없이 오른쪽이 고르게 밝은 빛"으로 시드 3·4 를 다시 뽑았지만 빛이 아예 사라져 천사가 왔다는 표시가 없어졌다 — 시드 1(빛이 얼굴과 손에 퍼지는 것)을 쓴다.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'scripts'))
import gen_ig_art as g
g.WIDTH, g.HEIGHT = 1600, 1200
g.NEGATIVE += (", angel, wings, halo, Jesus, God the Father, Virgin Mary, blue veil, cross, church, candles, wax candle, "
               "glass, glass lantern, eyeglasses, modern furniture, chair")
OUT = Path(sys.argv[1])
ZECH = ("Zechariah, an elderly Jewish priest of about seventy with a long white beard, a deeply lined kind face and bushy white "
        "eyebrows, wearing a plain white linen priest's tunic, a round white linen priest's cap, and a long woven sash "
        "striped in crimson and purple tied at the waist")
ZECH_HOME = ("Zechariah, an elderly Jewish man of about seventy with a long white beard and a deeply lined kind face, wearing a "
             "simple undyed brown wool robe and a striped cream prayer shawl over his shoulders")
ELIZ = ("Elizabeth, an elderly Middle Eastern woman of about sixty-five with grey hair under a dusty plum-coloured wool head "
        "wrap, gentle wrinkles, wearing a long terracotta-brown robe")
HOUSE = ("a simple first-century stone house in a small village in the hill country of Judea, rough plastered walls, a low "
         "wooden ceiling beam, woven reed mats on a packed earth floor, shelves of clay jars")
LAMP = "The only light comes from small open clay oil lamps; no glass, no candles."
TEMPLE = ("the Holy Place inside the Jerusalem temple: a small square golden altar of incense with glowing coals, a tall golden "
          "seven-branched lampstand with open oil flames, a heavy embroidered curtain in crimson, purple and gold behind, "
          "cedar-panelled walls overlaid with gold")
NOBODY = "No other people are in the picture."
SHOTS = {
 # 0초 훅 — 감정이 가장 센 얼굴(REVIEW H1): 천사의 말을 듣는 순간의 두려움과 놀람. 천사는 빛으로만.
 "a_temple": (f"Close-up of {ZECH} inside {TEMPLE}. His eyes are wide with fear and astonishment, eyebrows raised, mouth "
              f"slightly open, one trembling hand raised. The whole right side of the picture glows with a soft, diffuse white-gold "
              f"radiance, like dawn filling the room, that bathes his face and hand evenly; there is no beam and no ray of "
              f"light, and its source is unseen outside the frame. Fragrant incense smoke curls around him. "
              f"{NOBODY} Dramatic, awe-struck mood, his face large and clearly visible."),
 # 오래 기다린 세월 — 저녁, 둘이 나란히 기도(이 편에서 가장 어두운 장면, 짧게)
 "b_home": (f"Evening inside {HOUSE}. {ZECH_HOME} and {ELIZ} sit side by side on a reed mat, old and tired, their hands open "
            f"in prayer, eyes closed, foreheads almost touching, faithful and patient. The room is quiet and bare. {LAMP} "
            f"Warm lamplight on their faces, soft blue dusk through a small window. {NOBODY} Medium shot, tender, "
            f"wistful mood."),
 # 제비뽑기로 분향 — 성전 안 넓게, 금빛(어둡지 않게)
 "c_altar": (f"Wide shot of {TEMPLE}. {ZECH} stands alone before the golden altar of incense, carefully scattering incense "
             f"from a small golden bowl onto the glowing coals; a column of fragrant smoke rises. Warm golden lamplight fills "
             f"the room. On the right side of the altar the air is just beginning to glow with a soft white light. {NOBODY} "
             f"Reverent, hushed mood."),
 # 말을 못 하고 나옴 — 낮, 성전 뜰의 사람들
 "d_mute": (f"Daylight in the stone temple courtyard in Jerusalem, at the top of wide stone steps. {ZECH} has just come out; "
            f"he presses one hand to his lips and gestures with the other, unable to speak, his face full of wonder. Below "
            f"him a crowd of first-century Jewish men and women in plain robes and head coverings look up at him, puzzled "
            f"and murmuring. Bright soft sunlight, pale stone, blue sky. Medium wide shot, Zechariah large in the middle."),
 # 엘리사벳 — 아침 햇빛, 배에 손(밝아지는 쪽으로)
 "e_eliz": (f"Morning inside {HOUSE}. {ELIZ}, now visibly pregnant, stands by a small open window with both hands resting on "
            f"her rounded belly, tears on her cheeks and a wondering smile, looking up toward the light. Warm golden morning "
            f"sunlight streams through the window onto her face. {NOBODY} Medium shot, joyful, hopeful mood."),
 # 밝아지는 순간 — 이름을 쓰고 입이 열려 찬양(햇빛 마당)
 "f_name": (f"A sunlit stone courtyard of {HOUSE.replace('a simple', 'the simple')}, midday. {ZECH_HOME} stands holding a small "
            f"wooden writing tablet in one hand, his face lifted to the sky, mouth open, laughing and praising with tears of "
            f"joy, his other arm raised. Beside him {ELIZ} holds a tiny newborn baby wrapped in white linen and smiles. "
            f"Around them a few village relatives and neighbours in plain robes smile and marvel. Bright warm sunlight, "
            f"an olive tree, blue sky. Medium wide shot, Zechariah and Elizabeth large in the middle."),
 # 끝 — 새벽, 아기를 안은 노부부가 해 뜨는 산을 봄
 "g_dawn": (f"Dawn on a rocky hillside above a small village in the hill country of Judea. {ZECH_HOME} and {ELIZ} sit close "
            f"together on a low stone wall, Elizabeth holding their tiny baby son wrapped in linen, both gazing peacefully at "
            f"the sunrise; golden first light spreads over terraced hills and olive trees, soft pink and gold sky. {NOBODY} "
            f"Medium wide shot from slightly behind and to the side, their faces in profile, restful, hopeful mood."),
}
args = sys.argv[2:]
seeds = [1, 2]
if "--seeds" in args:
    k = args.index("--seeds")
    seeds, args = [int(x) for x in args[k + 1:]], args[:k]
names = args or list(SHOTS)
for name in names:
    g.generate(SHOTS[name], seeds, 9, OUT, name)
    print("done", name, flush=True)
