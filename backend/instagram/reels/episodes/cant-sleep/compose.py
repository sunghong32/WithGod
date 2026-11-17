"""Mia 1화 「3:07 a.m.」 음악 — 느린 새벽 로파이(약 68.6 BPM, 한 마디 3.5초, 60초). 피아노·현악이 아닌 일렉 피아노·베이스·
부드러운 드럼·비브라폰으로 월요일 인물 이야기와 소리부터 다르게 한다(사용자: "음악도 피아노밖에 못넣나?").

    python3 compose.py events.json   → finish.py 가 swift music.swift 로 렌더(spec 의 "lofi": true 로 고음 깎기·잡음)

마디(초)와 장면: A 0–17.5 잠 못 드는 생각(A단조, 드럼 없이 시계처럼 똑딱이는 높은 음, 끝에 E7sus 로 걸림 — "WithGod 앱을
열었다" 자막 중에 풀림) · B 17.5–42 앱(타자 → 말씀 → 풀이, Fmaj7–Em7–Dm7–Cmaj7 위로 비트가 조용히) · C 42–49 휴대폰을
엎어 둠(드럼이 빠지고 화음만) · D 49–60 금색 시편 4:8 → 끝 멘트(Fmaj9 → Dm9·G13sus → Cmaj9 로 길게 맺고, 첫 장면의 내려가는
한숨 선율 도–시–라가 끝에서 올라가는 미–파–솔로 바뀐다).
"""
import json
import sys

BAR, BEAT = 3.5, 0.875
SW = 0.08  # 스윙(뒤 8분음표를 늦게)
B0, C0, D0, END = 17.5, 42.0, 49.0, 59.5
ev = []


def n(t, d, note, vel, inst='gm4'):
    ev.append({'t': round(t, 3), 'dur': round(d, 3), 'note': note, 'vel': vel, 'inst': inst})


def chord(t, d, notes, vel, inst='gm4', roll=0.025):
    for i, x in enumerate(notes):  # 살짝 굴려 친다(손으로 친 느낌)
        n(t + i * roll, d, x, vel, inst)


def beat(t0, bars, kick=58, rim=44, hat=30):
    for b in range(bars):
        s = t0 + b * BAR
        n(s, 0.2, 36, kick, 'drums'); n(s + 2.5 * BEAT, 0.2, 36, kick - 10, 'drums')
        n(s + BEAT, 0.2, 37, rim, 'drums'); n(s + 3 * BEAT, 0.2, 37, rim, 'drums')
        for k in range(8):
            n(s + k * BEAT / 2 + (SW if k % 2 else 0), 0.1, 42, hat - (8 if k % 2 else 0), 'drums')


# A 잠 못 드는 생각 (0–17.5): Am9 – Fmaj9 – Am9 – Fmaj9 – Dm9·E7sus. 드럼 없이, 박마다 아주 작은 높은 미(시계)
AM9, FM9 = (45, [60, 64, 67, 71]), (41, [57, 60, 64, 67])
A = [(0.0, *AM9, 3.4), (3.5, *FM9, 3.4), (7.0, *AM9, 3.4), (10.5, *FM9, 3.4),
     (14.0, 38, [60, 64, 65, 69], 1.7), (15.75, 40, [57, 59, 62, 64], 1.7)]
for t, bass, ch, d in A:
    n(t, d + 0.2, bass, 40); chord(t + 0.05, d, ch, 34)
    n(t, d + 0.3, bass + 12, 26, 'gm89')
t = 0.0
while t < B0 - 0.1:
    n(t + 0.44, 0.12, 88, 18)
    t += BEAT
for t, d, x in [(1.3, 0.7, 72), (2.0, 0.6, 71), (2.6, 0.9, 69), (4.8, 0.7, 76), (5.5, 0.6, 74), (6.1, 0.9, 72),
                (8.3, 0.7, 72), (9.0, 0.6, 71), (9.6, 1.2, 69), (15.0, 0.5, 74), (15.75, 1.5, 71)]:
    n(t, d, x, 30)  # 한숨처럼 내려가는 도–시–라

