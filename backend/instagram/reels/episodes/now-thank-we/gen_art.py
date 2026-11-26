"""「Now Thank We All Our God」 찬송가 이야기 릴스 장면 그림(로컬 Z-Image-Turbo q8). 장면마다 시드 1·2 를 뽑아 고른다(고른 것은 picks.json).

    ~/.local/share/withgod-imagegen/venv/bin/python gen_art.py <작업폴더>/art [장면...] [--seeds 3 4]

1630년대 작센 아일렌부르크(30년 전쟁·1637년 역병). 루터교 목사 차림은 그 시절 그대로 — 검은 가운 + 흰 맷돌 주름 깃(Mühlsteinkragen).
이 모델은 negative 를 무시하므로 시대 착오(근대 유리 랜턴·가스등·전구)와 시신은 본 프롬프트에 직접 적어 막는다.
역병 장면은 무덤·조문객만 — 시신·병든 사람은 그리지 않는다(자식·가족을 잃은 사람도 본다).
고른 그림 중 c_table_1·d_plague_2 는 감마 0.78·0.88 로 그림자를 들어 올린 사본(*b.png)을 쓴다(사용자 11/26 "너무 어두침침" —
평균 밝기 60·65 → 약 75·72, 아내 무덤 47 은 가장 낮은 순간이라 그대로).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'scripts'))
import gen_ig_art as g
g.WIDTH, g.HEIGHT = 1600, 1200
g.NEGATIVE += (", corpse, dead body, skull, skeleton, blood, gore, sick person, plague doctor mask, halo, Virgin Mary, blue veil, "
               "electric light, light bulb, gas lamp, glass lantern, eyeglasses, wristwatch")
OUT = Path(sys.argv[1])
RINKART = ("Pastor Martin Rinkart, a German Lutheran minister of about fifty with a short grey-streaked dark beard and moustache, "
           "a lined, weary face and deep-set kind eyes, a full head of thick, wavy, grey-streaked dark hair "
           "combed back (not bald, no cap, no hat), wearing a long black Lutheran preaching gown without a hood and a large "
           "white pleated millstone ruff collar")
WIFE = ("his wife, a German woman in her forties with a white linen cap over her hair and a plain white collar on a dark "
        "brown wool dress")
TOWN = ("Eilenburg, a small walled town in Saxony in the 1630s: a grey stone town wall with a gate tower, steep red-tiled roofs, "
        "half-timbered houses, and the tall Gothic tower of the town church")
ERA = "Seventeenth-century Germany during the Thirty Years' War; no modern objects."
NOBODY_ELSE = "No other people are in the picture."
SHOTS = {
 # 0초 훅 — 감정이 가장 센 얼굴(REVIEW H1). 무덤은 뒤로 흐리게.
 # 첫 시안(11/26)은 검은 빵모자 + 수염이 랍비로, 모자를 빼니 대머리 + 두건 옷이 수도사로 읽혔다 — 숱 많은 머리·두건 없는 가운을 못박는다.
 "a_grave": (f"Close medium shot of {RINKART}, standing in a crowded churchyard under a low grey sky, holding a worn open "
             f"prayer book against his chest. His face is drained and grief-stricken, eyes red and wet, jaw clenched, "
             f"looking down at a freshly dug grave just below the frame. Behind him, out of focus, rows of fresh earth "
             f"grave mounds with plain wooden crosses and the church wall. {ERA} His face large and clearly visible, "
             f"filling the right half of the picture."),
 "b_town": (f"Wide shot of {TOWN}, seen from the road outside the gate on a cold grey day. A long line of ragged refugees "
            f"with bundles, handcarts and children trudges through the open town gate; two soldiers in 1630s buff coats "
            f"and broad-brimmed hats with long pikes stand at the gate. Far behind the town, thin columns of smoke rise "
            f"from burned farmhouses in the fields. Muddy dirt road. {ERA} Somber, crowded mood."),
 "c_table": (f"Warm evening interior of a modest seventeenth-century German pastor's house with dark wooden beams and "
             f"whitewashed walls. {RINKART} sits at a plain wooden table across from {WIFE}, just the two of them. "
             f"On the bare table there is only one small round loaf of dark rye bread, a clay water jug and wooden bowls. "
             f"Both fold their hands and bow their heads to pray at the table; Rinkart's eyes are closed with a "
             f"gentle, grateful smile. The only light is one tallow candle in a simple iron holder on the table and the "
             f"last blue dusk through a small window of leaded glass panes. {ERA} Poor but tender, warm mood. "
             f"{NOBODY_ELSE} Medium shot, both faces visible."),
 "d_plague": (f"A churchyard beside a Gothic stone church in a seventeenth-century German town on a misty grey morning, "
              f"crowded with many fresh earth grave mounds and simple wooden crosses. {RINKART} stands at an open grave "
              f"reading aloud from a book, while a small group of mourners in black cloaks and hoods stands with bowed "
              f"heads and two gravediggers lean on their spades. More mourners wait at the churchyard gate. "
              f"No bodies or coffins are visible. {ERA} Wide shot, quiet and heavy mood."),
 "e_wife": (f"At dusk, {RINKART} kneels alone beside one fresh grave with a small wooden cross and a few wild flowers laid "
            f"on the earth, in a quiet corner of the churchyard by the old stone wall. His head is bowed, one hand pressed "
            f"to his chest, his eyes closed, tears on his cheeks. Cold blue evening light, bare trees. {NOBODY_ELSE} {ERA} "
            f"Medium shot from the side, his face clearly visible, deeply sorrowful, intimate mood."),
 # 전환 — 같은 사람이 새벽빛을 올려다본다(무엇을 했다는 행동은 그리지 않는다: 사실로 확인된 것만 자막에).
 # 영상이 밝아지는 순간(REVIEW S4, 사용자 11/26 "너무 어두침침") — 시드 1·2(11/26)는 회색 구름 + 곁눈질이라 밝기를 못박았다(시드 3·4).
 # 아내 무덤 바로 다음 컷이라 웃는 얼굴은 "하룻밤에 털고 웃었다"로 보일 수 있다(2차 검토) — 웃음 없이 고요한 얼굴로.
 "f_dawn": (f"Bright sunrise in the churchyard of {TOWN}. {RINKART} stands facing the rising sun, his face and white ruff "
            f"bathed in warm golden sunlight, eyes gently closed, a quiet, peaceful face (not smiling), chin lifted toward "
            f"the light. Long golden sunbeams stream across the picture; the sky behind him is clearing to warm gold, peach "
            f"and pale blue, the last clouds lit from below. Dew sparkling on the grass. {NOBODY_ELSE} {ERA} Medium "
            f"close shot, his face large and clearly visible, luminous, radiant, hopeful mood, high-key bright colors."),
 # 오늘 — 추수감사절에 이 찬송을 부르는 교회(보는 사람의 자리로)
 "g_today": (f"Present-day interior of a small, warm wooden American church on Thanksgiving morning, decorated with "
             f"pumpkins, wheat sheaves and autumn leaves along the windowsills. A congregation of all ages — families, "
             f"grandparents, children — stands in the pews holding open hymn books and singing together, soft golden "
             f"autumn sunlight through tall clear windows. No cross, no stained glass. Medium wide shot, faces happy and "
             f"moved, cozy and hopeful mood."),
 "h_sunrise": (f"Sunrise over {TOWN} beside a quiet river with morning mist, the town wall and the church tower glowing in "
               f"warm golden light, birds in a clear pale sky, frost on the meadow in the foreground. {NOBODY_ELSE} {ERA} "
               f"Wide peaceful landscape, hopeful mood."),
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
