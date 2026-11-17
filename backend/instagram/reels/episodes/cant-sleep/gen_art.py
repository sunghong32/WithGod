"""Mia 1화 「3:07 a.m.」(잠 못 드는 밤) 장면 그림 — 로컬 Z-Image-Turbo q8, 세로. 장면마다 시드 1·2 를 뽑아 고른다.

    ~/.local/share/withgod-imagegen/venv/bin/python gen_art.py <작업폴더>/art [장면...]
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import mia  # noqa: E402
from mia import MIA, ROOM  # noqa: E402

NIGHT = "Three in the morning, dark deep-blue night shadows, faint cool city glow through the blinds."
SHOTS = {
 "a_ceiling": (f"Overhead shot looking straight down at {MIA}, lying on her back in bed in {ROOM}, the blanket pulled up "
               f"to her chest, wide awake with tired open eyes staring up at the ceiling, restless and worn out. {NIGHT} "
               f"Vertical composition, her face clearly visible in the middle of the frame, dark pillow and sheets around her."),
 "b_knees": (f"{MIA} sits up in bed in {ROOM}, hugging her knees under the rumpled blue blanket, chin resting on her knees, "
             f"worried eyes looking toward the window with blinds where city lights glow. {NIGHT} Lonely anxious mood, "
             f"vertical composition, her whole figure in the lower half of the frame, dark wall above."),
 "c_phone": (f"Close-up of {MIA} lying on her side in bed in {ROOM}, holding a smartphone close with both hands; the back "
             f"of the phone faces the viewer and its soft white glow lights her face and glasses. Quiet, thoughtful, a little "
             f"hopeful expression. {NIGHT} Vertical composition, her face in the upper middle of the frame."),
 "d_down": (f"{MIA} lies on her back in bed in {ROOM}, eyes half closed, face relaxed, a slow calm exhale, one hand resting "
            f"on her chest. Her smartphone lies face-down on the nightstand next to the green-striped mug. Soft silver "
            f"moonlight across the blanket, calm and peaceful mood. Vertical composition, medium shot from the side of the bed."),
 "e_asleep": (f"{MIA} has fallen asleep on her side in {ROOM}, eyes closed, a tiny hint of a smile, her round "
              f"glasses still on her face, slightly crooked, as if she drifted off mid-thought. Her smartphone lies face-down "
              f"on the nightstand next to the green-striped mug; there is only one pair of glasses in the whole picture. "
              f"The first pale blue light of dawn through the blinds, the city lights fading. Peaceful, restful, hopeful mood. "
              f"Vertical composition, she is in the lower half of the frame, soft dark wall and window above."),
}

if __name__ == '__main__':
    mia.generate(SHOTS, Path(sys.argv[1]), sys.argv[2:] or None)
