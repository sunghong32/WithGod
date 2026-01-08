# 신과함께 (WithGod) 앱 세미나 자료

## 발표 개요
- **앱 이름**: 신과함께 (WithGod)
- **플랫폼**: iOS / Android (React Native + Expo)
- **주요 기능**: AI 기반 맞춤형 성경 구절 추천
- **기술 구성**: Frontend (React Native) + Backend (RAG 시스템)

---

# 슬라이드 1: 프로젝트 소개

## 신과함께 (WithGod)

> "당신의 마음에 위로를 전해요"

### 앱 소개
- 사용자의 **기분/고민**을 입력하면
- **AI가 분석**하여
- **맞춤형 성경 구절**과 **위로의 메시지**를 추천

### 주요 기능
1. **오늘의 말씀**: 매일 랜덤 성경 구절 제공
2. **맞춤 추천**: 사용자 감정에 맞는 구절 AI 추천
3. **위로 메시지**: 구절과 함께 따뜻한 코멘트 제공

---

# 슬라이드 2: 전체 시스템 아키텍처

## Full Stack Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      CLIENT (Mobile App)                    │
│              React Native + Expo + TypeScript               │
└─────────────────────────────┬───────────────────────────────┘
                              │ REST API
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      SERVER (FastAPI)                       │
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐  │
│  │  /random    │    │ /recommend  │    │  RAG Pipeline   │  │
│  │  (랜덤 구절)  │    │ (AI 추천)     │   │                  │  │
│  └─────────────┘    └──────┬──────┘    │ • Embedding     │  │
│                            │           │ • FAISS Search  │  │
│                            ▼           │ • LLM Generate  │  │
│  ┌─────────────────────────────────┐   └─────────────────┘  │
│  │         Vector DB (FAISS)       │                        │
│  │      성경 31,000절 임베딩 저장       │                        │
│  └─────────────────────────────────┘                        │
│                            │                                │
│                            ▼                                │
│  ┌─────────────────────────────────┐                        │
│  │      LLM (OpenAI gpt-4o-mini)   │                        │
│  │         코멘트 & 태그 생성          │                        │
│  └─────────────────────────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

---

# 슬라이드 3: 왜 React Native인가?

## Flutter vs React Native

### 기술 비교
| 항목 | Flutter | React Native |
|------|---------|--------------|
| **언어** | Dart | JavaScript/TypeScript |
| **렌더링** | 자체 엔진 (Skia) | 네이티브 UI 컴포넌트 |
| **개발사** | Google | Meta (Facebook) |
| **출시** | 2018 | 2015 |

### React Native 선택 이유

**1. 웹 개발자 친화적 생태계**
- JavaScript/TypeScript 기반 → 웹 개발 경험 활용 가능
- React 패턴 그대로 사용 (Hooks, Context, JSX)
- npm 생태계의 방대한 라이브러리 활용

**2. 네이티브 UI 철학**
- 플랫폼 네이티브 컴포넌트 사용 → iOS는 iOS답게, Android는 Android답게
- Flutter는 자체 렌더링 → 플랫폼 느낌이 다를 수 있음

**3. 점진적 도입 용이**
- 기존 네이티브 앱에 부분 적용 가능 (Brownfield)
- 네이티브 모듈 연동이 상대적으로 수월

**4. Expo의 강력한 DX**
- 빌드/배포 자동화 (EAS Build)
- OTA 업데이트 (앱스토어 심사 없이 즉시 배포)
- 다양한 기본 제공 API (카메라, 위치, 알림 등)

**5. 실제 사용 기업**
- Meta (Facebook, Instagram, Messenger)
- Microsoft (Outlook, Teams)
- Shopify, Discord, Pinterest

> "익숙한 기술로 빠르게 시작하고, 네이티브 경험을 유지하자"

---

# 슬라이드 4: 기술 스택 개요

## Technology Stack

### Frontend (Mobile App)
| 분류 | 기술 |
|------|------|
| **Framework** | React Native 0.81 + Expo 54 |
| **Language** | TypeScript 5.9 |
| **Routing** | Expo Router (파일 기반) |
| **상태관리** | Zustand + React Query |
| **API 통신** | Axios |
| **데이터 검증** | Zod |

