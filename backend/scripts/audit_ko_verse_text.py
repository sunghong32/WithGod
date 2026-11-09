# -*- coding: utf-8 -*-
"""verses.csv 본문을 공식 개역한글과 대조해 틀린 절을 고친다 (이슈 #44).

`data/verses.csv`(개역한글 31,084절)는 eBible `kor` 원본에서 왔고, 절 번호 집합이
어긋난 57개 장만 getbible(위키문헌 계열)로 통째 바꿨다(#13). 두 원본 모두 절 안에
오기·누락이 있다 — 잠언 30:19 에서 「반석 위로 기어다니는 뱀의 자취와」가 빠졌고,
위키문헌 계열은 「세례」를 「침례」로 바꿔 두었다.

1. **전수 대조** — bolls.life KRV 와 getbible 을 받아 절마다 비교한다(공백·문장부호 무시).
   둘이 서로 같은데 csv 만 다른 절, 그리고 둘이 서로 다른 절을 후보로 뽑는다.
2. **공식 확인** — 후보가 있는 장만 대한성서공회 공식 온라인 개역한글(version=HAN)을 받는다.
   각주(`a.comment`·`div.D2`)·소제목(`font.smallTitle`)은 뺀다. 요청 사이 1초 쉰다.
3. **고치기** — 공식 본문과 다르고, 독립 출처(bolls 또는 eBible 원본) 하나 이상이 공식과
   같은 절만 고친다. getbible 은 단독 근거로 쓰지 않는다(「침례」 변조).

**표기 변이는 고치지 않는다.** 공식은 「할찌니라·일찌기」, csv 는 대부분 「할지니라」처럼
같은 말을 다르게 적는다(`fold`). 고칠 때도 바뀌는 어절만 공식 본문으로 바꾸고, 나머지
어절의 문장부호·표기는 csv 것을 그대로 둔다. 시편 1절 앞 표제 `(다윗의 시)` 는 eBible 이
붙인 것이고 공식은 소제목이라 비교에서 뺀다. 공회가 두 절을 한 번호로 묶은 곳(「18-19」)은
묶음 전체로 비교하고, 고칠 때는 csv 가 여러 행에 나눠 적은 경계를 그대로 살린다.

개역한글판(1961)은 저작재산권 보호기간이 2011-12-31 에 끝났다(대한성서공회 저작권 안내 표).

    python scripts/audit_ko_verse_text.py                     # 대조만 (기본)
    python scripts/audit_ko_verse_text.py --report audit.tsv  # 후보 전부를 표로
    python scripts/audit_ko_verse_text.py --apply             # verses.csv 에 반영

받은 원본은 `data_raw/text_audit/` 에 남겨 두고 다시 쓴다. 반영한 뒤엔
`scripts/sync_index_with_csv.py --apply` 로 검색 인덱스를 맞출 것.
"""
from __future__ import annotations

import argparse
import csv
import html
import io
import json
import re
import time
import urllib.request
import zipfile
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "data" / "verses.csv"
KOR = ROOT / "data_raw" / "kor_usfm.zip"
CACHE = ROOT / "data_raw" / "text_audit"
DAILY = ROOT / "notifications" / "daily_verses.json"

# bolls 는 장마다(`/get-text/KRV/<책>/<장>/`) 받을 수도 있지만 판본 전체가 zip 하나로 있다.
BOLLS_URL = "https://bolls.life/static/translations/KRV.zip"
GETBIBLE_URL = "https://api.getbible.net/v2/korean.json"
KBS_URL = "https://www.bskorea.or.kr/bible/korbibReadpage.php?version=HAN&book={book}&chap={chap}"
# 공회 사이트는 브라우저가 아니면 본문을 주지 않는다.
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
KBS_DELAY = 1.0
KBS_BOOK = {"JON": "jnh"}  # 공회 책 약어는 정경 코드 소문자 — 요나만 다르다

