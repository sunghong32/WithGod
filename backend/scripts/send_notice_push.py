# -*- coding: utf-8 -*-
"""AI 장애 사과 푸시 1회 발송 (2026-11, 일회성).

9/18 ~ 11/2 생성 AI 가 멈춰 위로의 말씀이 끊기고 풀이가 한 줄로 나갔다. 알림을 켠 기기에
기기 언어로 사과·개선 안내를 한 번 보낸다. 앱 안의 1회성 팝업(`aiNotice`)과 짝이다.

**운영 서버에서** 서비스와 같은 환경변수로 돌린다(FIREBASE·DEVICE_STORE 경로가 거기 있다).

    set -a; source /etc/with-god-rag.env; set +a
    python scripts/send_notice_push.py                    # 미리보기 — 보내지 않고 대상만 센다
    python scripts/send_notice_push.py --token <TOKEN>    # 한 기기에만 시험 발송
    python scripts/send_notice_push.py --send             # 전체 발송

- 알림을 끈 기기에는 보내지 않는다.
- 기기 현지 시각이 `--hours`(기본 9-21시) 밖이면 건너뛴다. 새벽에 깨우지 않으려는 것이다.
  시간대가 갈리면 나중에 한 번 더 `--send` 하면 된다 — 이미 받은 기기는 기록(`SENT_LOG`)을 보고
  건너뛰므로 두 번 가지 않는다.
- device_store 는 읽기만 한다. 스케줄러가 30초마다 같은 파일을 쓰기 때문에, 죽은 토큰 정리는
  스케줄러에 맡긴다.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from languages import resolve_lang  # noqa: E402
from notifications.models import DeviceRegistration, PushPayload  # noqa: E402

NOTICE_ID = "ai-outage-2026-11"

# 앱 팝업(aiNotice)과 같은 말을 짧게. 앱 문구에 맞춰 외국어는 친근한 2인칭(tu·du)이다.
NOTICE_MESSAGES: dict[str, tuple[str, str]] = {
    "ko": ("그동안 불편을 드려 죄송합니다",
           "AI 기능을 새롭게 개선했어요. 더 깊어진 위로의 말씀을 지금 만나 보세요."),
    "en": ("We're sorry for the inconvenience",
           "We've improved our AI. Come find deeper Words of Comfort today."),
    "es": ("Perdón por las molestias",
           "Hemos mejorado nuestra IA. Descubre hoy unas Palabras de consuelo más profundas."),
    "pt": ("Desculpe pelo transtorno",
           "Melhoramos nossa IA. Descubra hoje um Versículo de conforto ainda mais profundo."),
    "de": ("Entschuldige die Unannehmlichkeiten",
           "Wir haben unsere KI verbessert. Entdecke jetzt noch tiefere Worte des Trostes."),
    "fr": ("Désolés pour la gêne occasionnée",
           "Nous avons amélioré notre IA. Découvre dès maintenant un réconfort plus profond."),
    "it": ("Ci scusiamo per il disagio",
           "Abbiamo migliorato la nostra IA. Scopri ora Parole di conforto ancora più profonde."),
    "pl": ("Przepraszamy za utrudnienia",
           "Ulepszyliśmy naszą AI. Odkryj teraz jeszcze głębsze Słowo pociechy."),
}

DEFAULT_TIMEZONE = "Asia/Seoul"


def build_payload(lang: str) -> PushPayload:
    title, body = NOTICE_MESSAGES.get(lang, NOTICE_MESSAGES["ko"])
    # url 을 주지 않으면 앱이 홈으로 연다 — 홈에서 사과 팝업이 뜬다.
    return PushPayload(
        title=title,
        body=body,
        data={"type": "notice", "noticeId": NOTICE_ID, "title": title, "body": body},
    )


def local_hour(device: DeviceRegistration, now: datetime) -> int:
    try:
        tz = ZoneInfo(device.timezone or DEFAULT_TIMEZONE)
    except (ZoneInfoNotFoundError, ValueError):
        tz = ZoneInfo(DEFAULT_TIMEZONE)
    return now.astimezone(tz).hour


def select_targets(
    devices: list[DeviceRegistration],
    already_sent: set[str],
    now: datetime,
    hours: tuple[int, int],
) -> tuple[list[DeviceRegistration], list[DeviceRegistration]]:
    """(지금 보낼 기기, 현지 시각이 밖이라 미룬 기기). 알림 끔·이미 받은 기기는 둘 다에서 뺀다."""
    start, end = hours
    ready: list[DeviceRegistration] = []
    deferred: list[DeviceRegistration] = []
    seen: set[str] = set()
    for device in devices:
        if not device.enabled or not device.token:
            continue
        if device.token in already_sent or device.token in seen:
            continue
        seen.add(device.token)
        if start <= local_hour(device, now) < end:
            ready.append(device)
        else:
            deferred.append(device)
    return ready, deferred


def load_sent(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return set(json.loads(path.read_text(encoding="utf-8")).get(NOTICE_ID, []))


def save_sent(path: Path, tokens: set[str]) -> None:
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    data[NOTICE_ID] = sorted(tokens)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_hours(raw: str) -> tuple[int, int]:
    start, end = (int(part) for part in raw.split("-", 1))
    if not 0 <= start < end <= 24:
        raise argparse.ArgumentTypeError("--hours 는 9-21 꼴(0 <= 시작 < 끝 <= 24)")
    return start, end


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--send", action="store_true", help="실제로 보낸다(없으면 미리보기)")
    parser.add_argument("--token", action="append", default=[], help="이 토큰에만 보낸다(시험용, 여러 번 가능)")
    parser.add_argument("--hours", type=parse_hours, default=(9, 21), help="보낼 현지 시각 범위(기본 9-21)")
    args = parser.parse_args()

    from notifications.device_store import DeviceStore
    from settings import AppSettings

    settings = AppSettings.from_env()
    store = DeviceStore(settings.device_store_path)
    sent_log = Path(settings.device_store_path).with_name("notice_push_sent.json")
    now = datetime.now(ZoneInfo(DEFAULT_TIMEZONE))

    if args.token:
        wanted = set(args.token)
        # 시험 발송은 기록도 시각 범위도 보지 않는다 — 본발송 때 그 기기도 정상으로 한 번 받는다.
        targets = [d for d in store.list_devices() if d.token in wanted]
        deferred: list[DeviceRegistration] = []
        missing = wanted - {d.token for d in targets}
        if missing:
            print(f"device_store 에 없는 토큰 {len(missing)}개는 건너뜀")
    else:
        already_sent = load_sent(sent_log)
        targets, deferred = select_targets(store.list_devices(), already_sent, now, args.hours)
        print(f"이미 받은 기기 {len(already_sent)}대는 제외")

    by_lang: dict[str, list[DeviceRegistration]] = {}
    for device in targets:
        by_lang.setdefault(resolve_lang(device.language), []).append(device)

    print(f"지금 보낼 대상 {len(targets)}대 · 현지 시각이 {args.hours[0]}-{args.hours[1]}시 밖이라 미룬 기기 {len(deferred)}대")
    for lang, group in sorted(by_lang.items()):
        title, body = NOTICE_MESSAGES.get(lang, NOTICE_MESSAGES["ko"])
        print(f"  [{lang}] {len(group)}대 — {title} / {body}")
    if deferred:
        zones = Counter(d.timezone or DEFAULT_TIMEZONE for d in deferred)
        print("  미룬 기기 시간대:", ", ".join(f"{tz} {n}" for tz, n in zones.most_common()))

    if not (args.send or args.token):
        print("미리보기만 했습니다. 보내려면 --send (시험은 --token).")
        return 0
    if not targets:
        return 0

    from notifications.push_service import FirebasePushGateway

    gateway = FirebasePushGateway(settings.firebase_service_account_path)
    delivered: set[str] = set()
    failures = 0
    for lang, group in sorted(by_lang.items()):
        result = gateway.send(group, build_payload(lang))
        failed = set(result.failed_tokens)
        delivered.update(d.token for d in group if d.token not in failed)
        failures += result.failure_count
        print(f"  [{lang}] 성공 {result.success_count} · 실패 {result.failure_count}")

    if not args.token:
        save_sent(sent_log, load_sent(sent_log) | delivered)
    print(f"끝 — 성공 {len(delivered)} · 실패 {failures}"
          + (f" · 미룬 기기 {len(deferred)}대는 나중에 --send 를 한 번 더" if deferred else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
