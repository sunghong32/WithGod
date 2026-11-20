"""성화 원본 받기(위키미디어 공용 Google Art Project 사본, 둘 다 퍼블릭 도메인).

- 렘브란트 「탕자의 귀환」(약 1668, 에르미타주) — 3840px 판(3840×5011). 원본(22991×30000)은 너무 커서 3840 으로 충분하다.
- 렘브란트 「탕자로 분한 렘브란트와 사스키아」(약 1635, 드레스덴 고전 거장 미술관) — 원본 그대로(3020×3827).
  젊은 렘브란트가 술집의 탕자로 자기 자신을 그린 그림. 첫 장면(「젊을 때 자신을 탕자로 그렸다」)에 쓴다.

    python3 get_art.py <작업폴더>      # → <작업폴더>/art/prodigal-3840.jpg, tavern-3020.jpg

https://commons.wikimedia.org/wiki/File:Rembrandt_Harmensz_van_Rijn_-_Return_of_the_Prodigal_Son_-_Google_Art_Project.jpg
https://commons.wikimedia.org/wiki/File:Rembrandt_-_Rembrandt_and_Saskia_in_the_Scene_of_the_Prodigal_Son_-_Google_Art_Project.jpg
"""
import sys
import urllib.request
from pathlib import Path

ART = {
    'prodigal-3840.jpg': 'https://upload.wikimedia.org/wikipedia/commons/thumb/9/93/'
                         'Rembrandt_Harmensz_van_Rijn_-_Return_of_the_Prodigal_Son_-_Google_Art_Project.jpg/'
                         '3840px-Rembrandt_Harmensz_van_Rijn_-_Return_of_the_Prodigal_Son_-_Google_Art_Project.jpg',
    'tavern-3020.jpg': 'https://upload.wikimedia.org/wikipedia/commons/a/ae/'
                       'Rembrandt_-_Rembrandt_and_Saskia_in_the_Scene_of_the_Prodigal_Son_-_Google_Art_Project.jpg',
}

for name, url in ART.items():
    out = Path(sys.argv[1]) / 'art' / name
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists():
        req = urllib.request.Request(url, headers={'User-Agent': 'withgod-reels/1.0 (painting download)'})
        out.write_bytes(urllib.request.urlopen(req, timeout=120).read())
    print(out)