# B 앱 (17.5–42): Fmaj7 – Em7 – Dm7 – Cmaj7 – Fmaj7 – Em7 – Dm7, 비트가 조용히 들어온다
CH = [(41, [57, 60, 64, 67]), (40, [55, 59, 62, 67]), (38, [57, 60, 64, 65]), (36, [55, 59, 62, 64])]
for k in range(7):
    bass, ch = CH[k % 4]
    s = B0 + k * BAR
    chord(s + 0.03, 1.6, ch, 40); chord(s + 2.5 * BEAT + 0.03, 0.9, [x + 12 if x < 60 else x for x in ch[1:]], 30)
    n(s, 0.8, bass, 66, 'gm33'); n(s + 2.5 * BEAT, 0.4, bass + 7, 54, 'gm33'); n(s + 3.5 * BEAT, 0.3, bass + 12, 46, 'gm33')
    n(s, BAR, bass + 24, 22, 'gm89')
beat(B0, 7)
MOTIF = [[(1.8, 0.4, 72), (2.2, 0.4, 74), (2.6, 1.2, 76)], [(1.8, 0.4, 74), (2.2, 1.4, 71)],
         [(1.8, 0.4, 72), (2.2, 0.4, 74), (2.6, 1.2, 77)], [(1.8, 0.5, 76), (2.3, 1.2, 79)]]
for k in range(7):
    for t, d, x in MOTIF[k % 4]:
        n(B0 + k * BAR + t, d, x, 38 if k < 4 else 34, 'gm11')

# C 휴대폰을 엎어 둠 (42–49): 드럼이 빠지고 Fmaj9 – G6sus 만 길게
for s, bass, ch in [(C0, 41, [57, 60, 64, 67, 69]), (C0 + BAR, 43, [57, 60, 62, 64, 67])]:
    n(s, 3.4, bass, 50, 'gm33'); chord(s + 0.05, 3.3, ch, 34, roll=0.06); n(s, 3.5, bass + 24, 24, 'gm89')
for t, d, x in [(1.1, 0.6, 72), (1.8, 1.6, 74), (4.6, 0.6, 76), (5.3, 1.5, 74)]:
    n(C0 + t, d, x, 32, 'gm11')

# D 금색 말씀 → 끝 (49–60): Fmaj9 → Dm9·G13sus → Cmaj9 를 길게, 올라가는 미–파–솔
n(D0, 3.4, 41, 54, 'gm33'); chord(D0 + 0.05, 3.3, [57, 60, 64, 67, 72], 38, roll=0.05); n(D0, 3.5, 65, 26, 'gm89')
n(D0 + 3.5, 1.7, 38, 50, 'gm33'); chord(D0 + 3.55, 1.7, [60, 64, 65, 69], 36, roll=0.05)
n(D0 + 5.25, 1.7, 43, 50, 'gm33'); chord(D0 + 5.3, 1.7, [57, 60, 64, 65], 34, roll=0.05)
n(D0 + 7.0, 4.4, 36, 54, 'gm33'); chord(D0 + 7.05, 4.2, [55, 59, 62, 64, 71], 36, roll=0.07); n(D0 + 7.0, 4.4, 60, 28, 'gm89')
for k in range(3):  # 하이햇만 아주 작게 남겨 숨을 쉬게
    s = D0 + k * BAR
    for j in range(8):
        if s + j * BEAT / 2 < D0 + 9.0:
            n(s + j * BEAT / 2 + (SW if j % 2 else 0), 0.1, 42, 20 - (6 if j % 2 else 0), 'drums')
for t, d, x in [(0.9, 0.6, 72), (1.6, 0.6, 74), (2.3, 1.4, 76), (3.9, 0.6, 76), (4.6, 0.6, 77), (5.4, 1.4, 79),
                (7.1, 3.0, 76)]:
    n(D0 + t, d, x, 36, 'gm11')

song = {'reverb': 'mediumRoom', 'wet': 22,
        'mix': {'drums': {'vol': 0.6, 'dry': True}, 'gm33': {'vol': 0.75, 'dry': True}, 'gm4': {'vol': 0.95},
                'gm11': {'vol': 0.55}, 'gm89': {'vol': 0.45}},
        'events': sorted(ev, key=lambda e: e['t'])}
json.dump(song, open(sys.argv[1], 'w'))
print(len(ev), 'events')
