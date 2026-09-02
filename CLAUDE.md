# WithGod — 프로젝트 가이드 (에이전트용)

이 저장소는 **모노레포**입니다.

| 폴더 | 내용 |
|---|---|
| `WithGod/` | React Native (Expo) 모바일 클라이언트 |
| `backend/` | FastAPI 백엔드 (gunicorn + uvicorn worker). 오늘의 말씀 추천/푸시 스케줄러 포함 |
| `withgod-web/` | 웹 |

- 배포 기준 브랜치: **`app-develop`**.
- 백엔드 운영 서버 접속/배포 절차 등 민감한 인프라 정보는 이 파일에 적지 않습니다(이 레포는 공개). 필요한 값은 각 폴더의 `.env`(gitignore됨)에서 읽으세요.

> ⚠️ **이 파일은 `CLAUDE.md` 와 `AGENTS.md` 두 벌로 존재합니다.**
> Claude Code 는 `CLAUDE.md` 를, Codex 는 `AGENTS.md` 를 읽습니다.
> **한쪽을 고치면 반드시 다른 쪽도 같이 고칠 것.** 내용은 완전히 같아야 하고,
> 유일하게 다른 곳은 아래 텔레그램 브릿지 문단의 경로·명령어(`claude` ↔ `Codex`)뿐입니다.
> 확인: `diff CLAUDE.md AGENTS.md` → 그 한 줄만 나와야 정상입니다.



## ⚠️ 작업 시작 전 필독 (반드시)

작업을 시작하기 전에 **[docs/STATUS.md](docs/STATUS.md) 를 반드시 먼저 읽을 것.**
이 저장소의 지금 상태와 앞으로 할 일이 모두 거기 있다.

**작업을 완료하면 `docs/STATUS.md` 를 갱신할 것** — 「지금 상태」·「진행/예정」과
「최근 변경 이력」에 무엇을·왜 했는지 한 줄. 새 개선 항목은 「앞으로 할 일」에 넣는다.
갱신하지 않으면 다음 세션이 낡은 정보로 일하게 된다.

> 변하지 않는 규칙은 이 파일에, 변하는 진행 상황은 docs/STATUS.md 에 쓴다.
> 이 파일이 자주 바뀌면 프롬프트 캐시가 깨져 토큰을 더 쓴다.
> 자세한 운영 방식은 [docs/컨텍스트관리_가이드.md](docs/컨텍스트관리_가이드.md).
> **`docs/STATUS.md` 는 20KB 아래로 유지한다.** 이 파일은 세션이 시작될 때마다 통째로
> 주입되므로 커질수록 매 요청이 비싸진다. 완료된 작업 이력은 `CHANGELOG.md` 나
> git history 로 넘기고, 여기에는 **지금 상태와 앞으로 할 일만** 남긴다.

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