HANJA = re.compile(r"\([\u3400-\u9fff\uf900-\ufaff·,\s]+\)")  # 하나님의 신(神)은
TITLE = re.compile(r"^\s*\([^)]*\)\s*")  # 시편 1절 앞 표제
# 공회가 두 절을 한 번호로 묶은 곳(신명기 6:18-19)에서 둘째 절 자리에 적힌 것
SAME_AS = re.compile(r"^\((?:\d+|앞)절과\s*(?:같음|동일)\)$")       # csv: (18절과 같음)·(앞절과 동일)
INCLUDED = re.compile(r"^\(\d+절에 포함되어 있음\)$")              # bolls
BOUNDARY = "¶"  # 묶인 절을 이어 붙여 고칠 때 csv 행 경계 표시(한글이 아니라 비교에서 빠진다)
CONTINUED = re.compile(r"\s*\((?:\d+절에서 이어짐|\d+장 \d+절 내용의 계속임).*$")  # csv 의 이어짐 주석

# 같은 말을 달리 적은 것 — 비교할 때만 한쪽으로 모은다. 글자 수가 같은 짝만 쓴다
# (`keyed` 가 글자 위치를 그대로 쓴다). 공식 본문과 csv 를 실제로 맞대어 나온 짝들이다.
SPELLING = [("일찍이", "일찌기"), ("셋째", "세째"), ("넷째", "네째"), ("둘째", "두째"),
            ("꺾", "꺽"), ("깎", "깍"), ("꾼", "군"), ("숫군", "수군"), ("륙", "육"), ("참예", "참여"),
            ("까웠", "까왔"), ("까워", "까와"), ("로웠", "로왔"), ("로워", "로와"),
            ("다웠", "다왔"), ("다워", "다와"),
            ("년", "연"), ("곤란", "곤난"), ("침로", "침노"),           # 두음·ㄴ/ㄹ
            ("맟도", "맞도"), ("이였", "이었"), ("였였", "였었"), ("일컬음", "일컫음"),
            ("잠깐", "잠간"), ("움큼", "웅큼"), ("덮인", "덮힌"), ("흔듦", "흔듬"),
            ("베개", "베게"), ("꿰맬", "꿰멜"), ("머무르", "머므르"), ("지껄이", "지꺼리"),
            ("오랫동", "오래동"), ("기촛돌", "기초돌"), ("윗짝", "위짝"), ("뒷발", "뒤발"),  # 사이시옷
            ("싸와", "싸워")]
# ㄹ 받침 뒤 된소리(할찌니라·할쌔). csv 는 대부분 예사소리로 적는다.
TENSE = {"찌": "지", "찐": "진", "쌔": "새"}


def has_rieul(ch: str) -> bool:
    o = ord(ch) - 0xAC00
    return 0 <= o < 11172 and o % 28 == 8


def plain_tense(s: str) -> str:
    return "".join(TENSE[c] if c in TENSE and i and has_rieul(s[i - 1]) else c
                   for i, c in enumerate(s))


def key(s: str | None) -> str:
    """한글·숫자만 남긴다 — 띄어쓰기·문장부호·한자 병기는 비교하지 않는다."""
    return re.sub(r"[^가-힣0-9]", "", HANJA.sub("", s or ""))


def fold(s: str) -> str:
    for a, b in SPELLING:
        s = s.replace(a, b)
    return plain_tense(s)


def same(a: str | None, b: str | None) -> bool:
    return a is not None and b is not None and fold(key(a)) == fold(key(b))


def ws(s: str) -> str:
    return " ".join(s.split())


def split_title(book: str, verse: int, text: str) -> tuple[str, str]:
    if book == "시편" and verse == 1:
        m = TITLE.match(text)
        if m:
            return m.group(0), text[m.end():]
    return "", text


# ---------- 원본 ----------

def books() -> tuple[list[str], list[str]]:
    src = (ROOT / "languages.py").read_text(encoding="utf-8")

    def grab(name: str) -> list[str]:
        return re.findall(r'"([^"]+)"', re.search(rf"{name} = \[(.*?)\]", src, re.S).group(1))

    return grab("_KO_BOOKS"), grab("_CANON_CODES")


