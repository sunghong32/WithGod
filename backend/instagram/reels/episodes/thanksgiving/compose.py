"""Mia 2화 「Thanksgiving eve」 음악 — 밤 버스 로파이(72 BPM, 한 마디 3.333초, 64.5초). 1화(A단조·시계 소리)와 같은 악기
(일렉 피아노 gm4·베이스 gm33·드럼·비브라폰 gm11·패드 gm89)지만 조와 진행을 바꿔 다른 밤으로 들리게 한다.

    python3 compose.py events.json   → finish.py 가 swift music.swift 로 렌더(spec 의 "lofi": true 로 고음 깎기·잡음)

장면(초): A 0–19.4 버스 창가의 걱정(D단조 Dm9–B♭maj7–Gm9–A7sus, 드럼 없이 지나가는 가로등처럼 가끔 높은 종) ·
B 19.4–39.4 앱(타자 → 욥기 → 빌립보서, B♭maj7–Am7–Gm7–Fmaj7 위로 비트가 조용히) · C 39.4–49.8 하나님께 다 말함(드럼이
빠지고 Gm9 → C9sus 길게) · D 49.8–64.5 현관 · 금색 빌 4:6 · 끝 멘트(Fmaj9 → B♭maj9 → C13sus → Fmaj9 로 길게, 첫 장면의
내려가는 한숨 선율 라–솔–파가 끝에서 올라가는 파–솔–라–도로 바뀐다).
"""
import json
import sys

BAR, BEAT = 3.333, 0.8333
SW = 0.07
B0, C0, D0, END = 19.4, 39.4, 49.8, 64.5
ev = []


def n(t, d, note, vel, inst='gm4'):
    ev.append({'t': round(t, 3), 'dur': round(d, 3), 'note': note, 'vel': vel, 'inst': inst})


def chord(t, d, notes, vel, inst='gm4', roll=0.025):
    for i, x in enumerate(notes):
        n(t + i * roll, d, x, vel, inst)


def beat(t0, bars, kick=56, rim=42, hat=28):
    for b in range(bars):
        s = t0 + b * BAR
        if s >= C0 - 0.1:
            break
        n(s, 0.2, 36, kick, 'drums'); n(s + 2.5 * BEAT, 0.2, 36, kick - 10, 'drums')
        n(s + BEAT, 0.2, 37, rim, 'drums'); n(s + 3 * BEAT, 0.2, 37, rim, 'drums')
        for k in range(8):
            n(s + k * BEAT / 2 + (SW if k % 2 else 0), 0.1, 42, hat - (8 if k % 2 else 0), 'drums')


# A 버스 창가 (0–19.4): Dm9 – B♭maj7 – Gm9 – A7sus 를 두 번(마지막 A7sus 는 앱을 여는 줄에서 풀리지 않고 걸림)
A = [(38, [57, 60, 64, 65]), (34, [57, 62, 65, 69]), (31, [58, 62, 65, 69]), (33, [57, 62, 64, 67])]
for k in range(6):
    s = k * BAR
    bass, ch = A[k % 4]
    n(s, BAR + 0.1, bass, 40); chord(s + 0.05, BAR - 0.1, ch, 33)
    n(s, BAR + 0.2, bass + 12, 24, 'gm89')
    n(s + 1.9, 0.5, 86 if k % 2 else 84, 16, 'gm11')  # 지나가는 가로등 같은 높은 종
for t, d, x in [(0.9, 0.7, 69), (1.6, 0.6, 67), (2.2, 1.0, 65), (4.3, 0.7, 69), (5.0, 0.6, 67), (5.6, 1.2, 65),
                (7.6, 0.7, 70), (8.3, 0.6, 69), (8.9, 1.2, 67), (11.0, 0.7, 69), (11.7, 1.4, 67),
                (14.2, 0.7, 69), (14.9, 0.6, 67), (15.5, 1.2, 65), (17.6, 1.6, 67)]:
    n(t, d, x, 30)
n(B0 - 0.5, 0.6, 33, 30, 'gm33')

