"""「Now Thank We All Our God」 릴스 spec(장면·카메라·자막) → spec.json, cover-spec.json. 카메라 [시각, 중심x, 중심y, 폭] 은 원본(1600×1200) 픽셀.
사용: python3 make_spec.py <작업폴더>   (작업폴더에 picks.json·cams.json·art/ — 이 폴더의 것을 복사해 쓴다)

음악(compose.py)이 한 줄 = 4분음표 8개(♩=78, 6.15초)로 가므로 장면 바꿈을 줄 경계(L(n))에 맞춘다 — 찬송 선율과 장면이 같이 바뀐다.
가사 자막 두 곳은 그 가사의 선율이 나오는 줄에 맞췄다: 「Now thank we all our God」 = A1(L(2)), 「…with countless gifts of love,」 = B3(L(6)), 「and still is ours today.」 = 1절 마지막 줄 B4(L(7)).
어두운 장면(전쟁·역병·밤의 무덤)은 L(3)~L(6) 18.5초 한 덩어리, L(6)=36.9초에 새벽빛으로 밝아지고 끝까지 밝다(REVIEW S4, 사용자 11/26).
끝 멘트 "God is still yours today" 는 되풀이한 마지막 줄 B4(L(9)) 위에. 가사는 Winkworth 1858(뉴욕판 "hath blessed", "to-day"→"today").
금색은 시편 23:4 하나뿐(REVIEW T1). 찬송 가사는 흰 기울임(.t.it), 장절 없음 — 출처는 캡션에.
"""
import json
import sys
from pathlib import Path

W = Path(sys.argv[1])
ART = json.loads((W / 'picks.json').read_text())
CAM = json.loads((W / 'cams.json').read_text())
P = CAM.get('pos', {})
Q = 60 / 78


def L(n):
    """n 번째 줄이 시작하는 시각(초)."""
    return round(n * 8 * Q, 2)


def at(t, key, dw=0):
    x, y, w = CAM[key]
    return [t, x, y, w + dw]


DUR = round(L(9) + 5 * Q + 6.0 + 2.0, 2)  # 마지막 화음(끝 줄 5박째) 6초 + 잔향
shots = [
    # 첫 화면: 무덤가의 링카르트 얼굴 — 0~1.3초에 1.2배로 밀고 들어가 2.4초에 식탁으로 컷(1630년 무렵으로 거슬러 감)
    {'img': ART['a_grave'], 't0': 0.0, 't1': 2.4, 'cam': [at(0, 'face0'), at(1.3, 'face1'), at(2.4, 'face1', -10)]},
    {'img': ART['c_table'], 't0': 2.4, 't1': L(3), 'fade': 0.25,
     'cam': [at(2.4, 'table0'), at(L(2), 'table1'), at(L(3) + 0.4, 'table2')]},
    {'img': ART['b_town'], 't0': L(3), 't1': L(4), 'fade': 0.7, 'cam': [at(L(3), 'town0'), at(L(4) + 0.4, 'town1')]},
    {'img': ART['d_plague'], 't0': L(4), 't1': L(5), 'fade': 0.5, 'cam': [at(L(4), 'plague0'), at(L(5) + 0.4, 'plague1')]},
    {'img': ART['e_wife'], 't0': L(5), 't1': L(6), 'fade': 0.8, 'cam': [at(L(5), 'wife0'), at(L(6) + 0.4, 'wife1')]},
    # 밝아지는 순간(REVIEW S4) — 밤의 무덤에서 새벽 햇빛으로, 음악도 여기서 오르간 4성부로 풀린다
    {'img': ART['f_dawn'], 't0': L(6), 't1': L(8), 'fade': 1.2,
     'cam': [at(L(6), 'dawn0'), at(L(7), 'dawn1'), at(L(8) + 0.4, 'dawn2')]},
    {'img': ART['g_today'], 't0': L(8), 't1': L(8) + 2.6, 'fade': 0.8, 'cam': [at(L(8), 'today0'), at(L(8) + 3.0, 'today1')]},
    {'img': ART['h_sunrise'], 't0': L(8) + 2.6, 't1': DUR, 'fade': 0.9, 'cam': [at(L(8) + 2.6, 'sun0'), at(DUR, 'sun1')]},
]


def t(text, cls='t'):
    return f"<p class='{cls}'>{text}</p>" if cls in ('t', 't it') else f"<div class='{cls}'>{text}</div>"


TITLE = ("<div class='b' style='top:230px'><div class='h1'>The story behind<br>“Now Thank We<br>All Our God”</div>"
         "<div class='sub'>Martin Rinkart · Germany, 1630s</div></div>")
