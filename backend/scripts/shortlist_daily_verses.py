# -*- coding: utf-8 -*-
"""'오늘의 말씀' 후보 압축 — 배제 규칙만으로 거른다.

이전 385개 선정이 실패한 원인은 (1) 위로 키워드 점수로 후보를 만들고
(2) 61권에 균등 배분한 것이다. 키워드는 '평안'이 들어갔다는 이유로
누가복음 10:6(빈 평안)을 끌어왔고, 균등 배분은 룻기·에스라에서 바닥을 긁게
만들었다. 그래서 여기서는 점수를 매기지 않는다. **혼자 떼어놓고 읽을 수 없는
구절을 배제**하기만 하고, 무엇이 좋은지는 사람이 읽고 고른다.

규칙은 오탐(좋은 구절을 버림)을 줄이는 쪽으로 맞춰져 있다. 개역한글은 완결된
문장도 '…것임이요', '…없나니', '…더하시나니' 처럼 연결어미로 끝나므로 어미만
보고 조각으로 판정하면 마태복음 5:4·로마서 8:1 같은 명문이 통째로 날아간다.
--check 로 손큐레이션 목록 회수율을 재서 규칙이 과하지 않은지 확인할 수 있다.

    python scripts/shortlist_daily_verses.py --out docs/daily_verse_candidates.csv --check
"""
from __future__ import annotations

import argparse
import ast
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 1) 사람끼리 주고받는 대화 프레임 — 이야기 속 한 장면이라 혼자 읽히지 않는다.
#    '가라사대·이르시되'(하나님·예수의 말씀 도입)는 남긴다. 내용이 좋을 수 있어
#    사람이 보고 판단하는 편이 낫다.
NARRATIVE = re.compile(
    r"이르되|가로되|대답하되|대답하여|말하되|여짜오되|고하되|아뢰되|묻되|물으니"
    r"|하더라$|하였더라$|이더라$|있더라$|하시더라$|았더라$|었더라$"
)
# 2) 문장이 끊긴 조각. 어미가 아니라 '나열 도중' 신호만 본다 —
#    쉼표로 끝나거나, 조사로 끝나거나, 명백한 연결형으로 끝나는 경우.
FRAGMENT_END = re.compile(
    r"[,·]$|(에게|에서|으로써|보다|과|와|을|를|의|께|이며|하되|시되|커니와|하며)$"
)
# 3) 문맥을 앞 절에 넘기는 시작어.
DEPENDENT_START = ("이는 ", "이에 ", "곧 ", "그런즉 ", "이러므로 ", "그리하면 ",
                   "그러하나 ", "이같이 ", "그 때에 ", "이 날에 ", "그 날에 ")
# 3-1) 지시대명사 시작은 같은 절에 하나님을 가리키는 말이 없을 때만 배제한다
#      (시편의 '저가 너를 그 깃으로 덮으시리니'처럼 주어가 자명한 경우가 많다).
PRONOUN_START = ("저가 ", "그가 ", "저희가 ", "그들이 ", "그를 ", "그의 ")
DIVINE = re.compile(r"여호와|하나님|예수|그리스도|성령|주께서|주는 |주의 |주를 ")

# 4) 고유명사 — 그 이야기를 알아야 읽히는 인명·지명.
#    이스라엘·야곱·유다·시온은 시적 호칭으로 흔히 쓰여 제외하지 않는다.
#    '누가'(의문사)가 인명으로 오인되지 않도록 어절 경계를 본다.
PROPER = re.compile(
    r"(?<![가-힣])("
    r"아브라함|이삭|야곱아|요셉|모세|아론|여호수아|사무엘|사울|다윗|솔로몬|엘리야|엘리사"
    r"|히스기야|요시야|므낫세|아사|웃시야|여호사밧|다니엘|느헤미야|에스라|에스더|모르드개"
    r"|나오미|보아스|기드온|삼손|드보라|라합|베드로|바울|바나바|디모데|디도|실라|스데반"
    r"|아볼로|브리스길라|아굴라|빌레몬|오네시모|빌라도|헤롯|가룟|마르다|나사로"
    r"|애굽|바벨론|앗수르|가나안|블레셋|미디안|아말렉|모압|에돔|사마리아|갈릴리|나사렛"
    r"|베들레헴|가버나움|고린도|에베소|빌립보|데살로니가|안디옥|다메섹|시내산|요단|홍해"
    r"|소돔|고모라|니느웨|바로|고레스|느부갓네살|아합|이세벨|욥이|엘리후|엘리바스"
    r")"
)
# 5) 율법 조항·제의 용어 — 오늘 나에게 건네는 말이 아니다.
CULTIC = re.compile(
    r"번제|소제|속죄제|속건제|화목제|요제|거제|안식년|희년|십일조|할례"
    r"|제사장|레위인|성막|법궤|분향단|지성소|무교병|유월절|초막절|나실인|부정하니"
    r"|수송아지|어린 양을 잡|피를 뿌리|기름을 바르"
)


