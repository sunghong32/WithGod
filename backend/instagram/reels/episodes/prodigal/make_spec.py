"""성화 읽기 「탕자의 귀환 — 사람들이 놓치는 디테일 4개」 spec(장면·카메라·표시·자막) → spec.json, cover-spec.json.

그림풀이처럼 보이게(사용자 11/19: "그림에 글만 바뀌면 그냥 그림이다, 궁금증도 안 생긴다"):
- 첫 화면부터 그림 위에 금색 동그라미가 그려지고, 그림 전체에 번호 1~4 를 찍어 "디테일 4개"를 예고한다.
- 디테일마다 번호 띠(1 / 4 · THE HANDS) → 동그라미·조명으로 짚기 → 숨은 뒷얘기 → 「In the Bible」 카드로 성경 구절과 잇는다.
- 두 손은 나란히 놓고 비교한다(panels).
카메라 [시각, 중심x, 중심y, 폭] · 표시(marks) 좌표는 원본(3840×5011) 픽셀. 9:16 창의 높이 = 폭 × 1.778.

    python3 get_art.py <작업폴더> && python3 make_spec.py <작업폴더>
    python3 ../../render.py <작업폴더>/spec.json --only 1.0,7.5     # 자리 잡을 때 스냅만

자리(원본 픽셀): 아버지 얼굴 (1129, 1829)·머리 위 1530 · 아들 머리 (1043, 2557) · 가는 손(보는 쪽 왼쪽) (885, 2980) ·
굵은 손(오른쪽) (1255, 2955) · 아들 허리의 짧은 칼 (1190, 3790, 손잡이 3573~칼집 끝 4013) · 맨발 (510, 4540) ·
벗겨진 신 (720, 4700) · 닳은 신 (1110, 4590) · 큰아들 얼굴 (3040, 1000)·모은 두 손 (3010, 2150).
자막 띠: top = 화면 y 300~600, low = 1100~1400. 「In the Bible」 카드(.vc)는 raw 로 top 픽셀을 직접 준다.
"""
import json
import sys
from pathlib import Path

W = Path(sys.argv[1])
IMG = str(W / 'art' / 'prodigal-3840.jpg')
WHOLE = [1920, 2505, 3840]  # 그림 전체(위·아래 띠)
DUR = 57.0

SLENDER, BROAD = [885, 2980, 165, 200], [1255, 2955, 180, 195]
SWORD = [1190, 3790, 100, 255]
BARE, WORN = [510, 4540, 135, 270], [1110, 4590, 145, 250]
BRO_HANDS = [3010, 2150, 175, 150]


def num(n):
    return f"<div class='num'>{n}</div>"


def lbl(text):
    return f"<div class='lbl'>{text}</div>"


def tag(n, what):
    return f"<span class='tag'>{n} / 4 · {what}</span>"


def card(ref, quote, top):
    return {'raw': True, 'html': f"<div class='vc' style='top:{top}px'><div class='ref'>In the Bible · {ref}</div>"
                                 f"<div class='q'>{quote}</div></div>"}


def plbl(text, left):  # 나란히 보기 판 아래쪽 이름표(화면 좌표)
    return {'raw': True, 'html': f"<div class='lbl' style='position:absolute;left:{left}px;top:1356px'>{text}</div>"}


