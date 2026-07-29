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
        language: str = "ko",
        enabled: bool = True,
        schedule_hour: int | None = None,
        schedule_minute: int | None = None,
    ) -> tuple[DeviceRegistration, bool]:
        with self._lock:
            devices = self._read_all()
            now = datetime.now(dt_timezone.utc).isoformat()
            # device_id 가 오면 device_id 기준으로 식별, 없으면 기존대로 token 기준.
            match_index = self._find_index(devices, token=token, device_id=device_id)
            if match_index is not None:
                existing = devices[match_index]
                devices[match_index] = DeviceRegistration(
                    token=token,
                    platform=platform,
                    timezone=timezone,
                    device_id=device_id,
                    app_version=app_version,
                    os_version=os_version,
                    language=language,
                    enabled=enabled,
                    schedule_hour=schedule_hour,
                    schedule_minute=schedule_minute,
                    created_at=existing.created_at or now,
                    updated_at=now,
                    last_daily_sent_on=existing.last_daily_sent_on,
                )
                self._write_all(devices)
                return devices[match_index], False

            created = DeviceRegistration(
                token=token,
                platform=platform,
                timezone=timezone,
                device_id=device_id,
                app_version=app_version,
                os_version=os_version,
                language=language,
                enabled=enabled,
                schedule_hour=schedule_hour,
                schedule_minute=schedule_minute,
                created_at=now,
                updated_at=now,
            )
            devices.append(created)
            self._write_all(devices)
            return created, True

    @staticmethod
    def _find_index(
        devices: list[DeviceRegistration],
        token: str,
        device_id: str = "",
    ) -> int | None:
        # device_id 가 주어지면 우선적으로 device_id 로 매칭(설치 단위 갱신).
        if device_id:
            for index, device in enumerate(devices):
                if device.device_id == device_id:
                    return index
        for index, device in enumerate(devices):
            if device.token == token:
                return index
        return None

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
                    language=device.language,
                    enabled=device.enabled,
                    schedule_hour=device.schedule_hour,
                    schedule_minute=device.schedule_minute,
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
                    language=device.language,
                    enabled=False,
                    schedule_hour=device.schedule_hour,
                    schedule_minute=device.schedule_minute,
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
                language=str(item.get("language", "ko")),
                enabled=bool(item.get("enabled", True)),
                schedule_hour=self._optional_int(item.get("schedule_hour")),
                schedule_minute=self._optional_int(item.get("schedule_minute")),
                created_at=str(item.get("created_at", "")),
                updated_at=str(item.get("updated_at", "")),
                last_daily_sent_on=str(item.get("last_daily_sent_on", "")),
            )
            for item in raw
        ]

    @staticmethod
    def _optional_int(value: object) -> int | None:
        # 하위호환: 기존 항목에는 schedule_* 가 없으므로 None 으로 둔다.
        if value is None:
            return None
        return int(value)

    def _write_all(self, devices: list[DeviceRegistration]) -> None:
        self.path.write_text(
            json.dumps([asdict(device) for device in devices], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