### Backend (AI Server)
| 분류 | 기술 |
|------|------|
| **Framework** | FastAPI (Python) |
| **Embedding** | SentenceTransformer (multilingual-e5-base) |
| **Vector DB** | FAISS (IndexFlatIP) |
| **LLM** | OpenAI gpt-4o-mini |
| **데이터** | 성경 KR1910 (약 31,000절) |

---

# 슬라이드 5: RAG란 무엇인가?

## Retrieval-Augmented Generation

### 왜 RAG인가?

**LLM 단독 생성의 한계**
- 최신 정보 반영 어려움
- 도메인 지식 정확성 부족
- 근거 없는 응답 (Hallucination) 가능
- 특정 문헌(성경)에 대한 직접 참조 불가

**RAG의 해결책**
- 외부 지식 **검색(Retrieval)** + LLM **생성(Generation)** 결합
- 도메인 DB 기반 검색으로 응답 정확성 향상
- 성경 본문을 근거로 신뢰도 높은 응답 제공

### RAG 핵심 구성 요소
1. **벡터 임베딩** - 텍스트를 벡터로 변환
2. **벡터 DB** - 효율적 인덱싱/검색
3. **검색 (Retrieval)** - 질의와 유사한 텍스트 검색
4. **생성 (Generation)** - 검색된 정보 기반 LLM 응답

---

# 슬라이드 6: RAG 파이프라인 상세

## 3단계 파이프라인

```
┌─────────────────────────────────────────────────────────────┐
│ 1. INDEXING (사전 준비)                                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  성경 원문 → 절 단위 Chunking → Embedding → FAISS 저장       │
│                                                              │
│  • 청킹 전략: "성경 한 절 = 하나의 chunk"                     │
│  • 임베딩 모델: multilingual-e5-base                         │
│  • 저장: FAISS IndexFlatIP (약 31,000 벡터)                  │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. RETRIEVAL (검색)                                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  사용자 입력 → Query 임베딩 → FAISS 유사도 검색 → Top-K 결과  │
│                                                              │
│  • 입력: "오늘 너무 힘들어요"                                 │
│  • 검색: 코사인 유사도 기반 Top-5 성경 구절                   │
└─────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. GENERATION (생성)                                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  검색 결과(Context) + Prompt → LLM → 최종 응답               │
│                                                              │
│  • 검색된 5개 구절 중 최적 3개 선택                           │
│  • 각 구절에 맞는 위로 코멘트 생성                            │
│  • 태그 생성 (소망, 위로, 평안 등)                            │
└─────────────────────────────────────────────────────────────┘
```

---

# 슬라이드 7: Indexing 단계 상세

## 성경 데이터 벡터화

### 1. 문서 준비 (prepare.py)
```python
# 장 단위 텍스트를 절 단위로 파싱
def parse_chapter_text(name, text):
    for line in text.splitlines():
        # "1 태초에 하나님이 천지를 창조하시니라"
        mv = re.match(r"^(\d+)\s+(.+)$", line)
        if mv:
            vnum = int(mv.group(1))
            body = mv.group(2).strip()
            # 성경 한 절 = 하나의 chunk
            verses.append((book_name, chap, vnum, body))
    return verses
```

### 2. 임베딩 생성 (index.py)
```python
# SentenceTransformer 기반 임베딩
model = SentenceTransformer("intfloat/multilingual-e5-base")

# E5 모델 권장 방식: passage: prefix
passages = [f"passage: {t}" for t in df["clean"].tolist()]
emb = model.encode(passages, normalize_embeddings=True)
```

### 3. FAISS 인덱스 생성
```python
# 정규화된 벡터 + Inner Product = 코사인 유사도
index = faiss.IndexFlatIP(emb.shape[1])
index.add(emb)
faiss.write_index(index, "bible.faiss")
```

---

# 슬라이드 8: Retrieval & Generation 단계

## 검색 및 생성

### Retrieval (검색)
```python
# 사용자 입력을 query: prefix로 임베딩
q = model.encode([f"query: {mood}"], normalize_embeddings=True)

# FAISS에서 Top-K 검색
D, I = index.search(q, TOP_K)  # TOP_K = 5

# 검색 결과를 후보군으로 구성
for score, idx in zip(D[0], I[0]):
    row = df.iloc[int(idx)]
    candidates.append({
        "ref": f"{row['book']} {row['chapter']}:{row['verse']}",
        "text": row["text"],
        "score": float(score)
    })
```

