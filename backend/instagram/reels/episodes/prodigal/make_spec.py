"""성화 읽기 「탕자의 귀환 — 아버지의 두 손」 spec(장면·카메라·자막) → spec.json, cover-spec.json.
카메라 [시각, 중심x, 중심y, 폭] 은 원본(3840×5011) 픽셀. 9:16 창의 높이 = 폭 × 1.778 — 폭 2819 를 넘거나 위·아래 끝에
닿으면 bg 띠가 생긴다(전체 그림 3840 은 위·아래 띠 약 255px 를 일부러 둔다, 발 장면은 아래 띠가 인스타 캡션 자리에 숨는다).

    python3 get_art.py <작업폴더> && python3 make_spec.py <작업폴더>

자리(원본 픽셀): 아버지 얼굴 (1129, 1829)·머리 위 1530 · 아들 머리 (1043, 2557) · 굵은 손(보는 쪽 오른쪽) (1257, 2957) ·
가는 손(왼쪽) (871, 2986) · 발 (810, 4600) · 큰아들 얼굴 (3125, 950)·두 손 (3075, 2100).
자막 띠: top = 화면 y 300~600, low = 1100~1400. 얼굴이 자막 띠에 걸리지 않게 창을 잡았다(스냅으로 확인).
"""
import json
import sys
from pathlib import Path

W = Path(sys.argv[1])
IMG = str(W / 'art' / 'prodigal-3840.jpg')
WHOLE = [1920, 2505, 3840]  # 그림 전체(위·아래 띠)
DUR = 52.6

shots = [
    # 0초: 아들을 안은 아버지의 얼굴과 두 손 → 1.3초에 얼굴 쪽으로 1.2배 밀고 → 2.4초에 손 디테일로 컷
    {'img': IMG, 't0': 0.0, 't1': 2.4, 'cam': [[0, 1100, 2050, 1700], [1.3, 1110, 2003, 1400], [2.4, 1115, 1995, 1370]]},
    # 두 손: 굵은 손(화면 왼쪽에, 가는 손은 창 밖) → 가는 손(화면 오른쪽에, 굵은 손은 창 밖) → 다시 물러나 아버지와 아들
    {'img': IMG, 't0': 2.4, 't1': 12.6, 'fade': 0.25,
     'cam': [[2.4, 1390, 3020, 760], [5.2, 1385, 3025, 700], [6.1, 755, 3040, 700], [8.4, 760, 3045, 660],
             [9.8, 1100, 2150, 1700], [12.6, 1100, 2160, 1640]]},
    # 그림 전체 → 아버지와 아들 전신 → 아들 뒷머리·해진 옷 → 발
    {'img': IMG, 't0': 12.6, 't1': 29.0, 'fade': 0.6,
     'cam': [[12.6, *WHOLE], [16.6, 1920, 2505, 3680], [17.6, 1100, 3150, 2000], [20.8, 1080, 3200, 1900],
             [21.8, 1040, 3039, 1000], [24.8, 1040, 3060, 950], [25.8, 810, 4222, 1200], [29.0, 810, 4240, 1150]]},
    # 아버지 얼굴 → 오른쪽 큰아들로 옮겨 감
    {'img': IMG, 't0': 29.0, 't1': 38.0, 'fade': 0.5,
     'cam': [[29.0, 1129, 2094, 1100], [33.0, 1129, 2080, 1020], [34.2, 3150, 1504, 1300], [38.0, 3150, 1500, 1240]]},
    # 말씀: 아버지와 아들 → 끝: 그림 전체로 물러남
    {'img': IMG, 't0': 38.0, 't1': DUR, 'fade': 0.8,
     'cam': [[38.0, 1150, 2100, 1900], [43.6, 1150, 2110, 1800], [46.6, *WHOLE], [DUR, 1920, 2505, 3760]]},
]