shots = [
    # 0초: 두 손 — 0.25·0.5초에 동그라미가 그려지고 2.4초까지 1.25배 밀고 들어간다
    {'img': IMG, 't0': 0.0, 't1': 2.45, 'cam': [[0, 1070, 2972, 1350], [2.4, 1070, 2960, 1080]],
     'marks': [{'t0': 0.25, 't1': 2.6, 'ring': SLENDER}, {'t0': 0.5, 't1': 2.6, 'ring': BROAD}]},
    # 그림 전체 — 번호 1~4 가 차례로 찍힌다(손 · 칼 · 발 · 오른쪽 남자)
    {'img': IMG, 't0': 2.45, 't1': 6.4, 'fade': 0.2, 'cam': [[2.45, *WHOLE], [6.4, 1900, 2560, 3500]],
     'marks': [{'t0': 4.6, 't1': 6.6, 'tag': num(1), 'at': [1070, 2960]},
               {'t0': 4.85, 't1': 6.6, 'tag': num(2), 'at': [1250, 3790]},
               {'t0': 5.1, 't1': 6.6, 'tag': num(3), 'at': [800, 4560]},
               {'t0': 5.35, 't1': 6.6, 'tag': num(4), 'at': [3040, 1650]}]},
    # 1 손: 나란히 비교(왼쪽 가는 손 · 오른쪽 굵은 손 — 그림에서 놓인 자리 그대로)
    {'t0': 6.4, 't1': 12.6, 'fade': 0.25, 'under': [1900, 2560, 3500], 'under_img': IMG,
     'panels': [{'img': IMG, 'box': [60, 650, 470, 800], 'from': [-560, 0],
                 'cam': [[6.4, 890, 2985, 360], [12.6, 890, 2990, 320]]},
                {'img': IMG, 'box': [550, 650, 470, 800], 'from': [560, 0],
                 'cam': [[6.4, 1250, 2960, 360], [12.6, 1250, 2965, 320]]}]},
    # 아버지가 아들을 안은 모습 + 눅 15:20 카드
    {'img': IMG, 't0': 12.6, 't1': 16.4, 'fade': 0.4, 'cam': [[12.6, 1070, 2180, 1500], [16.4, 1070, 2170, 1400]]},
    # 2 아들: 깎은 머리·해진 옷 → 허리의 짧은 칼(조명 + 동그라미 + 이름표)
    {'img': IMG, 't0': 16.4, 't1': 26.6, 'fade': 0.4,
     'cam': [[16.4, 1060, 2800, 1200], [19.2, 1060, 2840, 1150], [20.0, 1190, 3720, 1000], [26.6, 1190, 3740, 950]],
     'marks': [{'t0': 19.9, 't1': 23.0, 'spot': [1190, 3790, 190, 340]},
               {'t0': 20.2, 't1': 23.0, 'ring': SWORD},
               {'t0': 20.7, 't1': 23.0, 'tag': lbl('a short sword'), 'at': [1190, 3790], 'off': [270, -200]}]},
    # 3 발: 맨발(신이 벗겨져 옆에) · 닳은 신 → 눅 15:22 카드 → 맨발에 다시 조명
    {'img': IMG, 't0': 26.6, 't1': 35.4, 'fade': 0.4, 'cam': [[26.6, 820, 4616, 1000], [35.4, 820, 4600, 940]],
     'marks': [{'t0': 27.1, 't1': 30.3, 'ring': BARE}, {'t0': 27.7, 't1': 30.3, 'ring': WORN},
               {'t0': 27.4, 't1': 30.3, 'tag': lbl('bare'), 'at': [510, 4540], 'off': [0, -330]},
               {'t0': 28.0, 't1': 30.3, 'tag': lbl('worn through'), 'at': [1110, 4590], 'off': [-20, -320]},
               {'t0': 32.7, 't1': 35.6, 'spot': [560, 4560, 260, 330], 'dim': 0.55}]},
    # 4 오른쪽 남자: 얼굴과 모은 두 손 → 물러나 아버지·아들과 떨어져 선 거리 + 조명
    {'img': IMG, 't0': 35.4, 't1': 44.6, 'fade': 0.4,
     'cam': [[35.4, 3000, 1457, 1900], [38.6, 3000, 1470, 1800], [40.0, 2200, 2505, 3700], [44.6, 2200, 2505, 3600]],
     'marks': [{'t0': 36.0, 't1': 39.3, 'ring': BRO_HANDS},
               {'t0': 39.6, 't1': 44.8, 'spot': [3030, 1750, 560, 1300], 'dim': 0.58}]},
    # 말씀: 아버지와 아들
    {'img': IMG, 't0': 44.6, 't1': 50.2, 'fade': 0.6, 'cam': [[44.6, 1150, 2100, 1900], [50.2, 1150, 2110, 1800]]},
    # 끝: 그림 전체로 물러남
    {'img': IMG, 't0': 50.2, 't1': DUR, 'fade': 0.8,
     'cam': [[50.2, 1150, 2110, 1800], [53.2, *WHOLE], [DUR, 1920, 2505, 3760]]},
]

