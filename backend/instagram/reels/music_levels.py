"""악기별 크기 재기 — events.json 의 악기를 하나씩 따로 렌더해(같은 mix·잔향·뱅크) 섞였을 때 각각 얼마나 큰지 본다.
사용: python3 music_levels.py events.json [시작초 길이초]   (기본: 전 구간)

소리 뱅크마다 악기별 크기가 크게 달라서(GeneralUser 피아노는 내장 GS 보다 ~20dB 큼) 편성·뱅크를 바꾸면 귀로 듣기 전에 이걸로
먼저 맞춘다. 기준(마르다 비교 샘플, 11/26): 선율 0 > 기타 −3 > 베이스 −4 > 드럼 −9 > 패드 −12dB 쯤. 선율이 가장 커야 한다.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
song = json.loads(Path(sys.argv[1]).read_text())
if isinstance(song, list):
    song = {'events': song}
win = ['-ss', sys.argv[2], '-t', sys.argv[3]] if len(sys.argv) > 3 else []
total = max(e['t'] + e['dur'] for e in song['events']) + 0.6
rows = []
with tempfile.TemporaryDirectory() as d:
    for inst in sorted({e['inst'] for e in song['events']}):
        one = dict(song, events=[e for e in song['events'] if e['inst'] == inst])
        js, wav = Path(d) / f'{inst}.json', Path(d) / f'{inst}.wav'
        js.write_text(json.dumps(one))
        subprocess.run(['swift', HERE / 'music.swift', js, wav, str(total)], check=True, capture_output=True)
        err = subprocess.run(['ffmpeg', '-hide_banner', *win, '-i', wav, '-af', 'volumedetect', '-f', 'null', '-'],
                             capture_output=True, text=True).stderr
        mean = float(next(x for x in err.splitlines() if 'mean_volume' in x).split(':')[1].split()[0])
        rows.append((mean, inst, len(one['events'])))
top = max(r[0] for r in rows)
for mean, inst, n in sorted(rows, reverse=True):
    print(f'{inst:10} {mean:6.1f} dB  ({mean - top:+5.1f})  {n} 음')