def download(url: str, path: Path, delay: float = 0.0) -> bytes:
    if path.exists():
        return path.read_bytes()
    time.sleep(delay)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def load_bolls(names: list[str]) -> dict[tuple[str, int, int], str]:
    raw = download(BOLLS_URL, CACHE / "KRV.zip")
    z = zipfile.ZipFile(io.BytesIO(raw))
    rows = json.loads(z.read(z.namelist()[0]))
    return {(names[r["book"] - 1], r["chapter"], r["verse"]): ws(re.sub(r"<[^>]+>", " ", r["text"]))
            for r in rows if 1 <= r["book"] <= len(names)}


def load_getbible(names: list[str]) -> dict[tuple[str, int, int], str]:
    data = json.loads(download(GETBIBLE_URL, CACHE / "getbible_korean.json"))
    return {(names[int(b["nr"]) - 1], int(v["chapter"]), int(v["verse"])): ws(v["text"])
            for b in data["books"] for c in b["chapters"] for v in c["verses"]}


def load_ebible(names: list[str], codes: list[str]) -> dict[tuple[str, int, int], str]:
    """eBible `kor` USFM 원본 — 한 절이 여러 줄(\\q 등)에 걸칠 수 있다."""
    name_of = dict(zip(codes, names))
    out: dict[tuple[str, int, int], str] = {}
    z = zipfile.ZipFile(KOR)
    for n in z.namelist():
        m = re.search(r"\d\d-([A-Z0-9]{3})", n)
        if not m or m.group(1) not in name_of:
            continue
        text = re.sub(r"\\f .*?\\f\*|\\x .*?\\x\*", " ", z.read(n).decode("utf-8", "replace"), flags=re.S)
        ch, cur = None, None
        for line in text.splitlines():
            if mm := re.match(r"\\c (\d+)", line):
                ch, cur = int(mm.group(1)), None
            elif (mm := re.match(r"\\v (\d+)\S* ?(.*)", line)) and ch:
                cur = (name_of[m.group(1)], ch, int(mm.group(1)))
                out[cur] = mm.group(2)
            elif cur and not re.match(r"\\(id|ide|h|toc\d|mt\d?|s\d?|d)\b", line):
                out[cur] += " " + re.sub(r"^\\\w+\s*", "", line)
    return {k: ws(v) for k, v in out.items()}


def parse_kbs(page: str) -> tuple[dict[int, str], dict[int, int]]:
    """공회 본문 영역(#tdBible1)에서 절 번호와 본문만 뽑는다.

    공회는 몇 곳에서 두 절을 한 번호로 묶는다(신명기 6:18-19). 그 본문은 첫 절에 두고,
    묶인 범위를 {첫 절: 끝 절} 로 따로 돌려준다.
    """
    a = page.find('id="tdBible1"')
    if a < 0:
        return {}, {}
    b = page.find("text-align: center", a)  # 본문 아래 이전·다음 단추
    seg = page[a: page.rfind("<", a, b) if b > 0 else len(page)]
    seg = re.sub(r"<div[^>]*class=D2.*?</div>", " ", seg, flags=re.S | re.I)    # 각주 본문
    seg = re.sub(r"<a[^>]*class=comment.*?</a>", "", seg, flags=re.S | re.I)    # 각주 번호
    seg = re.sub(r'<font class="smallTitle">.*?</font>(?=\s*<br)', " ", seg, flags=re.S)
    seg = re.sub(r'<font class="chapNum">.*?</font>', " ", seg)
    parts = re.split(r'<span class="number">(\d+)(?:-(\d+))?(?:&nbsp;|\s)*</span>', seg)
    verses, spans = {}, {}
    for v, end, body in zip(parts[1::3], parts[2::3], parts[3::3]):
        verses[int(v)] = ws(html.unescape(re.sub(r"<[^>]+>", "", body)))
        if end:
            spans[int(v)] = int(end)
    return verses, spans


