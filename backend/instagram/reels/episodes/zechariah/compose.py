"""사가랴와 엘리사벳 릴스 음악(약 66.5초) — 대림절 찬송가 VENI EMMANUEL 한 곡을 처음부터 끝까지 같은 빠르기·같은 조(마단조)로, 장면 따라 편성만 바꾼다.
사용: python3 compose.py <veni.json> events.json        (뱅크 GeneralUser GS — 크기는 music_levels.py 로 맞춘 값)

곡: VENI EMMANUEL(「O Come, O Come, Emmanuel」) — 선율 Thomas Helmore 편(The Hymnal Noted, 1850년대; 15세기 프랑스 행렬 성가에서),
가사 J. M. Neale(1851)·Hymns Ancient & Modern(1861). 미국 퍼블릭 도메인. 4성부는 Common Service Book(1917) 1장 —
Open Hymnal Project 의 ABC 파일(OpenHymnal2026.11.abc, X:47)을 music21 로 읽어 veni.json 으로 옮겼다(기억으로 쓰지 않음,
소프라노는 위키백과 악보와 음 59개 대조 일치). 4/4, 줄마다 못갖춘마디 1박, 한 절 = 4줄 + 후렴 2줄 = 4분음표 76개.
왜 이 곡: 대림절(11/29 시작) 첫 주의 기다림 노래이고, 넷째 절 "O come, Thou Day-spring" 의 Dayspring 이 바로 사가랴의 노래
(눅 1:78 "the dayspring from on high", KJV)에서 왔다. 후렴 "Rejoice! Rejoice!" 가 이름 짓는 날(입이 열려 찬양)에 온다.

빠르기 4분음표 = 75(0.8초) 하나로 끝까지. 바꿈은 마디 경계(줄 시작 + 0.8 · 4.0 · 7.2초)에서만, 드럼·스윙·당김음 없음.
악기(사용자 11/26 "그때그때 잘 어울리는 악기를 조합해서") — 늙은 부부의 밤 = 첼로 독주 + 하프, 성전 = 교회 오르간을 아주 여리게,
천사 = 플루트 선율 + 하프 아르페지오, 말 못 하는 아홉 달 = 선율이 빠진 낮은 현악(말이 없어진 것을 음악도),
이름 짓는 날 = 플루트 + 나일론 기타 + 현악(밝아지는 순간), 새벽·금색 말씀 = 합창 「아」 + 현악 + 하프(절정).

  시각(초)       장면                                    줄            편성
  0.0–9.6       훅(놀란 얼굴) · 밤에 기도하는 노부부        L1 O come     첼로 선율(한 옥타브 아래) + 하프 화음(박마다)
  9.6–13.6      "They had prayed … for years"           L2 ransom     같음
  13.6–19.2     제비뽑혀 성전 안 분향                      L2 (2마디째~)  + 교회 오르간 긴 화음(여리게)
  19.2–26.4     천사 "Don't be afraid…"                  L3 mourns     플루트 선율 + 하프 8분음 아르페지오 + 낮은 현악
  26.4–28.8     "How can I be sure?"                    L3 (마지막 마디) 선율이 빠지고 낮은 현악만 — 의심
  28.8–32.8     말을 못 하고 나옴                          L4 Until      선율 없이 낮은 현악 + 마디마다 하프 한 음(침묵)
  32.8–38.4     엘리사벳 "the Lord … looked at me"        L4 (2마디째~)  첼로 선율이 여리게 돌아옴 + 하프
  38.4–51.2     이름 짓는 날 · 입이 열려 찬양 · 이름 뜻       R1 Rejoice!   플루트 + 나일론 기타 아르페지오 + 현악 + 하프 — 밝아지는 순간
  51.2–66.5     새벽 · 금색 눅 1:78–79 · 끝 멘트            R2 Shall come 합창 「아」 선율 + 현악 4성부 + 하프, 마지막 화음을 길게(약 8초)
"""
import json
import sys

Q = 0.8                    # 4분음표(초)
LINES = json.load(open(sys.argv[1]))['lines']
NAMES = ['L1', 'L2', 'L3', 'L4', 'R1', 'R2']
LEN = {'L1': 12, 'L2': 12, 'L3': 12, 'L4': 12, 'R1': 16, 'R2': 12}
START = {}
t = 0.0
for n in NAMES:
    START[n] = t
    t += LEN[n] * Q
DUR = 66.5
LAST_HOLD = DUR - (START['R2'] + 9 * Q) + 0.3   # R2 마지막 음(9박째)을 영상 끝까지
V = {n: LINES[i] for i, n in enumerate(NAMES)}
ev = []


def note(t, dur, n, vel, inst):
    ev.append({'t': round(t, 3), 'dur': round(dur, 3), 'note': n, 'vel': max(1, min(127, int(vel))), 'inst': inst})


def part(line, voice, vel, inst, shift=0, frm=0.0, to=99.0, last=False, legato=1.02):
    t0 = START[line]
    for p, d, n in V[line][voice]:
        if not (frm <= p < to):
            continue
        dur = LAST_HOLD if last and p + d >= LEN[line] else d * Q * legato
        note(t0 + p * Q, dur, n + shift, vel + (4 if (p - 1) % 4 == 0 else 0), inst)   # 마디 첫 박만 살짝


def at(line, voice, pos):
    for p, d, n in V[line][voice]:
        if p <= pos < p + d:
            return n
    return V[line][voice][-1][2]


