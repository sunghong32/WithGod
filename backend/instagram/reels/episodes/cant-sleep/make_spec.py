"""Mia 1화 「3:07 a.m.」 spec → spec.json, cover-spec.json (수요일 시리즈 Mia, 형식은 mia.py).
사용: python3 make_spec.py <작업폴더>   (작업폴더에 picks.json·cams.json·art/·app30.mp4)

이야기: 새벽 3시 7분, 몸은 지쳤는데 머리가 안 꺼진다(천장) → 출근·월세·답 못 한 문자(무릎을 안고) → 스크롤 말고
조용해지고 싶어서 WithGod 앱에 그대로 적는다(휴대폰 불빛) → 실제 앱 화면(전체 화면, 자막 없이) → 한 줄을 세 번 읽음 ·
해결된 건 없지만 조용해졌다(휴대폰을 엎어 둠) → 새벽빛에 잠든 Mia 위로 금색 말씀 → 보는 사람에게 돌려주는 한 줄.
광고처럼 보이지 않게: 기능 설명·떠 있는 휴대폰 카드·큰 스티커 없이, 자막은 Mia 의 속마음만.

app30.mp4 = iPhone 17 Pro 시뮬레이터 녹화(1206×2622, 상태 막대 03:07 고정)를 30fps 로 바꾼 것. 홈에서 딥링크
`withgod://result?mood=It's 3am and I can't sleep. My mind won't stop racing.` 로 연 실제 앱 응답이다(11/17 운영 서버,
시편 119:114). 녹화 시점: 0–1.9 홈 · 1.9–2.3 넘어감 · 2.0–10.2 찾는 중 · 10.4–12.6 말씀 · 13.6–24.5 풀이(21~24 에
「Tonight, you do not have to solve everything …」 줄이 나오고 앱이 스스로 아래로 내린다 — 24초에 원본 y 1730–1910).
"""
import json
import sys
from pathlib import Path

W = Path(sys.argv[1])
ART = json.loads((W / 'picks.json').read_text())
CAM = json.loads((W / 'cams.json').read_text())
APP = str(W / 'app30.mp4')
FPS = 30
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from mia import CSS  # noqa: E402


def at(t, key, dw=0):
    x, y, w = CAM[key]
    return [t, x, y, w + dw]


TOP, BOTTOM = [603, 1072, 1206], [603, 1478, 1206]  # 앱 화면 위쪽 맞춤 / 아래쪽 맞춤(전체 폭 — 카드 양옆이 안 잘리게)
LINE = [603, 1730, 1000]  # 「Tonight, you do not have to solve everything …」 줄로 천천히 다가감


def app(t, pos):
    return [t] + pos


DUR = 42.0
shots = [
    {'img': ART['a_ceiling'], 't0': 0.0, 't1': 3.8, 'cam': [at(0, 'a0'), at(4.4, 'a1')]},
    {'img': ART['b_knees'], 't0': 3.8, 't1': 8.4, 'fade': 0.7, 'cam': [at(3.8, 'b0'), at(9.0, 'b1')]},
    {'img': ART['c_phone'], 't0': 8.4, 't1': 12.4, 'fade': 0.7, 'cam': [at(8.4, 'c0'), at(12.8, 'c1')]},
    # 앱(휴대폰 화면을 그대로): 홈 → 결과 화면(Mia 가 적은 말이 말풍선으로) — 찾는 동안은 잘라 낸다
    {'video': APP, 'src_fps': FPS, 'start_frame': int(0.6 * FPS), 't0': 12.4, 't1': 15.2, 'fade': 0.5, 'cam': [app(12.4, TOP)]},
    {'video': APP, 'src_fps': FPS, 'start_frame': int(10.2 * FPS), 't0': 15.2, 't1': 18.2, 'fade': 0.3, 'cam': [app(15.2, TOP)]},
    {'video': APP, 'src_fps': FPS, 'start_frame': int(13.6 * FPS), 't0': 18.2, 't1': 20.6, 'fade': 0.3, 'cam': [app(18.2, TOP)]},
    # 그 줄이 채워지는 동안 천천히(0.76배) 다가간다
    {'video': APP, 'src_fps': FPS, 'speed': 0.76, 'start_frame': int(21.4 * FPS), 't0': 20.6, 't1': 24.4, 'fade': 0.4,
     'cam': [app(20.6, BOTTOM), app(22.4, BOTTOM), app(24.4, LINE)]},
    {'img': ART['d_down'], 't0': 24.4, 't1': 30.6, 'fade': 0.8, 'cam': [at(24.4, 'd0'), at(31.4, 'd1')]},
    {'img': ART['e_asleep'], 't0': 30.6, 't1': DUR, 'fade': 1.2, 'cam': [at(30.6, 'e0'), at(DUR, 'e1')]},
]


