# With God RAG

성경 RAG 추천 API와 Android / iOS 오늘의 말씀 푸시 백엔드를 함께 제공하는 FastAPI 프로젝트입니다.

## 주요 기능

- `/recommend`
  - 기분/상태를 입력하면 RAG + OpenAI로 말씀 추천
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
OPENAI_API_KEY=
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