texts = [
    # 줄은 <br> 로 직접 나눈다(한 낱말만 떨어지지 않게). 첫 문장(훅) — 0초부터, 뒤 자막은 앞 자막이 사라지기 직전에(첫 8초 빈 틈 0)
    {'t0': 0.0, 't1': 2.45, 'fi': 0, 'fo': 0.35, 'html': "<div class='hook'>The father’s hands<br>in this painting<br>don’t match.</div>"},
    {'t0': 2.4, 't1': 5.45, 'fi': 0.3, 'fo': 0.3, 'html': "<p class='t'>One is broad and strong.</p>"},
    {'t0': 5.4, 't1': 8.5, 'fi': 0.3, 'fo': 0.4, 'html': "<p class='t'>The other is slender and gentle.</p>"},
    {'t0': 8.45, 't1': 12.5, 'fi': 0.3, 'html': "<p class='t'>Some see a father’s hand<br>and a mother’s hand,<br>holding the same son.</p>"},
    {'t0': 12.8, 't1': 16.6, 'pos': 'low', 'html': "<p class='t'>Rembrandt painted it<br>near the end of his life.</p>"
                                                 "<div class='sub'><i>The Return of the Prodigal Son</i>, about 1668</div>"},
    {'t0': 16.8, 't1': 20.8, 'pos': 'low', 'html': "<p class='t'>In Jesus’ story, a son takes<br>his inheritance early<br>and wastes all of it.</p>"},
    {'t0': 21.0, 't1': 24.8, 'pos': 'low', 'html': "<p class='t'>He comes home with nothing.<br>Shaved head. Torn clothes.</p>"},
    {'t0': 25.0, 't1': 28.8, 'html': "<p class='t'>One foot is bare,<br>its sandal slipped off.</p><p class='t'>The other sandal is worn out.</p>"},
    {'t0': 29.0, 't1': 33.0, 'pos': 'low', 'html': "<p class='t'>He only hoped to be hired<br>as a servant.</p><p class='t'>His father ran to meet him.</p>"},
    {'t0': 33.4, 't1': 38.0, 'pos': 'low', 'html': "<p class='t'>On the right, the older brother.<br>Angry, he wouldn’t come in.</p>"
                                                 "<p class='t'>So the father went out<br>to him, too.</p>"},
    {'t0': 38.2, 't1': 43.6, 'html': "<div class='v'>“…this, my son, was dead<br>and is alive again.<br>He was lost and is found.”</div>"
                                     "<div class='r'>Luke 15:24</div>"},
    {'t0': 43.8, 't1': DUR + 0.4, 'pos': 'low', 'html': "<div class='h1'>Feeling far from God?<br>In Jesus’ story, the father<br>is the one who runs.</div>"},
    {'t0': 45.2, 't1': DUR + 0.4, 'raw': True, 'html': "<div class='hd' style='bottom:400px'>@withgod.app · find your verse, link in bio</div>"},
]

spec = {'out': str(W / 'reel-silent.mp4'), 'dur': DUR, 'bg': '#0e0b09', 'crf': 23,  # 캔버스 결 — crf 18 이면 33Mbps
        'snaps': [1.0, 2.3, 3.8, 7.0, 11.0, 14.6, 18.8, 22.9, 27.0, 31.0, 36.0, 41.0, 49.0], 'shots': shots, 'texts': texts}
(W / 'spec.json').write_text(json.dumps(spec, ensure_ascii=False, indent=1))
cover = {'out': str(W / 'cover.mp4'), 'dur': 0.2, 'bg': '#0e0b09', 'snaps': [0.0],
         'shots': [{'img': IMG, 't0': 0, 't1': 0.2, 'cam': [[0, 1100, 2000, 1700]]}],
         'texts': [{'t0': 0, 't1': 1, 'fi': 0, 'html': "<div class='hook'>The father’s hands<br>in this painting<br>don’t match.</div>"
                                                       "<div class='sub'>Rembrandt · Luke 15</div>"}]}
(W / 'cover-spec.json').write_text(json.dumps(cover, ensure_ascii=False, indent=1))
print('spec ok')
