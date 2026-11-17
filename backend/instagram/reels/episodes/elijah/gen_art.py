"""엘리야 편 첫 장면 3개(a·b·c) 프롬프트. 나머지 d_fire·e_queen·f_eat·g_flee 는 세션에서 따로 뽑았다(프롬프트 미보존).
그림 원본: ~/.local/share/withgod-ig-reels/work/elijah/art/ — spec.json 의 art/ 는 그 폴더 기준."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'scripts'))
import gen_ig_art as g
OUT = Path(sys.argv[1])
ELIJAH = ("Elijah, a weathered bearded Middle Eastern man in his forties with long dark hair, "
          "wearing a rough brown hair cloak tied with a leather belt")
SHOTS = {
 "a_alone": f"A vast empty desert wilderness at dusk, rocky hills and sand stretching to the horizon. On the right side, a lone small scraggly desert shrub tree, and under it {ELIJAH} sits on the ground hunched over, elbows on his knees, head in his hands, utterly exhausted. Long shadows, fading orange and purple sky. Lonely, quiet mood.",
 "b_bread": f"Early morning in the desert. {ELIJAH} lies asleep on his side on the sand in the shade of a small scraggly desert shrub tree. Near his head, a round flat loaf of bread baking on a few glowing hot stones with a thin wisp of smoke, and a clay jar of water. Soft golden sunrise light falls gently on him. Peaceful, tender mood.",
 "c_journey": f"Sunrise in a rocky desert. Seen from behind, {ELIJAH} walks away along a winding path toward distant blue mountains, holding a wooden staff, small in the wide landscape. A long road ahead, warm hopeful morning light, clear sky.",
}
for name, prompt in SHOTS.items():
    g.generate(prompt, [1, 2], 9, OUT, name)
    print("done", name, flush=True)
