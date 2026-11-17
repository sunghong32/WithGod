"""「I told a Bible app I couldn't sleep」 spec → spec.json, cover-spec.json.
사용: python3 make_spec.py <작업폴더>   (작업폴더에 picks.json·cams.json·art/·app30.mp4)

app30.mp4 = iPhone 17 Pro 시뮬레이터 녹화(1206×2622, 상태 막대 03:07 고정)를 30fps 로 바꾼 것. 홈에서 딥링크
`withgod://result?mood=It's 3am and I can't sleep. My mind won't stop racing.` 로 결과 화면을 연 실제 앱 응답이다
(11/17 운영 서버, 시편 119:114). 녹화 시점: 0–1.9 홈 · 1.9–2.3 넘어감 · 2.0–10.2 찾는 중 · 10.4–12.6 말씀 ·
13.6–24.5 풀이. 찾는 동안(3.4–10.2)은 잘라 낸다. 앱 화면 카메라는 전체 폭(1206) — 카드 양옆이 잘리지 않게.
"""
import json
import sys
from pathlib import Path

W = Path(sys.argv[1])
ART = json.loads((W / 'picks.json').read_text())
CAM = json.loads((W / 'cams.json').read_text())
APP = str(W / 'app30.mp4')
FPS = 30


def at(t, key, dw=0):
    x, y, w = CAM[key]
    return [t, x, y, w + dw]


TOP, BOTTOM = [603, 1072, 1206], [603, 1550, 1206]  # 앱 화면 위쪽 맞춤 / 아래쪽 맞춤


def app(t, pos):
    return [t] + pos


DUR = 36.6
shots = [
    # 새벽 3시: 휴대폰 불빛에 비친 얼굴 → 물러나 방 전체
    {'img': ART['a_awake'], 't0': 0.0, 't1': 7.0, 'cam': [at(0, 'face'), at(3.4, 'face', 40), at(6.4, 'room'), at(7.4, 'room', -20)]},
    # 앱: 홈 → 결과 화면(입력한 말이 말풍선으로) → 찾는 중
    {'video': APP, 'src_fps': FPS, 'start_frame': int(0.6 * FPS), 't0': 7.0, 't1': 9.8, 'fade': 0.6, 'cam': [app(7.0, TOP)]},
    # 말씀이 뜸(찾는 동안은 잘라 냄)
    {'video': APP, 'src_fps': FPS, 'start_frame': int(10.2 * FPS), 't0': 9.8, 't1': 13.2, 'fade': 0.3, 'cam': [app(9.8, TOP)]},
    # 풀이가 채워짐(1.25배) — 글이 내려가는 만큼 카메라도 아래로
    {'video': APP, 'src_fps': FPS, 'speed': 1.25, 'start_frame': int(13.6 * FPS), 't0': 13.2, 't1': 22.0, 'fade': 0.2,
     'cam': [app(13.2, TOP), app(15.4, TOP), app(18.0, BOTTOM), app(22.0, BOTTOM)]},
    # 금색 말씀 → 끝 멘트
    {'img': ART['b_end'], 't0': 22.0, 't1': DUR, 'fade': 1.0,
     'cam': [at(22.0, 'end_a'), at(28.0, 'end_a', -30), at(DUR, 'end_b')]},
]

texts = [
    {'t0': 0.0, 't1': 3.4, 'fi': 0, 'pos': CAM.get('pos_hook', 'top'), 'html': "<div class='h1'>I told a Bible app I couldn’t sleep.</div>"},
    {'t0': 3.6, 't1': 6.8, 'pos': CAM.get('pos_hook', 'top'), 'html': "<p class='t'>It was 3 a.m., and my mind wouldn’t stop racing.</p>"},
    {'t0': 7.2, 't1': 9.6, 'raw': True, 'fi': 0.3, 'fo': 0.3, 'html': "<div class='card low'>So I typed exactly that.</div>"},
    {'t0': 18.6, 't1': 21.8, 'raw': True, 'fi': 0.25, 'fo': 0.25,  # 반투명으로 겹쳐 보이는 시간을 줄인다
     # 말씀 카드(제목~장절)를 반쯤 가리면 지저분해서 상자를 키워 통째로 덮는다(아래 「Anxiety, Restlessness」부터 보임)
     'html': "<div class='card top' style='top:175px;left:24px;right:24px;min-height:490px;box-sizing:border-box;display:flex;"
             "flex-direction:column;justify-content:center'><div style='font:500 30px S;letter-spacing:.02em;opacity:.8;margin-bottom:14px'>"
             "One line stayed with me</div><div class='q'>“Tonight, you do not have to solve everything or silence "
             "every thought before morning.”</div></div>"},
    {'t0': 22.6, 't1': 27.8, 'pos': CAM.get('pos_end', 'low'),
     'html': "<div class='v'>“You are my hiding place and my shield. I hope in your word.”</div><div class='r'>Psalm 119:114</div>"},
    {'t0': 28.2, 't1': DUR + 0.4, 'pos': CAM.get('pos_end', 'low'),
     'html': "<div class='h1'>Awake tonight too? Tell it what’s keeping you up.</div>"},
    {'t0': 29.6, 't1': DUR + 0.4, 'raw': True, 'html': "<div class='hd' style='bottom:400px'>@withgod.app · find your verse, link in bio</div>"},
]

spec = {'out': str(W / 'reel-silent.mp4'), 'dur': DUR, 'bg': '#F6F6F8',
        'snaps': [1.0, 5.0, 8.6, 12.8, 16.0, 18.9, 20.2, 21.7, 25.0, 33.0], 'shots': shots, 'texts': texts}
(W / 'spec.json').write_text(json.dumps(spec, ensure_ascii=False, indent=1))
x, y, w = CAM['cover']
cover = {'out': str(W / 'cover.mp4'), 'dur': 0.2, 'bg': '#141018', 'snaps': [0.0],
         'shots': [{'img': ART['a_awake'], 't0': 0, 't1': 0.2, 'cam': [[0, x, y, w]]}],
         'texts': [{'t0': 0, 't1': 1, 'fi': 0, 'pos': CAM.get('pos_hook', 'top'),
                    'html': "<div class='h1'>I told a Bible app I couldn’t sleep.</div><div class='sub'>Here’s what it said</div>"}]}
(W / 'cover-spec.json').write_text(json.dumps(cover, ensure_ascii=False, indent=1))
print('spec ok')
