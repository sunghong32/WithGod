from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from notifications.models import DeviceRegistration, PushDispatchResult, PushPayload


class PushGateway(ABC):
    @abstractmethod
    def send(self, devices: list[DeviceRegistration], payload: PushPayload) -> PushDispatchResult:
        raise NotImplementedError


class FirebasePushGateway(PushGateway):
    def __init__(self, service_account_path: str) -> None:
        try:
            import firebase_admin
            from firebase_admin import credentials
        except ImportError as exc:
            raise RuntimeError(
                "firebase-admin is not installed. Run `pip install firebase-admin` first."
            ) from exc

        if not service_account_path:
            raise RuntimeError("Missing FIREBASE_SERVICE_ACCOUNT_PATH")
        credential_path = Path(service_account_path)
        if not credential_path.exists():
            raise RuntimeError(f"Firebase service account file not found: {credential_path}")

        self._firebase_admin = firebase_admin
        self._credentials = credentials
        self._app = self._get_or_create_app(str(credential_path))

    def send(self, devices: list[DeviceRegistration], payload: PushPayload) -> PushDispatchResult:
        from firebase_admin import exceptions as firebase_exceptions
        from firebase_admin import messaging

        success_count = 0
        failure_count = 0
        invalid_tokens: list[str] = []
        failed_tokens: list[str] = []

        for device in devices:
            message = messaging.Message(
                token=device.token,
                notification=messaging.Notification(title=payload.title, body=payload.body),
                data=payload.data,
                android=messaging.AndroidConfig(
                    priority="high",
                    notification=messaging.AndroidNotification(
                        sound="default",
                        channel_id="daily_verse",
                    ),
                ),
                apns=messaging.APNSConfig(
                    headers={"apns-priority": "10"},
                    payload=messaging.APNSPayload(
                        aps=messaging.Aps(
                            sound="default",
                            badge=1,
                        )
                    ),
                ),
            )
            try:
                messaging.send(message, app=self._app)
                success_count += 1
            except firebase_exceptions.FirebaseError as exc:
                failure_count += 1
                failed_tokens.append(device.token)
                if "registration-token-not-registered" in str(exc):
                    invalid_tokens.append(device.token)
            except Exception:
                failure_count += 1
                failed_tokens.append(device.token)

        return PushDispatchResult(
            success_count=success_count,
            failure_count=failure_count,
            invalid_tokens=invalid_tokens,
            failed_tokens=failed_tokens,
        )

    def _get_or_create_app(self, service_account_path: str):
        from firebase_admin import credentials

        app_name = "with-god-daily-verse"
        try:
            return self._firebase_admin.get_app(app_name)
        except ValueError:
            return self._firebase_admin.initialize_app(
                credentials.Certificate(service_account_path),
                name=app_name,
            )


class NoopPushGateway(PushGateway):
    def __init__(self, reason: str) -> None:
        self.reason = reason

    def send(self, devices: list[DeviceRegistration], payload: PushPayload) -> PushDispatchResult:
        raise RuntimeError(self.reason)
