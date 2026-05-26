from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone as dt_timezone
from pathlib import Path
from threading import Lock

from notifications.models import DeviceRegistration, MobilePlatform


class DeviceStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def list_devices(self) -> list[DeviceRegistration]:
        with self._lock:
            return self._read_all()

    def list_enabled_devices(self) -> list[DeviceRegistration]:
        return [device for device in self.list_devices() if device.enabled]

    def upsert(
        self,
        token: str,
        platform: MobilePlatform,
        timezone: str,
        device_id: str = "",
        app_version: str = "",
        os_version: str = "",
        enabled: bool = True,
    ) -> tuple[DeviceRegistration, bool]:
        with self._lock:
            devices = self._read_all()
            now = datetime.now(dt_timezone.utc).isoformat()
            for index, device in enumerate(devices):
                if device.token != token:
                    continue
                devices[index] = DeviceRegistration(
                    token=token,
                    platform=platform,
                    timezone=timezone,
                    device_id=device_id,
                    app_version=app_version,
                    os_version=os_version,
                    enabled=enabled,
                    created_at=device.created_at or now,
                    updated_at=now,
                    last_daily_sent_on=device.last_daily_sent_on,
                )
                self._write_all(devices)
                return devices[index], False

            created = DeviceRegistration(
                token=token,
                platform=platform,
                timezone=timezone,
                device_id=device_id,
                app_version=app_version,
                os_version=os_version,
                enabled=enabled,
                created_at=now,
                updated_at=now,
            )
            devices.append(created)
            self._write_all(devices)
            return created, True

    def delete(self, token: str) -> bool:
        with self._lock:
            devices = self._read_all()
            remaining = [device for device in devices if device.token != token]
            changed = len(remaining) != len(devices)
            if changed:
                self._write_all(remaining)
            return changed

    def mark_sent(self, token: str, local_date: str) -> None:
        with self._lock:
            devices = self._read_all()
            changed = False
            for index, device in enumerate(devices):
                if device.token != token:
                    continue
                devices[index] = DeviceRegistration(
                    token=device.token,
                    platform=device.platform,
                    timezone=device.timezone,
                    device_id=device.device_id,
                    app_version=device.app_version,
                    os_version=device.os_version,
                    enabled=device.enabled,
                    created_at=device.created_at,
                    updated_at=datetime.now(dt_timezone.utc).isoformat(),
                    last_daily_sent_on=local_date,
                )
                changed = True
                break
            if changed:
                self._write_all(devices)

    def disable_tokens(self, tokens: list[str]) -> None:
        if not tokens:
            return
        blocked = set(tokens)
        with self._lock:
            devices = self._read_all()
            changed = False
            now = datetime.now(dt_timezone.utc).isoformat()
            for index, device in enumerate(devices):
                if device.token not in blocked:
                    continue
                devices[index] = DeviceRegistration(
                    token=device.token,
                    platform=device.platform,
                    timezone=device.timezone,
                    device_id=device.device_id,
                    app_version=device.app_version,
                    os_version=device.os_version,
                    enabled=False,
                    created_at=device.created_at,
                    updated_at=now,
                    last_daily_sent_on=device.last_daily_sent_on,
                )
                changed = True
            if changed:
                self._write_all(devices)

    def _read_all(self) -> list[DeviceRegistration]:
        if not self.path.exists():
            return []
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return [
            DeviceRegistration(
                token=item["token"],
                platform=MobilePlatform(item["platform"]),
                timezone=item["timezone"],
                device_id=str(item.get("device_id", "")),
                app_version=str(item.get("app_version", "")),
                os_version=str(item.get("os_version", "")),
                enabled=bool(item.get("enabled", True)),
                created_at=str(item.get("created_at", "")),
                updated_at=str(item.get("updated_at", "")),
                last_daily_sent_on=str(item.get("last_daily_sent_on", "")),
            )
            for item in raw
        ]

    def _write_all(self, devices: list[DeviceRegistration]) -> None:
        self.path.write_text(
            json.dumps([asdict(device) for device in devices], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
