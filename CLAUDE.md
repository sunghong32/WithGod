# WithGod — 프로젝트 가이드 (에이전트용)

이 저장소는 **모노레포**입니다.

| 폴더 | 내용 |
|---|---|
| `WithGod/` | React Native (Expo) 모바일 클라이언트 |
| `backend/` | FastAPI 백엔드 (gunicorn + uvicorn worker). 오늘의 말씀 추천/푸시 스케줄러 포함 |
| `withgod-web/` | 웹 |

- 배포 기준 브랜치: **`app-develop`**.
- 백엔드 운영 서버 접속/배포 절차 등 민감한 인프라 정보는 이 파일에 적지 않습니다(이 레포는 공개). 필요한 값은 각 폴더의 `.env`(gitignore됨)에서 읽으세요.

## ⚠️ 텔레그램 작업 알림 — 긴 작업은 "시작 전에" 먼저 알린다

이 프로젝트는 텔레그램 브릿지(`~/.local/share/tg-claude-bridge/bot.py`)를 통해 작업 지시를 받을 수 있습니다. 브릿지는 `claude -p` 가 **완전히 끝나야** 결과를 회신하는 구조라, 작업 도중 오래 걸리는 명령을 시작하면 사용자는 진행 사실을 알 수 없습니다(내용 없는 하트비트만 보임).

따라서 **수 분 이상 걸릴 수 있는 작업은 실행 직전에 반드시 텔레그램으로 먼저 알립니다.**

대상 예시: `eas build`, `eas submit`, 앱 스토어 제출, `pod install`, 장시간 빌드/테스트, 원격 서버(SSH) 배포, 대용량 다운로드 등.

```bash
# 시작 직전
./scripts/tg-notify.sh "🛠 EAS iOS production 빌드 시작합니다 (10~40분 예상). 끝나면 다시 알릴게요."

# (단계가 여러 개면 단계 전환마다 짧게)
./scripts/tg-notify.sh "📦 빌드 완료 → 이제 스토어 제출(eas submit) 진행합니다."

# 끝난 후 (성공/실패 + 결과 링크 등)
./scripts/tg-notify.sh "✅ iOS 빌드 완료: <빌드 URL>"
```

규칙:
- **빌드/배포/제출은 "올렸다"는 사실 자체를 즉시 알릴 것.** (사용자가 가장 답답해하는 부분)
- 알림 전송이 실패해도 본 작업은 계속 진행한다 (`tg-notify.sh` 는 best-effort).
- 자격증명은 루트 `.env` 의 `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_CHAT_IDS` 를 스크립트가 알아서 읽는다 — 토큰을 코드/로그에 직접 노출하지 말 것.

## 📱 스토어 제출 시 테스트 노트 필수

TestFlight / Play 비공개테스트에 빌드를 제출하면 **테스터가 무엇을 테스트할지 알 수 있게 반드시 테스트 노트를 채운다** (버전별 변경점 + 테스트 포인트 목록).

- **Play**: 제출 직후 `python3 scripts/play_release_notes.py --track alpha --notes "..."` (500자 제한, google-auth 필요 — 키는 backend/secrets/play-submit-key.json)
- **TestFlight**: 제출 직후 `python3 scripts/asc_test_notes.py --wait --notes "..."` (ASC API — 키는 backend/secrets/AuthKey_*.p8 + asc-api-key.json, pyjwt·cryptography 필요. --wait 는 애플 처리 완료까지 폴링)