### Generation (LLM 생성)
```python
system_prompt = """
당신은 한국어만 사용하는 목회적 상담 도우미입니다.
항상 따뜻하고 공감적인 어휘를 사용하세요.
"""

user_prompt = f"""
사용자 기분/상태: "{mood}"
후보 성경 구절(5개): {candidates}

요청:
1) 가장 적절한 성경 구절 3개만 선택
2) 각 구절에 대한 위로 comment 생성
3) 태그 생성
4) JSON 배열만 출력
"""
```

---

# 슬라이드 9: Backend API 설계

## FastAPI 엔드포인트

### /random - 랜덤 성경 구절
```
GET /random
Response: { ref, text }
```
- 검색/생성 없이 랜덤 구절 반환
- 가벼운 요청으로 빠른 응답

### /recommend - RAG 기반 추천
```
POST /recommend
Body: { mood: "오늘 너무 힘들어요" }
Response: [
  {
    "ref": "시편 23:1",
    "text": "여호와는 나의 목자시니...",
    "comment": "힘들 때 하나님께 맡기며...",
    "tag": "소망"
  },
  ...
]
```

### 주요 파라미터
- **TOP_K**: 5 (검색할 후보 개수)
- **PICKS**: 3 (최종 선택 개수)
- **temperature**: 0.4 (LLM 창작 억제)
- **response_format**: json_object (구조화 응답)

---

# 슬라이드 10: Frontend 아키텍처

## Feature-based Layered Architecture

```
┌─────────────────────────────────┐
│      Presentation Layer         │
│   (app/ - 화면, 라우팅)          │
└───────────────┬─────────────────┘
                │
┌───────────────▼─────────────────┐
│       Features Layer            │
│  (features/verse - 도메인 로직)  │
│  • API 함수                      │
│  • Zod 스키마                    │
│  • React Query 훅               │
└───────────────┬─────────────────┘
                │
┌───────────────▼─────────────────┐
│        Shared Layer             │
│  • API 클라이언트               │
│  • 공통 훅 & 컴포넌트            │
│  • Zustand 스토어               │
│  • 테마 & 상수                   │
└─────────────────────────────────┘
```

---

# 슬라이드 11: Frontend 폴더 구조

## 프로젝트 구조

```
src/
├── app/                    # 화면 & 라우팅
│   ├── (tabs)/            # 탭 네비게이션
│   │   └── index.tsx      # 메인 홈
│   ├── result.tsx         # 추천 결과
│   └── _layout.tsx        # 루트 레이아웃
│
├── features/              # 기능 모듈
│   └── verse/
│       ├── api/           # API 레이어
│       │   ├── verseApi.ts
│       │   └── schema.ts  # Zod 스키마
│       └── hooks/         # React Query 훅
│
└── shared/                # 공유 리소스
    ├── api/               # Axios 설정
    ├── hooks/             # 커스텀 훅
    ├── stores/            # Zustand
    ├── styles/            # 공통 스타일
    └── lib/               # React Query 설정
```

---

# 슬라이드 12: React Hooks 개요

## Hooks란?

> 함수형 컴포넌트에서 상태와 생명주기를 다루는 함수

### React 16.8 (2019) 이전 vs 이후
```
이전: Class 컴포넌트 필수 (this.state, componentDidMount 등)
     ↓
이후: 함수형 컴포넌트 + Hooks로 동일 기능 구현
     → 코드 간결화, 로직 재사용 용이
```

### 왜 Hooks가 중요한가?
- **React Native의 핵심 패러다임**
- 상태, 사이드 이펙트, 메모이제이션 모두 Hooks로 처리
- 커스텀 훅으로 **비즈니스 로직 재사용**

### 프로젝트에서 사용한 Hooks 분류

| 분류 | 훅 | 용도 |
|------|-----|------|
| **React 기본** | useState, useEffect, useMemo, useCallback | 상태, 효과, 최적화 |
| **React Query** | useQuery, useMutation | 서버 상태 관리 |
| **Expo Router** | useRouter, useLocalSearchParams | 화면 이동, 파라미터 |
| **SafeArea** | useSafeAreaInsets | 노치/홈바 영역 처리 |
| **커스텀** | useKeyboardVisible, useSafeAreaPadding 등 | 비즈니스 로직 추상화 |

---

# 슬라이드 13: React 기본 Hooks

## 핵심 4가지 Hooks

### 1. useState - 상태 관리
```typescript
const [message, setMessage] = useState("");

// 사용자 입력 저장
<TextInput value={message} onChangeText={setMessage} />
```

