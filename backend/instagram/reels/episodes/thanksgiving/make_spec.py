"""Mia 2화 「Thanksgiving eve」 spec → spec.json, cover-spec.json (수요일 시리즈 Mia, 형식은 mia.py).
사용: python3 make_spec.py <작업폴더>   (작업폴더에 picks.json·cams.json·art/·app.mp4 — app 은 build_app.py 로)

이야기: 추수감사절 전날 밤 부모님 집으로 가는 버스(9:12 P.M.) → 뻔한 질문들 → 괜찮은 척하기 싫어 WithGod 앱에 적음 →
실제 앱 화면(입력 → 욥기 31:34 → 풀이 끝 「…you do not walk into that room alone…」 + 빌립보서 4:6) → 그 말을 듣고
하나님께 다 말함(눈 감은 Mia) → 다음 날 저녁 현관 앞 · 금색 빌 4:6 → 보는 사람에게 한 줄.

app.mp4 시각(초) = 녹화 시각 − 62.9: 0–1.4 홈 · 1.4–1.7 겹쳐 빈 입력창(키보드) · 1.9–8.6 타자 · 8.8 보내기 · 9.1 결과 화면 ·
15.1–19.8 욥기 31:34 가 흘러나옴(19.8 = 녹화 82.7, 장절까지 나오고 풀이 첫 글자 "Jo" 만 — 앱 풀이가 이 구절을 '욥의 고백'으로
잘못 읽어서 여기서 끊는다) · 43.1 멈출 장면(녹화 106.0 — 풀이 윗부분 "Job's…" 는 이미 화면 밖, 인용할 줄이 화면 높이 40% 쯤).
"""
import json
import sys
from pathlib import Path

W = Path(sys.argv[1])
ART = json.loads((W / 'picks.json').read_text())
CAM = json.loads((W / 'cams.json').read_text())
APP = str(W / 'app.mp4')
FPS = 30
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from mia import CSS  # noqa: E402


def at(t, key, dw=0):
    x, y, w = CAM[key]
    return [t, x, y, w + dw]


TOP, BOTTOM = [603, 1072, 1206], [603, 1550, 1206]  # 앱 화면 위쪽 / 아래쪽 맞춤(전체 폭)
LINE = [603, 1000, 1000]  # 멈춘 장면에서 「…you do not walk into that room alone…」(원본 y 783–915) + 빌 4:6 쪽으로 1.2배


def app(t, pos):
    return [t] + pos


DUR = 64.5
A0 = 19.4  # 앱 시작
shots = [
    {'img': ART['a_bus'], 't0': 0.0, 't1': 4.7, 'cam': [at(0, 'a0'), at(1.3, 'a1'), at(5.2, 'a2')]},
    {'img': ART['b_reflection'], 't0': 4.7, 't1': 11.2, 'fade': 0.5, 'cam': [at(4.7, 'b0'), at(11.6, 'b1')]},
    {'img': ART['c_phone'], 't0': 11.2, 't1': A0, 'fade': 0.8, 'cam': [at(11.2, 'c0'), at(A0 + 0.6, 'c1')]},
    # 홈 → (겹쳐) 빈 입력창 · 키보드 → 한 글자씩 → 보내면 결과 화면
    {'video': APP, 'src_fps': FPS, 't0': A0, 't1': A0 + 10.1, 'fade': 0.6,
     'cam': [app(A0, TOP), app(A0 + 1.2, TOP), app(A0 + 1.9, BOTTOM), app(A0 + 8.7, BOTTOM), app(A0 + 9.4, TOP)]},
    # 욥기 31:34 가 흘러나와 장절까지 — 풀이가 나오기 전에 멈춰 잠깐 머묾
    {'video': APP, 'src_fps': FPS, 'start_frame': int(15.1 * FPS), 't0': A0 + 10.1, 't1': A0 + 14.8, 'fade': 0.3,
     'cam': [app(0, TOP)]},
    {'video': APP, 'src_fps': FPS, 'speed': 0, 'start_frame': int(19.8 * FPS), 't0': A0 + 14.8, 't1': A0 + 16.0, 'fade': 0.05,
     'cam': [app(0, TOP)]},
    # 풀이 끝 줄과 빌립보서 4:6 이 함께 보이는 장면에 멈춰 그 줄로 다가감
    {'video': APP, 'src_fps': FPS, 'speed': 0, 'start_frame': int(43.1 * FPS), 't0': A0 + 16.0, 't1': A0 + 20.0, 'fade': 0.35,
     'cam': [app(A0 + 16.0, TOP), app(A0 + 20.0, LINE)]},
    {'img': ART['d_calm'], 't0': A0 + 20.0, 't1': 49.8, 'fade': 0.9, 'cam': [at(A0 + 20.0, 'd0'), at(50.4, 'd1')]},
    {'img': ART['e_porch'], 't0': 49.8, 't1': DUR, 'fade': 1.2, 'cam': [at(49.8, 'e0'), at(DUR, 'e1')]},
]


