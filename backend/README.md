# With God RAG

성경 RAG 추천 API와 Android / iOS 오늘의 말씀 푸시 백엔드를 함께 제공하는 FastAPI 프로젝트입니다.

## 주요 기능

- `/recommend`
  - 기분/상태를 입력하면 RAG + Claude(Anthropic)로 말씀 추천
- `/random`
  - 하루 1개 오늘의 말씀 반환
- `/daily-verse`
  - 푸시용 오늘의 말씀 조회
- `/push/devices`
  - 디바이스 FCM 토큰 등록/조회/삭제
- `/push/send/daily-verse`
  - 수동 발송

## 환경 변수

`backend/.env` 를 사용합니다. 이 파일은 Git에 커밋하지 않고 개발자에게 별도로 전달합니다.

```env
ANTHROPIC_API_KEY=
# 생성 모델(추천·코멘트·키워드·제목·풀이). 생략하면 claude-haiku-5-5.
LLM_MODEL=claude-haiku-5-5
# (선택) 오늘의 말씀 풀이(외국어 즉석 생성) 모델. 생략하면 LLM_MODEL. 한국어는 검토본을 쓴다.
# LLM_INTERPRETATION_MODEL=claude-sonnet-5-5
# (선택) 이탈리아어 코멘트만 다른 모델로. 생략하면 LLM_MODEL.
# LLM_MODEL_IT=claude-sonnet-5-5
FIREBASE_SERVICE_ACCOUNT_PATH=secrets/firebase-service-account.json
PUSH_SCHEDULE_HOUR=9
PUSH_SCHEDULE_MINUTE=0
PUSH_DEFAULT_TIMEZONE=Asia/Seoul
DEVICE_STORE_PATH=data/device_store.json
DAILY_VERSE_STORE_PATH=notifications/daily_verses.json
```

## 실행

```bash
cd backend
uvicorn app:app --reload --port 8000
```

## 배치 실행

운영에서는 내장 스케줄러만 믿지 말고 배치를 같이 두는 편이 맞습니다.

```bash
cd backend
python3 -m notifications.jobs
```

이 배치는 지금 시점에 오전 9시 대상인 기기만 처리합니다.

## React Native 연동

RN 개발자에게 전달할 문서는 아래에 있습니다.

- [`docs/react-native-push-integration.md`](docs/react-native-push-integration.md)
