"""성화 읽기 「렘브란트 〈탕자의 귀환〉 그림 이야기」 — 미술관 액자 + 내레이션 → narration.json · voice.wav · spec.json · cover-spec.json.

사용자 11/19(세 번째 안): "그림 이야기로 시작해서 그림이 70% 로 줄어 액자에 걸리고, 아래에 글이 뜨고, 그 설명을 내레이션이
같이 읽어 준다. 그림에 원·숫자 표시는 안 하고, 해당 설명이 나올 때 그림을 클로즈업." 목소리는 계정의 Mia(af_heart).
사용자 11/20(네 번째 안): "말하고자 하는 바가 애매하다. 손이 다른 건 너무 다른 얘기 같다 — 어머니·아버지의 손을 성경·하나님과
연관지어야." → 메시지 하나 「돌아오면 하나님은 이렇게 안아 주신다」로 묶었다. 디테일마다 그 메시지의 증거가 되게:
젊은 렘브란트가 자신을 탕자로 그린 1635년 그림 → 30년의 상실 → 이 그림 → 발(얼마나 낮아져 돌아왔나) → 종이 되려던 아들을
말도 꺼내기 전에 안는 아버지 → 두 손(붙잡는 손·위로하는 손, 나우웬) → 이사야 66:13(어머니처럼 위로하시는 하나님)
→ 눅 15:20(아직 먼데 보고 달려감) → "하나님은 아직 길을 바라보고 계신다". 큰아들은 메시지가 갈라져 캡션으로만 뺐다.

    python3 get_art.py <작업폴더> && python3 make_spec.py <작업폴더>
    # 문장이 바뀌면 TTS venv 로 narrate.py 를 다시 돌려 timeline.json(문장마다 시작·끝)을 만들고 그 시각에 자막·카메라를 맞춘다.

가상 화면(1080×1920): 그림 자리(화면 폭의 70%, 756px) + 금색 액자 40px, 아래 자막 y 1300~.
장면 A = 술집의 탕자(1635, 3020×3827), 장면 B = 탕자의 귀환(1668, 3840×5011). 같은 벽·같은 자리 액자라 그림만 바뀌어 보인다.
카메라는 가상 화면 좌표. 디테일은 원본 픽셀로 적고 close() 가 가상 좌표로 바꾼다.
자리(B 원본): 아버지 얼굴 (1129, 1829) · 아들 머리 (1043, 2557) · 가는 손 (885, 2980) · 굵은 손 (1255, 2955) ·
맨발 (510, 4540) · 닳은 신 (1110, 4590). (A 원본): 렘브란트 얼굴 (1900, 1700) · 사스키아 얼굴 (1200, 1100) · 술잔 (1650, 1000).
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


def hole(src_w, src_h, top=236, center_h=987):
    """폭 756 의 그림 자리. 높이가 다른 그림도 가운데가 같은 자리에 오게."""
    h = round(756 * src_h / src_w)
    return [162, round(top + (center_h - h) / 2), 756, h]


A = {'img': str(W / 'art' / 'tavern-3020.jpg'), 'src_w': 3020, 'hole': hole(3020, 3827)}
B = {'img': str(W / 'art' / 'prodigal-3840.jpg'), 'src_w': 3840, 'hole': hole(3840, 5011)}
FRAME = [540, 960, 1080]  # 액자 전체


def close(p, x, y, w, at=760):
    """그림 p 의 원본 (x, y) 디테일을 화면 높이 at 에 두는 원본 폭 w 의 창 → 가상 화면 카메라 [cx, cy, w]."""
    hx, hy, hw, _ = p['hole']
    k = hw / p['src_w']
    cy = y + (960 - at) * w / 1080
    return [round(hx + x * k, 2), round(hy + cy * k, 2), round(w * k, 2)]


V = "<div class='v'>{}</div><div class='r'>{}</div>"
# (id, 장면, 자막, 읽을 말(None = 자막 그대로), 카메라, 뒤 쉼)
SEGS = [
    ('young', A, "Young Rembrandt painted himself<br>as the prodigal son,<br>partying in a tavern.", None, FRAME, 0.35),
    ('later', A, "Thirty years later, he had lost his wife,<br>four children,<br>and everything he owned.", None,
     close(A, 1550, 1450, 1400), 0.5),
    ('this', B, "Near the end of his life,<br>he painted this.", None, FRAME, 0.55),
    ('story', B, "In Jesus’ story, a son wastes everything<br>and comes home with nothing.", None,
     close(B, 1060, 3050, 1500, 700), 0.3),
    ('feet', B, "One sandal is gone.<br>The other is worn through.", None, close(B, 810, 4570, 1400, 640), 0.35),
    ('servant', B, "He only hoped to be taken back<br>as a servant.", None, close(B, 1040, 2600, 1000, 720), 0.3),
    ('embrace', B, "But before he could ask,<br>his father held him.", None, close(B, 1120, 2200, 1350, 700), 0.6),
    ('hands', B, "Look at the father’s hands.", None, close(B, 1070, 2960, 1100), 0.25),
    ('broad', B, "One is broad and strong.<br>It holds.", None, close(B, 1290, 2955, 720), 0.25),
    ('slender', B, "The other is slender and gentle.<br>It comforts.", None, close(B, 860, 2985, 720), 0.35),
    ('nouwen', B, "Henri Nouwen saw a father’s hand<br>and a mother’s hand.",
     "[Henri](/ɑnɹˈi/) [Nouwen](/nˈWən/) saw a father's hand, and a mother's hand.", close(B, 1070, 2960, 1150), 0.45),
    ('bible', B, "The Bible speaks of God the same way.", None, close(B, 1100, 2450, 1900, 760), 0.3),
    ('isaiah', B, V.format("“As one whom his mother comforts,<br>so I will comfort you.”", "Isaiah 66:13"),
     "As one whom his mother comforts, so I will comfort you.", close(B, 1100, 2450, 1900, 760), 0.6),
    ('hold', B, "Strong enough not to let go.<br>Gentle enough not to hurt.", None, close(B, 1070, 2960, 1250), 0.7),
    ('verse', B, V.format("“While he was still far off,<br>his father saw him… and ran.”", "Luke 15:20"),
     "While he was still far off, his father saw him, and ran.", [540, 930, 1000], 0.7),
    ('end', B, "Feel too far from God?<br>He’s still watching the road for you.", None, FRAME, 2.6),
]
VOICE, SPEED, LEAD = 'af_heart', 0.95, 0.35


def plain(html):
    import re
    return re.sub(r'<[^>]+>', '', html.replace('<br>', ' ')).replace('’', "'").replace('“', '').replace('”', '').replace('…', '').split()


narr = {'voice': VOICE, 'speed': SPEED, 'lead': LEAD,
        'segments': [{'id': i, 'say': say or ' '.join(plain(text)), 'pause': p} for i, _, text, say, _, p in SEGS]}
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
starts = [tl[i]['t0'] for i, *_ in SEGS]
CUT = round(tl['this']['t0'] - 0.45, 3)  # 장면 A → B(같은 액자 안에서 그림이 겹쳐 바뀜, 0.8초)


def track(first, segs, nxt_after):
    """카메라: 문장이 시작되기 0.25초 전에 움직여 0.9~1.1초 만에 닿고, 다음 문장까지 아주 천천히 다가간다."""
    cam = list(first)
    for n, (i, _, _, _, target, _) in enumerate(segs):
        t0 = tl[i]['t0']
        nxt = tl[segs[n + 1][0]]['t0'] if n + 1 < len(segs) else nxt_after
        same = n > 0 and segs[n - 1][4] == target  # 앞 문장과 같은 자리면 멈추지 않고 계속 천천히 다가간다
        if cam[-1][1:] == target or same:
            hold_from = cam[-1][0]
            target = cam[-1][1:]
        else:
            mv0 = max(cam[-1][0] + 0.05, t0 - 0.25)
            cam.append([round(mv0, 3), *cam[-1][1:]])
            hold_from = mv0 + (1.1 if target[2] < 600 else 0.9)
            cam.append([round(hold_from, 3), *target])
        end_t = max(hold_from + 0.1, nxt - 0.3)
        drift = [target[0], target[1], round(target[2] * (0.96 if target[2] < 1000 else 0.985), 2)]
        cam.append([round(end_t, 3), *drift])
    return cam


# 장면 A: 0초 젊은 렘브란트와 술잔이 화면을 채운 채 시작 → 2.3초에 액자 전체로 물러나며 벽에 걸린다 → '30년 뒤'에 두 얼굴로 다가감.
seg_a = [s for s in SEGS if s[1] is A]
seg_b = [s for s in SEGS if s[1] is B]
cam_a = track([[0.0, *close(A, 1750, 1750, 1900, 960)], [2.3, *FRAME]], seg_a, CUT + 0.8)
# 장면 B: 젊은 렘브란트의 얼굴이 늙은 아버지의 얼굴로 겹쳐 바뀌고, '이 그림을 그렸다'에서 액자 전체로 물러난다.
T_THIS = tl['this']['t0']
F0 = close(B, 1129, 2100, 1700, 640)
cam_b = track([[CUT, *F0], [round(T_THIS + 0.5, 3), *F0[:2], round(F0[2] * 0.97, 2)], [round(T_THIS + 2.0, 3), *FRAME]],
              seg_b, DUR)

texts = [{'t0': 0.0, 't1': 2.6, 'fi': 0, 'fo': 0.4,
          'html': "<div class='hook'>Rembrandt painted<br>himself as<br>the prodigal son.</div>"}]
for n, (i, _, text, _, _, _) in enumerate(SEGS):
    t0 = starts[n] - 0.05
    t1 = (starts[n + 1] - 0.05) if n + 1 < len(SEGS) else DUR + 0.4
    html = text if text.startswith('<div') else f"<p class='n'>{text}</p>"
    if i == 'end':
        html += "<div class='sub' style='margin-top:26px'>@withgod.app · find your verse, link in bio</div>"
    texts.append({'t0': round(t0, 3), 't1': round(t1, 3), 'pos': 'under', 'fi': 0.2, 'fo': 0.2, 'html': html})

# 벽: 미술관의 짙은 녹색 벽(그림의 붉은색·금색과 맞서지 않게) + 액자 위 따뜻한 조명
WALL = ("radial-gradient(ellipse 62% 30% at 50% 31%, rgba(255,220,160,.16), rgba(255,220,160,0) 72%), "
        "radial-gradient(ellipse 120% 78% at 50% 38%, #34423a 0%, #222c26 55%, #0f1411 100%)")


def gallery(p):
    return {'img': p['img'], 'hole': p['hole'], 'frame': 40, 'wall': WALL}


spec = {'out': str(W / 'reel-silent.mp4'), 'dur': DUR, 'bg': '#0e0b09', 'crf': 23, 'voice': 'voice.wav',
        'snaps': [0.0, 1.2, 2.4, round(CUT + 0.4, 2)] + [round(tl[i]['t0'] + 1.2, 2) for i, *_ in SEGS],
        'shots': [{'gallery': gallery(A), 't0': 0.0, 't1': CUT, 'cam': cam_a},
                  {'gallery': gallery(B), 't0': CUT, 't1': DUR, 'cam': cam_b, 'fade': 0.8}],
        'texts': texts}
(W / 'spec.json').write_text(json.dumps(spec, ensure_ascii=False, indent=1))
cover = {'out': str(W / 'cover.mp4'), 'dur': 0.2, 'bg': '#0e0b09', 'snaps': [0.0],
         'shots': [{'gallery': gallery(B), 't0': 0, 't1': 0.2, 'cam': [[0, *FRAME]]}],
         'texts': [{'t0': 0, 't1': 1, 'fi': 0, 'pos': 'under',
                    'html': "<div class='h1'>The Return of<br>the Prodigal Son</div>"
                            "<div class='sub'>The story behind Rembrandt’s painting</div>"}]}
(W / 'cover-spec.json').write_text(json.dumps(cover, ensure_ascii=False, indent=1))
print('spec ok', DUR, 's · cut', CUT)