def harp_beats(line, vel, frm=0.0, to=99.0, every=1.0, last=False):
    """하프: 박마다(every=1) 또는 마디마다(every=4, 1박 위치부터) 그 자리 베이스 + 테너 + 알토를 아래서 위로 살짝 굴려서."""
    t0 = START[line]
    p = frm
    while p < min(to, LEN[line]):
        if every == 1.0 or (p - 1) % 4 == 0:
            b = at(line, 'B', p)
            tones = [b - 12, at(line, 'T', p), at(line, 'A', p)] if every == 1.0 else [b]
            for i, x in enumerate(tones):
                d = LAST_HOLD if last and p >= 9 else Q * (2.0 if every == 1.0 else 4.0)
                note(t0 + p * Q + 0.04 * i, d, x, vel - 4 * i, 'gm46')
        p += 1.0


def harp_arp(line, vel, frm=0.0, to=99.0):
    """천사 장면: 8분음마다 한 음(베이스 · 테너 · 알토 · 테너), 박 위에만 고르게."""
    t0 = START[line]
    order = ('B', 'T', 'A', 'T')
    k = 0
    p = frm
    while p < min(to, LEN[line]):
        v = order[k % 4]
        n = at(line, v, p) + (12 if v == 'B' else 12)
        note(t0 + p * Q, Q * 0.9, n, vel + (5 if k % 4 == 0 else 0), 'gm46')
        p += 0.5
        k += 1


def guitar(line, vel, last=False):
    """나일론 기타 아르페지오(8분음, 박 위에만): 베이스 · 테너 · 알토 · 테너."""
    t0 = START[line]
    order = ('B', 'T', 'A', 'T')
    for k in range(int(LEN[line] * 2)):
        p = k * 0.5
        v = order[k % 4]
        n = at(line, v, p)
        if v == 'B' and n > 52:
            n -= 12
        note(t0 + p * Q, Q * 1.1, n, vel + (6 if k % 4 == 0 else 0), 'gm24')


def low_strings(line, vel, frm=0.0, to=99.0, last=False):
    """낮은 현악 — 베이스(한 옥타브 아래)와 테너를 길게, 같은 음이 이어지면 다시 치지 않는다."""
    for voice, shift, dv in (('B', -12, 0), ('T', -12, -6)):
        t0 = START[line]
        segs = []
        for p, d, n in V[line][voice]:
            if not (frm <= p < to):
                continue
            if segs and segs[-1][2] == n + shift:
                segs[-1][1] += d
            else:
                segs.append([p, d, n + shift])
        for p, d, n in segs:
            dur = LAST_HOLD if last and p + d >= LEN[line] else min(d, to - p) * Q + 0.05
            note(t0 + p * Q, dur, n, vel + dv, 'gm48')


# L1 — 훅 · 밤에 기도하는 노부부: 첼로 독주 + 하프
part('L1', 'S', 52, 'gm42', shift=-12, legato=1.0)
harp_beats('L1', 40)
# L2 — 1마디(0~1박)까지 같음, 2마디째(5박, 13.6초 — 성전)부터 오르간이 여리게 더해짐
part('L2', 'S', 52, 'gm42', shift=-12, legato=1.0)
harp_beats('L2', 38)
for v, vel in (('A', 40), ('T', 38), ('B', 42)):
    part('L2', v, vel, 'gm19', frm=5.0, legato=1.0)
# L3 — 천사: 플루트 선율 + 하프 아르페지오 + 낮은 현악, 마지막 마디(9박, 26.4초 "How can I be sure?")는 선율·하프를 빼고 낮은 현악만
part('L3', 'S', 54, 'gm73', to=9.0, legato=0.98)
harp_arp('L3', 36, to=9.0)
low_strings('L3', 34)
# L4 — 말을 못 함: 선율 없이 낮은 현악 + 마디마다 하프 한 음 → 5박(32.8초, 엘리사벳)부터 첼로 선율이 여리게 돌아옴
low_strings('L4', 34)
harp_beats('L4', 34, to=5.0, every=4.0)
part('L4', 'S', 46, 'gm42', shift=-12, frm=5.0, legato=1.0)
harp_beats('L4', 34, frm=5.0)
# R1 — 이름 짓는 날, 입이 열려 찬양: 밝아지는 순간. 플루트 + 나일론 기타 + 현악(알토·테너) + 하프
part('R1', 'S', 62, 'gm73', legato=0.98)
guitar('R1', 58)
for v, vel in (('A', 40), ('T', 40)):
    part('R1', v, vel, 'gm48')
part('R1', 'B', 44, 'gm48', shift=-12)
# R2 — 새벽 · 금색 말씀 · 끝: 합창 「아」 선율 + 현악 4성부 + 하프, 마지막 화음을 끝까지
part('R2', 'S', 60, 'gm52', last=True)
part('R2', 'A', 46, 'gm52', last=True)
for v, vel in (('S', 42), ('A', 40), ('T', 40)):
    part('R2', v, vel, 'gm48', last=True)
part('R2', 'B', 46, 'gm48', shift=-12, last=True)
harp_beats('R2', 40, last=True)

song = {'bank': 'gu', 'reverb': 'cathedral', 'wet': 28,
        'mix': {'gm42': {'vol': 1.0}, 'gm46': {'vol': 0.7}, 'gm19': {'vol': 1.0}, 'gm73': {'vol': 0.8},
                'gm48': {'vol': 0.5}, 'gm24': {'vol': 1.0}, 'gm52': {'vol': 0.6}},
        'events': sorted(ev, key=lambda e: e['t'])}
json.dump(song, open(sys.argv[2], 'w'))
end = max(e['t'] + e['dur'] for e in ev)
print(len(ev), 'events, last note ends', round(end, 2), '· 줄 시작', {k: round(v, 2) for k, v in START.items()})