### 2. useEffect - 사이드 이펙트
```typescript
// 컴포넌트 마운트 시 실행
useEffect(() => {
  // API 호출, 이벤트 리스너 등록 등
  return () => {
    // 클린업 (언마운트 시)
  };
}, [dependencies]);
```

### 3. useMemo - 값 메모이제이션
```typescript
// message가 변경될 때만 재계산
const trimmedMessage = useMemo(() => message.trim(), [message]);
```

### 4. useCallback - 함수 메모이제이션
```typescript
// 불필요한 함수 재생성 방지
const handleSend = useCallback(() => {
  router.push({ pathname: "/result", params: { mood } });
}, [router, mood]);
```

### 메모이제이션이 중요한 이유
- React는 상태 변경 시 **리렌더링** 발생
- 매번 함수/값이 새로 생성되면 **성능 저하**
- useMemo/useCallback으로 **불필요한 재생성 방지**

---

# 슬라이드 14: 상태 관리 전략

## Zustand + React Query

### 역할 분담

| 상태 종류 | 관리 도구 | 예시 |
|----------|----------|------|
| **서버 상태** | React Query | API 응답, 캐싱 |
| **전역 UI 상태** | Zustand | 로딩, 현재 말씀 |
| **로컬 상태** | useState | 입력값, 토글 |

### React Query 설정
```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,  // 5분
      gcTime: 10 * 60 * 1000,    // 10분
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
});
```

---

# 슬라이드 15: Zod 런타임 검증

## TypeScript + Zod

### 문제 상황
- API 응답이 예상과 다를 수 있음
- TypeScript는 **컴파일 타임**에만 검증
- 런타임 에러 발생 가능

### 해결책: Zod 스키마
```typescript
const RecommendOutSchema = z.object({
  mood: z.string(),
  results: z.array(z.object({
    ref: z.string(),
    text: z.string(),
    comment: z.string().optional(),
    tag: z.string().optional(),
  })),
  candidates: z.array(...).nullable().optional(),
});

// 자동 타입 추론
type RecommendOut = z.infer<typeof RecommendOutSchema>;

// API 응답 검증
const data = RecommendOutSchema.parse(apiResponse);
```

### 실제 해결 사례
- API가 `candidates: null` 반환
- `.nullable().optional()` 추가로 해결

---

# 슬라이드 16: 커스텀 훅 패턴

## Platform Abstraction

### 키보드 감지 훅
```typescript
export function useKeyboardVisible() {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const showEvent = Platform.OS === "ios"
      ? "keyboardWillShow"
      : "keyboardDidShow";

    const subscription = Keyboard.addListener(showEvent, () => {
      setIsVisible(true);
    });
    return () => subscription.remove();
  }, []);

  return isVisible;
}
```

### SafeArea 패딩 훅
```typescript
export function useSafeAreaPadding() {
  const insets = useSafeAreaInsets();

  const headerPaddingTop = useMemo(() => {
    return Platform.OS === "android"
      ? (StatusBar.currentHeight ?? 0) + 12
      : insets.top + 12;
  }, [insets.top]);

  return { insets, headerPaddingTop };
}
```

---

# 슬라이드 17: 플랫폼별 처리

## iOS / Android 차이점

### 키보드 처리 전략
```typescript
// iOS: KeyboardAvoidingView 사용
// Android: app.json의 softwareKeyboardLayoutMode: "resize"

if (Platform.OS === "ios") {
  return (
    <KeyboardAvoidingView behavior="padding">
      {content}
    </KeyboardAvoidingView>
  );
}
return content;  // Android는 시스템이 처리
```

### app.json 설정
```json
{
  "android": {
    "softwareKeyboardLayoutMode": "resize"
  }
}
```

### 폰트 설정
```typescript
export const baseFontFamily = Platform.select({
  ios: "System",
  android: "Roboto",
  default: "sans-serif",
});
```

---

# 슬라이드 18: 성능 최적화

## Frontend & Backend 최적화

### Frontend
```typescript
// 1. useCallback - 함수 메모이제이션
const handleSend = useCallback(() => {
  router.push({ pathname: "/result", params: { mood } });
}, [router, mood]);

// 2. useMemo - 값 메모이제이션
const trimmedMessage = useMemo(() => message.trim(), [message]);

// 3. isLoading vs isFetching
const showLoading = isLoading || isFetching;  // refetch도 로딩 표시
```

