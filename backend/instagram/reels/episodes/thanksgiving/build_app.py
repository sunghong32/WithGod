"""Mia 2화 앱 장면 — 시뮬레이터 실제 녹화(take2-30.mp4)에서 타자 장면을 자연스러운 속도로 줄여 app.mp4 를 만든다.

    python3 build_app.py <작업폴더>      # 작업폴더/take2-30.mp4 → app.mp4 + app.json(구간표)

녹화(11/25, iPhone 17 Pro 시뮬레이터, 상태 막대 21:12, 2번째 녹화): 홈 → 입력창 탭 → 화면 키보드로 한 글자씩
"I'm dreading Thanksgiving with my family." 입력(자동 고침이 Im→I’m) → 보내기 → 실제 응답(욥기 31:34, 빌립보서 4:6,
고린도전서 2:3). 첫 녹화는 에스겔 21:17 이 섞여 쓰지 않았다(take1-job-ezekiel.mov).
이 녹화는 입력창 탭 직후 "M" 이 잘못 들어가 지운 구간(2.5–12초)이 있어서, 홈(키보드 없음)에서 지운 뒤의 빈 입력창
(키보드 올라옴)으로 8프레임 겹쳐 넘긴다. 그다음은 1화(cant-sleep/build_app.py)와 같이 글자가 바뀐 프레임만 이어
사람이 치는 속도(초당 약 6자)로 줄인다 — 화면은 꾸미지 않고 시간만 줄인다. 보내기 뒤는 녹화 그대로.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

W, H, FPS = 1206, 2622, 30
STEP, XFADE = 5, 8           # 글자마다 5프레임(0.17초), 홈 → 빈 입력창 겹침 8프레임
HOME = (0.3, 1.5)            # 입력 전 홈(가만히, 키보드 없음)
EMPTY = (12.3, 13.0)         # 잘못 친 M 을 지운 뒤 — 키보드가 올라온 빈 입력창
TYPING = (15.6, 69.6)        # 첫 글자 I ~ 마지막 마침표
SEND = 71.7                  # 보내기 직전부터 끝까지 그대로


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
    """입력창(키보드가 올라온 뒤 y 1300–1650)의 어두운 글자 모양이 바뀐 첫 프레임들. 파란 커서·회색 예측 글자는 빼고 본다."""
    out, prev = [], None
    for i, b in enumerate(frames(path)):
        t = i / FPS
        if not TYPING[0] <= t <= TYPING[1]:
            continue
        f = np.frombuffer(b, np.uint8).reshape(H, W, 3)
        sig = (f[1300:1650, 80:960].max(axis=2) < 130)[::2, ::2]
        if prev is None or (sig != prev).sum() > 6:
            out.append(i)
            prev = sig
    merged = []  # 0.25초 안에 이어진 변화(자동 고침·줄바꿈 애니메이션)는 마지막 것만
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
    home = list(range(int(HOME[0] * FPS), int(HOME[1] * FPS)))
    empty = list(range(int(EMPTY[0] * FPS), int(EMPTY[1] * FPS)))
    pick = home + empty
    xfade_at = len(home)  # 이 자리부터 XFADE 프레임 동안 홈 마지막 프레임과 섞는다
    for i in states:
        pick += list(range(i, i + STEP))
    pick += list(range(states[-1] + STEP, states[-1] + STEP + 12))  # 다 친 문장을 잠깐 본다
    send_at = len(pick) / FPS
    total = sum(1 for _ in frames(src))
    pick += list(range(int(SEND * FPS), total))
    want = {}
    for j, i in enumerate(pick):
        want.setdefault(i, []).append(j)
    buf = {}
    for i, b in enumerate(frames(src)):
        for j in want.get(i, []):
            buf[j] = b
    last_home = np.frombuffer(buf[xfade_at - 1], np.uint8).reshape(H, W, 3).astype(np.float32)
    ff = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
                           '-i', '-', '-c:v', 'libx264', '-crf', '14', '-preset', 'fast', '-pix_fmt', 'yuv420p',
                           str(w / 'app.mp4')], stdin=subprocess.PIPE)
    for j in range(len(pick)):
        b = buf.pop(j)
        k = j - xfade_at
        if 0 <= k < XFADE:
            a = (k + 1) / (XFADE + 1)
            f = np.frombuffer(b, np.uint8).reshape(H, W, 3).astype(np.float32)
            b = (last_home * (1 - a) + f * a).astype(np.uint8).tobytes()
        ff.stdin.write(b)
    ff.stdin.close(); ff.wait()
    info = {'states': len(states), 'typing_from': len(home + empty) / FPS, 'send_at': send_at,
            'src_offset': SEND - send_at, 'frames': len(pick)}
    (w / 'app.json').write_text(json.dumps(info, indent=1))
    print(info)


if __name__ == '__main__':
    main()
