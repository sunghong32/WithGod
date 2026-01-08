# 성경 말씀 기반 AI RAG 시스템

## **1. 서론**

본 연구는 **한국어 성경** 전체 데이터를 기반으로 RAG 시스템을 구축하고, 사용자의 감정/상태 기반으로 **적절한 성경 말씀을 추천 + 코멘트 생성**이 가능한 **AI RAG 서비스**를 설계·구현하였다.

대규모 언어 모델(LLM)은 뛰어난 자연어 생성 능력을 갖지만, 성경 구절과 같이 **도메인 특화·정형 지식**을 요구하는 영역에서는 정확성과 신뢰성 측면에서 한계를 가진다. 특히 LLM 단독 생성 방식은 근거 없는 응답(hallucination)을 생성할 가능성이 존재한다.

검색 증강 생성(Retrieval-Augmented Generation, RAG)은 외부 지식 검색 결과를 생성 과정에 결합함으로써 이러한 한계를 보완하는 접근 방식이다.

본 연구는 한국어 성경을 기반으로 RAG 구조를 적용한 AI 성경 말씀 추천 시스템을 설계·구현하고, 사용자의 감정/상태에 맞는 성경 구절과 코멘트를 생성하는 것을 목표로 한다.

---

## **2. RAG 개요 및 배경**

### **2.1 RAG란?**

RAG는 **검색(Retrieval)**과 **생성(Generation)**을 결합한 구조로,
사용자 질의와 관련된 외부 지식을 먼저 검색한 뒤 이를 근거로 LLM이 응답을 생성하는 방식이다.

**핵심 구성 요소**

1. **벡터 임베딩(Embeddings)** – 텍스트를 벡터로 변환
2. **벡터 데이터베이스(Vector DB)** – 효율적 인덱싱/검색
3. **검색(Retrieval)** – 질의와 유사한 텍스트 검색
4. **생성(Generation)** – 검색된 정보를 포함해 LLM으로 결과 생성

### **2.2 왜 RAG인가?**

LLM 단독 생성 방식은:

- 최신 정보 반영이 어려움
- 도메인 지식에 대한 정확성 부족
- 근거 없는 응답(hallucination) 가능성
- 특정 문헌(성경 본문)에 대한 직접적 참조 불가

RAG는 이를 보완하며, 도메인 데이터베이스 기반의 검색 + LLM 답변을 합성함으로써 응답의 정확성과 신뢰도를 크게 개선한다.

---

## **3. 시스템 구조**

