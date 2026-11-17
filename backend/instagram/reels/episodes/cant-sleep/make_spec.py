"""Mia 1화 「3:07 a.m.」 spec → spec.json, cover-spec.json (수요일 시리즈 Mia, 형식은 mia.py).
사용: python3 make_spec.py <작업폴더>   (작업폴더에 picks.json·cams.json·art/·app2.mp4 — app2 는 build_app.py 로)

이야기: 새벽 3시 7분, 몸은 지쳤는데 머리가 안 꺼진다(천장) → 출근·월세·답 못 한 문자(무릎을 안고) → 스크롤 말고
조용해지고 싶어서 WithGod 앱을 연다(휴대폰 불빛) → 실제 앱 화면: 입력창에 한 글자씩 "I can't sleep. My mind won't stop
racing." → 시편 4:4 → 시편 4:8 → 풀이 끝 줄 「Rest may come slowly, and that is alright …」에서 멈춰 다가감 → 그 줄을 세 번
읽음 · 해결된 건 없지만 조용해졌다(휴대폰을 엎어 둠) → 잠든 Mia 위로 금색 시편 4:8 → 보는 사람에게 돌려주는 한 줄.
광고처럼 보이지 않게: 기능 설명·떠 있는 휴대폰 카드·큰 스티커 없이, 자막은 Mia 의 속마음만. 사용자 피드백(11/17 2차):
"글이 휙휙 지나간다, WithGod 이름이 순식간에 지워진다" → 자막마다 3~4초 이상, 앱 화면에는 자막을 얹지 않는다.

app2.mp4 시각(초): 0–1.2 홈 · 1.2–1.9 키보드 올라옴 · 1.9–8.5 타자 · 8.7 보내기 · 9.0 결과 화면(찾는 중) ·
11.9–15.5 시편 4:4 · 27.9–31.5 시편 4:8 · 41.8–44.4 풀이 끝 줄 · 프레임 1333 = 「…keeping watch tonight.」 다 나온 마지막 장면.
"""
import json
import sys
from pathlib import Path

W = Path(sys.argv[1])
ART = json.loads((W / 'picks.json').read_text())
CAM = json.loads((W / 'cams.json').read_text())
APP = str(W / 'app2.mp4')
FPS = 30
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from mia import CSS  # noqa: E402


def at(t, key, dw=0):
    x, y, w = CAM[key]
    return [t, x, y, w + dw]


TOP, BOTTOM = [603, 1072, 1206], [603, 1550, 1206]  # 앱 화면 위쪽 맞춤 / 아래쪽 맞춤(전체 폭 — 카드 양옆이 안 잘리게)
LINE = [603, 1769, 960]  # 「Rest may come slowly, and that is alright, because …」(원본 y 1935–2107)로 다가감
FREEZE = 1333            # 그 줄이 다 나온 프레임(바로 뒤에 다음 말씀이 시작되며 화면이 올라간다)


def app(t, pos):
    return [t] + pos


