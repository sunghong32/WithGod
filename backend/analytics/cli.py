"""수동/크론 실행용 진입점.

    python -m analytics.cli rollup
    python -m analytics.cli overview
"""

from __future__ import annotations

import json
import sys

from analytics import queries
from analytics.db import init_db
from analytics.rollup import run_rollup
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
    elif command == "overview":
        result = queries.get_overview(settings.analytics_db_path)
    else:
        print(f"unknown command: {command}", file=sys.stderr)
        raise SystemExit(2)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