def load_kbs(chapters: set[tuple[str, int]], names: list[str], codes: list[str]):
    """→ ({절: 공식 본문}, {묶인 절마다: (책, 장, 첫 절, 끝 절)})"""
    code_of = {n: KBS_BOOK.get(c, c.lower()) for n, c in zip(names, codes)}
    out: dict[tuple[str, int, int], str] = {}
    joined: dict[tuple[str, int, int], tuple[str, int, int, int]] = {}
    todo = sorted(chapters, key=lambda c: (names.index(c[0]), c[1]))
    fetched = 0
    for i, (book, ch) in enumerate(todo, 1):
        path = CACHE / "kbs" / f"{code_of[book]}_{ch}.html"
        if not path.exists():
            fetched += 1
            if fetched % 50 == 1:
                print(f"  공회 본문 받는 중 {i}/{len(todo)} …", flush=True)
        page = download(KBS_URL.format(book=code_of[book], chap=ch), path,
                        delay=KBS_DELAY if not path.exists() else 0).decode("utf-8", "replace")
        verses, spans = parse_kbs(page)
        if not verses:
            raise SystemExit(f"공회 본문을 읽지 못했다: {book} {ch}장 ({path})")
        for v, t in verses.items():
            out[(book, ch, v)] = t
        for v1, v2 in spans.items():
            for v in range(v1, v2 + 1):
                joined[(book, ch, v)] = (book, ch, v1, v2)
    return out, joined


# ---------- 고치기 ----------

def keyed(s: str) -> tuple[str, list[int]]:
    """`key` 와 같은 글자열(표기 변이는 모음)과, 글자마다 원문에서의 위치.
    `fold` 는 글자 수를 바꾸지 않으므로 위치가 그대로 맞는다."""
    hanja = {i for m in HANJA.finditer(s) for i in range(m.start(), m.end())}
    pos = [i for i, c in enumerate(s) if i not in hanja and re.match(r"[가-힣0-9]", c)]
    return fold("".join(s[i] for i in pos)), pos


