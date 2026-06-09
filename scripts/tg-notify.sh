#!/usr/bin/env bash
# scripts/tg-notify.sh
# 에이전트(또는 사람)가 긴 작업을 "시작하기 전/끝난 후" 텔레그램으로 즉시 알림을 보낼 때 사용.
#
# 텔레그램 브릿지(~/.local/share/tg-claude-bridge/bot.py)는 claude -p 가 완전히
# 끝나야만 결과를 회신한다. 그래서 EAS 빌드처럼 오래 걸리는 작업을 시작하면
# 그 사이 사용자는 진행 사실을 모른다. 이 스크립트로 에이전트가 직접 알림을 push 한다.
#
# 사용:
#   ./scripts/tg-notify.sh "🛠 EAS iOS 빌드 시작합니다 (10~40분 소요 예상). 끝나면 다시 알릴게요."
#
# 자격증명은 레포 루트의 .env (gitignore 됨) 에서 읽는다:
#   TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_CHAT_IDS (CSV) 또는 TELEGRAM_CHAT_ID
# best-effort: 실패해도 exit 0 에 가깝게 — 본 작업을 막지 않는다.

set -uo pipefail

MSG="${1:-}"
if [ -z "$MSG" ]; then
  echo "usage: $0 <message>" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "[tg-notify] .env 없음: $ENV_FILE (알림 건너뜀)" >&2
  exit 0
fi

TOKEN=$(grep -E '^TELEGRAM_BOT_TOKEN=' "$ENV_FILE" | head -1 | cut -d= -f2-)
IDS=$(grep -E '^TELEGRAM_ALLOWED_CHAT_IDS=' "$ENV_FILE" | head -1 | cut -d= -f2-)
[ -n "${IDS}" ] || IDS=$(grep -E '^TELEGRAM_CHAT_ID=' "$ENV_FILE" | head -1 | cut -d= -f2-)

if [ -z "${TOKEN}" ] || [ -z "${IDS}" ]; then
  echo "[tg-notify] TOKEN 또는 CHAT_ID 미설정 (알림 건너뜀)" >&2
  exit 0
fi

IFS=',' read -ra CHATS <<< "$IDS"
for chat in "${CHATS[@]}"; do
  chat="$(echo "$chat" | xargs)"   # 공백 제거
  [ -n "$chat" ] || continue
  curl -s -o /dev/null --max-time 15 \
    "https://api.telegram.org/bot${TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${chat}" \
    --data-urlencode "text=${MSG}" \
    --data-urlencode "disable_web_page_preview=true" \
    || echo "[tg-notify] 전송 실패 (chat=${chat}) — 무시하고 계속" >&2
done
exit 0
