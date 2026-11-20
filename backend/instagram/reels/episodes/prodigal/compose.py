"""「탕자의 귀환 그림 이야기」 배경 음악(피아노·현악) — 내레이션 밑에 깐다. 사용: python3 compose.py <작업폴더>/events.json
같은 폴더의 timeline.json(narrate.py — 문장마다 시작 시각)에 맞춰 화음을 바꾼다. finish.py 가 목소리 아래(-30 LUFS)로 낮추고
목소리가 나올 때 더 누른다(sidechain).

말 밑에 까는 음악이라 선율은 말 사이 쉼에만 짧게 두고, 화음은 펼쳐(아르페지오 + 현악 지속음) 찬송가처럼 들리지 않게.
젊은 렘브란트(E♭, 조금 들뜨게) → 30년의 상실(C단조, 느리게) → 이 그림·아들 이야기(G단조) → 발·종(A♭→D, 낮아짐)
→ 아버지가 안음(E♭, 풀림) → 옷·반지·신(A♭) → 아들로(B♭) → 두 손(F·B♭·E♭, 따뜻하게) → 이사야(B♭, 현악 크게) → "놓지 않을 만큼"(E♭)
→ 눅 15:20(B♭, 한숨 선율이 위로) → 끝 B♭·E♭·F·B♭ 로 맺음.
"""
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
tl = json.loads((out.parent / 'timeline.json').read_text())
seg = {s['id']: s for s in tl['segments']}
order = [s['id'] for s in tl['segments']]
END = tl['end']
ev = []


def note(t, dur, n, vel, inst='piano'):
    ev.append({'t': round(t, 3), 'dur': round(dur, 3), 'note': n, 'vel': vel, 'inst': inst})


def chord(t0, t1, bass, arp, pad, step=0.5, vb=42, va=30, vp=30):
    for b in bass:
        note(t0, t1 - t0 + 0.4, b, vb)
    k, t = 0, t0
    while t < t1 - 1e-6:
        note(t, min(1.6, t1 - t + 0.5), arp[k % len(arp)], va)
        t += step
        k += 1
    for p in pad:
        note(t0, t1 - t0 + 0.3, p, vp, 'strings')


def span(a, b=None):
    """문장 a 시작 0.15초 전 ~ 문장 b(없으면 a) 다음 문장 시작 0.15초 전."""
    i = order.index(b or a)
    end = seg[order[i + 1]]['t0'] - 0.15 if i + 1 < len(order) else END
    return max(0.0, seg[a]['t0'] - 0.15), end


def gap_melody(after, notes, vel=40):
    """문장 after 가 끝나고 다음 문장 전 쉼에 짧은 선율."""
    t = seg[after]['t1'] + 0.05
    for n, d in notes:
        note(t, d + 0.3, n, vel)
        t += d


Gm = ([31, 43], [55, 62, 67, 70, 67, 62], [55, 62, 67])
Eb = ([39, 51], [58, 63, 67, 70, 67, 63], [55, 58, 63])
F = ([41, 53], [60, 65, 69, 72, 69, 65], [57, 60, 65])
Bb = ([34, 46], [58, 62, 65, 70, 65, 62], [58, 62, 65])
Cm = ([36, 48], [55, 60, 63, 67, 63, 60], [55, 60, 63])
Ab = ([44, 56], [60, 63, 68, 72, 68, 63], [60, 63, 68])
D = ([38, 50], [54, 57, 62, 66, 62, 57], [54, 57, 62])

# 0초 — 젊은 렘브란트가 술잔을 든 첫 화면: E♭ 위로 가볍게 튀는 선율
for n in [39, 51, 58]:
    note(0.0, 2.6, n, 40)
for t, n, d in [(0.25, 70, 0.3), (0.55, 72, 0.3), (0.85, 75, 0.45), (1.3, 74, 0.3), (1.6, 70, 0.8)]:
    note(t, d + 0.3, n, 44)
chord(2.4, span('young')[1], *Eb, step=0.35, va=32)
chord(*span('later'), *Cm, step=0.7, va=26)
gap_melody('later', [(67, 0.4), (63, 0.4), (62, 0.7)], 38)
chord(*span('this'), *Gm, step=0.6, vp=34)
chord(*span('story'), *Gm, step=0.6)
chord(*span('feet'), *Ab, step=0.6)
chord(*span('servant'), *D, step=0.6)
chord(*span('embrace'), *Eb, step=0.4, va=34, vp=34)
gap_melody('embrace', [(74, 0.25), (75, 0.25), (77, 0.4)], 44)
# 옷·반지·신 → 종이 아니라 아들로: A♭ 에서 B♭ 으로 올라 풀림
chord(*span('robe'), *Ab, step=0.45, va=32)
chord(*span('son'), *Bb, step=0.4, vb=46, va=34, vp=36)
gap_melody('son', [(70, 0.3), (74, 0.3), (77, 0.6)], 44)
chord(*span('hands'), *F, step=0.45)
chord(*span('broad'), *Bb, step=0.5, vb=46)
chord(*span('slender'), *Eb, step=0.5, va=26)
chord(*span('nouwen'), *Gm, step=0.5)
chord(*span('bible'), *Cm, step=0.5)
# 이사야: B♭ 현악을 크게 — 어머니처럼 위로하시는 하나님
i0, i1 = span('isaiah')
chord(i0, i1, *Bb, step=0.5, vb=46, va=30, vp=40)
for n in [70, 74]:
    note(i0, i1 - i0, n, 26, 'strings')
gap_melody('isaiah', [(74, 0.3), (72, 0.3), (70, 0.5)])
chord(*span('hold'), *Eb, step=0.5, va=32, vp=36)
# 말씀: B♭장조, 한숨 선율이 위로(레–미♭–파)
v0, v1 = span('verse')
chord(v0, v1, *Bb, step=0.5, vb=48, va=32, vp=40)
for n in [70, 74]:
    note(v0, v1 - v0, n, 26, 'strings')
gap_melody('verse', [(74, 0.3), (75, 0.3), (77, 0.6)], 44)
# 끝: B♭ → E♭ → F → B♭ 로 맺고 길게
e0 = span('end')[0]
third = (seg['end']['t1'] - e0) / 3
chord(e0, e0 + third, *Bb)
chord(e0 + third, e0 + 2 * third, *Eb)
chord(e0 + 2 * third, seg['end']['t1'] + 0.1, *F)
fin = seg['end']['t1'] + 0.15
for n in [34, 46, 53]:
    note(fin, 4.0, n, 46)
for n in [62, 65, 70]:
    note(fin, 3.6, n, 38)
for n in [58, 62, 65, 70]:
    note(fin, 4.0, n, 34, 'strings')
note(fin + 0.2, 2.6, 74, 42)

json.dump(sorted(ev, key=lambda e: e['t']), open(out, 'w'))
print(len(ev), 'events, end', END)
