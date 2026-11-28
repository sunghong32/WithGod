"""사가랴와 엘리사벳 릴스 spec(장면·카메라·자막) → spec.json, cover-spec.json. 카메라 [시각, 중심x, 중심y, 폭] 은 원본(1600×1200) 픽셀.
사용: python3 make_spec.py <작업폴더>   (작업폴더에 picks.json·cams.json·art/ — 이 폴더의 것을 복사해 쓴다)

자막 위치(top/low)는 cams.json 의 "pos" — 얼굴이 위쪽이면 low. 금색은 눅 1:78–79 하나뿐(REVIEW T1), 천사·사가랴·엘리사벳의 말은 흰 자막에 장절 없이.
장면 바꿈은 compose.py 의 줄·마디 경계와 맞춘다(이름 짓는 날 38.4초 = 후렴 "Rejoice!").
"""
import json
import sys
from pathlib import Path

W = Path(sys.argv[1])
ART = json.loads((W / 'picks.json').read_text())
CAM = json.loads((W / 'cams.json').read_text())
P = CAM.get('pos', {})


def at(t, key, dw=0):
    x, y, w = CAM[key]
    return [t, x, y, w + dw]


DUR = 66.5
shots = [
    # 첫 화면: 놀란 사가랴 얼굴 — 0~1.3초에 1.2배로 밀고 들어가 2.4초에 집으로 컷
    {'img': ART['a_temple'], 't0': 0.0, 't1': 2.4, 'cam': [at(0, 'face0'), at(1.3, 'face1'), at(2.4, 'face1', -10)]},
    {'img': ART['b_home'], 't0': 2.4, 't1': 13.6, 'fade': 0.25,
     'cam': [at(2.4, 'home0'), at(7.0, 'home1'), at(14.0, 'home2')]},
    {'img': ART['c_altar'], 't0': 13.6, 't1': 19.2, 'fade': 0.6, 'cam': [at(13.6, 'altar0'), at(19.6, 'altar1')]},
    {'img': ART['a_temple'], 't0': 19.2, 't1': 28.8, 'fade': 0.5,
     'cam': [at(19.2, 'angel0'), at(24.9, 'angel1'), at(29.2, 'angel2')]},
    {'img': ART['d_mute'], 't0': 28.8, 't1': 32.8, 'fade': 0.5, 'cam': [at(28.8, 'mute0'), at(33.2, 'mute1')]},
    {'img': ART['e_eliz'], 't0': 32.8, 't1': 38.4, 'fade': 0.6, 'cam': [at(32.8, 'eliz0'), at(38.8, 'eliz1')]},
    # 밝아지는 순간 — 후렴 "Rejoice!"(38.4)와 같이
    {'img': ART['f_name'], 't0': 38.4, 't1': 49.0, 'fade': 0.5,
     'cam': [at(38.4, 'name0'), at(44.6, 'name1'), at(49.4, 'name2')]},
    {'img': ART['g_dawn'], 't0': 49.0, 't1': DUR, 'fade': 1.0, 'cam': [at(49.0, 'dawn0'), at(57.6, 'dawn1'), at(DUR, 'dawn2')]},
]


def t(text, cls='t'):
    return f"<p class='{cls}'>{text}</p>" if cls == 't' else f"<div class='{cls}'>{text}</div>"


# 0초에 무슨 이야기인지 제목(REVIEW H3), 훅과 같이 3.2초
TITLE = ("<div class='b' style='top:230px'><div class='h1'>The story of<br>Zechariah and Elizabeth</div>"
         "<div class='sub'>Luke 1</div></div>")
