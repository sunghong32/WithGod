"""성화 원본 받기: 렘브란트 「탕자의 귀환」(약 1668, 에르미타주) — 위키미디어 공용 Google Art Project 사본(퍼블릭 도메인)의
3840px 판(3840×5011). 원본(22991×30000)은 너무 커서 3840 으로 충분하다(가장 가까이 가도 폭 780px 창).

    python3 get_art.py <작업폴더>      # → <작업폴더>/art/prodigal-3840.jpg

https://commons.wikimedia.org/wiki/File:Rembrandt_Harmensz_van_Rijn_-_Return_of_the_Prodigal_Son_-_Google_Art_Project.jpg
"""
import sys
import urllib.request
from pathlib import Path

URL = ('https://upload.wikimedia.org/wikipedia/commons/thumb/9/93/'
       'Rembrandt_Harmensz_van_Rijn_-_Return_of_the_Prodigal_Son_-_Google_Art_Project.jpg/'
       '3840px-Rembrandt_Harmensz_van_Rijn_-_Return_of_the_Prodigal_Son_-_Google_Art_Project.jpg')

out = Path(sys.argv[1]) / 'art' / 'prodigal-3840.jpg'
out.parent.mkdir(parents=True, exist_ok=True)
if not out.exists():
    req = urllib.request.Request(URL, headers={'User-Agent': 'withgod-reels/1.0 (painting download)'})
    out.write_bytes(urllib.request.urlopen(req, timeout=120).read())
print(out)
