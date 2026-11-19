"""「탕자의 귀환 그림 이야기」 배경 음악(피아노·현악) — 내레이션 밑에 깐다. 사용: python3 compose.py <작업폴더>/events.json
같은 폴더의 timeline.json(narrate.py — 문장마다 시작 시각)에 맞춰 화음을 바꾼다. finish.py 가 목소리 아래(-30 LUFS)로 낮추고
목소리가 나올 때 더 누른다(sidechain).

말 밑에 까는 음악이라 선율은 말 사이 쉼에만 짧게 두고, 화음은 펼쳐(아르페지오 0.5초 + 현악 지속음) 찬송가처럼 들리지 않게.
G단조(그림 소개·아들) → E♭·F(아버지가 달려감) → B♭·E♭(두 손, 따뜻하게) → A♭→D(발) → E♭(예복·반지·신)
→ D/E♭ 부딪힘(큰아들) → E♭ 로 풀림(아버지가 그에게도 나감) → B♭장조(말씀) → B♭·E♭·F·B♭ 로 맺음.
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

# 0초 — 그림이 화면을 채운 첫 화면: 낮은 G 위 한숨 선율(레–미♭–레–시♭)
for n in [43, 55, 62]:
    note(0.0, 2.8, n, 40)
for n in [67, 70]:
    note(0.0, 3.0, n, 30, 'strings')
for t, n, d in [(0.3, 74, 0.45), (0.75, 75, 0.4), (1.15, 74, 0.5), (1.65, 70, 0.9)]:
    note(t, d + 0.3, n, 46)

chord(2.6, span('title')[1], *Gm)
chord(*span('story'), *Eb)
gap_melody('story', [(70, 0.3), (72, 0.3)])
chord(*span('son1'), *Cm, step=0.6)
chord(*span('son2'), *Gm, step=0.6)
chord(*span('ran'), *Eb, step=0.35, va=34)
gap_melody('ran', [(74, 0.25), (75, 0.25), (77, 0.35)], 44)
chord(*span('hands'), *F, step=0.45)
chord(*span('broad'), *Bb, step=0.5, vb=46)
chord(*span('slender'), *Eb, step=0.5, va=26)
chord(*span('nouwen'), *Gm, step=0.5)
gap_melody('nouwen', [(74, 0.3), (72, 0.3), (70, 0.5)])
chord(*span('feet'), *Ab, step=0.6)
chord(*span('worn'), *D, step=0.6)
chord(*span('robe'), *Eb, step=0.45, va=34, vp=34)
gap_melody('robe', [(75, 0.25), (77, 0.25), (79, 0.4)], 44)
# 큰아들: 낮은 현악 레·미♭ 반음 부딪힘
b0, b1 = span('bro1')
note(b0, b1 - b0 + 0.3, 38, 38, 'strings')
note(b0, b1 - b0 + 0.3, 39, 32, 'strings')
for t in [b0 + 0.2, b0 + 1.4]:
    for n in [50, 51, 58]:
        note(t, 1.1, n, 30)
chord(*span('bro2'), *Eb, step=0.55)
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
