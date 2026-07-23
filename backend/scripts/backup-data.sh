#!/usr/bin/env bash
#
# WithGod 백엔드 데이터 백업.
#
# 지표(analytics.sqlite3)와 푸시 기기 목록(device_store.json)은 한 번 잃으면
# 복구할 방법이 없다. 인스턴스가 통째로 죽는 경우까지 대비하려면 같은 EBS 볼륨에
# 두는 것으로는 부족하므로, BACKUP_S3_BUCKET 이 설정돼 있으면 S3 로도 올린다.
#
# 사용:
#   ./backup-data.sh                 # 로컬 백업만
#   BACKUP_S3_BUCKET=my-bucket ./backup-data.sh
#
# 설치는 backend/docs/analytics.md 의 "백업" 절 참고.

set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${DATA_DIR:-${BACKEND_DIR}/data}"
NOTIFICATIONS_DIR="${BACKEND_DIR}/notifications"
# /var/backups 는 root 전용이라 서비스 사용자로는 못 쓴다. systemd 유닛이
# StateDirectory 로 만들어 주는 경로를 기본값으로 둔다.
BACKUP_ROOT="${BACKUP_ROOT:-/var/lib/with-god-backup}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"

STAMP="$(date +%Y%m%d-%H%M%S)"
WORK_DIR="$(mktemp -d)"
ARCHIVE="${BACKUP_ROOT}/with-god-${STAMP}.tar.gz"

cleanup() { rm -rf "${WORK_DIR}"; }
trap cleanup EXIT

fail() {
  echo "[backup] FAILED: $*" >&2
  # 서버에 텔레그램 알림 스크립트가 있으면 실패를 알린다(없으면 그냥 넘어간다).
  if [ -x /usr/local/bin/tg-alert ]; then
    /usr/local/bin/tg-alert "🚨 WithGod 백업 실패: $*" || true
  fi
  exit 1
}

mkdir -p "${BACKUP_ROOT}" || fail "백업 디렉터리를 만들 수 없습니다: ${BACKUP_ROOT}"

# --- SQLite: 실행 중인 프로세스가 쓰는 중일 수 있으므로 파일 복사 대신 .backup ---
# (WAL 모드라 .sqlite3 파일만 복사하면 최근 트랜잭션이 빠진 사본이 나온다)
for db in analytics.sqlite3 daily_random.sqlite3; do
  src="${DATA_DIR}/${db}"
  [ -f "${src}" ] || continue
  if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "${src}" ".backup '${WORK_DIR}/${db}'" || fail "${db} 백업 실패"
  else
    # sqlite3 CLI 가 없으면 파이썬 표준 라이브러리로 같은 일을 한다.
    python3 - "$src" "${WORK_DIR}/${db}" <<'PY' || fail "${db} 백업 실패 (python)"
import sqlite3, sys
source = sqlite3.connect(sys.argv[1])
target = sqlite3.connect(sys.argv[2])
with target:
    source.backup(target)
source.close(); target.close()
PY
  fi
done

# --- JSON 저장소: 원자적으로 쓰이므로 그대로 복사해도 안전 ---
for json_file in \
  "${DATA_DIR}/device_store.json" \
  "${DATA_DIR}/verse_interpretations.json" \
  "${NOTIFICATIONS_DIR}/daily_verses.json"
do
  [ -f "${json_file}" ] && cp -p "${json_file}" "${WORK_DIR}/"
done

if [ -z "$(ls -A "${WORK_DIR}")" ]; then
  fail "백업할 파일을 찾지 못했습니다 (DATA_DIR=${DATA_DIR})"
fi

tar -czf "${ARCHIVE}" -C "${WORK_DIR}" . || fail "아카이브 생성 실패"
SIZE="$(du -h "${ARCHIVE}" | cut -f1)"
echo "[backup] ${ARCHIVE} (${SIZE})"

# --- 오프사이트 사본 ---
# 자격증명은 EC2 인스턴스 역할(IMDS)에서 자동으로 온다. 키를 파일에 두지 않는다.
if [ -n "${BACKUP_S3_BUCKET:-}" ]; then
  KEY="with-god/$(basename "${ARCHIVE}")"
  if command -v aws >/dev/null 2>&1; then
    aws s3 cp "${ARCHIVE}" "s3://${BACKUP_S3_BUCKET}/${KEY}" --only-show-errors \
      || fail "S3 업로드 실패"
  else
    # aws CLI 가 없는 서버가 있어 boto3 로도 올릴 수 있게 해둔다.
    # (BACKUP_PYTHON 으로 boto3 가 설치된 인터프리터를 지정한다)
    "${BACKUP_PYTHON:-python3}" - "${ARCHIVE}" "${BACKUP_S3_BUCKET}" "${KEY}" <<'PY' \
      || fail "S3 업로드 실패 (boto3). aws CLI 또는 boto3 가 필요합니다"
import sys
try:
    import boto3
except ImportError:
    sys.exit("boto3 가 설치돼 있지 않습니다")
archive, bucket, key = sys.argv[1:4]
boto3.client("s3").upload_file(archive, bucket, key)
PY
  fi
  echo "[backup] s3://${BACKUP_S3_BUCKET}/${KEY}"
fi

# --- 로컬 보관 정리 (S3 쪽은 버킷 수명주기 규칙에 맡긴다) ---
find "${BACKUP_ROOT}" -name 'with-god-*.tar.gz' -mtime "+${KEEP_DAYS}" -delete

echo "[backup] done"