# B 앱 (19.4–40.9): B♭maj7 – Am7 – Gm7 – Fmaj7 위로 비트가 조용히 들어온다
CH = [(34, [57, 62, 65, 69]), (33, [55, 60, 64, 67]), (31, [53, 58, 62, 65]), (29, [57, 60, 64, 67])]
bars_b = int((C0 - B0) / BAR) + 1
for k in range(bars_b):
    s = B0 + k * BAR
    if s >= C0 - 0.1:
        break
    bass, ch = CH[k % 4]
    chord(s + 0.03, 1.5, ch, 38); chord(s + 2.5 * BEAT + 0.03, 0.8, [x + 12 if x < 60 else x for x in ch[1:]], 28)
    n(s, 0.8, bass + 12, 64, 'gm33'); n(s + 2.5 * BEAT, 0.4, bass + 19, 52, 'gm33'); n(s + 3.5 * BEAT, 0.3, bass + 24, 44, 'gm33')
    n(s, BAR, bass + 36, 20, 'gm89')
beat(B0 + BAR, bars_b - 1)  # 첫 마디(타자 시작)는 비트 없이
MOTIF = [[(1.7, 0.4, 74), (2.1, 0.4, 76), (2.5, 1.1, 77)], [(1.7, 0.4, 76), (2.1, 1.3, 72)],
         [(1.7, 0.4, 74), (2.1, 0.4, 72), (2.5, 1.1, 70)], [(1.7, 0.5, 72), (2.2, 1.2, 76)]]
for k in range(bars_b):
    if B0 + k * BAR >= C0 - 0.5:
        break
    for t, d, x in MOTIF[k % 4]:
        n(B0 + k * BAR + t, d, x, 36 if k < 4 else 32, 'gm11')

# C 하나님께 다 말함 (39.4–49.8): 드럼이 빠지고 Gm9 – C9sus 만 길게
for s, bass, ch, d in [(C0, 31, [58, 62, 65, 69], 5.0), (C0 + 5.05, 36, [58, 60, 62, 65], 5.35)]:
    n(s, d, bass + 12, 50, 'gm33'); chord(s + 0.05, d - 0.1, ch, 33, roll=0.06); n(s, d + 0.1, bass + 36, 22, 'gm89')
for t, d, x in [(1.0, 0.6, 74), (1.7, 1.8, 72), (6.1, 0.6, 72), (6.8, 2.0, 70)]:
    n(C0 + t, d, x, 30, 'gm11')

# D 현관 · 금색 말씀 · 끝 (49.8–64.5): Fmaj9 → B♭maj9 → C13sus → Fmaj9 를 길게, 올라가는 파–솔–라–도
n(D0, 3.3, 41, 54, 'gm33'); chord(D0 + 0.05, 3.2, [57, 60, 64, 67, 72], 38, roll=0.05); n(D0, 3.4, 65, 26, 'gm89')
n(D0 + 3.35, 3.3, 34, 52, 'gm33'); chord(D0 + 3.4, 3.2, [57, 60, 62, 65, 69], 36, roll=0.05)
n(D0 + 6.7, 3.3, 36, 50, 'gm33'); chord(D0 + 6.75, 3.2, [58, 62, 64, 65, 69], 34, roll=0.05)
n(D0 + 10.05, 4.8, 29, 54, 'gm33'); n(D0 + 10.05, 4.8, 41, 46, 'gm33')
chord(D0 + 10.1, 4.6, [57, 60, 64, 67, 72], 36, roll=0.07); n(D0 + 10.05, 4.8, 65, 28, 'gm89')
for k in range(3):  # 하이햇만 아주 작게
    s = D0 + k * BAR
    for j in range(8):
        if s + j * BEAT / 2 < D0 + 9.5:
            n(s + j * BEAT / 2 + (SW if j % 2 else 0), 0.1, 42, 19 - (6 if j % 2 else 0), 'drums')
for t, d, x in [(0.9, 0.6, 65), (1.6, 0.6, 67), (2.3, 1.4, 69), (4.2, 0.6, 69), (4.9, 0.6, 70), (5.6, 1.4, 72),
                (7.5, 0.6, 72), (8.2, 0.6, 74), (8.9, 1.2, 76), (10.3, 3.6, 77)]:
    n(D0 + t, d, x, 34, 'gm11')

song = {'reverb': 'mediumRoom', 'wet': 22,
        'mix': {'drums': {'vol': 0.6, 'dry': True}, 'gm33': {'vol': 0.75, 'dry': True}, 'gm4': {'vol': 0.95},
                'gm11': {'vol': 0.55}, 'gm89': {'vol': 0.45}},
        'events': sorted(ev, key=lambda e: e['t'])}
json.dump(song, open(sys.argv[1], 'w'))
print(len(ev), 'events')
