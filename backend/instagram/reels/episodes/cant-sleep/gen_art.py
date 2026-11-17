"""앱 시연 「I told a Bible app I couldn't sleep」 장면 그림(로컬 Z-Image-Turbo q8). 장면마다 시드 1·2 를 뽑아 고른다.

    ~/.local/share/withgod-imagegen/venv/bin/python gen_art.py <작업폴더>/art [장면...]

앱 화면은 그리지 않는다 — iPhone 시뮬레이터에서 실제 앱을 녹화해 쓴다(휴대폰 화면은 보는 사람 반대쪽을 향하게).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'scripts'))
import gen_ig_art as g
g.WIDTH, g.HEIGHT = 1600, 1200
g.NEGATIVE += (", visible phone screen, text on screen, user interface, clock digits, numbers, television, "
               "laptop, cross, crucifix, halo, candles")
WOMAN = ("a young woman in her late twenties with messy shoulder-length auburn hair, wearing a soft grey "
         "long-sleeve t-shirt")
SHOTS = {
 "a_awake": (f"A dark cozy modern bedroom at three in the morning. {WOMAN} lies in bed on her side under a "
             f"rumpled cream quilt, wide awake, tired eyes open, holding a smartphone close to her face; the "
             f"phone's back faces the viewer and its cool white glow lights her face. Pale moonlight through a "
             f"window with thin curtains on the right side of the room, a wooden nightstand with a lamp switched "
             f"off. Deep blue night shadows, quiet, lonely, restless mood, medium wide shot, her face clearly visible."),
 "b_calm": (f"A dark cozy modern bedroom late at night. {WOMAN} lies on her back in bed under a cream quilt, "
            f"eyes closed, face relaxed and calm, one hand resting on her chest. A smartphone lies face-down on a "
            f"wooden nightstand beside her. Soft silver moonlight from a window with thin curtains falls across "
            f"the quilt. Peaceful, gentle, restful mood, medium wide shot."),
}
names = sys.argv[2:] or list(SHOTS)
for name in names:
    g.generate(SHOTS[name], [1, 2], 9, OUT := Path(sys.argv[1]), name)
    print("done", name, flush=True)
