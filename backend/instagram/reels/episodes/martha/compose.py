"""마르다 릴스 음악(63.5초) — 찬송가 「Sweet Hour of Prayer」 피아노·현악 편곡. 사용: python3 compose.py events.json

곡: SWEET HOUR, William B. Bradbury(1861, 퍼블릭 도메인). 가사(William W. Walford, 1845) "Sweet hour of prayer … that calls me
from a world of care" 가 마르다 이야기(분주함에서 불러내 곁에 앉게 함)와 맞다. 선율·화음은 hymnary.org 에 있는
『Hymnal and Order of Service』(1901) 146장 스캔(라 장조, 6/8, 16마디 + 못갖춘마디)에서 옮겼다 — 기억으로 쓰지 않음.

사용자 지적(11/25 "성경 이야기 쪽 음악은 박자가 편안하지 않고 엇박이 많고 휙휙 바뀐다")대로: 처음부터 끝까지 같은 빠르기
(점4분음표 = 40, 한 마디 1.5초, 8분음표 0.25초)·같은 조, 화음은 박 위에만, 장면이 바뀌어도 곡은 이어 가고 악기·세기로만 키운다.
  1절 0.0–24.25  피아노 선율 + 박마다 길게 누르는 화음(가장 조용히) — 훅·부엌·마리아·항의
  2절 24.25–48.25 "Jesus answered her"부터 — 왼손이 고른 8분음으로 흐름
  3절 48.0–63.5   후반부(9–16마디)만: 금색 요 11:5(49.2) 아래 곡의 절정 "In seasons of distress"(높은 D), 현악이 더해짐,
                  끝 멘트(54.2)에서 첫 선율이 돌아오고 마지막 D장조 화음이 4초 머문다.
"""
import json
import sys

E = 0.25         # 8분음표(초)
BAR = 6 * E      # 6/8 한 마디
ev = []


def note(t, dur, n, vel, inst='piano'):
    ev.append({'t': round(t, 3), 'dur': round(dur, 3), 'note': n, 'vel': vel, 'inst': inst})


# 선율(소프라노) — 마디 번호: [(8분음 위치, 길이(8분음), 음)]. D4=62 E4=64 F#4=66 G4=67 A4=69 B4=71 C#5=73 D5=74
A1 = [(0, 2, 66), (2, 1, 67), (3, 2, 69), (5, 1, 69)]        # Sweet hour of prayer, sweet
A2 = [(0, 2, 71), (2, 1, 73), (3, 2, 74), (5, 1, 71)]        # hour of prayer, That
MEL = {
    1: A1, 2: A2,
    3: [(0, 2, 69), (2, 1, 66), (3, 1, 66), (4, 1, 64), (5, 1, 62)],   # calls me from a
    4: [(0, 2, 64), (2, 1, 66), (3, 2, 64), (5, 1, 62)],               # world of care, | And
    5: A1, 6: A2,
    7: [(0, 2, 69), (2, 1, 66), (3, 2, 66), (5, 1, 62)],               # all my wants and
    8: [(0, 2, 66), (2, 1, 64), (3, 2, 62), (5, 1, 69)],               # wish-es known; | In
    9: [(0, 2, 74), (2, 1, 73), (3, 2, 74), (5, 1, 71)],               # sea-sons of dis-
    10: [(0, 2, 69), (2, 1, 66), (3, 2, 69), (5, 1, 69)],              # tress and grief, | My
    11: [(0, 2, 74), (2, 1, 73), (3, 2, 74), (5, 1, 71)],              # soul has oft-en
    12: [(0, 2, 69), (2, 1, 66), (3, 2, 64), (5, 1, 62)],              # found re-lief, | And
    13: A1, 14: A2,
    15: [(0, 2, 69), (2, 1, 66), (3, 2, 66), (5, 1, 62)],              # thy re-turn, sweet
    16: [(0, 2, 66), (2, 1, 64), (3, 2, 62)],                          # hour of prayer.
}
# 화음(악보의 베이스·안성부 그대로): 마디 → [(8분음 위치, 화음)]
CH = {'D': (38, [50, 54, 57]), 'G': (43, [50, 55, 59]), 'A': (45, [49, 52, 57]), 'A7': (45, [49, 55, 57]),
      'D/A': (45, [50, 54, 57]), 'D/F#': (42, [50, 54, 57])}
