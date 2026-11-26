"""마르다 릴스 음악(63.5초) — 찬송가 「Sweet Hour of Prayer」 피아노·현악 편곡, 장면을 따라 편성. 사용: python3 compose.py events.json

곡: SWEET HOUR, William B. Bradbury(1861, 퍼블릭 도메인). 가사(William W. Walford, 1845) "Sweet hour of prayer … that calls me
from a world of care" 가 마르다 이야기(분주함에서 불러내 곁에 앉게 함)와 맞다. 선율·화음은 hymnary.org 에 있는
『Hymnal and Order of Service』(1901) 146장 스캔(라 장조, 6/8, 16마디 + 못갖춘마디)에서 옮겼다 — 기억으로 쓰지 않음.

사용자 지적(11/25): ① "성경 이야기 쪽 음악은 엇박이 많고 휙휙 바뀐다" → 처음부터 끝까지 같은 곡·같은 빠르기(점4분음표 = 40,
한 마디 1.5초, 8분음표 0.25초)·같은 조, 화음은 박 위에만. ② "노래는 무난한데 스토리랑 너무 따로 논다" → 같은 곡 안에서
장면의 감정에 맞춰 편성만 바꾼다(바꿈은 마디 경계에서):

  시각(초)       장면                                   편성
  0.0–10.75     훅(찌푸린 얼굴) · 부엌의 분주함          선율 + 쉬지 않고 흐르는 8분음 반주(분주함)
  10.75–15.25   바닥에 앉아 듣는 마리아                  선율을 여리게 + 길게 누르는 화음(고요)
  15.25–24.25   "Martha had had enough." 항의            선율이 빠지고, 낮은 음역 sus 화음이 박마다 무겁게 — 풀리지 않음
  24.0–36.25    "Jesus answered her:" → 이름을 두 번     선율이 돌아오며 D장조로 풀림(2절), 아주 부드럽게 — 이야기의 전환점
  36.25–48.25   한 가지 · 곁에 있기를 · 성경은 말하지 않음  선율 + 긴 화음(고요), 42.25 부터 현악이 조용히
  48.0–54.25    금색 요 11:5(48.3) "Now Jesus loved Martha…" 곡의 절정 "In seasons of…"(높은 D, 48.25) + 현악·옥타브 선율, 가장 크게
  54.25–63.5    끝 멘트 · 쉬는 마르다                     첫 선율이 긴 화음 위로 돌아오고 마지막 D장조 화음이 3.6초 머문다
흐르는 8분음 반주는 부엌(분주함)에만 쓴다 — 고요한 장면·쉼에 깔면 분주함과 쉼이 음악에서 구별되지 않는다(4차 검토).
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
# 항의 장면용 — 같은 화음 진행을 낮은 음역 sus 로(3음을 빼고 4·9음을 걸어 풀리지 않게)
TENSE = {'D': (38, [45, 50, 52]), 'G': (31, [43, 50, 57]), 'A': (33, [45, 50, 52]), 'A7': (33, [43, 50, 52]),
         'D/A': (33, [45, 50, 52]), 'D/F#': (38, [45, 50, 52])}
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


def play_bar(t0, bar, mel_vel, style, strings=0, last=False, acc=30, no_pickup=False):
    """mel_vel=0 이면 선율을 빼고 반주만. style: flow(흐르는 8분음) · pad(긴 화음) · tense(낮은 sus 화음을 박마다)."""
    if mel_vel:
        for pos, dur, n in MEL[bar]:
            if no_pickup and pos == 5:  # 다음 마디에서 선율이 빠지면 이음음(못갖춘마디)도 뺀다
                continue
            if last and pos == 3:  # 마지막 화음은 길게(영상 끝 전에 맺게 3.6초)
                note(t0 + pos * E, 3.6, n, mel_vel)
                continue
            note(t0 + pos * E, dur * E * 1.05, n, mel_vel + (4 if pos in (0, 3) else 0))  # 박 머리만 살짝
    for s, e, c in segments(bar):
        start, length = t0 + s * E, (e - s) * E
        if last and s == 3:
            length = 3.6
        if style == 'tense':
            bass, tones = TENSE[c]
            for beat in (0, 3):  # 박(점4분음표)마다 무겁게 — 박 위에만
                if s <= beat < e:
                    note(t0 + beat * E, (min(e, beat + 3) - beat) * E + 0.05, bass, 44)
                    for x in tones:
                        note(t0 + beat * E + 0.02, (min(e, beat + 3) - beat) * E, x, 30)
            continue
        bass, tones = CH[c]
        note(start, length + 0.1, bass, 40 if style == 'pad' else 42)
        if style == 'pad' or last and s == 3:
            for x in tones:
                note(start + 0.02, length + 0.05, x, acc - 2)
        else:  # 흐르는 8분음: 화음 구간 안의 8분음마다 한 음씩(박 위에만, 고르게)
            pat = [tones[0], tones[1], tones[2], tones[1]]
            for k in range(e - s):
                if s + k == 0:  # 마디 첫 8분음은 베이스가 맡는다
                    continue
                note(start + k * E, E * 1.4, pat[k % len(pat)], acc)
        if strings:
            for x in STRINGS[c]:
                note(start, length + 0.08, x, strings, 'strings')


def pickup(t, n, vel):
    note(t, E * 1.05, n, vel)


T1 = 0.25                       # 1절 1마디
T2 = T1 + 16 * BAR              # 2절 1마디(24.25)
T3 = T2 + 16 * BAR - 8 * BAR    # 3절은 9마디가 48.25 에 오도록


def bar_t(t0, b):
    return t0 + (b - 1) * BAR


# 1절 — 훅·부엌(1–7마디, 흐름) → 마리아(8–10마디, 고요) → 항의(11–16마디, 선율 없이 sus)
pickup(0.0, 62, 46)
for b in range(1, 8):
    play_bar(bar_t(T1, b), b, 46, 'flow', acc=32)
for b in range(8, 11):
    play_bar(bar_t(T1, b), b, 40, 'pad', acc=30, no_pickup=(b == 10))
for b in range(11, 17):
    play_bar(bar_t(T1, b), b, 0, 'tense')
# 2절 — "Jesus answered her:" 에서 선율이 돌아오며 풀림(못갖춘마디 D 24.0)
pickup(T2 - E, 62, 42)
for b in range(1, 9):           # 1–8마디: 아주 부드럽게, 긴 화음
    play_bar(bar_t(T2, b), b, 42, 'pad', acc=28)
for b in range(9, 17):          # 9–16마디: 긴 화음(고요), 13마디(42.25 — "He wanted Martha with Him, too")부터 현악이 조용히
    play_bar(bar_t(T2, b), b, 43, 'pad', strings=26 if b >= 13 else 0, acc=28)
pickup(bar_t(T2, 16) + 5 * E, 69, 48)   # 3절 못갖춘마디 A → "In seasons…"
# 3절 — 후반부(9–16마디): 금색 요 11:5 아래 절정, 끝 멘트에서 첫 선율, 마지막 화음 4초
for b in range(9, 17):          # 절정(9–12)도 끝(13–16)도 긴 화음 — 크기는 선율·현악으로
    play_bar(bar_t(T3, b), b, 54 if b < 13 else 47, 'pad', strings=40 if b < 13 else 34, last=(b == 16), acc=32 if b < 13 else 30)
for b in range(9, 17):          # 현악이 선율을 한 옥타브 아래에서 아주 작게 받쳐 준다
    for pos, dur, n in MEL[b]:
        note(bar_t(T3, b) + pos * E, (3.6 if b == 16 and pos == 3 else dur * E * 1.05), n - 12, 30 if b < 13 else 24, 'strings')

json.dump(sorted(ev, key=lambda e: e['t']), open(sys.argv[1], 'w'))
end = max(e['t'] + e['dur'] for e in ev)
print(len(ev), 'events, last note ends', round(end, 2))