# 6) 개역한글(1961)이 쓰는 장애·질병 호칭 중 지금은 비하어가 된 말.
#    본문을 고칠 수 없으므로 카드로 내보내지 않는다. '~하고자'의 '고자'가
#    걸리지 않도록 어절 경계를 본다.
SLUR = re.compile(
    r"병신|소경|벙어리|귀머거리|절뚝발이|앉은뱅이|문둥이|난쟁이|불구자"
    r"|(?<![가-힣])고자(?![가-힣])|(?<![가-힣])계집"
)


def ko_name_to_code() -> dict[str, str]:
    """languages.py 의 책 이름·코드 목록을 그대로 읽어 온다.

    import 하면 fastapi 등 서버 의존성이 딸려 오므로 소스만 파싱한다
    (목록의 단일 출처는 languages.py 로 유지).
    """
    src = (ROOT / "languages.py").read_text(encoding="utf-8")

    def grab(name: str) -> list[str]:
        body = re.search(rf"{name} = \[(.*?)\]", src, re.S).group(1)
        return re.findall(r'"([^"]+)"', body)

    return dict(zip(grab("_KO_BOOKS"), grab("_CANON_CODES")))


def curated_refs() -> set[str]:
    """app.py 의 손큐레이션 인기 구절 170개 — 회수율 측정 기준."""
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    i = src.index("_POPULAR_VERSE_REFS = [")
    j = src.index("\n]", i) + 2
    body = src[i + len("_POPULAR_VERSE_REFS = "):j]
    return {f"{b} {c}:{v}" for b, c, v in ast.literal_eval(re.sub(r"#.*", "", body))}


def load_unsuitable() -> set[str]:
    """기존 '위로 카드로 부적합' 분류 결과(이슈 #11) 재사용."""
    path = ROOT / "data" / "langs" / "unsuitable_refs.json"
    if not path.exists():
        return set()
    return set(json.loads(path.read_text(encoding="utf-8"))["unsuitable"])


def reject(text: str, ref_code: str, unsuitable: set[str],
           min_len: int, max_len: int) -> str | None:
    """배제 사유를 돌려준다. 통과면 None."""
    if ref_code in unsuitable:
        return "위로부적합(기존분류)"
    if not (min_len <= len(text) <= max_len):
        return "길이"
    if NARRATIVE.search(text):
        return "서사·대화"
    if PROPER.search(text):
        return "고유명사"
    if CULTIC.search(text):
        return "율법·제의"
    if SLUR.search(text):
        return "비하 표현"
    if text.startswith(DEPENDENT_START):
        return "문맥의존 시작"
    if text.startswith(PRONOUN_START) and not DIVINE.search(text):
        return "지시대명사 시작"
    if FRAGMENT_END.search(re.sub(r"[!?.\s]+$", "", text)):
        return "문장 조각"
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/daily_verse_candidates.csv")
    ap.add_argument("--min-len", type=int, default=8)
    ap.add_argument("--max-len", type=int, default=130)
    ap.add_argument("--check", action="store_true",
                    help="손큐레이션 170개 회수율과 탈락 사유를 함께 출력")
    args = ap.parse_args()

    unsuitable = load_unsuitable()
    name_to_code = ko_name_to_code()
    kept, drops, dropped_ref = [], {}, {}

    with open(ROOT / "data" / "verses.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    for r in rows:
        book, ch, vs = r["book"], int(r["chapter"]), int(r["verse"])
        text = re.sub(r"\([^)]*\)", "", r["text"]).strip()  # 한자 병기 제거
        text = re.sub(r"\s+", " ", text)
        ref = f"{book} {ch}:{vs}"
        code = name_to_code.get(book, "")

        why = reject(text, f"{code} {ch}:{vs}", unsuitable, args.min_len, args.max_len)
        if why:
            drops[why] = drops.get(why, 0) + 1
            dropped_ref[ref] = why
            continue
        kept.append({"book": book, "chapter": ch, "verse": vs,
                     "reference": ref, "text": text})

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["book", "chapter", "verse", "reference", "text"])
        w.writeheader(); w.writerows(kept)

    print(f"전체 {len(rows)}절 → 후보 {len(kept)}절")
    for k, n in sorted(drops.items(), key=lambda kv: -kv[1]):
        print(f"  배제 {k:18s} {n:6d}")

    if args.check:
        pop = curated_refs()
        got = {k["reference"] for k in kept} & pop
        print(f"\n손큐레이션 {len(pop)}개 회수율: {len(got)}/{len(pop)} "
              f"({len(got) / len(pop) * 100:.0f}%)")
        for ref in sorted(pop - got):
            print(f"  탈락 [{dropped_ref.get(ref, '?')}] {ref}")

    print(f"\n→ {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