DUR = 60.0
A0 = 18.8  # 앱 시작
shots = [
    {'img': ART['a_ceiling'], 't0': 0.0, 't1': 4.6, 'cam': [at(0, 'a0'), at(5.2, 'a1')]},
    {'img': ART['b_knees'], 't0': 4.6, 't1': 11.2, 'fade': 0.8, 'cam': [at(4.6, 'b0'), at(11.8, 'b1')]},
    {'img': ART['c_phone'], 't0': 11.2, 't1': A0, 'fade': 0.8, 'cam': [at(11.2, 'c0'), at(19.4, 'c1')]},
    # 홈 → 입력창을 누르면 키보드가 올라오고(아래로 내려 봄) 한 글자씩 → 보내면 결과 화면(다시 위로)
    {'video': APP, 'src_fps': FPS, 't0': A0, 't1': A0 + 9.6, 'fade': 0.6,
     'cam': [app(A0, TOP), app(A0 + 1.1, TOP), app(A0 + 1.9, BOTTOM), app(A0 + 8.6, BOTTOM), app(A0 + 9.4, TOP)]},
    {'video': APP, 'src_fps': FPS, 'start_frame': int(11.7 * FPS), 't0': A0 + 9.6, 't1': A0 + 13.4, 'fade': 0.3, 'cam': [app(0, TOP)]},
    {'video': APP, 'src_fps': FPS, 'start_frame': int(27.9 * FPS), 't0': A0 + 13.4, 't1': A0 + 17.4, 'fade': 0.35,
     'cam': [app(0, BOTTOM)]},
    {'video': APP, 'src_fps': FPS, 'start_frame': FREEZE - int(2.6 * FPS), 't0': A0 + 17.4, 't1': A0 + 20.0, 'fade': 0.35,
     'cam': [app(0, BOTTOM)]},
    # 그 줄이 다 나온 장면에 머물며 천천히 다가간다(같은 프레임)
    {'video': APP, 'src_fps': FPS, 'speed': 0, 'start_frame': FREEZE, 't0': A0 + 20.0, 't1': A0 + 22.6, 'fade': 0.1,
     'cam': [app(A0 + 20.0, BOTTOM), app(A0 + 22.6, LINE)]},
    {'img': ART['d_down'], 't0': A0 + 22.6, 't1': 49.0, 'fade': 0.9, 'cam': [at(A0 + 22.6, 'd0'), at(49.8, 'd1')]},
    {'img': ART['e_asleep'], 't0': 49.0, 't1': DUR, 'fade': 1.2, 'cam': [at(49.0, 'e0'), at(DUR, 'e1')]},
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
    {'t0': 0.0, 't1': 4.4, 'fi': 0, 'raw': True, 'html': "<div class='stamp'>3:07 A.M.</div>"},
    {'t0': 0.0, 't1': 4.4, 'fi': 0, 'pos': P.get('a', 'low'),
     'html': m('My body’s exhausted. My brain is wide awake.', 'm big')},
    *[{'t0': 5.1 + 1.6 * i, 't1': 11.0, 'fi': 0.5, 'pos': P.get('b', 'top'), 'html': stack(WORRY, i)} for i in range(3)],
    {'t0': 11.6, 't1': 14.8, 'pos': P.get('c', 'top'), 'html': m('I didn’t want to scroll. I just wanted it to be quiet.')},
    {'t0': 15.1, 't1': A0 - 0.1, 'pos': P.get('c', 'top'), 'fo': 0.4, 'html': m('So I opened the WithGod app and just typed it out.')},
    # 어느 줄인지 알 수 있게 앱이 쓴 말 그대로 일부를 인용한다
    {'t0': 41.9, 't1': 45.9, 'pos': P.get('d', 'top'),
     'html': m('“Rest may come slowly, and that is alright…”<br><span class="dim">I read that three times.</span>')},
    {'t0': 46.2, 't1': 48.8, 'pos': P.get('d', 'top'), 'html': m('Nothing got fixed. <span class="dim">But it got quieter in here.</span>')},
    {'t0': 49.6, 't1': 55.4, 'pos': P.get('e', 'top'),
     'html': "<div class='v'>“In peace I will both lay myself down and sleep, for you alone, LORD, make me live in safety.”</div>"
             "<div class='r'>Psalm 4:8</div>"},
    {'t0': 55.8, 't1': DUR + 0.4, 'pos': P.get('e', 'top'), 'html': m('Still up too? You’re not the only one.', 'm big')},
    {'t0': 56.6, 't1': DUR + 0.4, 'raw': True,
     'html': f"<div class='hd' style='font-family:I;{CAM.get('hd', 'bottom:400px')}'>Mia · every Wednesday · @withgod.app</div>"},
]

spec = {'out': str(W / 'reel-silent.mp4'), 'dur': DUR, 'bg': '#0B0E1A', 'css': CSS, 'lofi': True,
        'snaps': [0.5, 9.0, 13.0, 17.0, 19.5, 22.5, 25.0, 30.5, 35.0, 37.5, 41.2, 44.0, 47.5, 52.0, 58.0], 'shots': shots,
        'texts': texts}
(W / 'spec.json').write_text(json.dumps(spec, ensure_ascii=False, indent=1))
cover = {'out': str(W / 'cover.mp4'), 'dur': 0.2, 'bg': '#0B0E1A', 'css': CSS, 'snaps': [0.0],
         'shots': [{'img': ART['a_ceiling'], 't0': 0, 't1': 0.2, 'cam': [at(0, 'a0')]}],
         'texts': [{'t0': 0, 't1': 1, 'fi': 0, 'raw': True, 'html': "<div class='stamp'>MIA · 3:07 A.M.</div>"},
                   {'t0': 0, 't1': 1, 'fi': 0, 'pos': P.get('a', 'low'),
                    'html': m('My body’s exhausted. My brain is wide awake.', 'm big')}]}
(W / 'cover-spec.json').write_text(json.dumps(cover, ensure_ascii=False, indent=1))
print('spec ok')
