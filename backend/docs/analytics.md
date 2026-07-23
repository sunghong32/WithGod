# 자체 사용자 지표 (analytics)

Firebase Analytics 는 집계가 최대 하루 늦고 원시 데이터를 꺼내려면 BigQuery 를
붙여야 해서, 어드민 대시보드에 숫자를 바로 꽂아 넣을 수 없다. DAU/WAU/MAU/신규/
리텐션은 사실상 `(날짜, 익명기기ID)` 한 테이블에서 전부 나오므로 직접 수집한다.
**Firebase 는 떼지 않는다** — 자체 수치가 맞는지 대조하는 기준으로 남긴다.

## 구성

```
앱(telemetry SDK) → POST /telemetry/events → SQLite → 롤업 잡 → GET /admin/analytics/*
     배치 전송            검증·레이트리밋       원시+집계     매일 새벽        어드민 웹
```

| 파일 | 역할 |
|---|---|
| `analytics/db.py` | 스키마·커넥션(WAL). 날짜는 전부 **Asia/Seoul 기준** |
| `analytics/schema.py` | 이벤트명 규칙, **파라미터 화이트리스트**(개인정보 차단 지점) |
| `analytics/ingest.py` | 배치 저장. `event_id` PK 로 재전송 멱등 |
| `analytics/rollup.py` | 일별 지표·리텐션 계산, 오래된 원시 이벤트 정리 |
| `analytics/queries.py` | 대시보드 조회. **오늘 값은 실시간 계산** |
| `analytics/routes.py` | 수집 API + 어드민 API |
| `analytics/scheduler.py` | 매일 새벽 롤업(워커 중복 실행은 `job_lock` 으로 차단) |
| `analytics/cli.py` | `python -m analytics.cli rollup` / `overview` |

## 테이블

- `events` — 원시 이벤트. 보관기간이 지나면 삭제된다.
- `device_profile` — 기기별 첫 방문일. **신규 판정의 유일한 근거라 영구 보관.**
- `daily_active` — `(날짜, 기기)`. 모든 활성 지표의 원천. 영구 보관.
- `daily_metrics` / `retention_cohort` — 사전 계산치. 원시 이벤트를 지워도 남는다.

원시 이벤트를 지워도 지표가 유지되는 구조라, 디스크가 빠듯해지면
`ANALYTICS_RAW_RETENTION_DAYS` 만 줄이면 된다.

## 환경변수 (`backend/.env`)

| 키 | 기본값 | 설명 |
|---|---|---|
| `ANALYTICS_DB_PATH` | `data/analytics.sqlite3` | SQLite 경로 |
| `ANALYTICS_RAW_RETENTION_DAYS` | `90` | 원시 이벤트 보관일. 집계치는 영구 |
| `ANALYTICS_ROLLUP_HOUR` | `3` | 롤업 실행 시각(KST) |
| `ANALYTICS_ADMIN_API_KEY` | (없음) | 대시보드 API 키. 없으면 `PUSH_ADMIN_API_KEY` 사용. **둘 다 비면 401 로 잠긴다** |

## 엔드포인트

수집(인증 없음, 레이트리밋으로 보호):

```
POST /telemetry/events
{ "anon_id": "...", "platform": "ios", "app_version": "1.2.0",
  "events": [{ "event_id": "uuid", "name": "verse_save", "ts": "...",
               "session_id": "...", "params": { "source": "daily" } }] }
→ 202 { "accepted": 3, "dropped": 0, "duplicates": 0 }
```

대시보드(`X-API-Key` 필요): `/admin/analytics/` 아래
`overview` · `timeseries?days=` · `retention?cohorts=` · `events?days=` ·
`breakdown?days=` · `POST rollup`(수동 실행)

## 개인정보

- 계정 체계가 없어 **익명 기기 ID(`withgod.deviceId`)만** 다룬다.
- 사용자가 입력한 마음 원문은 앱에서 보내지 않고, 서버도 `params` 키를
  화이트리스트로 걸러 받을 수 없게 해뒀다(`schema.py`). 새 파라미터를 추가할 때
  **개인 내용이 담길 수 있는 키인지 먼저 따질 것.**
- 앱 설정에 "사용 통계 보내기" 토글이 있다. 끄면 큐에 남은 이벤트까지 지운다.
- 스토어 신고: Play Console 데이터 보안 / App Store 개인정보 표기에 "분석" +
  "기기 ID" 항목이 필요하다.

## 운영 시 알아둘 것

- **기기 = 사용자 근사.** 앱을 지웠다 깔면 새 사용자로 잡힌다. 계정이 없는 한
  구조적 한계이고, 대시보드에도 그렇게 적어뒀다.
- 롤업은 웹 프로세스 안 스레드로 돈다. 웹과 분리하고 싶으면 스케줄러를 끄고
  cron 으로 `python -m analytics.cli rollup` 을 걸면 된다.

## 백업

지표 SQLite 와 `device_store.json` 은 한 번 잃으면 복구할 방법이 없다.
`scripts/backup-data.sh` 가 WAL 을 고려한 `.backup` 으로 안전한 사본을 뜨고
tar.gz 로 묶는다(로컬 14일 보관).

> **인스턴스가 통째로 죽으면 로컬 백업도 같이 사라진다.** 같은 EBS 볼륨에만
> 두는 건 백업이 아니다. `BACKUP_S3_BUCKET` 을 반드시 설정할 것.

서버 설치:

```bash
# 1) 오프사이트 버킷 (한 번만)
aws s3 mb s3://with-god-backups --region ap-northeast-2
aws s3api put-public-access-block --bucket with-god-backups \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

# 2) 타이머 등록
sudo cp backend/scripts/systemd/with-god-backup.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now with-god-backup.timer

# 3) 한 번 돌려서 확인
sudo systemctl start with-god-backup.service && journalctl -u with-god-backup -n 20
```

`with-god-backup.service` 안의 `BACKUP_S3_BUCKET` 주석을 풀어야 S3 로 올라간다.
EC2 인스턴스에 S3 쓰기 권한(인스턴스 프로파일)이 없으면 IAM 역할을 먼저 붙여야
한다.

복원:

```bash
tar -xzf with-god-YYYYMMDD-HHMMSS.tar.gz -C /tmp/restore
python3 -c "import sqlite3;print(sqlite3.connect('/tmp/restore/analytics.sqlite3').execute('PRAGMA integrity_check').fetchone())"
# 서비스 중지 → data/ 로 복사 → 재시작
```
