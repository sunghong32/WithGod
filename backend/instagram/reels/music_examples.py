"""악기 편성 본보기·비교 샘플(11/26 사용자에게 들려준 A·B·C·A2) — 마르다 편 찬송가 SWEET HOUR(Bradbury 1861) 1절 16마디를 같은 빠르기(점4분 = 40, 한 마디 1.5초)로 한 번.
모양은 둘 다 같다: 1–4마디 가볍게 → 5–8마디 반주가 더해짐 → 9–12마디 절정 → 13–16마디 처음 선율로 맺음.
  A: 피아노 + 현악(지금 마르다 편)
  B: 어쿠스틱 밴드 — 스틸 기타 아르페지오 + 베이스 + 브러시 드럼 + 따뜻한 패드, 선율은 피아노
사용: python3 music_examples.py A|B out.json [gu]   → swift music.swift out.json out.wav 29
      세 번째 인자 gu 면 GeneralUser GS 로(C·A2) — 뱅크마다 악기 크기가 달라 mix 를 따로 맞춰 둠(music_levels.py 로 잼).
기타 아르페지오 운지(GTR)·6/8 브러시 드럼(박 위에만)·베이스는 새 편에 그대로 가져다 쓸 수 있다."""
import json
import sys

E, BAR = 0.25, 1.5
A1 = [(0, 2, 66), (2, 1, 67), (3, 2, 69), (5, 1, 69)]
A2 = [(0, 2, 71), (2, 1, 73), (3, 2, 74), (5, 1, 71)]
MEL = {1: A1, 2: A2, 3: [(0, 2, 69), (2, 1, 66), (3, 1, 66), (4, 1, 64), (5, 1, 62)],
       4: [(0, 2, 64), (2, 1, 66), (3, 2, 64), (5, 1, 62)], 5: A1, 6: A2,
       7: [(0, 2, 69), (2, 1, 66), (3, 2, 66), (5, 1, 62)], 8: [(0, 2, 66), (2, 1, 64), (3, 2, 62), (5, 1, 69)],
       9: [(0, 2, 74), (2, 1, 73), (3, 2, 74), (5, 1, 71)], 10: [(0, 2, 69), (2, 1, 66), (3, 2, 69), (5, 1, 69)],
       11: [(0, 2, 74), (2, 1, 73), (3, 2, 74), (5, 1, 71)], 12: [(0, 2, 69), (2, 1, 66), (3, 2, 64), (5, 1, 62)],
       13: A1, 14: A2, 15: [(0, 2, 69), (2, 1, 66), (3, 2, 66), (5, 1, 62)], 16: [(0, 2, 66), (2, 1, 64), (3, 2, 62)]}
HAR = {1: [(0, 'D')], 2: [(0, 'G')], 3: [(0, 'D')], 4: [(0, 'A'), (3, 'A7')],
       5: [(0, 'D')], 6: [(0, 'G')], 7: [(0, 'D'), (3, 'D/F#')], 8: [(0, 'D/A'), (2, 'A7'), (3, 'D')],
       9: [(0, 'D'), (2, 'A7'), (3, 'D/F#'), (5, 'G')], 10: [(0, 'D')],
       11: [(0, 'D'), (2, 'A7'), (3, 'D/F#'), (5, 'G')], 12: [(0, 'D'), (3, 'A')],
       13: [(0, 'D')], 14: [(0, 'G')], 15: [(0, 'D'), (3, 'D/F#')], 16: [(0, 'D/A'), (2, 'A7'), (3, 'D')]}
CH = {'D': (38, [50, 54, 57]), 'G': (43, [50, 55, 59]), 'A': (45, [49, 52, 57]), 'A7': (45, [49, 55, 57]),
      'D/A': (45, [50, 54, 57]), 'D/F#': (42, [50, 54, 57])}
STRINGS = {'D': [62, 66, 69], 'G': [62, 67, 71], 'A': [61, 64, 69], 'A7': [61, 67, 69], 'D/A': [62, 66, 69], 'D/F#': [62, 66, 69]}
# 기타 운지(실제 기타에서 잡히는 소리): 베이스 줄 + 위 세 음
GTR = {'D': (50, [57, 62, 66]), 'G': (43, [55, 59, 62]), 'A': (45, [57, 61, 64]), 'A7': (45, [55, 61, 64]),
       'D/A': (45, [57, 62, 66]), 'D/F#': (42, [57, 62, 66])}
T1 = 0.25
LAST = 16
ev = []


def note(t, dur, n, vel, inst):
    ev.append({'t': round(t, 3), 'dur': round(dur, 3), 'note': n, 'vel': vel, 'inst': inst})


def segs(bar):
    h = HAR[bar]
    return [(s, h[i + 1][0] if i + 1 < len(h) else 6, c) for i, (s, c) in enumerate(h)]


def bt(b):
    return T1 + (b - 1) * BAR


def melody(b, vel, inst='piano'):
    for pos, dur, n in MEL[b]:
        d = 3.8 if b == LAST and pos == 3 else dur * E * 1.05
        note(bt(b) + pos * E, d, n, vel + (4 if pos in (0, 3) else 0), inst)


def vel_for(b, soft, mid, peak, end):
    return soft if b <= 4 else mid if b <= 8 else peak if b <= 12 else end


