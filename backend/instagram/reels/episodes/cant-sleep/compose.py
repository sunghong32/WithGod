"""Mia 1화 「3:07 a.m.」 음악 — 느린 새벽 로파이(약 68.6 BPM, 한 마디 3.5초). 피아노·현악이 아닌 일렉 피아노·베이스·
부드러운 드럼·비브라폰으로 월요일 인물 이야기와 소리부터 다르게 한다(사용자: "음악도 피아노밖에 못넣나?").

    python3 compose.py events.json   → finish.py 가 swift music.swift 로 렌더(spec 의 "lofi": true 로 고음 깎기·잡음)

마디(초)와 장면: A 0–10.5 잠 못 드는 생각(A단조, 드럼 없이 시계처럼 똑딱이는 높은 음, 마지막에 E7sus 로 걸림) ·
B 10.5–24.5 앱을 열고 말씀·풀이(Fmaj7–Em7–Dm7–Cmaj7, 비트가 조용히 들어온다) · C 24.5–31.5 휴대폰을 엎어 둠
(드럼이 빠지고 화음만) · D 31.5–42 금색 말씀 → 끝 멘트(Fmaj9 → Dm9–G13sus → Cmaj9 로 길게 맺고, 첫 장면의
내려가는 한숨 선율 도–시–라가 끝에서 올라가는 미–파–솔로 바뀐다).
"""
import json
import sys

BAR, BEAT = 3.5, 0.875
SW = 0.08  # 스윙(뒤 8분음표를 늦게)
ev = []


def n(t, d, note, vel, inst='gm4'):
    ev.append({'t': round(t, 3), 'dur': round(d, 3), 'note': note, 'vel': vel, 'inst': inst})


def chord(t, d, notes, vel, inst='gm4', roll=0.025):
    for i, x in enumerate(notes):  # 살짝 굴려 친다(손으로 친 느낌)
        n(t + i * roll, d, x, vel, inst)


def beat(t0, bars, kick=64, rim=50, hat=34):
    for b in range(bars):
        s = t0 + b * BAR
        n(s, 0.2, 36, kick, 'drums'); n(s + 2.5 * BEAT, 0.2, 36, kick - 10, 'drums')
        n(s + BEAT, 0.2, 37, rim, 'drums'); n(s + 3 * BEAT, 0.2, 37, rim, 'drums')
        for k in range(8):
            n(s + k * BEAT / 2 + (SW if k % 2 else 0), 0.1, 42, hat - (8 if k % 2 else 0), 'drums')


# A 잠 못 드는 생각 (0–10.5): Am9 → Fmaj9 → Dm9 · E7sus. 드럼 없이, 박마다 아주 작은 높은 미(시계)
A = [(0.0, 45, [60, 64, 67, 71]), (3.5, 41, [57, 60, 64, 67]), (7.0, 38, [60, 64, 65, 69]), (8.75, 40, [57, 59, 62, 64])]
for t, bass, ch in A:
    d = 3.4 if t < 7 else 1.7
    n(t, d + 0.2, bass, 40); chord(t + 0.05, d, ch, 34)
    n(t, d + 0.3, bass + 12, 26, 'gm89')
t = 0.0
while t < 10.4:
    n(t + 0.44, 0.12, 88, 18)
    t += BEAT
for t, d, x in [(1.3, 0.7, 72), (2.0, 0.6, 71), (2.6, 0.9, 69), (4.8, 0.7, 76), (5.5, 0.6, 74), (6.1, 0.9, 72),
                (8.0, 0.5, 74), (8.75, 1.4, 71)]:
    n(t, d, x, 30)  # 한숨처럼 내려가는 도–시–라

# B 앱 (10.5–24.5): Fmaj7 – Em7 – Dm7 – Cmaj7, 비트가 조용히 들어온다
B = [(41, [57, 60, 64, 67]), (40, [55, 59, 62, 67]), (38, [57, 60, 64, 65]), (36, [55, 59, 62, 64])]
for k, (bass, ch) in enumerate(B):
    s = 10.5 + k * BAR
    chord(s + 0.03, 1.6, ch, 40); chord(s + 2.5 * BEAT + 0.03, 0.9, [x + 12 if x < 60 else x for x in ch[1:]], 30)
    n(s, 0.8, bass, 66, 'gm33'); n(s + 2.5 * BEAT, 0.4, bass + 7, 54, 'gm33'); n(s + 3.5 * BEAT, 0.3, bass + 12, 46, 'gm33')
    n(s, BAR, bass + 24, 22, 'gm89')
beat(10.5, 4, kick=58, rim=44, hat=30)
for t, d, x in [(12.3, 0.4, 72), (12.7, 0.4, 74), (13.1, 1.2, 76), (15.8, 0.4, 74), (16.2, 1.4, 71), (19.3, 0.4, 72),
                (19.7, 0.4, 74), (20.1, 1.2, 77), (22.8, 0.5, 76), (23.3, 1.2, 79)]:
    n(t, d, x, 38, 'gm11')

# C 휴대폰을 엎어 둠 (24.5–31.5): 드럼이 빠지고 Fmaj9 – G6sus 만 길게
for s, bass, ch in [(24.5, 41, [57, 60, 64, 67, 69]), (28.0, 43, [57, 60, 62, 64, 67])]:
    n(s, 3.4, bass, 50, 'gm33'); chord(s + 0.05, 3.3, ch, 34, roll=0.06); n(s, 3.5, bass + 24, 24, 'gm89')
for t, d, x in [(25.6, 0.6, 72), (26.3, 1.6, 74), (29.1, 0.6, 76), (29.8, 1.5, 74)]:
    n(t, d, x, 32, 'gm11')

# D 금색 말씀 → 끝 (31.5–42): Fmaj9 → Dm9·G13sus → Cmaj9 를 길게, 올라가는 미–파–솔
n(31.5, 3.4, 41, 54, 'gm33'); chord(31.55, 3.3, [57, 60, 64, 67, 72], 38, roll=0.05); n(31.5, 3.5, 65, 26, 'gm89')
n(35.0, 1.7, 38, 50, 'gm33'); chord(35.05, 1.7, [60, 64, 65, 69], 36, roll=0.05)
n(36.75, 1.7, 43, 50, 'gm33'); chord(36.8, 1.7, [57, 60, 64, 65], 34, roll=0.05)
n(38.5, 4.2, 36, 54, 'gm33'); chord(38.55, 4.0, [55, 59, 62, 64, 71], 36, roll=0.07); n(38.5, 4.2, 60, 28, 'gm89')
for k in range(3):  # 하이햇만 아주 작게 남겨 숨을 쉬게
    s = 31.5 + k * BAR
    for j in range(8):
        if s + j * BEAT / 2 < 40.0:
            n(s + j * BEAT / 2 + (SW if j % 2 else 0), 0.1, 42, 20 - (6 if j % 2 else 0), 'drums')
for t, d, x in [(32.4, 0.6, 72), (33.1, 0.6, 74), (33.8, 1.4, 76), (35.4, 0.6, 76), (36.1, 0.6, 77), (36.9, 1.4, 79),
                (38.6, 2.8, 76)]:
    n(t, d, x, 36, 'gm11')

song = {'reverb': 'mediumRoom', 'wet': 22,
        'mix': {'drums': {'vol': 0.6, 'dry': True}, 'gm33': {'vol': 0.75, 'dry': True}, 'gm4': {'vol': 0.95},
                'gm11': {'vol': 0.55}, 'gm89': {'vol': 0.45}},
        'events': sorted(ev, key=lambda e: e['t'])}
json.dump(song, open(sys.argv[1], 'w'))
print(len(ev), 'events')
