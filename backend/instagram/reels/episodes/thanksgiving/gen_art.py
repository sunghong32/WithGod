"""Mia 2화 「Thanksgiving eve」(추수감사절 가족 식사가 두렵다) 장면 그림 — 로컬 Z-Image-Turbo q8, 세로. 시드 1·2 를 뽑아 고른다.

    ~/.local/share/withgod-imagegen/venv/bin/python gen_art.py <작업폴더>/art [장면...]

1화는 Mia 의 방이었고, 2화는 부모님 집으로 가는 추수감사절 전날 밤 버스 → 다음 날 저녁 현관. 앱 화면은 그리지 않는다
(휴대폰 뒷면만 보이게 — 실제 앱 녹화를 끼운다). 안경이 두 개 나오는 실수를 본 프롬프트로 막는다.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import mia  # noqa: E402
from mia import MIA  # noqa: E402

BUS = ("the window seat of a quiet intercity night bus, dim blue cabin lights, dark highway outside the window with blurred "
       "streaks of orange streetlights and red tail lights")
ONE = "She wears only one pair of glasses; there is only one pair of glasses in the whole picture."
SHOTS = {
 "a_bus": (f"Close-up of {MIA} sitting in {BUS}, a duffel bag on her lap, her forehead almost touching the cold window, "
           f"worried tired eyes staring out at the dark road, lips pressed together, dreading where she is going. {ONE} "
           f"Late evening, cool blue light with warm orange streaks across her face. Vertical composition, her face large "
           f"and clearly visible in the middle of the frame."),
 "b_reflection": (f"{MIA} sits in {BUS}, hugging her duffel bag tight against her chest, looking at her own faint reflection "
                  f"in the dark bus window, anxious and lost in thought. {ONE} The empty seats behind her fade into darkness. "
                  f"Vertical composition, her whole figure in the lower half of the frame, the dark window and passing lights above."),
 "c_phone": (f"Close-up of {MIA} in {BUS}, holding a smartphone close with both hands; the back of the phone faces the viewer "
             f"and its soft white glow lights her face and glasses. Quiet, thoughtful, a little hopeful expression. {ONE} "
             f"Vertical composition, her face in the upper middle of the frame."),
 "d_calm": (f"{MIA} in {BUS}, her head resting gently against the window, eyes closed, face relaxed, a slow calm exhale, "
            f"a faint small smile; her smartphone lies face-down on the duffel bag in her lap. {ONE} Soft warm orange "
            f"streetlight glow sliding across her face, peaceful mood. Vertical composition, medium shot."),
 "e_porch": (f"Evening. {MIA}, a duffel bag on her shoulder, stands on the front porch of a cozy suburban family house with warm "
             f"golden light glowing in the windows, an autumn leaf wreath on the wooden front door and pumpkins on the steps. "
             f"She takes a deep breath with a small brave smile, one hand raised to knock. {ONE} Crisp late-November dusk, "
             f"deep blue sky, warm and hopeful mood. Vertical composition, her whole figure in the lower half of the frame."),
}

if __name__ == '__main__':
    mia.generate(SHOTS, Path(sys.argv[1]), sys.argv[2:] or None)