### Backend (RAG)
- **FAISS**: 서버 없이 파일 기반 인덱스 (경량화)
- **임베딩 정규화**: Inner Product = 코사인 유사도
- **청킹 전략**: 절 단위로 의미적 완결성 확보
- **LLM 설정**: temperature 0.4로 일관성 유지

---

# 슬라이드 19: RAG 기술적 의의

## 연구적 가치

### 1. Hallucination 완화
- 생성 전 **FAISS 벡터 검색**으로 성경 본문 확보
- 검색 결과를 LLM 프롬프트의 **근거(Context)**로 주입
- LLM 단독 생성 대비 근거 없는 응답 가능성 **구조적 감소**

### 2. 의미 기반 검색
- 키워드 매칭이 아닌 **SentenceTransformer 의미 임베딩**
- 자연어 질의 ↔ 성경 구절 간 **의미적 유사도** 검색

### 3. 경량 아키텍처
- 외부 Vector DB 서버 없이 **파일 기반 FAISS**
- 약 3만 절 규모에 적합한 **저비용 구조**

### 4. 확장 가능성
- 모델 재학습 없이 **인덱스 갱신만으로 데이터 업데이트**
- 다른 도메인(정책 문서, 가이드 등)으로 확장 가능

---

# 슬라이드 20: 프로젝트 특징 요약

## 기술 하이라이트

| 영역 | 특징 |
|------|------|
| **AI/ML** | RAG 파이프라인, FAISS 벡터 검색, LLM 생성 |
| **Backend** | FastAPI, SentenceTransformer, 한글 후처리 |
| **Frontend** | React Native + Expo, TypeScript |
| **상태관리** | React Query + Zustand |
| **타입 안정성** | Zod 런타임 검증 |
| **크로스플랫폼** | iOS/Android 동시 지원 |

## 사용된 패턴
- RAG (Retrieval-Augmented Generation)
- Feature-based Layered Architecture
- Custom Hooks Pattern
- Platform Abstraction

---

# 슬라이드 21: 회고 및 배운 점

## 개발 중 이슈 & 해결

### Backend (RAG)
| 이슈 | 해결 |
|------|------|
| LLM Hallucination | RAG 구조로 근거 기반 생성 |
| 검색 정확도 | E5 모델 + query/passage prefix |
| 응답 형식 | JSON response_format 강제 |

### Frontend (React Native)
| 이슈 | 해결 |
|------|------|
| API 파싱 실패 | Zod `.nullable().optional()` |
| Android 키보드 이중 처리 | 플랫폼별 분기 처리 |
| refetch 로딩 미표시 | isFetching 활용 |

## React Native 스터디 후기

### 네이티브 vs 크로스플랫폼
| 항목 | iOS/AOS 네이티브 | React Native |
|------|-----------------|--------------|
| 코드베이스 | 2개 (Swift + Kotlin) | 1개 (TypeScript) |
| 개발 속도 | 플랫폼별 개별 개발 | 동시 개발 가능 |
| 러닝커브 | 각 플랫폼 별도 학습 | 웹 개발자 친화적 |
| 성능 | 최적화 유리 | 대부분 충분 |
| 핫 리로드 | 빌드 필요 | 즉시 반영 |

### 느낀 점
- **Expo의 강력함**: 빌드, 배포, OTA 업데이트가 매우 편리
- **플랫폼 차이**: iOS/Android 동작 차이를 이해하고 분기 처리 필요
- **생산성 향상**: 한 번의 개발로 두 플랫폼 동시 지원

---

# 슬라이드 22: SI 프로젝트 적용 가능성

## 신규 사업에 적용 가능한 역량

### 1. React Native로 신규 앱 프로젝트 수주 가능

```
기존 SI 수주 방식:
  iOS 앱 + Android 앱 = 개발자 2명 이상 필요
  → 인건비 증가, 일정 리스크

React Native 도입 시:
  iOS + Android 동시 개발 = 1명으로 가능
  → 경쟁력 있는 견적, 빠른 납품
```

**SI 관점에서의 장점**
- **견적 경쟁력**: 단일 코드베이스로 인건비 절감
- **납기 단축**: 양 플랫폼 동시 개발로 일정 50% 단축
- **유지보수 효율**: 하나의 코드만 관리
- **고객 만족**: iOS/Android 동일 기능 동시 출시

