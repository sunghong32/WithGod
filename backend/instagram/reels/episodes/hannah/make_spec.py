"""한나 릴스 spec(장면·카메라·자막) → spec.json, cover-spec.json. 카메라 [시각, 중심x, 중심y, 폭] 은 원본(1600×1200) 픽셀.
사용: python3 make_spec.py <작업폴더>   (작업폴더에 picks.json·cams.json·art/ — 이 폴더의 것을 복사해 쓴다)
"""
import json
import sys
from pathlib import Path

W = Path(sys.argv[1])
ART = json.loads((W / 'picks.json').read_text())  # {"a_temple": "art/a_temple_2.png", ...}
CAM = json.loads((W / 'cams.json').read_text())   # 장면별 대표 위치: {"hannah_close": [x, y, w], ...}


def at(t, key, dw=0):
    x, y, w = CAM[key]
    return [t, x, y, w + dw]


DUR = 59.6
shots = [
    # 첫 화면: 기도하는 한나 얼굴 가까이 → 살짝 물러남
    {'img': ART['a_temple'], 't0': 0.0, 't1': 3.4, 'cam': [at(0, 'hannah_face'), at(3.4, 'hannah_face', 60)]},
    # 잔치: 한나(외톨이) → 브닌나와 아이들 → 다시 한나
    {'img': ART['b_feast'], 't0': 3.4, 't1': 14.6, 'fade': 0.7,
     'cam': [at(3.4, 'feast_wide'), at(7.4, 'feast_wide', -40), at(9.6, 'peninnah'), at(11.4, 'peninnah', -30),
             at(13.6, 'feast_hannah'), at(15.2, 'feast_hannah', -20)]},
    # 남편: 둘을 함께 → "It didn't help" 에서 한나 쪽으로
    {'img': ART['c_husband'], 't0': 14.6, 't1': 21.6, 'fade': 0.8,
     'cam': [at(14.6, 'couple'), at(18.4, 'couple', -40), at(21.6, 'couple_hannah'), at(22.4, 'couple_hannah', -10)]},
    # 성전: 넓게 → 한나 입술 → 엘리 → 한나 → 둘 다
    {'img': ART['a_temple'], 't0': 21.6, 't1': 43.0, 'fade': 0.9,
     'cam': [at(21.6, 'temple_wide'), at(25.4, 'temple_wide', -60), at(27.0, 'hannah_face'), at(28.4, 'hannah_face', -30),
             at(30.0, 'eli'), at(32.0, 'eli', -30), at(33.6, 'hannah_mid'), at(36.0, 'hannah_mid', -20),
             at(37.0, 'eli'), at(37.6, 'eli', -10), at(39.0, 'hannah_mid'), at(43.0, 'hannah_mid', -40), at(43.8, 'hannah_mid', -45)]},
    # 아침: 가벼워진 얼굴로 걸어옴, 천천히 다가감
    {'img': ART['d_morning'], 't0': 43.0, 't1': DUR, 'fade': 1.2,
     'cam': [[43.0, 880, 600, 675], [51.2, 880, 560, 615], [DUR, 880, 520, 565]]},
]

texts = [
    {'t0': 0.0, 't1': 3.2, 'fi': 0, 'html': "<div class='h1'>She prayed so hard, the priest thought she was drunk.</div>"},
    {'t0': 3.6, 't1': 7.4, 'html': "<p class='t'>Her name was Hannah. For years she had longed for a child, and none came.</p>"},
    {'t0': 7.6, 't1': 11.2, 'html': "<p class='t'>Her husband’s other wife had many children, and never let her forget it.</p>"},
    {'t0': 11.4, 't1': 14.4, 'html': "<p class='t'>Every year at the feast in Shiloh, Hannah cried and couldn’t eat.</p>"},
    {'t0': 14.8, 't1': 18.4, 'html': "<p class='t'>Her husband tried to comfort her: “Am I not better to you than ten sons?”</p>"},
    {'t0': 18.6, 't1': 21.4, 'html': "<div class='h1'>It didn’t help.</div>"},
    {'t0': 21.8, 't1': 25.4, 'html': "<p class='t'>So she went to the temple and poured it all out to God.</p>"},
    {'t0': 25.6, 't1': 28.4, 'html': "<p class='t'>No sound. Only her lips moved.</p>"},
    {'t0': 28.6, 't1': 32.0, 'html': "<p class='t'>The old priest Eli was watching. “How long will you be drunk?”</p>"},
    {'t0': 32.2, 't1': 36.0, 'html': "<p class='t'>“I’m not drunk,” she said. “I was pouring out my soul before the LORD.”</p>"},
    {'t0': 36.2, 't1': 37.6, 'html': "<p class='t'>Eli answered:</p>"},
    {'t0': 37.8, 't1': 42.8, 'pos': 'low', 'html': "<div class='v'>“Go in peace; and may the God of Israel grant your petition "
                                                  "that you have asked of him.”</div><div class='r'>1 Samuel 1:17</div>"},
    {'t0': 43.2, 't1': 47.2, 'pos': 'low', 'html': "<p class='t'>She went her way and ate. Her face wasn’t sad anymore.</p>"},
    {'t0': 47.4, 't1': 51.0, 'pos': 'low', 'html': "<div class='h1'>Nothing had changed yet. She had finally said all of it to God.</div>"},
    {'t0': 51.2, 't1': 60.0, 'pos': 'low', 'html': "<div class='h1'>Carrying something you can’t say out loud? Tell God all of it, the way Hannah did.</div>"},
    {'t0': 52.6, 't1': 60.0, 'raw': True, 'html': "<div class='hd' style='bottom:400px'>@withgod.app · find your verse, link in bio</div>"},
]

spec = {'out': str(W / 'reel-silent.mp4'), 'dur': DUR, 'bg': '#141018',
        'snaps': [34.0, 36.8, 40.0, 45.0, 49.0, 57.0], 'shots': shots, 'texts': texts}
(W / 'spec.json').write_text(json.dumps(spec, ensure_ascii=False, indent=1))
x, y, w = CAM['cover']
cover = {'out': str(W / 'cover.mp4'), 'dur': 0.2, 'bg': '#141018', 'snaps': [0.0],
         'shots': [{'img': ART['a_temple'], 't0': 0, 't1': 0.2, 'cam': [[0, x, y, w]]}],
         'texts': [{'t0': 0, 't1': 1, 'fi': 0, 'html': "<div class='h1'>She prayed so hard, the priest thought she was drunk.</div>"
                                                       "<div class='sub'>1 Samuel 1</div>"}]}
(W / 'cover-spec.json').write_text(json.dumps(cover, ensure_ascii=False, indent=1))
print('spec ok')
