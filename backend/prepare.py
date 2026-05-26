# prepare.py
import re, zipfile, csv, os, glob
from pathlib import Path

RAW_DIR = Path("data_raw")
OUT_CSV = Path("verses.csv")

BOOK_MAP = {}  # 필요시 'GEN'->'창세기' 같은 맵 작성

def iter_plain_text_files():
    # eBible의 kor_readaloud.zip 같은 "장 단위 텍스트"를 가정
    zips = list(RAW_DIR.glob("*.zip"))
    for z in zips:
        with zipfile.ZipFile(z) as zf:
            for name in zf.namelist():
                if name.lower().endswith(".txt"):
                    yield name, zf.read(name).decode("utf-8", errors="ignore")

def parse_chapter_text(name, text):
    # 파일명에서 책/장 추출 (예: GEN_001.txt → 창세기 1장)
    base = Path(name).stem
    # 파일 네이밍 규칙은 배포본에 따라 다름. 필요시 정규식 수정
    m = re.match(r"([A-Za-z]+)[-_]?(\d+)", base)
    if not m:
        return []
    book_code, chap = m.group(1), int(m.group(2))
    book_name = BOOK_MAP.get(book_code, book_code)

    verses = []
    # 절 구분: "1  태초에 하나님이..." 형태 등. 실제 파일 규격에 맞춰 조정
    for line in text.splitlines():
        line = line.strip()
        mv = re.match(r"^(\d+)\s+(.+)$", line)
        if mv:
            vnum = int(mv.group(1))
            body = mv.group(2).strip()
            verses.append((book_name, chap, vnum, body))
    return verses

def main():
    OUT_CSV.unlink(missing_ok=True)
    os.makedirs(RAW_DIR, exist_ok=True)

    rows = []
    for name, txt in iter_plain_text_files():
        rows.extend(parse_chapter_text(name, txt))

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["book","chapter","verse","text"])
        for r in rows:
            w.writerow(r)

    print(f"Wrote {OUT_CSV} with {len(rows)} rows")

if __name__ == "__main__":
    main()