HOOK = "<div class='hook'>An angel said<br>his prayer was heard.<br>He asked for proof.</div>"
texts = [
    {'t0': 0.0, 't1': 3.2, 'fi': 0, 'raw': True, 'html': TITLE},
    {'t0': 0.0, 't1': 3.2, 'fi': 0, 'pos': P.get('a', 'low'), 'html': HOOK},
    {'t0': 3.15, 't1': 7.0, 'fi': 0.3, 'pos': P.get('b', 'low'),
     'html': t("Zechariah was a priest. He and his wife Elizabeth were “both righteous before God…”")},
    {'t0': 6.95, 't1': 10.6, 'fi': 0.3, 'pos': P.get('b', 'low'),
     'html': t("“But they had no child… and they both were well advanced in years.”")},
    {'t0': 10.55, 't1': 13.45, 'fi': 0.3, 'pos': P.get('b', 'low'), 'html': t("They had prayed for years.")},
    {'t0': 13.8, 't1': 16.75, 'pos': P.get('c', 'low'),
     'html': t("One day, he was chosen by lot to burn incense inside the temple.")},
    {'t0': 16.7, 't1': 19.0, 'fi': 0.3, 'pos': P.get('c', 'low'),
     'html': t("A priest got that honor once in a lifetime, if ever.")},
    {'t0': 19.4, 't1': 24.9, 'pos': P.get('a2', 'low'),
     'html': t("An angel said, “Don’t be afraid… your request has been heard. Your wife… will bear you a son…”")},
    {'t0': 24.85, 't1': 28.6, 'fi': 0.3, 'pos': P.get('a2', 'low'),
     'html': t("Zechariah answered, “How can I be sure of this? For I am an old man…”")},
    {'t0': 29.0, 't1': 32.7, 'pos': P.get('d', 'top'),
     'html': t("His proof: he couldn’t speak a word until the promise came true.")},
    {'t0': 33.0, 't1': 38.2, 'pos': P.get('e', 'low'),
     'html': t("Months later, Elizabeth was expecting. “Thus has the Lord done to me in the days in which he looked at me…”")},
    {'t0': 38.6, 't1': 42.0, 'pos': P.get('f', 'top'),
     'html': t("When they named the baby, he wrote: “His name is John.”")},
    {'t0': 41.95, 't1': 45.0, 'fi': 0.3, 'pos': P.get('f', 'top'),
     'html': t("Then he spoke again — and his first words were praise.")},
    {'t0': 45.0, 't1': 48.8, 'fi': 0.3, 'pos': P.get('f', 'top'),
     'html': t("Zechariah means “the Lord has remembered.” And He had — even in the years with no answer.")},
    {'t0': 49.2, 't1': 52.45, 'pos': P.get('g', 'top'), 'html': t("He sang of the light God was sending to all who wait in the dark:")},
    {'t0': 52.4, 't1': 57.4, 'fi': 0.3, 'pos': P.get('g', 'top'),
     'html': "<div class='v'>“…the dawn from on high will visit us, to shine on those who sit in darkness…”</div>"
             "<div class='r'>Luke 1:78–79</div>"},
    {'t0': 57.8, 't1': DUR + 0.4, 'pos': P.get('g', 'top'),
     'html': t("Still waiting on a prayer?<br>Waiting doesn’t mean<br>you’ve been forgotten.", 'h1')},
    {'t0': 59.0, 't1': DUR + 0.4, 'raw': True,
     'html': f"<div class='hd' style='{CAM.get('hd', 'bottom:400px')}'>@withgod.app · find your verse, link in bio</div>"},
]

spec = {'out': str(W / 'reel-silent.mp4'), 'dur': DUR, 'bg': '#16110D',
        'snaps': [0.5, 2.2, 5.0, 9.0, 12.0, 15.0, 18.0, 20.5, 23.5, 27.5, 31.0, 36.0, 40.0, 43.5, 47.0, 50.5, 54.5, 62.0],
        'shots': shots, 'texts': texts}
(W / 'spec.json').write_text(json.dumps(spec, ensure_ascii=False, indent=1))
x, y, w = CAM['cover']
cover = {'out': str(W / 'cover.mp4'), 'dur': 0.2, 'bg': '#16110D', 'snaps': [0.0],
         'shots': [{'img': ART['a_temple'], 't0': 0, 't1': 0.2, 'cam': [[0, x, y, w]]}],
         'texts': [{'t0': 0, 't1': 1, 'fi': 0, 'raw': True, 'html': TITLE},
                   {'t0': 0, 't1': 1, 'fi': 0, 'pos': P.get('a', 'low'), 'html': HOOK}]}
(W / 'cover-spec.json').write_text(json.dumps(cover, ensure_ascii=False, indent=1))
print('spec ok')