HAR = {1: [(0, 'D')], 2: [(0, 'G')], 3: [(0, 'D')], 4: [(0, 'A'), (3, 'A7')],
       5: [(0, 'D')], 6: [(0, 'G')], 7: [(0, 'D'), (3, 'D/F#')], 8: [(0, 'D/A'), (2, 'A7'), (3, 'D')],
       9: [(0, 'D'), (2, 'A7'), (3, 'D/F#'), (5, 'G')], 10: [(0, 'D')],
       11: [(0, 'D'), (2, 'A7'), (3, 'D/F#'), (5, 'G')], 12: [(0, 'D'), (3, 'A')],
       13: [(0, 'D')], 14: [(0, 'G')], 15: [(0, 'D'), (3, 'D/F#')], 16: [(0, 'D/A'), (2, 'A7'), (3, 'D')]}
STRINGS = {'D': [62, 66, 69], 'G': [62, 67, 71], 'A': [61, 64, 69], 'A7': [61, 67, 69], 'D/A': [62, 66, 69], 'D/F#': [62, 66, 69]}


def segments(bar):
    """마디 안의 화음 구간 [(시작 8분음, 끝 8분음, 화음)]."""
    h = HAR[bar]
    return [(s, h[i + 1][0] if i + 1 < len(h) else 6, c) for i, (s, c) in enumerate(h)]


def play_bar(t0, bar, mel_vel, style, strings=0, last=False):
    for pos, dur, n in MEL[bar]:
        if last and pos == 3:  # 마지막 화음은 길게(4초)
            note(t0 + pos * E, 4.0, n, mel_vel)
            continue
        accent = 4 if pos in (0, 3) else 0  # 박 머리만 살짝
        note(t0 + pos * E, dur * E * 1.05, n, mel_vel + accent)
    for s, e, c in segments(bar):
        bass, tones = CH[c]
        start, length = t0 + s * E, (e - s) * E
        if last and s == 3:
            length = 4.0
        note(start, length + 0.1, bass, 40 if style == 'pad' else 42)
        if style == 'pad' or last and s == 3:
            for x in tones:
                note(start + 0.02, length + 0.05, x, 28)
        else:  # 흐르는 8분음: 화음 구간 안의 8분음마다 한 음씩(박 위에만, 고르게)
            pat = [tones[0], tones[1], tones[2], tones[1]]
            for k in range(e - s):
                if s + k == 0 and bass:  # 마디 첫 8분음은 베이스가 맡는다
                    continue
                note(start + k * E, E * 1.4, pat[k % len(pat)], 30)
        if strings:
            for x in STRINGS[c]:
                note(start, length + 0.08, x, strings, 'strings')


def pickup(t, n, vel):
    note(t, E * 1.05, n, vel)


# 1절 (0.0–24.25): 못갖춘마디 D → 16마디, 박마다 길게 누르는 화음
T1 = 0.25
pickup(0.0, 62, 44)
for b in range(1, 17):
    play_bar(T1 + (b - 1) * BAR, b, 44, 'pad')
# 16마디 끝 8분음 = 2절 못갖춘마디 D
pickup(T1 + 15 * BAR + 5 * E, 62, 46)

# 2절 (24.25–48.25): 같은 빠르기, 왼손이 고른 8분음으로
T2 = T1 + 16 * BAR
for b in range(1, 17):
    play_bar(T2 + (b - 1) * BAR, b, 47, 'flow')
pickup(T2 + 15 * BAR + 5 * E, 69, 48)  # 3절 못갖춘마디 A (후반부 "In seasons…" 로)

# 3절 (48.25–63.5): 후반부 9–16마디만, 현악이 더해지고 마지막 화음을 4초
T3 = T2 + 16 * BAR - 8 * BAR  # 9마디가 48.25 에 오도록
for b in range(9, 17):
    play_bar(T3 + (b - 1) * BAR, b, 52, 'flow', strings=36 if b < 13 else 40, last=(b == 16))
# 3절 선율을 현악이 한 옥타브 아래로 아주 작게 받쳐 준다(9–16마디)
for b in range(9, 17):
    t0 = T3 + (b - 1) * BAR
    for pos, dur, n in MEL[b]:
        note(t0 + pos * E, (4.0 if b == 16 and pos == 3 else dur * E * 1.05), n - 12, 26, 'strings')

json.dump(sorted(ev, key=lambda e: e['t']), open(sys.argv[1], 'w'))
end = max(e['t'] + e['dur'] for e in ev)
print(len(ev), 'events, last note ends', round(end, 2))
