# -*- coding: utf-8 -*-
"""설날·추석 양력 날짜표 생성 → `notifications/lunar_holidays.json`.

오늘의 말씀은 절기에 정해진 말씀을 고정한다(`verse_provider.fixed_verse_id`).
양력 절기(새해·성탄)와 부활절은 계산으로 얻지만, 설날(음력 1월 1일)·추석(음력
8월 15일)은 음력이라 표가 필요하다.

**한국 음력 라이브러리(`korean_lunar_calendar`, 한국천문연구원 자료 기반)를 쓴다.
중국 음력 라이브러리를 쓰면 틀린다.** 삭(朔, 새달)이 자정 근처에 걸리는 해에는
한국(UTC+9)이 중국(UTC+8)보다 하루 늦게 새달을 맞기 때문이다. 독립 구현인
`lunardate`(중국 음력)와 2020~2050년을 대조했더니 62개 날짜 중 3개가 달랐다.

    2027 설날  한국 2/7   중국식 2/6
    2028 설날  한국 1/27  중국식 1/26
    2040 추석  한국 9/21  중국식 9/20

나머지 59개는 일치했고, 이미 지난 2023~2026년 날짜는 실제 공휴일과 맞았다.

라이브러리를 서버 의존성으로 두지 않고 표로 커밋하는 이유: 서버 venv 는 손으로
관리하고 있어(requirements 파일 없음) 설치를 빠뜨리면 앱이 기동 시 import 에서
죽고 푸시 스케줄러도 같이 멈춘다. 라이브러리 자체가 2050년까지만 지원하므로
2050년까지의 표와 담는 정보가 같다. **2050년이 가까워지면 다시 돌릴 것.**

    pip install korean-lunar-calendar
    python scripts/build_lunar_holidays.py            # 표 생성
    python scripts/build_lunar_holidays.py --check    # 커밋된 표가 라이브러리와 같은지
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "notifications" / "lunar_holidays.json"

FIRST_YEAR = 2026
LAST_YEAR = 2050  # korean_lunar_calendar 지원 상한

HOLIDAYS = {
    "seollal": (1, 1),   # 설날 — 음력 1월 1일
    "chuseok": (8, 15),  # 추석 — 음력 8월 15일
}


def solar_of(year: int, month: int, day: int) -> date:
    from korean_lunar_calendar import KoreanLunarCalendar

    cal = KoreanLunarCalendar()
    if not cal.setLunarDate(year, month, day, False):
        raise ValueError(f"음력 {year}-{month}-{day} 를 양력으로 바꿀 수 없다")
    return date.fromisoformat(cal.SolarIsoFormat())


def build() -> dict:
    table: dict = {
        "_source": (
            "korean_lunar_calendar (한국천문연구원 음력 자료) — "
            "scripts/build_lunar_holidays.py 로 생성. 손으로 고치지 말 것."
        ),
    }
    for name, (m, d) in HOLIDAYS.items():
        table[name] = {
            str(y): solar_of(y, m, d).isoformat() for y in range(FIRST_YEAR, LAST_YEAR + 1)
        }
    return table


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="커밋된 표가 라이브러리 계산과 같은지만 본다")
    args = ap.parse_args()

    fresh = build()
    if args.check:
        current = json.loads(OUT.read_text(encoding="utf-8"))
        bad = [
            (name, y, current.get(name, {}).get(y), iso)
            for name in HOLIDAYS
            for y, iso in fresh[name].items()
            if current.get(name, {}).get(y) != iso
        ]
        if bad:
            for name, y, got, want in bad:
                print(f"✗ {name} {y}: 표 {got} / 계산 {want}")
            return 1
        print(f"✓ 표와 계산이 일치한다 ({FIRST_YEAR}~{LAST_YEAR}, {len(HOLIDAYS)}개 절기)")
        return 0

    OUT.write_text(json.dumps(fresh, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"→ {OUT}")
    for name in HOLIDAYS:
        first = list(fresh[name].items())[:3]
        print(f"  {name}: " + " · ".join(f"{y} {iso}" for y, iso in first) + " …")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
