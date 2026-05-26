from __future__ import annotations

import json
from datetime import datetime

from notifications.device_store import DeviceStore
from notifications.manager import DailyVerseNotificationManager
from notifications.push_service import FirebasePushGateway, NoopPushGateway
from notifications.verse_provider import DailyVerseProvider
from settings import AppSettings


def build_notification_manager(settings: AppSettings) -> DailyVerseNotificationManager:
    store = DeviceStore(settings.device_store_path)
    provider = DailyVerseProvider(settings.daily_verse_store_path)
    try:
        gateway = FirebasePushGateway(settings.firebase_service_account_path)
    except RuntimeError as exc:
        gateway = NoopPushGateway(str(exc))
    return DailyVerseNotificationManager(
        settings=settings,
        device_store=store,
        verse_provider=provider,
        push_gateway=gateway,
    )


def run_daily_verse_batch(now: datetime | None = None) -> dict[str, object]:
    settings = AppSettings.from_env()
    manager = build_notification_manager(settings)
    return manager.send_due_notifications(now=now)


def main() -> None:
    result = run_daily_verse_batch()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