def m(text, cls='m'):
    return f"<p class='{cls}'>{text}</p>"


def stack(lines, show, cls='m'):
    """여러 줄을 한 줄씩 나타나게 — 모든 줄을 같은 자리에 두고 show 번째 줄만 보이게 한 층을 따로 찍는다."""
    return ''.join(f"<p class='{cls}' style='visibility:{'visible' if i == show else 'hidden'}'>{x}</p>"
                   for i, x in enumerate(lines))


P = CAM.get('pos', {})
WORRY = ['Work in five hours.', 'Rent on Friday.', 'That text I still haven’t answered.']
texts = [
    {'t0': 0.0, 't1': 3.6, 'fi': 0, 'raw': True, 'html': "<div class='stamp'>3:07 A.M.</div>"},
    {'t0': 0.0, 't1': 3.6, 'fi': 0, 'pos': P.get('a', 'low'),
     'html': m('My body’s exhausted. My brain is wide awake.', 'm big')},
    *[{'t0': 4.1 + 1.2 * i, 't1': 8.2, 'fi': 0.4, 'pos': P.get('b', 'top'), 'html': stack(WORRY, i)} for i in range(3)],
    {'t0': 8.7, 't1': 10.5, 'pos': P.get('c', 'top'), 'html': m('I didn’t want to scroll. I just wanted it to be quiet.')},
    {'t0': 10.6, 't1': 12.3, 'pos': P.get('c', 'top'), 'fo': 0.3, 'html': m('So I opened the WithGod app and just typed it out.')},
    # 어느 줄인지 알 수 있게 앱이 쓴 말 그대로 일부를 인용한다
    {'t0': 24.8, 't1': 27.9, 'pos': P.get('d', 'top'),
     'html': m('“Tonight, you do not have to solve everything…”<br><span class="dim">I read that three times.</span>')},
    {'t0': 28.1, 't1': 30.4, 'pos': P.get('d', 'top'), 'html': m('Nothing got fixed. <span class="dim">But it got quieter in here.</span>')},
    {'t0': 31.5, 't1': 36.2, 'pos': P.get('e', 'top'),
     'html': "<div class='v'>“You are my hiding place and my shield. I hope in your word.”</div><div class='r'>Psalm 119:114</div>"},
    {'t0': 36.6, 't1': DUR + 0.4, 'pos': P.get('e', 'top'), 'html': m('Still up too? You’re not the only one.', 'm big')},
    {'t0': 37.6, 't1': DUR + 0.4, 'raw': True,
     'html': f"<div class='hd' style='font-family:I;{CAM.get('hd', 'bottom:400px')}'>Mia · every Wednesday · @withgod.app</div>"},
]

spec = {'out': str(W / 'reel-silent.mp4'), 'dur': DUR, 'bg': '#0B0E1A', 'css': CSS, 'lofi': True,
        'snaps': [0.5, 7.0, 11.5, 13.0, 17.5, 22.0, 24.3, 26.5, 29.0, 33.0, 39.0], 'shots': shots,
        'texts': texts}
(W / 'spec.json').write_text(json.dumps(spec, ensure_ascii=False, indent=1))
cover = {'out': str(W / 'cover.mp4'), 'dur': 0.2, 'bg': '#0B0E1A', 'css': CSS, 'snaps': [0.0],
         'shots': [{'img': ART['a_ceiling'], 't0': 0, 't1': 0.2, 'cam': [at(0, 'a0')]}],
         'texts': [{'t0': 0, 't1': 1, 'fi': 0, 'raw': True, 'html': "<div class='stamp'>MIA · 3:07 A.M.</div>"},
                   {'t0': 0, 't1': 1, 'fi': 0, 'pos': P.get('a', 'low'),
                    'html': m('My body’s exhausted. My brain is wide awake.', 'm big')}]}
(W / 'cover-spec.json').write_text(json.dumps(cover, ensure_ascii=False, indent=1))
print('spec ok')
