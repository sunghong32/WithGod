"""Mia 1화 앱 장면 — 시뮬레이터 실제 녹화(take2-30.mp4)에서 타자 장면을 자연스러운 속도로 줄여 app2.mp4 를 만든다.

    python3 build_app.py <작업폴더>      # 작업폴더/take2-30.mp4 → app2.mp4 + app2.json(구간표)

녹화(11/17, iPhone 17 Pro 시뮬레이터, 상태 막대 03:07): 홈 → 입력창 탭 → 화면 키보드로 한 글자씩
"I can't sleep. My mind won't stop racing." 입력(iOS 자동 고침이 cant→can't, wont→won't) → 보내기 → 실제 응답
(시편 4:4, 4:8, 5:1). 시뮬레이터는 키 하나 누르는 데 1~2초가 걸려서 타자 구간이 80초다 — 글자가 바뀐 순간마다
진짜 프레임을 STEP 장씩만 이어 사람이 치는 속도(초당 약 6자)로 만든다(그림을 꾸미지 않고 시간만 줄인다).
보내기 뒤로는 녹화 그대로 이어 붙인다. 입력창이 막혀 있던 건 알림 안내를 아직 안 본 상태에서 업데이트 안내와
겹쳤기 때문 — 녹화 전에 앱 저장소에 withgod.notifications.primingSeen=true 를 넣었다.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

W, H, FPS = 1206, 2622, 30
STEP, PAUSE = 5, 14          # 글자마다 5프레임(0.17초), 문장 사이 14프레임
HOME = (3.4, 4.6)            # 입력 전 홈(가만히)
KEYBOARD = (8.2, 8.9)        # 입력창을 누르고 키보드가 올라옴
TYPING = (16.0, 100.5)       # 첫 글자 ~ 마지막 마침표
SEND = 102.5                 # 보내기 직전부터 끝까지 그대로


def frames(path):
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', str(path), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         stdout=subprocess.PIPE)
    n = W * H * 3
    while True:
        b = p.stdout.read(n)
        if len(b) < n:
            return
        yield b


def typing_states(path):
    """입력창(키보드가 올라온 뒤 y 1340–1600)의 어두운 글자 모양이 바뀐 첫 프레임들. 깜박이는 파란 커서는 빼고 본다."""
    out, prev = [], None
    for i, b in enumerate(frames(path)):
        t = i / FPS
        if not TYPING[0] <= t <= TYPING[1]:
            continue
        f = np.frombuffer(b, np.uint8).reshape(H, W, 3)
        sig = (f[1340:1600, 80:960].max(axis=2) < 130)[::2, ::2]
        if prev is None or (sig != prev).sum() > 25:
            out.append(i)
            prev = sig
    merged = []  # 0.25초 안에 이어진 변화(자동 고침 애니메이션, 'Inline Predictions' 안내)는 마지막 것만
    for i in out:
        if merged and i - merged[-1] < 0.25 * FPS:
            merged[-1] = i
        else:
            merged.append(i)
    return merged


def main():
    w = Path(sys.argv[1])
    src = w / 'take2-30.mp4'
    states = typing_states(src)
    pick = list(range(int(HOME[0] * FPS), int(HOME[1] * FPS))) + list(range(int(KEYBOARD[0] * FPS), int(KEYBOARD[1] * FPS)))
    for k, i in enumerate(states):
        nxt = states[k + 1] if k + 1 < len(states) else None
        hold = PAUSE if nxt is not None and nxt - i > 10 * FPS else STEP
        pick += list(range(i, i + hold))
    pick += list(range(states[-1] + STEP, states[-1] + STEP + 12))  # 다 친 문장을 잠깐 본다
    send_at = len(pick) / FPS
    total = sum(1 for _ in frames(src))
    pick += list(range(int(SEND * FPS), total))
    want = {}
    for j, i in enumerate(pick):
        want.setdefault(i, []).append(j)
    ff = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
                           '-i', '-', '-c:v', 'libx264', '-crf', '14', '-preset', 'fast', '-pix_fmt', 'yuv420p',
                           str(w / 'app2.mp4')], stdin=subprocess.PIPE)
    for i, b in enumerate(frames(src)):  # pick 은 오름차순이라 한 번 읽으며 쓴다
        for _ in want.get(i, []):
            ff.stdin.write(b)
    ff.stdin.close(); ff.wait()
    info = {'states': len(states), 'typing_from': (len(range(int(HOME[0] * FPS), int(HOME[1] * FPS))) +
                                                   len(range(int(KEYBOARD[0] * FPS), int(KEYBOARD[1] * FPS)))) / FPS,
            'send_at': send_at, 'src_offset': SEND - send_at, 'frames': len(pick)}
    (w / 'app2.json').write_text(json.dumps(info, indent=1))
    print(info)


if __name__ == '__main__':
    main()
