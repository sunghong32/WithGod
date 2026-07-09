from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load_dotenv(path: str | Path | None = None) -> None:
    env_path = Path(path) if path else ROOT / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(slots=True)
class AppSettings:
    firebase_service_account_path: str
    device_store_path: str
    daily_verse_store_path: str
    verse_interpretation_store_path: str
    push_schedule_hour: int
    push_schedule_minute: int
    push_default_timezone: str
    scheduler_poll_seconds: int

    @classmethod
    def from_env(cls) -> "AppSettings":
        load_dotenv()
        data_dir = ROOT / "data"
        notifications_dir = ROOT / "notifications"
        return cls(
            firebase_service_account_path=os.getenv(
                "FIREBASE_SERVICE_ACCOUNT_PATH",
                str(ROOT / "secrets" / "firebase-service-account.json"),
            ),
            device_store_path=os.getenv(
                "DEVICE_STORE_PATH",
                str(data_dir / "device_store.json"),
            ),
            daily_verse_store_path=os.getenv(
                "DAILY_VERSE_STORE_PATH",
                str(notifications_dir / "daily_verses.json"),
            ),
            verse_interpretation_store_path=os.getenv(
                "VERSE_INTERPRETATION_STORE_PATH",
                str(data_dir / "verse_interpretations.json"),
            ),
            push_schedule_hour=int(os.getenv("PUSH_SCHEDULE_HOUR", "9")),
            push_schedule_minute=int(os.getenv("PUSH_SCHEDULE_MINUTE", "0")),
            push_default_timezone=os.getenv("PUSH_DEFAULT_TIMEZONE", "Asia/Seoul"),
            scheduler_poll_seconds=int(os.getenv("SCHEDULER_POLL_SECONDS", "30")),
        )