HOOK = "<div class='hook'>He wrote this<br>thank-you hymn.<br>Then plague<br>took his wife.</div>"
texts = [
    {'t0': 0.0, 't1': 3.2, 'fi': 0, 'raw': True, 'html': TITLE},
    {'t0': 0.0, 't1': 3.2, 'fi': 0, 'pos': P.get('a', 'low'), 'html': HOOK},
    {'t0': 3.15, 't1': 7.6, 'fi': 0.3, 'pos': P.get('c', 'top'),
     'html': t("Martin Rinkart was a pastor in Eilenburg, a small walled town in Germany.")},
    {'t0': 7.55, 't1': L(2) - 0.05, 'fi': 0.3, 'pos': P.get('c', 'top'),
     'html': t("Around 1630, with war raging across Germany, he wrote a short prayer to sing at the table:")},
    # 가사 첫 줄 — 음악 L(2) 가 바로 「Now thank we all our God」 선율(A1)
    {'t0': L(2), 't1': L(3) - 0.15, 'fi': 0.3, 'pos': P.get('c', 'top'),
     'html': t("“Now thank we all our God…”", 'h1 it')},
    {'t0': L(3) + 0.15, 't1': L(4) - 0.1, 'pos': P.get('b', 'top'),
     'html': t("Then the war came to his town.<br>Armies demanded money,<br>and refugees poured in.")},
    {'t0': L(4) + 0.1, 't1': L(4) + 3.1, 'pos': P.get('d', 'top'), 'html': t("In 1637, plague came.<br>About 4,000 people died.", 'h1')},
    {'t0': L(4) + 3.15, 't1': L(5) - 0.1, 'pos': P.get('d', 'top'),
     'html': t("For a time, he was the town’s only pastor.")},
    {'t0': L(5) + 0.2, 't1': L(5) + 3.3, 'pos': P.get('e', 'low'), 'html': t("Among the dead was his wife, Christine.", 'h1')},
    {'t0': L(5) + 3.35, 't1': L(6) + 0.6, 'pos': P.get('e', 'low'),
     'html': t("He stayed, still trusting<br>the God of his prayer —")},
    # 가사 1절 마지막 두 줄 — 한 줄씩, 그 줄의 선율이 나올 때(B3 L(6) · B4 L(7)), 새벽빛 위에
    {'t0': L(6) + 0.7, 't1': L(7) - 0.1, 'pos': P.get('f', 'low'), 'html': t("“…with countless<br>gifts of love,", 'h1 it')},
    {'t0': L(7), 't1': L(8) - 0.2, 'pos': P.get('f', 'low'), 'html': t("and still is<br>ours today.”", 'h1 it')},
    {'t0': L(8) + 0.2, 't1': L(8) + 2.55, 'pos': P.get('g', 'top'),
     'html': t("Churches still sing it at Thanksgiving.", 'h1')},
    {'t0': L(8) + 2.7, 't1': L(9) + 3.5, 'pos': P.get('h', 'top'),
     'html': "<div class='v'>“Even though I walk through the valley of the shadow of death, I will fear no evil, for you are with me…”</div>"
             "<div class='r'>Psalm 23:4</div>"},
    # 끝 멘트 — 음악이 다시 「and still is ours today」 줄을 지나 마지막 화음
    {'t0': L(9) + 3.6, 't1': DUR + 0.4, 'pos': P.get('h', 'top'),
     'html': t("Hard year?<br>You don’t have to<br>pretend it wasn’t.<br>God is still yours today.", 'h1')},
    {'t0': L(9) + 4.8, 't1': DUR + 0.4, 'raw': True,
     'html': f"<div class='hd' style='{CAM.get('hd', 'bottom:400px')}'>@withgod.app · find your verse, link in bio</div>"},
]

spec = {'out': str(W / 'reel-silent.mp4'), 'dur': DUR, 'bg': '#14110E',
        'snaps': [0.5, 2.2, 5.0, 10.0, 15.0, 21.0, 26.0, 29.0, 32.5, 35.5, 37.0, 38.5, 41.5, 46.0, 50.5, 54.0, 57.5, 60.0, 63.0, 66.5],
        'shots': shots, 'texts': texts}
(W / 'spec.json').write_text(json.dumps(spec, ensure_ascii=False, indent=1))
x, y, w = CAM['cover']
cover = {'out': str(W / 'cover.mp4'), 'dur': 0.2, 'bg': '#14110E', 'snaps': [0.0],
         'shots': [{'img': ART['a_grave'], 't0': 0, 't1': 0.2, 'cam': [[0, x, y, w]]}],
         'texts': [{'t0': 0, 't1': 1, 'fi': 0, 'raw': True, 'html': TITLE},
                   {'t0': 0, 't1': 1, 'fi': 0, 'pos': P.get('a', 'low'), 'html': HOOK}]}
(W / 'cover-spec.json').write_text(json.dumps(cover, ensure_ascii=False, indent=1))
print('spec ok', DUR)