**수주 가능한 프로젝트 유형**
| 유형 | 예시 |
|------|------|
| 신규 앱 개발 | 고객사 서비스 앱, 사내 업무 앱 |
| 기존 앱 리뉴얼 | 네이티브 → 크로스플랫폼 전환 |
| MVP 빠른 개발 | 스타트업/신사업 PoC |

---

### 2. RAG 기반 AI 프로젝트 수주 가능

```
고객사 요구: "우리 회사 문서 기반으로 AI 챗봇 만들어주세요"
     ↓
RAG 기술로 구현 가능!
  • 고객사 문서 → 벡터화 → 검색 → LLM 답변
  • 모델 학습 없이 문서만 넣으면 바로 서비스 가능
```

**SI에서 RAG가 강력한 이유**
- **빠른 구축**: Fine-tuning 없이 문서만 색인하면 끝
- **쉬운 업데이트**: 문서 변경 시 재색인만 하면 됨
- **비용 효율**: 자체 모델 학습 불필요

**수주 가능한 AI 프로젝트**
| 도메인 | 프로젝트 예시 |
|--------|-------------|
| **금융/보험** | 약관 기반 상담 챗봇 |
| **제조/건설** | 매뉴얼 기반 기술 지원 시스템 |
| **공공기관** | 민원 FAQ 자동 응답 |
| **유통/커머스** | 상품 추천 AI |
| **헬스케어** | 의료 정보 검색 서비스 |

---

### 3. 검증된 기술 스택

```
이번 프로젝트에서 검증 완료한 기술
├── 모바일: React Native + Expo + TypeScript
├── 상태관리: React Query + Zustand + Zod
└── AI: RAG + FAISS + LLM (OpenAI)
    ↓
신규 SI 프로젝트에 즉시 적용 가능!
```

**기술 역량 확보 현황**
- 크로스플랫폼 앱 개발: **실제 앱스토어/플레이스토어 출시 경험**
- RAG 시스템 구축: **31,000건 문서 기반 서비스 운영 경험**
- 전체 파이프라인: **기획 → 개발 → 배포까지 풀스택 경험**

---

# 슬라이드 23: 향후 발전 방향

## 팀 역량 강화 로드맵

### 단기 목표 (3-6개월)
| 목표 | 내용 |
|------|------|
| **RN 역량 확산** | 팀 내 React Native 스터디/세션 진행 |
| **신규 사업 적용** | 차기 앱 프로젝트에 React Native 도입 |
| **RAG 템플릿화** | 재사용 가능한 RAG 보일러플레이트 구축 |

### 중장기 목표 (6-12개월)
| 목표 | 내용 |
|------|------|
| **AI 사업 확대** | RAG 기반 SI 프로젝트 적극 수주 |
| **기술 고도화** | Reranking, Hybrid Search 등 검색 품질 향상 |
| **자체 솔루션** | 문서 기반 AI 챗봇 솔루션 패키지화 |

### 기술 로드맵
| 영역 | 현재 | 목표 |
|------|------|------|
| **Vector DB** | FAISS (파일 기반) | Pinecone/Weaviate (클라우드) |
| **검색** | 단순 유사도 | Reranking + Hybrid Search |
| **LLM** | OpenAI API | Azure OpenAI / 온프레미스 LLM |
| **앱 배포** | 수동 빌드 | EAS + CI/CD 자동화 |

### 기대 효과
```
크로스플랫폼 + AI 역량 확보
     ↓
SI 수주 경쟁력 강화
     ↓
신규 사업 영역 확대 (AI 솔루션)
```

---

# 슬라이드 24: Q&A

## 감사합니다!

### 테스트 환경
- **API**: https://mincha.co.kr/recommend
- **Swagger**: https://mincha.co.kr/docs

### 질문 있으신가요?

---

## 부록: 참고 자료

### Frontend
- [Expo Documentation](https://docs.expo.dev/)
- [React Query Documentation](https://tanstack.com/query)
- [Zod Documentation](https://zod.dev/)
- [Zustand Documentation](https://zustand-demo.pmnd.rs/)

### Backend / AI
- [FAISS Documentation](https://faiss.ai/)
- [SentenceTransformers](https://www.sbert.net/)
- [RAG Indexing Methods](https://thetechbuffet.substack.com/p/rag-indexing-methods)

### 데이터
- 성경 데이터: Korean Revised Version 1910 (Public Domain)
- 총 규모: 약 31,000절