def m(text, cls='m'):
    return f"<p class='{cls}'>{text}</p>"


def stack(lines, show, cls='m'):
    """여러 줄을 한 줄씩 나타나게 — 모든 줄을 같은 자리에 두고 show 번째 줄만 보이게 한 층을 따로 찍는다."""
    return ''.join(f"<p class='{cls}' style='visibility:{'visible' if i == show else 'hidden'}'>{x}</p>"
                   for i, x in enumerate(lines))


P = CAM.get('pos', {})
QUESTIONS = ['“So… still at that job?”', '“Seeing anyone yet?”', '“Your cousin just bought a house!”']
texts = [
    {'t0': 0.0, 't1': 4.75, 'fi': 0, 'raw': True, 'html': "<div class='stamp'>9:12 P.M.</div>"},
    {'t0': 0.0, 't1': 4.75, 'fi': 0, 'pos': P.get('a', 'low'),
     'html': m('Thanksgiving<br>is tomorrow.<br>I already know<br>every question.', 'm hook')},
    *[{'t0': 4.7 + 1.6 * i, 't1': 11.0, 'fi': 0.4, 'pos': P.get('b', 'top'), 'html': stack(QUESTIONS, i)} for i in range(3)],
    {'t0': 11.5, 't1': 14.7, 'pos': P.get('c', 'top'), 'html': m('Tomorrow I’ll say<br>“I’m good” all day.')},
    {'t0': 14.9, 't1': A0 - 0.1, 'pos': P.get('c', 'top'), 'fo': 0.4,
     'html': m('Tonight I wanted to say<br>what’s really true.<br>So I typed it into<br>the WithGod app.')},
    {'t0': A0 + 20.5, 't1': A0 + 25.2, 'pos': P.get('d', 'top'),
     'html': m('“…you do not walk<br>into that room alone…”<br><span class="dim">I needed to hear that tonight.</span>')},
    {'t0': A0 + 25.5, 't1': 49.6, 'pos': P.get('d', 'top'),
     'html': m('So I told God all of it.<br><span class="dim">The job. The cousin.<br>Every question.</span>')},
    {'t0': 50.0, 't1': 56.0, 'fi': 0.8, 'raw': True, 'html': "<div class='stamp'>THURSDAY · 5:40 P.M.</div>"},
    {'t0': 50.4, 't1': 56.6, 'pos': P.get('e', 'top'),
     'html': "<div class='v'>“In nothing be anxious, but in everything, by prayer and petition with thanksgiving, "
             "let your requests be made known to God.”</div><div class='r'>Philippians 4:6</div>"},
    {'t0': 56.9, 't1': DUR + 0.4, 'pos': P.get('e', 'top'),
     'html': m('Dreading this<br>week’s dinner?<br>Tell Him first.<br>You won’t walk in alone.', 'm big')},
    {'t0': 57.6, 't1': DUR + 0.4, 'raw': True,
     'html': f"<div class='hd' style='font-family:I;{CAM.get('hd', 'bottom:400px')}'>Mia · every Wednesday · @withgod.app</div>"},
]

spec = {'out': str(W / 'reel-silent.mp4'), 'dur': DUR, 'bg': '#0B0E1A', 'css': CSS, 'lofi': True,
        'snaps': [0.5, 2.3, 6.0, 9.5, 13.0, 17.0, 20.0, 23.5, 27.0, 31.5, 34.0, 36.5, 38.9, 42.0, 47.0, 53.0, 60.0],
        'shots': shots, 'texts': texts}
(W / 'spec.json').write_text(json.dumps(spec, ensure_ascii=False, indent=1))
cover = {'out': str(W / 'cover.mp4'), 'dur': 0.2, 'bg': '#0B0E1A', 'css': CSS, 'snaps': [0.0],
         'shots': [{'img': ART['a_bus'], 't0': 0, 't1': 0.2, 'cam': [at(0, 'a0')]}],
         'texts': [{'t0': 0, 't1': 1, 'fi': 0, 'raw': True, 'html': "<div class='stamp'>MIA · THANKSGIVING EVE</div>"},
                   {'t0': 0, 't1': 1, 'fi': 0, 'pos': P.get('a', 'low'),
                    'html': m('Thanksgiving<br>is tomorrow.<br>I already know<br>every question.', 'm big')}]}
(W / 'cover-spec.json').write_text(json.dumps(cover, ensure_ascii=False, indent=1))
print('spec ok')