variant = sys.argv[1]
note(0.0, E * 1.05, 62, 44, 'piano')  # 못갖춘마디 "Sweet"
if variant == 'A':
    for b in range(1, 17):
        melody(b, vel_for(b, 44, 46, 54, 47))
        for s, e, c in segs(b):
            start, length = bt(b) + s * E, (e - s) * E
            if b == LAST and s == 3:
                length = 3.8
            bass, tones = CH[c]
            note(start, length + 0.1, bass, 42, 'piano')
            if b <= 8 and not (b == LAST):  # 앞 절반: 흐르는 8분음
                pat = [tones[0], tones[1], tones[2], tones[1]]
                for k in range(e - s):
                    if s + k:
                        note(start + k * E, E * 1.4, pat[k % 4], 32, 'piano')
            else:  # 뒤 절반: 긴 화음 + 현악
                for x in tones:
                    note(start + 0.02, length + 0.05, x, 30, 'piano')
            if b >= 5:
                for x in STRINGS[c]:
                    note(start, length + 0.08, x, 24 if b <= 8 else 40 if b <= 12 else 32, 'strings')
    for b in range(9, 17):  # 현악이 선율을 한 옥타브 아래에서
        for pos, dur, n in MEL[b]:
            note(bt(b) + pos * E, 3.8 if b == LAST and pos == 3 else dur * E * 1.05, n - 12, 30 if b < 13 else 24, 'strings')
    song = {'reverb': 'largeHall', 'wet': 28, 'mix': {'strings': {'vol': 0.55}}, 'events': ev}
else:
    KIT = 'drums40'  # GS 브러시 세트
    for b in range(1, 17):
        melody(b, vel_for(b, 46, 48, 56, 48))
        for s, e, c in segs(b):
            start = bt(b) + s * E
            gb, up = GTR[c]
            last_ring = b == LAST and s == 3
            # 기타 아르페지오(6/8 손가락 뜯기): 베이스 – 1 – 2 – 3 – 2 – 1, 8분음마다 한 음, 줄은 화음이 바뀔 때까지 울림
            pat = {0: gb, 1: up[0], 2: up[1], 3: up[2], 4: up[1], 5: up[0]}
            for k in range(e - s):
                pos = s + k
                if last_ring and k:
                    break
                n = gb if k == 0 else pat[pos]
                ring = 3.8 if last_ring else (e - pos) * E + 0.25
                note(bt(b) + pos * E, ring, n, (44 if k == 0 else 38) + (4 if b >= 9 and b <= 12 else 0), 'gm25')
            if last_ring:  # 마지막 화음은 천천히 긁어 내림
                for i, x in enumerate(up):
                    note(start + 0.06 * (i + 1), 3.7, x, 40, 'gm25')
            if b >= 5:  # 베이스: 박(점4분음)마다 근음
                bass = CH[c][0] - 12 if CH[c][0] >= 40 else CH[c][0]
                for beat in (0, 3):
                    if s <= beat < e:
                        d = 3.8 if last_ring else (min(e, beat + 3) - beat) * E - 0.05
                        note(bt(b) + beat * E, d, bass, 50 if b <= 12 else 44, 'gm33')
            if b >= 9:  # 패드가 아주 조용히 받친다
                note(start, (3.8 if last_ring else (e - s) * E) + 0.1, STRINGS[c][1], 34, 'gm89')
        if 5 <= b < LAST:  # 브러시 드럼: 1박 킥 · 2박 스네어 · 8분음 하이햇 — 모두 박 위에
            t0 = bt(b)
            note(t0, 0.2, 36, 40 if b <= 8 else 50, KIT)
            if b >= 9:
                note(t0 + 3 * E, 0.2, 38, 40 if b <= 12 else 34, KIT)
            for k in range(6):
                note(t0 + k * E, 0.1, 42, (26 if k in (0, 3) else 18) + (4 if 9 <= b <= 12 else 0), KIT)
        if b == LAST:
            note(bt(b), 0.2, 36, 44, KIT)
            note(bt(b) + 3 * E, 2.0, 51, 30, KIT)  # 마지막 화음에 라이드 한 번
    song = {'reverb': 'mediumHall', 'wet': 22,
            'mix': {'gm25': {'vol': 0.75}, 'gm33': {'vol': 0.42, 'dry': True}, KIT: {'vol': 0.6, 'dry': True},
                    'piano': {'vol': 1.0}, 'gm89': {'vol': 0.6}},
            'events': ev}
if len(sys.argv) > 3 and sys.argv[3] == 'gu':  # GeneralUser GS: 피아노가 기본 뱅크보다 20dB 가까이 크고 드럼·베이스는 작다 — 악기별로 다시 맞춘다
    song['bank'] = 'gu'
    song['mix'] = ({'piano': {'vol': 0.19}, 'strings': {'vol': 0.37}} if variant == 'A' else
                   {'piano': {'vol': 0.155}, 'gm25': {'vol': 0.29}, 'gm33': {'vol': 0.6, 'dry': True},
                    KIT: {'vol': 0.8, 'dry': True}, 'gm89': {'vol': 0.145}})
    for x in ev:
        if x['inst'].startswith('drums'):
            x['vel'] = min(127, x['vel'] + 12)
song['events'] = sorted(ev, key=lambda x: x['t'])
json.dump({k: v for k, v in song.items() if v is not None}, open(sys.argv[2], 'w'))
print(variant, len(ev), 'events, ends', round(max(x['t'] + x['dur'] for x in ev), 2))
