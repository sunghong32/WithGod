"""성화 읽기 「렘브란트 〈탕자의 귀환〉 그림 이야기」 — 미술관 액자 + 내레이션 → narration.json · voice.wav · spec.json · cover-spec.json.

사용자 11/19(세 번째 안): "그림 이야기로 시작해서 그림이 70% 로 줄어 액자에 걸리고, 아래에 글이 뜨고, 그 설명을 내레이션이
같이 읽어 준다. 그림에 원·숫자 표시는 안 하고, 해당 설명이 나올 때 그림을 클로즈업." 목소리는 계정의 Mia(af_heart).

    python3 get_art.py <작업폴더> && python3 make_spec.py <작업폴더>
    # 문장이 바뀌면 TTS venv 로 narrate.py 를 다시 돌려 timeline.json(문장마다 시작·끝)을 만들고 그 시각에 자막·카메라를 맞춘다.

가상 화면(1080×1920): 그림 자리 HOLE = (162, 236) 756×987(화면 폭의 70%), 금색 액자 40px, 아래 자막 y 1300~.
카메라는 이 가상 화면 좌표. 디테일은 원본(3840×5011) 픽셀로 적고 close() 가 가상 좌표로 바꾼다.
자리(원본): 아버지 얼굴 (1129, 1829) · 아들 머리 (1043, 2557) · 가는 손 (885, 2980) · 굵은 손 (1255, 2955) ·
맨발 (510, 4540) · 닳은 신 (1110, 4590) · 큰아들 얼굴 (3040, 1000)·모은 두 손 (3010, 2150).
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REELS = HERE.parent.parent
TTS_PY = Path.home() / '.local/share/withgod-tts/venv/bin/python'
W = Path(sys.argv[1]).resolve()
IMG = str(W / 'art' / 'prodigal-3840.jpg')
SRC_W, SRC_H = 3840, 5011
HOLE = [162, 236, 756, round(756 * SRC_H / SRC_W)]
K = HOLE[2] / SRC_W  # 가상 px / 원본 px
FRAME = [540, 960, 1080]  # 액자 전체


def close(x, y, w, at=760):
    """원본 (x, y) 디테일을 화면 높이 at 에 두는 원본 폭 w 의 창 → 가상 화면 카메라 [cx, cy, w]."""
    cy = y + (960 - at) * w / 1080
    return [round(HOLE[0] + x * K, 2), round(HOLE[1] + cy * K, 2), round(w * K, 2)]


# (id, 자막, 읽을 말(None = 자막 그대로), 카메라, 뒤 쉼)
SEGS = [
    ('title', "This is <i>The Return of the Prodigal Son</i>,<br>one of Rembrandt’s last paintings.", None, FRAME, 0.45),
    ('story', "It comes from a story Jesus told.", None, [540, 950, 1040], 0.5),
    ('son1', "A son takes his inheritance early<br>and wastes all of it.", None, close(1060, 3050, 1500, 700), 0.3),
    ('son2', "He comes home with nothing,<br>hoping only to work as a servant.", None, close(1040, 2600, 1000, 720), 0.35),
    ('ran', "But his father runs to meet him.", None, close(1120, 2200, 1350, 700), 0.6),
    ('hands', "Look at the father’s hands.", None, close(1070, 2960, 1100), 0.25),
    ('broad', "One is broad and strong.", None, close(1290, 2955, 720), 0.2),
    ('slender', "The other is slender and gentle.", None, close(860, 2985, 720), 0.35),
    ('nouwen', "Henri Nouwen saw a father’s hand<br>and a mother’s hand.",
     "[Henri](/ɑnɹˈi/) [Nouwen](/nˈWən/) saw a father's hand, and a mother's hand.", close(1070, 2960, 1150), 0.6),
    ('feet', "Look at the son’s feet.<br>One is bare, its sandal slipped off.", None, close(800, 4560, 1250, 700), 0.25),
    ('worn', "The other sandal is worn through.", None, close(1110, 4590, 1000, 560), 0.35),
    ('robe', "His father calls for the best robe,<br>a ring, and sandals for his feet.", None, close(1100, 3000, 2300, 820), 0.6),
    ('bro1', "On the right, the older brother.<br>He wouldn’t come in.", None, close(3050, 1500, 1400), 0.25),
    ('bro2', "So the father went out to him, too.", None, FRAME, 0.7),
    ('verse', "<div class='v'>“…this, my son, was dead and is alive again.<br>He was lost and is found.”</div><div class='r'>Luke 15:24</div>",
     "This, my son, was dead, and is alive again. He was lost, and is found.", [540, 930, 1000], 0.7),
    ('end', "Feeling far from God?<br>In Jesus’ story, the father<br>is the one who runs.", None, FRAME, 2.6),
]
VOICE, SPEED, LEAD = 'af_heart', 0.95, 0.35


def plain(html):
    import re
    return re.sub(r'<[^>]+>', '', html.replace('<br>', ' ')).replace('’', "'").replace('“', '').replace('”', '').replace('…', '').split()


narr = {'voice': VOICE, 'speed': SPEED, 'lead': LEAD,
        'segments': [{'id': i, 'say': say or ' '.join(plain(text)), 'pause': p} for i, text, say, _, p in SEGS]}
blob = json.dumps(narr, ensure_ascii=False, indent=1)
(W / 'narration.json').write_text(blob)
stamp = hashlib.sha1(blob.encode()).hexdigest()
old = (W / 'narration.sha1').read_text() if (W / 'narration.sha1').exists() else ''
if not (W / 'timeline.json').exists() or old != stamp:  # 문장·목소리가 바뀌었을 때만 다시 녹음
    subprocess.run([str(TTS_PY), str(REELS / 'narrate.py'), str(W)], check=True)
    (W / 'narration.sha1').write_text(stamp)
tl = {s['id']: s for s in json.loads((W / 'timeline.json').read_text())['segments']}
END = json.loads((W / 'timeline.json').read_text())['end']
DUR = round(END, 2)

# 카메라: 0초 그림이 화면을 채운 채로 시작 → 2.3초에 액자 전체로 물러나며 벽에 걸린다.
# 그 뒤로는 문장이 시작되기 0.25초 전에 움직여 1초 만에 닿고, 다음 문장까지 아주 천천히 다가간다(4%).
cam = [[0.0, *close(1500, 2650, 2600, 960)], [2.3, *FRAME]]
starts = [tl[i]['t0'] for i, *_ in SEGS]
for n, (i, _, _, target, _) in enumerate(SEGS):
    t0 = starts[n]
    nxt = starts[n + 1] if n + 1 < len(SEGS) else DUR
    if n == 0:
        hold_from = 2.3
    else:
        mv0 = max(cam[-1][0] + 0.05, t0 - 0.25)
        cam.append([round(mv0, 3), *cam[-1][1:]])
        hold_from = mv0 + (1.1 if target[2] < 600 else 0.9)
        cam.append([round(hold_from, 3), *target])
    end_t = max(hold_from + 0.1, nxt - 0.3)
    drift = [target[0], target[1], round(target[2] * (0.96 if target[2] < 1000 else 0.985), 2)]
    cam.append([round(end_t, 3), *drift])

texts = [{'t0': 0.0, 't1': 2.6, 'fi': 0, 'fo': 0.4,
          'html': "<div class='hook'>The Return of<br>the Prodigal Son</div><div class='sub'>The story behind Rembrandt’s painting</div>"}]
for n, (i, text, _, _, _) in enumerate(SEGS):
    t0 = starts[n] - 0.05
    t1 = (starts[n + 1] - 0.05) if n + 1 < len(SEGS) else DUR + 0.4
    html = text if text.startswith('<div') else f"<p class='n'>{text}</p>"
    if i == 'end':
        html += "<div class='sub' style='margin-top:26px'>@withgod.app · find your verse, link in bio</div>"
    texts.append({'t0': round(t0, 3), 't1': round(t1, 3), 'pos': 'under', 'fi': 0.2, 'fo': 0.2, 'html': html})

# 벽: 미술관의 짙은 녹색 벽(그림의 붉은색·금색과 맞서지 않게) + 액자 위 따뜻한 조명
WALL = ("radial-gradient(ellipse 62% 30% at 50% 31%, rgba(255,220,160,.16), rgba(255,220,160,0) 72%), "
        "radial-gradient(ellipse 120% 78% at 50% 38%, #34423a 0%, #222c26 55%, #0f1411 100%)")
gallery = {'img': IMG, 'hole': HOLE, 'frame': 40, 'wall': WALL}
spec = {'out': str(W / 'reel-silent.mp4'), 'dur': DUR, 'bg': '#0e0b09', 'crf': 23, 'voice': 'voice.wav',
        'snaps': [0.0, 1.2, 2.4] + [round(tl[i]['t0'] + 1.2, 2) for i, *_ in SEGS],
        'shots': [{'gallery': gallery, 't0': 0.0, 't1': DUR, 'cam': cam}], 'texts': texts}
(W / 'spec.json').write_text(json.dumps(spec, ensure_ascii=False, indent=1))
cover = {'out': str(W / 'cover.mp4'), 'dur': 0.2, 'bg': '#0e0b09', 'snaps': [0.0],
         'shots': [{'gallery': gallery, 't0': 0, 't1': 0.2, 'cam': [[0, *FRAME]]}],
         'texts': [{'t0': 0, 't1': 1, 'fi': 0, 'pos': 'under',
                    'html': "<div class='h1'>The Return of<br>the Prodigal Son</div>"
                            "<div class='sub'>The story behind Rembrandt’s painting</div>"}]}
(W / 'cover-spec.json').write_text(json.dumps(cover, ensure_ascii=False, indent=1))
print('spec ok', DUR, 's')