![참고: [https://thetechbuffet.substack.com/p/rag-indexing-methods](https://thetechbuffet.substack.com/p/rag-indexing-methods)](%EC%84%B1%EA%B2%BD%20%EB%A7%90%EC%94%80%20%EA%B8%B0%EB%B0%98%20AI%20RAG%20%EC%8B%9C%EC%8A%A4%ED%85%9C/6a3cd853-e745-4a86-a2ce-41ffc1e917cf_4380x1454.png)

참고: [https://thetechbuffet.substack.com/p/rag-indexing-methods](https://thetechbuffet.substack.com/p/rag-indexing-methods)

전체 흐름은 **Indexing,** **Retrieval, Generation 단계**로 구분된다.

### **3.1 전체 구조 개요**

시스템은 다음과 같은 파이프라인으로 구성된다.

1. **Indexing**
    - 성경 원문 데이터를 정형화하고 벡터화하여 Vector DB(FAISS)에 저장
2. **Retrieval**
    - 사용자 입력을 벡터로 변환하여 의미적으로 유사한 성경 구절 검색
3. **Generation**
    - 검색된 구절을 근거(context)로 LLM이 추천 말씀과 코멘트를 생성

이 구조를 통해 모델의 환각(hallucination)을 최소화하고, 성경 본문에 기반한 신뢰도 높은 응답을 제공한다.

---

### **3.2 Indexing 단계**

Indexing 단계는 성경 전체 데이터를 **검색 가능한 벡터 형태로 변환**하는 과정이다.

윗 이미지에서 *Document → Chunking → Embedding → Vector DB 저장*에 해당하며,

본 시스템에서는 prepare.py와 index.py가 이 역할을 수행한다.

---

### **① 문서 준비 및 정형화 (prepare.py)**

원천 성경 데이터는 장(chapter) 단위 텍스트로 제공되며,
이를 절(verse) 단위로 파싱하여 (book, chapter, verse, text) 구조의 CSV 파일로 변환한다.

```jsx
# prepare.py
with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["book", "chapter", "verse", "text"])
```

이때 CSV의 **각 행(row)은 성경 한 절**을 의미하며,

이는 이후 RAG 전 과정에서 **하나의 검색 단위(chunk)**로 사용된다.

---

### **② 청크 분리 (Chunking)**

일반적인 RAG 시스템에서는 문서를 문단 또는 문장 단위로 분리하지만,

본 연구에서는 성경의 구조적 특성을 고려하여 **“성경 한 절 = 하나의 청크(chunk)”**로 정의하였다.

이는 문단/문장 단위 청킹보다
검색 결과의 의미적 완결성과 해석 가능성을 높이기 위한 선택이다.

아래 코드는 장 단위 텍스트를 줄 단위로 순회하면서,

각 줄을 하나의 절(청크)로 확정하는 실제 구현 예시이다.

```jsx
# prepare.py
def parse_chapter_text(name, text):
    # 파일명에서 책/장 정보 추출 (예: GEN_001.txt)
    base = Path(name).stem
    m = re.match(r"([A-Za-z]+)[-_]?(\\d+)", base)
    if not m:
        return []

    book_code, chap = m.group(1), int(m.group(2))
    book_name = BOOK_MAP.get(book_code, book_code)

    verses = []

    # 장 텍스트를 줄 단위로 분리
    for line in text.splitlines():
        line = line.strip()

        # "절번호 본문" 형태 파싱
        # 예: "1 태초에 하나님이 천지를 창조하시니라"
        mv = re.match(r"^(\\d+)\\s+(.+)$", line)
        if mv:
            vnum = int(mv.group(1))
            body = mv.group(2).strip()

            # ✅ 이 시점에서 성경 한 절 = 하나의 chunk
            verses.append((book_name, chap, vnum, body))

    return verses
```

이와 같은 방식으로 **청킹 기준이 코드 레벨에서 명확히 고정**되며,

검색 결과는 항상 의미적으로 완결된 성경 절 단위로 반환된다.

---

### **③ 임베딩 생성 (Embedding)**

청킹된 성경 절 텍스트는 SentenceTransformer 기반 임베딩 모델을 통해 벡터로 변환된다.

본 연구에서는 다국어 의미 검색에 적합한

intfloat/multilingual-e5-base 모델을 사용하였다.

**SentenceTransformer 선택 이유**

- 문장/문서 단위 **의미 기반 검색**에 특화
- 한국어를 포함한 다국어 성능 검증
- RAG 검색 목적에 맞게 학습된 E5 계열 모델 사용

E5 모델의 권장 방식에 따라,
문서 임베딩에는 passage: prefix,
질의 임베딩에는 query: prefix를 적용하여
질의–문서 간 의미 정렬을 강화하였다.

```jsx
# index.py
df = pd.read_csv(CSV)

def normalize(s: str) -> str:
    return " ".join(str(s).split())

df["clean"] = df["text"].map(normalize)

model = SentenceTransformer("intfloat/multilingual-e5-base", device="mps")

passages = [f"passage: {t}" for t in df["clean"].tolist()]
emb = model.encode(
    passages,
    batch_size=64,
    show_progress_bar=True,
    normalize_embeddings=True,
).astype("float32")
```

---

### **④ Vector DB 구성 (FAISS Index)**

생성된 임베딩 벡터는 **FAISS(Facebook AI Similarity Search)** 인덱스에 저장된다.

### **FAISS 선택 이유**

- 벡터 유사도 검색에 특화된 고성능 라이브러리
- 별도의 서버 없이 파일 기반으로 운영 가능
- 성경 전체(약 3만 절) 규모에서 빠른 검색 성능 제공

본 시스템에서는 IndexFlatIP 구조를 사용하며,

임베딩 벡터를 정규화(normalize)함으로써

내적(Inner Product) 기반 검색이

사실상 **코사인 유사도 검색**과 동일하게 동작하도록 설계하였다.

```jsx
# index.py
d = emb.shape[1]
index = faiss.IndexFlatIP(d)
index.add(emb)

faiss.write_index(index, IDX)
df[["book", "chapter", "verse", "clean", "text"]].to_parquet(META, index=False)
```

이때 FAISS 인덱스의 벡터 순서(row)는 DataFrame의 행 순서와 1:1로 대응되며,
Retrieval 단계에서 df.iloc[i] 방식으로 즉시 원문 절을 복원할 수 있다.

---

### **3.3 Retrieval 단계**

Retrieval 단계에서는 사용자 입력을 기반으로
의미적으로 가장 유사한 성경 절을 검색한다.

```jsx
# app.py
q = model.encode([f"query: {inp.mood}"], normalize_embeddings=True).astype("float32")
    _lap("encode", t)
    t = time.perf_counter()

    D, I = index.search(q, TOP_K)
    _lap("faiss", t)
    t = time.perf_counter()

    cands = []
    for s, i in zip(D[0], I[0]):
        # FAISS 검색 결과의 인덱스 i는 df의 행 번호와 1:1로 대응
        # 따라서 df.iloc[i]로 실제 성경 본문 데이터를 조회
        r = df.iloc[int(i)]
        cands.append({
            "ref": f"{r['book']} {int(r['chapter'])}:{int(r['verse'])}",
            "text": str(r["text"]),
            "score": float(s)
        })
    _lap("cands", t)
    t = time.perf_counter()
```

### **3.3 Retrieval 단계**

검색된 성경 절들은 LLM 프롬프트의 **근거(context)**로 주입된다.

LLM은 이 근거를 기반으로 다음을 수행한다.

- 가장 적절한 성경 구절 선택
- 사용자 감정에 맞는 코멘트 생성
- 태그(tag) 생성

이를 통해 LLM 단독 생성이 아닌,

**검색 기반·도메인 근거 중심의 응답 생성**이 이루어진다.

```jsx
limits = _style_to_limits(COMMENT_STYLE)
system = (
    "당신은 한국어만 사용하는 목회적 상담 도우미입니다. "
    "항상 따뜻하고 공감적인 어휘를 사용하고, 신학적으로 무난한 표현만 사용하세요. "
    "인용/적용은 균형 있게, 과장이나 단정적 단언은 피하세요."
)
user = _build_user_prompt(inp.mood, cands, PICKS, limits)
_lap("prompt", t)
t = time.perf_counter()
```

## **4. 기능 및 API 설계**

### **4.1 /recommend  api (맞춤 성경 + 코멘트 추천)**

요청: 사용자의 **기분/상태(mood) 텍스트**

답변: 연관 성경 구절 Top-k + 코멘트 + 태그 생성

**주요 흐름**

1. Query 임베딩 생성
2. FAISS에서 Top_K 구절 검색
3. OpenAI API로 **RAG Prompt 생성**
4. JSON 결과 반환

**OpenAI 프롬프트 구조**

사용 예:

```jsx
역할: 당신은 한국어만 사용하는 기독교 상담 도우미입니다.
사용자 기분/상태: "불안하고 잠이 안 와요"
후보 성경 구절(5개):
- 시편 23:1 :: 여호와는 나의 목자시니…
...
요청:
1) 가장 적절한 성경 구절 3개만 선택.
2) comment, tag 생성
3) JSON 배열만 출력
```

이 프롬프트는 생성문의 질을 높이고, JSON 구조화를 통해 API 응답 안정성 확보에 중요한 역할을 한다.

### **4.3 한글 후처리**

응답 중 **한자/가나 제거**, 공백 정리 등의 한국어 후처리를 적용해 사용자 이해도 향상.

---

## **5. 실험 및 결과**

[https://mincha.co.kr/recommend](https://mincha.co.kr/recommend) API 통해 테스트 가능 (Swagger 주소 - [https://mincha.co.kr/docs](https://mincha.co.kr/docs))

### **5.1 테스트 시나리오**

- 감정 입력: “오늘 너무 힘들어요”
- 검색 Top-k: k=5
- 선택 항목: 3개
- 스타일: long

### **5.2 결과 예시**

```jsx
[
  {
    "ref": "시편 23:1",
    "text": "여호와는 나의 목자시니…",
    "comment": "힘들 때 하나님께 맡기며 한 걸음씩 가는 것이 평안의 시작입니다.",
    "tag": "소망"
  },
  ...
]
```

이처럼 RAG 기반 시스템은 단순 추천이 아니라 **도메인 지식 기반 답변을 생성**한다.

---

## **6. 연구적 의의 및 향후 과제**

### **6.1 기술적 의의**

- **RAG 구조를 통한 LLM 할루시네이션 완화 검증**
    - 생성 이전 단계에서 **FAISS 기반 벡터 검색**으로 성경 본문을 선제적으로 확보하고,
        
        이를 LLM 프롬프트의 근거(context)로 주입함으로써
        
        LLM 단독 생성 방식 대비 **근거 없는 응답(hallucination) 발생 가능성을 구조적으로 감소**시켰다.
        
- **임베딩 기반 의미 검색의 도메인 적용 가능성 검증**
    - 키워드 매칭이 아닌 **SentenceTransformer 기반 의미 임베딩 검색**을 적용하여,
        
        자연어 질의와 도메인 문서(성경 절) 간 **의미적 유사도 기반 검색 구조**의 실효성을 확인하였다.
        
- **경량 벡터 검색 아키텍처 설계 및 구현**
    - 외부 Vector DB 서버 없이 **FAISS(IndexFlatIP)** 기반 파일형 인덱스를 사용함으로써,
        
        소규모~중규모 도메인 데이터(약 3만 절)에 적합한 **경량·저비용 RAG 아키텍처**를 구현하였다.
        
- **임베딩 정규화 + Inner Product 조합을 통한 코사인 유사도 검색 구현**
    - 임베딩 벡터 정규화와 Inner Product 기반 FAISS 인덱스를 결합하여,
        
        별도의 복잡한 설정 없이 **코사인 유사도 기반 의미 검색**을 안정적으로 수행하였다.
        
- **청킹 전략(절 단위)의 명시적 정의 및 고정**
    - 성경 텍스트의 구조적 특성을 반영하여 **“한 절 = 하나의 chunk”** 로 청킹 전략을 명확히 정의하고,
        
        Indexing 단계에서 청킹을 완료함으로써 Retrieval·Generation 단계의 복잡도를 줄였다.
        

### **6.2 향후 기술적 연구 방향**

본 연구에서 적용한 RAG 구조는 성경 텍스트 추천 시스템에 국한되지 않고, **근거 기반 응답이 요구되는 다양한 지식 시스템으로 확장 가능성**을 가진다.

특히 LLM 단독 응답 방식에서 발생하는 할루시네이션(hallucination)을 구조적으로 억제할 수 있다는 점에서, 향후 다음과 같은 방향의 기술적 확장이 가능하다.

RAG를 활용하면, 시스템이 임의로 응답을 생성하기보다, 사전에 벡터화된 문서 집합(정책, 가이드, 지식 문서 등)에서 관련 정보를 먼저 검색한 뒤 이를 근거(context)로 응답을 생성하도록 유도할 수 있다.

이를 통해 **사실 기반 응답, 출처 추적 가능성, 응답 범위 제어**가 가능해진다.

**이러한 특성은 향후**

- **복잡한 내부 지식을 다루는 지식 기반 서비스,**
- **근거 제시가 필요한 자동 응답 시스템,**
- **또는 Agent 형태의 지능형 시스템 등 다양한 응용 시나리오에서 활용될 수 있다.**

특히 문서 변경이나 정책 업데이트가 빈번한 환경에서도,

모델 재학습 없이 **벡터 인덱스 갱신만으로 지식 최신화가 가능**하다는 점은,

운영 효율성과 유지보수 측면에서 중요한 기술적 장점으로 작용한다.

---

## 산출물

### **/recommend API**

![Swagger -  [https://mincha.co.kr/docs](https://mincha.co.kr/docs)](%EC%84%B1%EA%B2%BD%20%EB%A7%90%EC%94%80%20%EA%B8%B0%EB%B0%98%20AI%20RAG%20%EC%8B%9C%EC%8A%A4%ED%85%9C/%E1%84%89%E1%85%B3%E1%84%8F%E1%85%B3%E1%84%85%E1%85%B5%E1%86%AB%E1%84%89%E1%85%A3%E1%86%BA_2025-12-24_%E1%84%8B%E1%85%A9%E1%84%8C%E1%85%A5%E1%86%AB_11.03.26.png)

Swagger -  [https://mincha.co.kr/docs](https://mincha.co.kr/docs)

/recommend API는 사용자의 감정·상태를 입력받아

**RAG(Retrieval-Augmented Generation)** 구조를 기반으로

관련성이 높은 성경 구절을 검색하고, 이를 근거로 AI가 코멘트를 생성하는 엔드포인트다.

### **동작 방식**

1. 사용자가 전달한 mood(Text)를 임베딩 벡터로 변환한다.
2. FAISS 기반 벡터 검색을 통해 성경 전체 데이터 중
    
    의미적으로 가장 유사한 성경 절 Top-K를 조회한다.
    
3. 검색된 성경 절을 LLM 프롬프트의 근거(context)로 전달한다.
4. LLM은 해당 근거를 바탕으로:
    - 가장 적절한 성경 구절 선택
    - 성경 본문 인용
    - 짧은 한국어 코멘트 및 태그 생성
5. 최종 결과를 JSON 형태로 반환한다.

### **iOS, 안드로이드 앱**

- 상기 API들을 활용한 애플리케이션 개발
- 크로스 플랫폼(React-Native) 통해 개발
- **현재 플레이스토어, 앱스토어 심사 중**

---

## **구현 및 실험 환경 스펙 요약**

### **1. 임베딩 및 검색 모델**

- **임베딩 모델 (Embedding Model)**
    - SentenceTransformer
    - **모델명**: intfloat/multilingual-e5-base
    - **특징**:
        - 다국어 의미 검색에 특화된 E5 계열 모델
        - query: / passage: prefix 기반 질의–문서 의미 정렬 지원
        - 한국어 문장에 대해 안정적인 의미 임베딩 성능 제공
- **벡터 검색 엔진 (Vector Search Engine)**
    - **FAISS (Facebook AI Similarity Search)**
    - **인덱스 타입**: IndexFlatIP
    - **유사도 방식**:
        - 임베딩 벡터 정규화(normalize) + Inner Product
        - → 코사인 유사도(Cosine Similarity)와 동일하게 동작
    - **설계 특징**:
        - 외부 Vector DB 서버 없이 파일 기반 인덱스 사용
        - 소규모~중규모 도메인 데이터(성경 약 3만 절)에 적합한 경량 구조

---

### **2. 생성 모델 (LLM)**

- **생성 모델 (Text Generation Model)**
    - **플랫폼**: OpenAI API
    - **모델명**: gpt-4o-mini
    - **사용 목적**:
        - 검색된 성경 구절을 근거로 코멘트 및 태그 생성
        - RAG 구조 내 Generation 단계 담당
    - **설정값**:
        - temperature = 0.4 (과도한 창작 억제)
        - response_format = json_object (구조화 응답 강제)

---

### **3. 데이터셋**

- **성경 데이터**
    - **버전**: Korean Revised Version 1910 (KR1910)
    - **라이선스**: Public Domain
    - **청킹 단위**: 성경 한 절(Verse)
    - **총 규모**: 약 31,000 절
- **저장 형식**
    - 원본: CSV
    - 메타 데이터: Parquet
    - 벡터 인덱스: FAISS (.faiss)

---

### **4. 서버 및 프레임워크**

- **API 서버**
    - **Framework**: FastAPI
    - **Python Version**: Python 3.x
    - **엔드포인트**:
        - GET /random : 랜덤 성경 절 반환 (검색/생성 없음)
        - POST /recommend : RAG 기반 성경 구절 추천 및 코멘트 생성
- **운영 환경**
    - 로컬 / EC2 환경 모두 지원

---

### **5. RAG 파라미터 설정**

- **Top-K 검색 개수**: TOP_K = 5
- **최종 선택 개수**: PICKS = 3
- **코멘트 스타일 옵션**:
    - short / medium / long
- **텍스트 후처리 옵션**:
    - 한자/가나 제거(KOREAN_ONLY = True)

---

### **6. 구현 특징 요약**

- 임베딩 모델과 벡터 검색 엔진의 **역할 분리**
- 검색–생성 단계 명확 분리(RAG)
- JSON 응답 강제 및 파싱 방어 로직 포함
- 재학습 없이 인덱스 갱신만으로 데이터 업데이트 가능