def patch(old: str, official: str) -> str:
    """공식 본문과 정말 다른 글자만 바꾼다 — 띄어쓰기·표기 변이·문장부호는 csv 그대로.

    글자 단위로 맞춰 보고 다른 토막만 공식 본문의 같은 토막으로 갈아 끼운다.
    빠진 말을 채울 때 띄어쓰기는 공식 본문을 따른다(따로 선 어절이면 앞뒤를 띄운다).
    """
    ok, op = keyed(old)
    kk, kp = keyed(official)
    out, last = [], 0

    def put(text: str) -> None:
        prev = "".join(out)[-1:]
        out.append(plain_tense(prev + text)[len(prev):])  # csv 처럼 할지니·할새

    for tag, i1, i2, j1, j2 in SequenceMatcher(None, ok, kk, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        new = official[kp[j1]: kp[j2 - 1] + 1] if j2 > j1 else ""
        if tag in ("replace", "delete"):
            head, last = old[last: op[i1]], op[i2 - 1] + 1
            if tag == "delete" and 0 < j1 < len(kp) and official[kp[j1 - 1] + 1: kp[j1]] == "":
                # 공식은 붙여 쓴 자리 — 지운 뒤 남는 공백도 지운다(매여 달리니 → 매달리니)
                head = head.rstrip(" ")
                while last < len(old) and old[last] == " ":
                    last += 1
            out.append(head)
            put(new)
            continue
        after_prev = op[i1 - 1] + 1 if i1 else 0         # 앞 글자 바로 뒤
        before_next = op[i1] if i1 < len(op) else len(old)  # 다음 글자 바로 앞
        if not old[after_prev:before_next].strip():
            # csv 쪽 틈이 공백뿐이면 공식 본문의 그 틈(띄어쓰기·괄호)을 그대로 옮긴다 — (셀라)
            seg = official[kp[j1 - 1] + 1 if j1 else 0: kp[j2] if j2 < len(kp) else len(official)]
            if seg.startswith("("):
                seg = " " + seg  # csv 는 괄호 앞을 띄운다 — 피난처시로다 (셀라)
            out.append(old[last:after_prev]); put(seg)
            last = before_next
            continue
        # insert — 앞뒤로 띄어 쓴 말인지 공식 본문에서 본다
        word_start = j1 == 0 or any(c.isspace() for c in official[kp[j1 - 1] + 1: kp[j1]])
        word_end = j2 == len(kp) or any(c.isspace() for c in official[kp[j2 - 1] + 1: kp[j2]])
        if word_start and word_end:      # 따로 선 어절 → 다음 어절 앞에
            if i1 < len(op):
                out.append(old[last:before_next]); put(new + " ")
            else:
                out.append(old[last:]); put(" " + new)
            last = before_next
        elif word_start:                 # 다음 어절의 앞부분
            out.append(old[last:before_next]); put(new)
            last = before_next
        else:                            # 앞 어절의 뒷부분이나 어절 가운데
            out.append(old[last:after_prev]); put(new)
            last = after_prev
    out.append(old[last:])
    return ws("".join(out))


def ref(k: tuple[str, int, int]) -> str:
    return f"{k[0]} {k[1]}:{k[2]}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--apply", action="store_true", help="verses.csv 를 실제로 고친다")
    ap.add_argument("--report", type=Path, help="후보 전부를 TSV 로 쓴다")
    args = ap.parse_args()

    names, codes = books()
    rows = list(csv.DictReader(open(CSV, encoding="utf-8")))
    cur = {(r["book"], int(r["chapter"]), int(r["verse"])): r["text"] for r in rows}
    bolls, gb, eb = load_bolls(names), load_getbible(names), load_ebible(names, codes)

    def body(k, src):
        t = src.get(k)
        return None if t is None else split_title(k[0], k[2], t)[1]

    # 1. 후보: bolls·getbible 이 서로 같은데 csv 만 다르거나, 둘이 서로 다르다.
    cand = {}
    for k in cur:
        b, g, c = body(k, bolls), body(k, gb), body(k, cur)
        if same(b, g):
            if not same(c, b):
                cand[k] = "bolls=getbible≠csv"
        else:
            cand[k] = "bolls≠getbible"
    chapters = {(k[0], k[1]) for k in cand}
    print(f"전체 {len(cur)}절 · 후보 {len(cand)}절 ({len(chapters)}개 장)")

    # 2. 후보가 있는 장만 공식 본문
    kbs, joined = load_kbs(chapters, names, codes)

    # 3. 판정
    groups: dict[str, list] = {k: [] for k in ("고침", "보류", "같음", "표기 변이", "합본 절", "공식에 없음")}
    fixes: dict[tuple[str, int, int], str] = {}

    def revise(old: str, official: str) -> str:
        # 절이 통째로 다르면(이웃 절과 자리가 바뀜·`missing verse`) 공식 본문을 그대로 쓴다
        close = SequenceMatcher(None, fold(key(old)), fold(key(official)), autojunk=False).ratio() >= 0.5
        return patch(old, official) if close else plain_tense(ws(official))

    # 3-1. 공회가 묶은 절 — 묶음 전체로 비교한다. csv 는 본문을 첫 절에 다 두기도 하고
    # 여러 절에 나눠 두기도 했다. 고칠 때는 csv 가 나눈 경계를 살려 그 안에서 고친다
    # (자리표시 행을 늘리지 않는다 — 검색이 「(10절과 같음)」 행을 돌려줄 수 있다).
    def whole(src, book, ch, v1, v2, skip) -> str:
        texts = (body((book, ch, v), src) for v in range(v1, v2 + 1))
        return " ".join(CONTINUED.sub("", t) for t in texts if t and not skip.match(t))

    for book, ch, v1, v2 in sorted({joined[k] for k in cand if k in joined}):
        span = [k for k in cand if joined.get(k) == (book, ch, v1, v2)]
        off, mine = kbs[(book, ch, v1)], whole(cur, book, ch, v1, v2, SAME_AS)
        if same(mine, off):
            groups["합본 절"] += [(k, cand[k], "") for k in span]
            continue
        if not same(whole(bolls, book, ch, v1, v2, INCLUDED), off):
            groups["보류"] += [(k, cand[k], "") for k in span]
            continue
        first = (book, ch, v1)
        title = split_title(book, v1, cur[first])[0]
        parts = [(book, ch, v) for v in range(v1, v2 + 1)
                 if (book, ch, v) in cur and not SAME_AS.match(body((book, ch, v), cur))]
        merged = revise(f" {BOUNDARY} ".join(CONTINUED.sub("", body(k, cur)) for k in parts), off)
        pieces = [ws(t) for t in merged.split(BOUNDARY)]
        if len(pieces) == len(parts) and all(pieces):
            new = dict(zip(parts, pieces))
        else:  # 경계가 무너지면 첫 절에 전부 두고 나머지는 자리표시
            new = {first: ws(merged.replace(BOUNDARY, " "))}
            new.update({(book, ch, v): f"({v1}절과 같음)" for v in range(v1 + 1, v2 + 1) if (book, ch, v) in cur})
        new[first] = title + new[first]
        for k, t in new.items():
            if t != cur[k]:
                fixes[k] = t
                groups["고침"].append((k, cand.get(k, "합본 절"), "bolls"))
        groups["합본 절"] += [(k, cand[k], "") for k in span if k not in fixes]

    for k, why in cand.items():
        off, c = kbs.get(k), body(k, cur)
        if k in joined:
            continue
        if off is None:
            groups["공식에 없음"].append((k, why, ""))
            continue
        if same(c, off):
            groups["같음" if key(c) == key(off) else "표기 변이"].append((k, why, ""))
            continue
        support = [n for n, src in (("bolls", bolls), ("eBible", eb)) if same(body(k, src), off)]
        if not support:
            groups["보류"].append((k, why, ""))
            continue
        title, rest = split_title(k[0], k[2], cur[k])
        new = title + revise(rest, off)
        if not same(split_title(k[0], k[2], new)[1], off):
            raise SystemExit(f"고친 본문이 공식과 다르다: {ref(k)}\n  {new}\n  {off}")
        fixes[k] = new
        groups["고침"].append((k, why, "·".join(support)))

    print("\n판정")
    for g, items in groups.items():
        print(f"  {g:<8} {len(items):>5}절")

    print(f"\n고칠 절 {len(fixes)}개 (근거: 공식 = 독립 출처)")
    for k, why, support in sorted(groups["고침"], key=lambda t: (names.index(t[0][0]), t[0][1:])):
        print(f"  {ref(k)}  [{support}]\n    전: {cur[k]}\n    후: {fixes[k]}")

    print(f"\n보류 {len(groups['보류'])}절 — 공식과 다르지만 bolls·eBible 어느 쪽도 공식과 같지 않다")
    for k, why, _ in sorted(groups["보류"], key=lambda t: (names.index(t[0][0]), t[0][1:])):
        print(f"  {ref(k)}\n    csv : {cur[k]}\n    공식: {kbs.get(k)}\n    bolls: {bolls.get(k)}")

    # 카드 본문은 csv 를 읽지 않고 따로 적혀 있다(docs/verse_picks/*_cards.csv → daily_verses.json).
    hit = []
    for e in json.loads(DAILY.read_text(encoding="utf-8")):
        m = re.match(r"(.+) (\d+):(\d+)(?:-(\d+))?[ab]?$", e["reference"])
        book, ch, v1, v2 = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4) or m.group(3))
        hit += [(e, k) for k in sorted(fixes) if k[0] == book and k[1] == ch and v1 <= k[2] <= v2]
    print(f"\n오늘의 말씀 카드에 걸린 절 {len(hit)}개 — 카드 본문·풀이 검토본은 따로 봐야 한다")
    for e, k in hit:
        print(f"  {e['reference']} ({ref(k)} 고침)\n    카드: {e['text']}")

    if args.report:
        with open(args.report, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter="\t")
            w.writerow(["절", "판정", "후보 사유", "근거", "csv", "공식", "bolls", "getbible", "eBible", "고친 본문"])
            for g, items in groups.items():
                for k, why, support in items:
                    w.writerow([ref(k), g, why, support, cur[k], kbs.get(k, ""), bolls.get(k, ""),
                                gb.get(k, ""), eb.get(k, ""), fixes.get(k, "")])
        print(f"\n표: {args.report}")

    if not args.apply:
        print("\n(대조만 했다. 반영하려면 --apply)")
        return 0

    with open(CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["book", "chapter", "verse", "text"])
        w.writeheader()
        for r in rows:
            k = (r["book"], int(r["chapter"]), int(r["verse"]))
            w.writerow({**r, "text": fixes.get(k, r["text"])})
    print(f"\n{len(fixes)}절 반영 완료 → scripts/sync_index_with_csv.py --apply 로 인덱스를 맞출 것")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
