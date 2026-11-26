"""마르다 릴스 spec(장면·카메라·자막) → spec.json, cover-spec.json. 카메라 [시각, 중심x, 중심y, 폭] 은 원본(1600×1200) 픽셀.
사용: python3 make_spec.py <작업폴더>   (작업폴더에 picks.json·cams.json·art/ — 이 폴더의 것을 복사해 쓴다)

자막 위치(top/low)는 cams.json 의 "pos" — 얼굴이 위쪽이면 low. 금색은 요 11:5 하나뿐(REVIEW T1), 마르다·예수님 말은 흰 자막에 장절 없이.
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


DUR = 63.5
shots = [
    # 첫 화면: 찌푸린 마르다 얼굴 — 0~1.3초에 1.2배로 밀고 들어가 2.4초에 부엌으로 컷
    {'img': ART['a_doorway'], 't0': 0.0, 't1': 2.4, 'cam': [at(0, 'face0'), at(1.3, 'face1'), at(2.4, 'face1', -10)]},
    {'img': ART['b_kitchen'], 't0': 2.4, 't1': 11.0, 'fade': 0.25,
     'cam': [at(2.4, 'kitchen0'), at(7.6, 'kitchen1'), at(11.4, 'kitchen2')]},
    {'img': ART['c_mary'], 't0': 11.0, 't1': 15.4, 'fade': 0.6, 'cam': [at(11.0, 'mary0'), at(15.8, 'mary1')]},
    {'img': ART['d_complain'], 't0': 15.4, 't1': 24.0, 'fade': 0.4,
     'cam': [at(15.4, 'complain0'), at(18.0, 'complain0', -30), at(19.0, 'complain1'), at(24.4, 'complain2')]},
    {'img': ART['e_listen'], 't0': 24.0, 't1': 36.2, 'fade': 0.7,
     'cam': [at(24.0, 'listen0'), at(26.0, 'listen1'), at(32.0, 'listen2'), at(36.6, 'listen2', -30)]},
    {'img': ART['c_mary'], 't0': 36.2, 't1': 41.8, 'fade': 0.8, 'cam': [at(36.2, 'mary1'), at(42.2, 'mary2')]},
    # 풀린 얼굴로 이어 간다(4차 검토: 41초에 따지던 그림으로 돌아가면 이야기 시간이 거꾸로 간다)
    {'img': ART['e_listen'], 't0': 41.8, 't1': 53.6, 'fade': 0.7,
     'cam': [at(41.8, 'listen1'), at(48.3, 'listen3'), at(54.0, 'listen3', -40)]},
    {'img': ART['f_rest'], 't0': 53.6, 't1': DUR, 'fade': 1.2, 'cam': [at(53.6, 'rest0'), at(DUR, 'rest1')]},
]


def t(text, cls='t'):
    return f"<p class='{cls}'>{text}</p>" if cls == 't' else f"<div class='{cls}'>{text}</div>"


# 0초에 무슨 이야기인지 제목(사용자 11/25 — REVIEW H3), 훅과 같이 3초
TITLE = ("<div class='b' style='top:230px'><div class='h1'>The story of Martha</div>"
         "<div class='sub'>Luke 10:38–42</div></div>")
texts = [
    {'t0': 0.0, 't1': 3.2, 'fi': 0, 'raw': True, 'html': TITLE},
    {'t0': 0.0, 't1': 3.2, 'fi': 0, 'pos': P.get('a', 'low'),
     'html': "<div class='hook'>She asked Jesus<br>to make her<br>sister help.<br>He didn’t.</div>"},
    {'t0': 3.15, 't1': 8.0, 'fi': 0.3, 'pos': P.get('b', 'top'),
     'html': t("Jesus had come to her village, and she had welcomed Him into her home.")},
    {'t0': 7.95, 't1': 10.9, 'fi': 0.3, 'pos': P.get('b', 'top'),
     'html': t("Then she was pulled in every direction by all the serving.")},
    {'t0': 11.5, 't1': 15.2, 'pos': P.get('c', 'top'), 'html': t("Her sister Mary sat at Jesus’ feet, listening to Him.")},
    {'t0': 15.6, 't1': 18.0, 'pos': P.get('d', 'top'), 'html': t("Martha had had enough.", 'h1')},
    {'t0': 18.2, 't1': 23.8, 'pos': P.get('d', 'top'),
     'html': t("“Lord, don’t you care that my sister left me to serve alone? Ask her therefore to help me.”")},
    {'t0': 24.3, 't1': 25.65, 'pos': P.get('e', 'low'), 'html': t("Jesus answered her:")},
    {'t0': 25.7, 't1': 29.15, 'pos': P.get('e', 'low'),
     'html': t("“Martha, Martha, you are anxious and troubled about many things,")},
    {'t0': 29.2, 't1': 32.0, 'fi': 0.2, 'pos': P.get('e', 'low'), 'html': t("but one thing is needed.”")},
    {'t0': 32.3, 't1': 36.0, 'pos': P.get('e', 'low'), 'html': t("He said her name twice. He saw the worry under all that work.")},
    {'t0': 36.5, 't1': 41.6, 'pos': P.get('c', 'top'),
     'html': t("The one thing needed was time with Him. Mary had it, and He wouldn’t take it from her.")},
    {'t0': 42.0, 't1': 44.4, 'pos': P.get('e', 'low'), 'html': t("He wanted Martha with Him, too.", 'h1')},
    {'t0': 44.5, 't1': 47.2, 'pos': P.get('e', 'low'), 'html': t("The Bible doesn’t say what Martha did next.")},
    {'t0': 47.15, 't1': 48.25, 'pos': P.get('e', 'low'), 'html': t("But it does say this:")},
    {'t0': 48.3, 't1': 53.4, 'pos': P.get('e', 'low'),
     'html': "<div class='v'>“Now Jesus loved Martha, and her sister…”</div><div class='r'>John 11:5</div>"},
    {'t0': 54.2, 't1': DUR + 0.4, 'pos': P.get('f', 'top'),
     'html': t("Doing it all this week?<br>You matter more to Him<br>than anything you get done.", 'h1')},
    {'t0': 55.4, 't1': DUR + 0.4, 'raw': True,
     'html': f"<div class='hd' style='{CAM.get('hd', 'bottom:400px')}'>@withgod.app · find your verse, link in bio</div>"},
]

spec = {'out': str(W / 'reel-silent.mp4'), 'dur': DUR, 'bg': '#16110D',
        'snaps': [0.5, 2.2, 5.0, 9.0, 13.0, 16.5, 21.0, 25.0, 28.0, 30.5, 34.0, 38.5, 43.0, 45.5, 47.5, 51.0, 58.0, 62.5],
        'shots': shots, 'texts': texts}
(W / 'spec.json').write_text(json.dumps(spec, ensure_ascii=False, indent=1))
x, y, w = CAM['cover']
cover = {'out': str(W / 'cover.mp4'), 'dur': 0.2, 'bg': '#16110D', 'snaps': [0.0],
         'shots': [{'img': ART['a_doorway'], 't0': 0, 't1': 0.2, 'cam': [[0, x, y, w]]}],
         'texts': [{'t0': 0, 't1': 1, 'fi': 0, 'raw': True, 'html': TITLE},
                   {'t0': 0, 't1': 1, 'fi': 0, 'pos': P.get('a', 'low'),
                    'html': "<div class='hook'>She asked Jesus<br>to make her<br>sister help.<br>He didn’t.</div>"}]}
(W / 'cover-spec.json').write_text(json.dumps(cover, ensure_ascii=False, indent=1))
print('spec ok')