texts = [
    # 첫 문장(훅) — 0초부터. 뒤 자막은 앞 자막이 사라지기 직전에(첫 8초 빈 틈 0)
    {'t0': 0.0, 't1': 2.45, 'fi': 0, 'fo': 0.3, 'html': "<div class='hook'>The father’s hands<br>in this painting<br>don’t match.</div>"},
    {'t0': 2.4, 't1': 4.5, 'fi': 0.3, 'fo': 0.3, 'html': "<p class='t'>Jesus’ story of a lost son,<br>painted by Rembrandt.</p>"
                                                       "<div class='sub'><i>The Return of the Prodigal Son</i>, about 1668</div>"},
    {'t0': 4.45, 't1': 6.45, 'fi': 0.25, 'fo': 0.3, 'html': "<div class='h1'>4 details<br>most people miss.</div>"},
    # 1 손
    {'t0': 6.4, 't1': 9.6, 'fi': 0.3, 'fo': 0.3, 'html': tag(1, 'The hands') + "<p class='t'>One is broad and strong.<br>One is slender and gentle.</p>"},
    {'t0': 6.9, 't1': 9.65, 'fi': 0.25, 'fo': 0.25, **plbl('broad · strong', 574)},
    {'t0': 7.9, 't1': 9.65, 'fi': 0.25, 'fo': 0.25, **plbl('slender · gentle', 84)},
    {'t0': 9.55, 't1': 12.6, 'fi': 0.3, 'fo': 0.3, 'html': "<p class='t'>Henri Nouwen saw<br>a father’s hand<br>and a mother’s hand.</p>"},
    {'t0': 9.65, 't1': 12.6, 'fi': 0.25, 'fo': 0.3, **plbl('a father’s hand', 574)},
    {'t0': 10.2, 't1': 12.6, 'fi': 0.25, 'fo': 0.3, **plbl('a mother’s hand', 84)},
    {'t0': 12.65, 't1': 16.35, 'fi': 0.3, 'fo': 0.35, 'html': "<p class='t'>In the story, the father<br>doesn’t wait.</p>"},
    {'t0': 13.1, 't1': 16.35, 'fi': 0.35, 'fo': 0.35,
     **card('Luke 15:20', '“…his father saw him and was moved with compassion, and ran…”', 1130)},
    # 2 아들
    {'t0': 16.45, 't1': 19.55, 'pos': 'low', 'fi': 0.3, 'fo': 0.3,
     'html': tag(2, 'The son') + "<p class='t'>He took his inheritance early<br>and wasted all of it.</p>"},
    {'t0': 19.5, 't1': 22.75, 'fi': 0.3, 'fo': 0.3, 'html': "<p class='t'>Torn clothes, shaved head.<br>But a sword still hangs<br>at his hip.</p>"},
    {'t0': 22.7, 't1': 26.55, 'fi': 0.3, 'fo': 0.35, 'html': "<p class='t'>Some see it as the last sign<br>he was still a son.</p>"},
    {'t0': 23.2, 't1': 26.55, 'fi': 0.35, 'fo': 0.35,
     **card('Luke 15:19', '“I am no more worthy to be called your son. Make me as one of your hired servants.”', 1150)},
    # 3 발
    {'t0': 26.65, 't1': 30.15, 'fi': 0.3, 'fo': 0.3,
     'html': tag(3, 'The feet') + "<p class='t'>One sandal has slipped off.<br>The other is worn through.</p>"},
    {'t0': 30.1, 't1': 32.75, 'fi': 0.3, 'fo': 0.3, 'html': "<p class='t'>And the father’s<br>first order?</p>"},
    {'t0': 30.6, 't1': 35.35, 'fi': 0.35, 'fo': 0.35,
     **card('Luke 15:22', '“…Put a ring on his hand and sandals on his feet.”', 1240)},
    {'t0': 32.7, 't1': 35.35, 'fi': 0.3, 'fo': 0.35, 'html': "<div class='h1'>Sandals.<br>A son, not a servant.</div>"},
    # 4 오른쪽 남자
    {'t0': 35.45, 't1': 39.1, 'fi': 0.3, 'fo': 0.35,
     'html': tag(4, 'The man on the right') + "<p class='t'>Most see the older brother.<br>Hands held tight.</p>"},
    {'t0': 40.0, 't1': 44.55, 'fi': 0.35, 'fo': 0.35,
     **card('Luke 15:28', '“But he was angry and would not go in. Therefore his father came out and begged him.”', 1150)},
    {'t0': 41.7, 't1': 44.55, 'fi': 0.3, 'fo': 0.35, 'html': "<div class='h1'>Jesus never says<br>if he went in.</div>"},
    # 말씀(금색 이탤릭 — 이 편의 위로) · 끝
    {'t0': 44.8, 't1': 50.1, 'html': "<div class='v'>“…this, my son, was dead<br>and is alive again.<br>He was lost and is found.”</div>"
                                     "<div class='r'>Luke 15:24</div>"},
    {'t0': 50.4, 't1': DUR + 0.4, 'pos': 'low', 'html': "<div class='h1'>Feeling far from God?<br>In Jesus’ story, the father<br>is the one who runs.</div>"},
    {'t0': 51.8, 't1': DUR + 0.4, 'raw': True, 'html': "<div class='hd' style='bottom:400px'>@withgod.app · find your verse, link in bio</div>"},
]

spec = {'out': str(W / 'reel-silent.mp4'), 'dur': DUR, 'bg': '#0e0b09', 'crf': 23,  # 캔버스 결 — crf 18 이면 33Mbps
        'snaps': [0.3, 1.0, 2.3, 3.5, 5.6, 7.0, 8.5, 11.0, 14.5, 17.5, 21.0, 24.5, 28.5, 31.5, 34.0, 37.5, 42.5, 47.0, 54.0],
        'shots': shots, 'texts': texts}
(W / 'spec.json').write_text(json.dumps(spec, ensure_ascii=False, indent=1))
cover = {'out': str(W / 'cover.mp4'), 'dur': 0.2, 'bg': '#0e0b09', 'snaps': [0.0],
         'shots': [{'img': IMG, 't0': 0, 't1': 0.2, 'cam': [[0, 1070, 2972, 1350]],
                    'marks': [{'t0': -1, 't1': 9, 'ring': SLENDER}, {'t0': -1, 't1': 9, 'ring': BROAD}]}],
         'texts': [{'t0': 0, 't1': 1, 'fi': 0, 'html': "<div class='hook'>The father’s hands<br>in this painting<br>don’t match.</div>"
                                                       "<div class='sub'>4 details most people miss · Rembrandt</div>"}]}
(W / 'cover-spec.json').write_text(json.dumps(cover, ensure_ascii=False, indent=1))
print('spec ok')
