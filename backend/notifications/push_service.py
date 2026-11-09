from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path

from notifications.models import DeviceRegistration, PushDispatchResult, PushPayload

log = logging.getLogger("with-god.push")

_BAD_REQUEST_DETAIL = "type.googleapis.com/google.rpc.BadRequest"


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
                        # badge 는 설정하지 않는다: 클라이언트에 배지 클리어 수단이 없어
                        # badge=1 이 앱 아이콘에 영구 잔류하는 문제가 있었다.
                        aps=messaging.Aps(sound="default")
                    ),
                ),
            )
            try:
                messaging.send(message, app=self._app)
                success_count += 1
            except firebase_exceptions.FirebaseError as exc:
                failure_count += 1
                failed_tokens.append(device.token)
                invalid = is_invalid_token_error(exc)
                if invalid:
                    invalid_tokens.append(device.token)
                response = getattr(exc, "http_response", None)
                log.warning(
                    "push: send failed token=%s… platform=%s app=%s %s code=%s http=%s invalid=%s: %s",
                    device.token[:12],
                    device.platform,
                    device.app_version,
                    type(exc).__name__,
                    exc.code,
                    getattr(response, "status_code", None),
                    invalid,
                    exc,
                )
            except Exception:
                failure_count += 1
                failed_tokens.append(device.token)
                log.exception(
                    "push: send failed token=%s… platform=%s (non-Firebase error)",
                    device.token[:12],
                    device.platform,
                )

        if failure_count:
            log.warning(
                "push: sent=%d failed=%d invalid_tokens=%d",
                success_count,
                failure_count,
                len(invalid_tokens),
            )
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


def is_invalid_token_error(exc: Exception) -> bool:
    """FCM 이 「이 토큰으로는 다시 보내도 소용없다」고 답한 오류인지.

    True 면 manager 가 그 기기를 끈다(disable_tokens). 그래서 애매하면 False 다 — 페이로드 오류나
    일시 오류로 멀쩡한 기기를 끄면 그 사용자는 앱을 다시 열 때까지 알림을 못 받는다.
    firebase-admin 7.x 는 에러 코드를 예외 타입으로 준다(str(exc) 는 FCM 메시지 본문이라
    UnregisteredError 도 'NotRegistered' 일 뿐 코드 문자열이 없다).
    - UnregisteredError(NOT_FOUND): 앱 삭제·토큰 폐기
    - SenderIdMismatchError(PERMISSION_DENIED): 다른 Firebase 프로젝트의 토큰
    ThirdPartyAuthError(APNs 인증)는 프로젝트 설정 문제라 iOS 전체가 같이 실패하므로 토큰 탓으로 보지 않는다.
    """
    from firebase_admin import exceptions as firebase_exceptions
    from firebase_admin import messaging

    if isinstance(exc, (messaging.UnregisteredError, messaging.SenderIdMismatchError)):
        return True
    if isinstance(exc, firebase_exceptions.InvalidArgumentError):
        # INVALID_ARGUMENT 는 페이로드 오류(message.data, message.apns.headers.* 등)에도 온다.
        # 토큰 형식 오류만 fieldViolations 의 field 가 message.token 이다. 토큰과 페이로드가
        # 둘 다 틀리면 FCM 은 페이로드 오류를 돌려준다(2026-11 운영 dry_run 확인).
        fields = _field_violations(exc)
        if fields:
            return "message.token" in fields
        return "not a valid FCM registration token" in str(exc)
    return False


def _field_violations(exc: Exception) -> set[str]:
    response = getattr(exc, "http_response", None)
    if response is None:
        return set()
    try:
        details = response.json().get("error", {}).get("details", [])
        return {
            violation.get("field", "")
            for detail in details
            if detail.get("@type") == _BAD_REQUEST_DETAIL
            for violation in detail.get("fieldViolations", [])
        }
    except Exception:
        # 본문이 JSON 이 아니거나 모양이 다르면 판별을 포기한다(발송 루프에서 예외를 내지 않는다).
        return set()


class RetryBackoff:
    """발송에 실패한 기기의 재시도 간격을 늘린다.

    스케줄러는 30초마다 「오늘 아직 못 받은」 기기를 다시 보내므로, 일시 오류(UNAVAILABLE·INTERNAL·
    QUOTA_EXCEEDED)나 원인 모를 실패가 이어지면 기기 하나가 현지 자정까지 하루 2,880번 재발송된다.
    실패할 때마다 간격을 1분 → 2분 → 4분 … 최대 1시간으로 늘리고, 성공하거나 현지 날짜가 바뀌면
    처음으로 돌린다. 장애가 길어도 그날 안에 계속 다시 시도하므로 그날 말씀을 버리지는 않는다.
    상태는 메모리에만 둔다 — 운영은 gunicorn 워커 1개이고, 재시작되면 처음부터 다시 시도할 뿐이다.
    """

    def __init__(
        self,
        first_delay: timedelta = timedelta(minutes=1),
        max_delay: timedelta = timedelta(hours=1),
    ) -> None:
        self.first_delay = first_delay
        self.max_delay = max_delay
        # token → (현지 날짜, 그날 연속 실패 수, 다음 시도 가능 시각)
        self._state: dict[str, tuple[str, int, datetime]] = {}

    def ready(self, token: str, local_date: str, now: datetime) -> bool:
        state = self._state.get(token)
        if state is None:
            return True
        if state[0] != local_date:
            del self._state[token]
            return True
        return now >= state[2]

    def record(self, token: str, local_date: str, now: datetime, failed: bool) -> None:
        if not failed:
            self._state.pop(token, None)
            return
        state = self._state.get(token)
        failures = state[1] + 1 if state and state[0] == local_date else 1
        delay = min(self.first_delay * 2 ** min(failures - 1, 16), self.max_delay)
        self._state[token] = (local_date, failures, now + delay)


class NoopPushGateway(PushGateway):
    def __init__(self, reason: str) -> None:
        self.reason = reason

    def send(self, devices: list[DeviceRegistration], payload: PushPayload) -> PushDispatchResult:
        raise RuntimeError(self.reason)
