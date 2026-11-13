"""수동/크론 실행용 진입점.

    python -m analytics.cli rollup
    python -m analytics.cli rollup-all   # 수집 첫날부터 전부 다시 굳힌다(집계 규칙을 바꾼 뒤 한 번)
    python -m analytics.cli overview
"""

from __future__ import annotations

import json
import sys
from datetime import date

from analytics import queries
from analytics.db import init_db, service_day, session
from analytics.rollup import DEFAULT_LOOKBACK_DAYS, run_rollup
from settings import AppSettings


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "rollup"
    settings = AppSettings.from_env()
    init_db(settings.analytics_db_path)

    if command == "rollup":
        result = run_rollup(
            settings.analytics_db_path,
            raw_retention_days=settings.analytics_raw_retention_days,
        )
    elif command == "rollup-all":
        with session(settings.analytics_db_path) as conn:
            first = conn.execute("SELECT MIN(day) FROM daily_active").fetchone()[0]
        lookback = DEFAULT_LOOKBACK_DAYS
        if first:
            span = (date.fromisoformat(service_day()) - date.fromisoformat(first)).days + 1
            lookback = max(lookback, span)
        result = run_rollup(
            settings.analytics_db_path,
            lookback_days=lookback,
            raw_retention_days=settings.analytics_raw_retention_days,
        )
    elif command == "overview":
        result = queries.get_overview(settings.analytics_db_path)
    else:
        print(f"unknown command: {command}", file=sys.stderr)
        raise SystemExit(2)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
