# app.py
# =========================================================
# Bible RAG (KR1910, Public Domain) + OpenAI API 추천
# - /recommend  : 기분/상태 -> RAG 상위 절 -> OpenAI가 한국어 추천/코멘트 생성
# - /random     : 랜덤으로 말씀 1개 반환(OpenAI 호출 없음)
# - comment_style: short | medium | long 로 코멘트 길이 조절
# 실행:
#   export OPENAI_API_KEY="키값"
#   uvicorn app:app --reload --port 8000
# =========================================================

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from pydantic import AliasChoices, BaseModel, Field
import pandas as pd
import faiss
from sentence_transformers import SentenceTransformer
from pathlib import Path
from typing import List, Optional, Union, Literal, AsyncGenerator
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from threading import Lock
import sqlite3
import random
import os, re, json, time, logging, asyncio, secrets

from analytics.db import init_db as init_analytics_db
from analytics.routes import router as analytics_router
from analytics.scheduler import AnalyticsRollupScheduler
from app_version import router as app_version_router
from notifications.jobs import build_notification_manager
from notifications.manager import DailyVerseNotificationManager
from notifications.scheduler import DailyVerseScheduler
from notifications.verse_provider import VerseInterpretationStore, VerseInterpreter
from settings import AppSettings, load_dotenv

# ---------- FastAPI ----------
app = FastAPI(title="With God")

load_dotenv()

# ---------- Logging ----------
# EC2/systemd 환경에서 stdout/stderr 로 찍히는 로그를 journalctl로 확인 가능
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("with-god")

# ---------- 경로 ----------
ROOT = Path(__file__).parent.resolve()
DATA = ROOT / "data"
META = str(DATA / "verses_meta.parquet")
CSV  = str(DATA / "verses.csv")
IDX  = str(DATA / "verses.faiss")
DAILY_RANDOM_DB = str(DATA / "daily_random.sqlite3")

# ---------- 데이터/인덱스/임베딩 ----------
# df (DataFrame)
# - 성경 전체 데이터를 메모리에 올려둔 테이블 형태의 객체
# - 한 행(row) = 성경 한 절
# - 주요 컬럼: book, chapter, verse, text ( + clean )
# - /random  : df.sample()로 랜덤 절 선택
# - /recommend: FAISS 검색 결과 인덱스로 df.iloc[i] 접근
# 1) 메타(parquet)가 있으면 parquet를 우선 사용
# 2) 없으면 csv를 사용 + clean 컬럼 생성(공백 정리)
if os.path.exists(META):
    df = pd.read_parquet(META)
else:
    df = pd.read_csv(CSV)
    df["clean"] = df["text"].astype(str).str.split().str.join(" ")

# FAISS 인덱스 로드
index = faiss.read_index(IDX)

# Apple Silicon 가속(MPS). 없으면 CPU로 자동 폴백.
try:
    model = SentenceTransformer("intfloat/multilingual-e5-small", device="mps")
    model.encode(["query: warmup"], normalize_embeddings=True)  # 워밍업
except Exception:
    model = SentenceTransformer("intfloat/multilingual-e5-small")


# =========================================================
# OpenAI API (생성)
# =========================================================
from openai import OpenAI

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # 빠르고 저렴한 기본값
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
APP_SETTINGS = AppSettings.from_env()

# 한자/가나 제거(옵션)
_RE_HANJA = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]")
_RE_KANA  = re.compile(r"[\u3040-\u30FF\u31F0-\u31FF]")

def _keep_korean_only(s: str) -> str:
    s = _RE_HANJA.sub("", s)
    s = _RE_KANA.sub("", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _clip(s: str, n=160) -> str:
    return (s[:n] + "…") if len(s) > n else s

# /random 일일 1회 지급을 위한 영구 저장소(SQLite)
_daily_random_lock = Lock()
_POPULAR_VERSE_REFS = [
    ("시편", 4, 8), ("시편", 9, 9), ("시편", 16, 8), ("시편", 18, 1), ("시편", 18, 2),
    ("시편", 23, 1), ("시편", 23, 2), ("시편", 23, 3), ("시편", 23, 4), ("시편", 23, 6),
    ("시편", 27, 1), ("시편", 27, 14), ("시편", 28, 7), ("시편", 30, 5), ("시편", 31, 24),
    ("시편", 34, 4), ("시편", 34, 8), ("시편", 34, 18), ("시편", 37, 4), ("시편", 42, 11),
    ("시편", 46, 1), ("시편", 46, 10), ("시편", 55, 22), ("시편", 56, 3), ("시편", 62, 1),
    ("시편", 62, 5), ("시편", 71, 20), ("시편", 73, 26), ("시편", 84, 11), ("시편", 91, 1),
    ("시편", 91, 2), ("시편", 91, 4), ("시편", 91, 11), ("시편", 94, 19), ("시편", 103, 2),
    ("시편", 103, 13), ("시편", 107, 1), ("시편", 118, 6), ("시편", 119, 50), ("시편", 119, 105),
    ("시편", 121, 1), ("시편", 121, 2), ("시편", 121, 7), ("시편", 121, 8), ("시편", 126, 5),
    ("시편", 139, 14), ("잠언", 3, 5), ("잠언", 3, 6), ("잠언", 4, 23), ("잠언", 16, 3),
    ("잠언", 17, 17), ("이사야", 26, 3), ("이사야", 30, 15), ("이사야", 40, 29), ("이사야", 40, 31),
    ("이사야", 41, 10), ("이사야", 41, 13), ("이사야", 43, 1), ("이사야", 43, 2), ("이사야", 54, 10),
    ("예레미야", 29, 11), ("예레미야", 31, 3), ("예레미야애가", 3, 22), ("예레미야애가", 3, 23), ("예레미야애가", 3, 24),
    ("스바냐", 3, 17), ("마태복음", 5, 4), ("마태복음", 6, 26), ("마태복음", 6, 34), ("마태복음", 11, 28),
    ("마태복음", 11, 29), ("마태복음", 11, 30), ("마태복음", 28, 20), ("누가복음", 1, 37), ("누가복음", 12, 32),
    ("요한복음", 14, 1), ("요한복음", 14, 6), ("요한복음", 14, 27), ("요한복음", 15, 9), ("요한복음", 16, 33),
    ("사도행전", 18, 10), ("로마서", 8, 1), ("로마서", 8, 18), ("로마서", 8, 28), ("로마서", 8, 31),
    ("로마서", 8, 38), ("로마서", 8, 39), ("로마서", 12, 12), ("고린도후서", 1, 3), ("고린도후서", 1, 4),
    ("고린도후서", 4, 16), ("고린도후서", 4, 17), ("고린도후서", 4, 18), ("고린도후서", 12, 9), ("갈라디아서", 6, 9),
    ("에베소서", 3, 20), ("빌립보서", 1, 6), ("빌립보서", 4, 4), ("빌립보서", 4, 6), ("빌립보서", 4, 7),
    ("빌립보서", 4, 8), ("빌립보서", 4, 13), ("빌립보서", 4, 19), ("데살로니가전서", 5, 16), ("데살로니가전서", 5, 17),
    ("데살로니가전서", 5, 18), ("데살로니가후서", 3, 3), ("디모데후서", 1, 7), ("히브리서", 4, 16), ("히브리서", 10, 23),
    ("히브리서", 11, 1), ("히브리서", 13, 5), ("히브리서", 13, 6), ("야고보서", 1, 5), ("야고보서", 1, 12),
    ("요한일서", 4, 18), ("요한계시록", 21, 4),
    # 인생교훈 확장
    ("잠언", 1, 7), ("잠언", 10, 12), ("잠언", 11, 25), ("잠언", 12, 1), ("잠언", 13, 20),
    ("잠언", 15, 1), ("잠언", 15, 16), ("잠언", 16, 9), ("잠언", 18, 21), ("잠언", 19, 21),
    ("잠언", 20, 13), ("잠언", 22, 1), ("잠언", 22, 6), ("잠언", 24, 16), ("잠언", 27, 17),
    ("전도서", 3, 1), ("전도서", 4, 9), ("전도서", 4, 10), ("전도서", 7, 8), ("전도서", 11, 4),
    ("미가", 6, 8), ("마태복음", 5, 9), ("마태복음", 6, 21), ("마태복음", 6, 33), ("마태복음", 7, 12),
    ("마태복음", 22, 37), ("마태복음", 22, 38), ("마태복음", 22, 39), ("누가복음", 6, 31), ("요한복음", 8, 32),
    ("요한복음", 13, 34), ("요한복음", 13, 35), ("요한복음", 15, 5), ("로마서", 12, 2), ("로마서", 12, 15),
    ("고린도전서", 10, 13), ("고린도전서", 13, 4), ("고린도전서", 13, 5), ("고린도전서", 13, 6), ("고린도전서", 13, 7),
    ("갈라디아서", 5, 22), ("갈라디아서", 5, 23), ("에베소서", 4, 26), ("에베소서", 4, 27), ("에베소서", 4, 29),
    ("골로새서", 3, 12), ("골로새서", 3, 13), ("골로새서", 3, 14), ("히브리서", 10, 24), ("히브리서", 10, 25),
    ("야고보서", 1, 19), ("야고보서", 1, 22), ("베드로전서", 5, 7),
]

def _build_ref(book: str, chapter: int, verse: int) -> str:
    return f"{book} {int(chapter)}:{int(verse)}"

def _seed_popular_verses(conn: sqlite3.Connection) -> None:
    rows = []
    for book, chapter, verse in _POPULAR_VERSE_REFS:
        matched = df[
            (df["book"] == book) &
            (df["chapter"].astype(int) == int(chapter)) &
            (df["verse"].astype(int) == int(verse))
        ]
        if matched.empty:
            continue
        text = str(matched.iloc[0]["text"])
        rows.append((_build_ref(book, chapter, verse), book, int(chapter), int(verse), text))

    if not rows:
        return

    # 중복 ref는 1개만 유지
    dedup = {}
    for row in rows:
        dedup[row[0]] = row
    rows = list(dedup.values())

    # 순차 조회 시 같은 책이 몰리지 않도록 고정 시드로 섞는다.
    random.Random(2026).shuffle(rows)

    # 현재 코드의 인기 구절 목록을 DB와 정확히 동기화한다.
    conn.execute("DELETE FROM popular_verses")
    conn.executemany(
        """
        INSERT INTO popular_verses (ref, book, chapter, verse, verse_text)
        VALUES (?, ?, ?, ?, ?)
        """,
        rows,
    )

def _pick_random_popular_verse_from_db() -> Optional[dict]:
    with sqlite3.connect(DAILY_RANDOM_DB) as conn:
        picked = conn.execute(
            """
            SELECT ref, verse_text
            FROM popular_verses
            ORDER BY RANDOM()
            LIMIT 1
            """
        ).fetchone()

        if not picked:
            return None
        return {"ref": picked[0], "text": picked[1]}

def _save_user_cursor(user_key: str, last_index: int) -> None:
    with sqlite3.connect(DAILY_RANDOM_DB) as conn:
        conn.execute(
            """
            INSERT INTO random_user_cursor (user_key, last_index)
            VALUES (?, ?)
            ON CONFLICT(user_key) DO UPDATE SET
                last_index = excluded.last_index
            """,
            (user_key, int(last_index)),
        )
        conn.commit()

def _init_daily_random_db():
    DATA.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DAILY_RANDOM_DB) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_random (
                user_key TEXT NOT NULL,
                day TEXT NOT NULL,
                ref TEXT NOT NULL,
                verse_text TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_key, day)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS popular_verses (
                ref TEXT PRIMARY KEY,
                book TEXT NOT NULL,
                chapter INTEGER NOT NULL,
                verse INTEGER NOT NULL,
                verse_text TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS random_user_cursor (
                user_key TEXT PRIMARY KEY,
                last_index INTEGER NOT NULL
            )
            """
        )
        _seed_popular_verses(conn)
        conn.commit()

def _get_daily_random_from_db(user_key: str, day: str) -> Optional[dict]:
    with sqlite3.connect(DAILY_RANDOM_DB) as conn:
        row = conn.execute(
            "SELECT ref, verse_text FROM daily_random WHERE user_key = ? AND day = ?",
            (user_key, day),
        ).fetchone()
    if not row:
        return None
    return {"ref": row[0], "text": row[1]}

def _save_daily_random_to_db(user_key: str, day: str, ref: str, text: str) -> None:
    with sqlite3.connect(DAILY_RANDOM_DB) as conn:
        conn.execute(
            """
            INSERT INTO daily_random (user_key, day, ref, verse_text)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_key, day) DO UPDATE SET
                ref = excluded.ref,
                verse_text = excluded.verse_text
            """,
            (user_key, day, ref, text),
        )
        conn.commit()

def _day_str(day_offset: int = 0) -> str:
    # 서버 OS 타임존(UTC 등)이 아니라 서비스 기준 타임존(기본 Asia/Seoul)의 '오늘'을 쓴다.
    # 캐시 키 형식(YYYY-MM-DD)은 기존과 동일하게 유지한다.
    local_now = datetime.now(ZoneInfo(APP_SETTINGS.push_default_timezone))
    return (local_now.date() + timedelta(days=int(day_offset))).isoformat()

def _resolve_user_key(request: Request) -> str:
    # 앱/클라이언트가 식별자를 보내주면 최우선 사용
    explicit_user_id = request.headers.get("x-user-id")
    if explicit_user_id:
        return f"uid:{explicit_user_id.strip()}"

    # 프록시 환경에서는 X-Forwarded-For의 첫 IP 사용
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown-ip"

    user_agent = request.headers.get("user-agent", "unknown-ua")
    return f"ipua:{client_ip}|{user_agent}"

_init_daily_random_db()

def _style_to_limits(style: str):
    style = (style or "medium").lower()
    if style == "short":
        return {
            "text_limit": "1문장(약 40–60자)",
            "comment_limit": "1문장(약 40–60자)",
            "max_tokens": 300
        }
    if style == "long":
        return {
            "text_limit": "1–2문장(약 120–180자)",
            "comment_limit": "4–5문장(약 260–360자)",
            "max_tokens": 1500
        }
    # default: medium
    return {
        "text_limit": "1–2문장(약 80–120자)",
        "comment_limit": "2문장(약 120–180자)",
        "max_tokens": 550
    }

# 추천 코멘트용 공용 시스템 프롬프트: '상담 도우미'가 아니라 '목사님'처럼,
# 말씀을 짧게 풀어 설명(성경 풀이)한 뒤 성도의 상황에 다정하게 적용하도록 지시.
_RECOMMEND_SYSTEM = (
    "당신은 따뜻하고 지혜로운 한국인 목사님입니다. "
    "성도가 털어놓은 마음에, 성경 구절을 짧게 설교하듯 풀어 건넵니다.\n"
    "규칙:\n"
    "- 반드시 한국어만 사용합니다.\n"
    "- 먼저 그 구절이 '무슨 뜻인지'를 쉽게 풀어 설명합니다(성경 풀이).\n"
    "- 그다음 그 말씀이 지금 이 사람의 상황에 어떤 위로·의미가 되는지 다정하게 적용합니다.\n"
    "- 훈계하듯 가르치지 말고, 곁에서 손잡아 주듯 부드럽게 말합니다.\n"
    "- 과장·단정적 단언·번영신학식 약속은 피하고 신학적으로 무난하게 씁니다."
)


def _build_user_prompt(mood: str, candidates: List[dict], picks: int, style_limits: dict) -> str:
    verses_block = "\n".join([f"- {c['ref']} :: {_clip(c['text'])}" for c in candidates])
    return f"""
역할: 당신은 따뜻한 한국인 목사님입니다.
규칙:
- 반드시 한국어만 사용하세요. 영어/중국어/일본어 금지.
- text는 {style_limits['text_limit']} 로 인용하세요.
- comment는 {style_limits['comment_limit']} 로 작성하되, 그 구절이 무슨 뜻인지 쉽게 풀어 설명(성경 풀이)한 뒤 성도의 상황에 다정하게 적용하는 흐름을 한 단락에 담으세요. (번호·소제목 없이 매끄럽게)
- 각 구절의 주제(감정)를 'tag'로 1~2개만 추가하세요. 예: \"두려움\", \"걱정\", \"사랑\", \"소망\", \"감사\", \"회개\" 등
- 출력은 JSON 배열만. 다른 설명/서문/주석 금지.

사용자 기분/상태: \"{mood}\"

후보 성경 구절({len(candidates)}개, 1910 퍼블릭 도메인):
{verses_block}

요청:
1) 가장 적절한 성경 구절 {picks}개만 선택.
2) 각 항목에 'text', 'ref', 'tag', 'comment'를 포함.
3) 정확한 JSON 배열로만 출력 (반드시 아래 키 순서를 지켜주세요):
[
  {{
    \"text\": \"성경 본문\",
    \"ref\": \"책 장:절\",
    \"tag\": \"두려움\",
    \"comment\": \"짧지 않지만 군더더기 없는 한국어 코멘트\"
  }}
]
""".strip()


def _build_single_comment_prompt(mood: str, verse: dict, style_limits: dict) -> str:
    """스트리밍용: 구절 1개에 대해 tag + comment(말씀 풀이+적용)를 생성하는 프롬프트"""
    return f"""
역할: 당신은 따뜻한 한국인 목사님입니다. (반드시 한국어만 사용)

성경 구절: {verse['ref']} :: {verse['text']}
성도의 마음: "{mood}"

요청: 이 구절을 성도에게 건네는 짧은 '말씀 나눔'을 comment 로 작성하세요.
- comment 분량: {style_limits['comment_limit']}.
- 반드시 아래 두 가지를 자연스러운 한 단락에 함께 담으세요:
  (1) 이 구절이 본래 무슨 뜻인지 쉽게 풀어 설명 (성경 풀이)
  (2) 그 말씀이 지금 성도의 상황에 어떤 위로·의미가 되는지 다정한 적용
- (1)(2) 같은 번호·표시나 소제목은 넣지 말고 매끄럽게 이어 쓰세요.
- 'tag'는 감정 주제 1~2개. 예: "두려움", "위로", "소망", "회복" 등
- 출력은 JSON 객체 1개만. 다른 설명/서문/주석 금지.

정확한 JSON 객체 1개로만 출력 (아래 키 순서 유지):
{{
  "tag": "두려움",
  "comment": "말씀 풀이와 적용이 함께 담긴 목회적 코멘트"
}}
""".strip()


def _call_openai_as_json(system: str, user: str, max_tokens: int) -> str:
    client = OpenAI(api_key=OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.4,              # 약간 풍부하게
        max_tokens=max_tokens,        # 스타일에 따라 증가
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user}
        ],
    )
    return resp.choices[0].message.content.strip()


def _call_openai_as_text(system: str, user: str, max_tokens: int) -> str:
    """_call_openai_as_json 과 동형이지만 JSON 강제 없이 평문(풀이 본문)만 받는 헬퍼."""
    client = OpenAI(api_key=OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.5,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user}
        ],
    )
    return resp.choices[0].message.content.strip()


# ---------- 오늘의 말씀 '풀이'(LLM) ----------
# 구절을 일상어로 부드럽게 풀어 주는 한국어 '풀이'를 생성한다.
# verse_id 기준 파일 캐시(VerseInterpreter)와 결합되어 말씀당 최대 1회만 호출된다.
_VERSE_INTERPRETATION_SYSTEM = """당신은 따뜻한 신앙 동반자입니다. 성경 구절을 일상어로 부드럽게 풀어 설명합니다.

규칙:
- 반드시 한국어로만 씁니다.
- 2문장 이내로 짧고 담백하게 풉니다.
- '~말씀이에요', '~해도 괜찮아요' 처럼 부드럽고 다정한 종결로 건넵니다.
- 제목, 따옴표, 구절 재인용 없이 '풀이 본문'만 출력합니다.
- 훈계하듯 가르치지 말고, 곁에서 조용히 다독이듯 말합니다.

예시 톤:
지친 하루의 짐을 혼자 지지 말라는 말씀이에요. 무거운 마음 그대로, 쉼을 주시는 분께 가져가면 돼요."""


def _build_verse_interpretation_user_prompt(reference: str, text: str) -> str:
    return f"""다음 성경 구절을 위 규칙대로 부드럽게 풀어 설명해 주세요.

구절: {reference}
본문: {text}

풀이(2문장 이내, 제목·따옴표·구절 재인용 없이 본문만):""".strip()


def _generate_verse_interpretation(reference: str, text: str) -> str:
    """구절(reference, text)을 받아 한국어 '풀이'를 생성한다.

    키가 없거나 호출이 실패하면 예외를 올려 상위(VerseInterpreter)가 reflection 으로 폴백한다.
    """
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    interpretation = _call_openai_as_text(
        _VERSE_INTERPRETATION_SYSTEM,
        _build_verse_interpretation_user_prompt(reference, text),
        max_tokens=200,
    )
    return _keep_korean_only(interpretation)


async def _stream_openai(system: str, user: str, max_tokens: int) -> AsyncGenerator[str, None]:
    """OpenAI API를 스트리밍으로 호출하여 토큰 단위로 yield"""
    client = OpenAI(api_key=OPENAI_API_KEY)
    stream = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.4,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user}
        ],
        stream=True,
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content

# ---------- /recommend ----------
class RecommendIn(BaseModel):
    mood: str = Field(..., examples=["오늘 너무 힘들어요"])


class CommentStreamIn(BaseModel):
    mood: str = Field(..., examples=["불안하고 잠이 안 와요"])
    ref: str = Field(..., examples=["시편 23:1"])
    text: str = Field(..., examples=["여호와는 나의 목자시니 내게 부족함이 없으리로다."])
    index: Optional[int] = Field(0, examples=[0])


class VerseCandidate(BaseModel):
    ref: str = Field(..., examples=["시편 23:1"])
    text: str = Field(..., examples=["여호와는 나의 목자시니 내게 부족함이 없으리로다."])
    score: float = Field(..., examples=[0.8123])


class RecommendItem(BaseModel):
    ref: str = Field(..., examples=["시편 23:1"])
    text: str = Field(..., examples=["여호와는 나의 목자시니 내게 부족함이 없으리로다."])
    comment: str = Field(..., examples=["지금은 불안을 혼자 견디지 말고, 하루를 맡기며 한 걸음씩 가도 괜찮습니다."])
    tag: str = Field(..., examples=["두려움"])


class RecommendParseError(BaseModel):
    error: str = Field(..., examples=["응답 파싱 실패"])
    raw: str = Field(..., examples=['[{"ref":"..."}]'])


RecommendResult = Union[RecommendItem, RecommendParseError]


class RecommendOut(BaseModel):
    mood: str = Field(..., examples=["불안하고 잠이 안 와요"])
    model: Optional[str] = Field(None, examples=["gpt-4o-mini"])
    style: Optional[str] = Field(None, examples=["long"])
    results: Optional[List[RecommendResult]] = None

    # 현재 코드가 실패 시 200으로 error/candidates를 반환하므로 optional로 허용
    error: Optional[str] = Field(None, examples=["OpenAI 호출 실패: ..."])
    candidates: Optional[List[VerseCandidate]] = None


# ---------- /random ----------
# OpenAI 없이, 인기 말씀 테이블에서 매 호출마다 랜덤으로 1개 반환하는 엔드포인트

class RandomOut(BaseModel):
    # 반환할 구절의 참조(책 장:절) 예: "시편 23:1"
    ref: str = Field(..., examples=["시편 23:1"])

    # 반환할 구절의 본문(텍스트)
    text: str = Field(..., examples=["여호와는 나의 목자시니 내게 부족함이 없으리로다."])


class RandomError(BaseModel):
    # 예외 발생 시 에러 메시지를 담아 반환
    error: str = Field(..., examples=["랜덤 구절 생성 실패"])


class DeviceRegisterIn(BaseModel):
    token: str = Field(..., examples=["fcm-registration-token"])
    platform: Literal["android", "ios"] = Field(..., examples=["ios"])
    timezone: Optional[str] = Field("Asia/Seoul", examples=["Asia/Seoul"])
    # 공유 API 규약은 snake_case(device_id), 기존 클라이언트는 camelCase(deviceId)를
    # 보내므로 두 키를 모두 허용한다(하위호환).
    device_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("device_id", "deviceId"),
        examples=["iphone-15-pro-max"],
    )
    schedule_hour: Optional[int] = Field(default=None, ge=0, le=23, examples=[9])
    schedule_minute: Optional[int] = Field(default=None, ge=0, le=59, examples=[0])
    # device_id 와 마찬가지로 snake_case(공유 규약)/camelCase(기존 클라이언트) 둘 다 허용.
    appVersion: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("app_version", "appVersion"),
        examples=["1.0.3"],
    )
    osVersion: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("os_version", "osVersion"),
        examples=["17.4.1"],
    )
    enabled: bool = Field(True, examples=[True])


class DeviceDeleteOut(BaseModel):
    deleted: bool = Field(..., examples=[True])


class PushTokensIn(BaseModel):
    tokens: Optional[List[str]] = Field(default=None, examples=[["token-a", "token-b"]])


def _notification_manager() -> DailyVerseNotificationManager:
    manager = getattr(app.state, "notification_manager", None)
    if manager is None:
        raise RuntimeError("Notification manager is not initialized")
    return manager


def require_push_admin(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> None:
    """푸시 관리용 엔드포인트 보호 (토큰 목록 조회/삭제/전체 즉시발송).

    키는 환경변수 PUSH_ADMIN_API_KEY 에서 읽는다(.env 는 모듈 로드 시 load_dotenv 로 반영).
    환경변수가 비어 있으면 관리 API 는 잠긴 상태로 둔다(무조건 401).
    클라이언트가 쓰는 등록 엔드포인트(POST /push/devices)에는 적용하지 않는다.
    """
    expected = os.getenv("PUSH_ADMIN_API_KEY", "")
    if not expected or x_api_key is None or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


# GET /random
# - body 없이 호출
# - day_offset=1 을 주면 내일 구절을 미리 확인 가능
# - 응답은 RandomOut(정상) 또는 RandomError(실패)
@app.get(
    "/random",  # 라우팅 경로
    response_model=Union[RandomOut, RandomError],  # Swagger에 표시될 응답 스키마
    responses={
        200: {
            "description": "Random Bible verse (KR1910)"  # 문서용 설명
        }
    }
)
def random_verse(request: Request, day_offset: int = Query(0, ge=0, le=30)):
    # ---------- Backend-only configuration ----------
    # API 요청 파라미터로 받지 않고, 서버 코드에서만 고정으로 조정하는 옵션
    KOREAN_ONLY = True  # 한자/가나 제거 여부

    try:
        # /random은 사용자별이 아니라 하루에 모두 같은 말씀을 반환한다.
        user_key = "global-daily-random"
        target_day = _day_str(day_offset)

        # 같은 날짜(day_offset/day 조합)에는 모든 사용자가 같은 말씀을 받는다.
        with _daily_random_lock:
            cached = _get_daily_random_from_db(user_key, target_day)
        if cached:
            return cached

        picked = _pick_random_popular_verse_from_db()
        if picked:
            ref = picked["ref"]
            text = picked["text"]
        else:
            # 인기 구절 풀이 비어 있으면 기존 전체 성경 랜덤으로 폴백
            r = df.sample(n=1).iloc[0]
            ref = _build_ref(str(r["book"]), int(r["chapter"]), int(r["verse"]))
            text = str(r["text"])

        # 한자/가나 제거 옵션이 켜져 있으면 후처리
        if KOREAN_ONLY:
            text = _keep_korean_only(text)

        payload = {
            "ref": ref,
            "text": text
        }

        with _daily_random_lock:
            _save_daily_random_to_db(user_key, target_day, ref, text)

        # 정상 응답 반환
        return payload

    except Exception as e:
        # 예외가 나면 에러 형태로 반환
        # (현재 스타일에 맞춰 200으로 에러를 담아 반환)
        return {"error": f"랜덤 구절 생성 실패: {e}"}


@app.get("/daily-verse")
def daily_verse():
    manager = _notification_manager()
    return {"daily_verse": manager.get_daily_verse()}


# 관리용: 전체 토큰 목록 노출 → X-API-Key 필요.
@app.get("/push/devices", dependencies=[Depends(require_push_admin)])
def list_push_devices():
    manager = _notification_manager()
    return {"devices": manager.list_devices()}


@app.post("/push/devices", status_code=201)
def register_push_device(inp: DeviceRegisterIn):
    manager = _notification_manager()
    try:
        result = manager.register_device(
            token=inp.token,
            platform=inp.platform,
            timezone=inp.timezone,
            device_id=inp.device_id or "",
            app_version=inp.appVersion or "",
            os_version=inp.osVersion or "",
            enabled=inp.enabled,
            schedule_hour=inp.schedule_hour,
            schedule_minute=inp.schedule_minute,
        )
    except ValueError as exc:
        # 잘못된 입력을 201 + {"error": ...} 로 돌려주던 것을 표준 400 으로 변경.
        raise HTTPException(status_code=400, detail=str(exc))
    return result


# 관리용: 임의 토큰 삭제 → X-API-Key 필요.
@app.delete(
    "/push/devices",
    response_model=DeviceDeleteOut,
    dependencies=[Depends(require_push_admin)],
)
def delete_push_device(token: str = Query(...)):
    manager = _notification_manager()
    deleted = manager.delete_device(token)
    if not deleted:
        raise HTTPException(status_code=404, detail="Device token not found")
    return {"deleted": True}


# 관리용: 전체(또는 지정 토큰) 즉시 발송 → X-API-Key 필요.
@app.post("/push/send/daily-verse", dependencies=[Depends(require_push_admin)])
def send_daily_verse(inp: PushTokensIn):
    manager = _notification_manager()
    try:
        return manager.send_daily_verse_now(tokens=inp.tokens)
    except RuntimeError as exc:
        return {"error": str(exc)}


@app.post(
    "/recommend",
    response_model=RecommendOut,
    responses={
        200: {
            "description": "Successful Response",
            "content": {
                "application/json": {
                    "example": {
                        "mood": "불안하고 잠이 안 와요",
                        "model": "gpt-4o-mini",
                        "style": "long",
                        "results": [
                            {
                                "ref": "시편 23:1",
                                "text": "여호와는 나의 목자시니 내게 부족함이 없으리로다.",
                                "comment": "지금은 불안을 혼자 견디지 말고, 하루를 맡기며 한 걸음씩 가도 괜찮습니다.",
                                "tag": "두려움"
                            },
                            {
                                "ref": "빌립보서 4:6",
                                "text": "아무것도 염려하지 말고 다만 모든 일에 기도와 간구로 너희 구할 것을 감사함으로 하나님께 아뢰라.",
                                "comment": "걱정이 올라올 때마다 한 문장 기도로 바꿔보면 마음의 소음이 조금씩 잦아듭니다.",
                                "tag": "걱정"
                            }
                        ]
                    }
                }
            }
        },
        422: {
            "description": "Validation Error"
        }
    }
)
def recommend(inp: RecommendIn):
    # ---------- Backend-only configuration ----------
    TOP_K = 12               # 넓게 뽑아 LLM이 재순위/선택
    PICKS = 3
    COMMENT_STYLE = "long"   # short | medium | long
    KOREAN_ONLY = True       # 한자/가나 제거 여부

    # ---------- Perf logging ----------
    t0 = time.perf_counter()
    def _lap(name: str, start: float):
        log.info("/recommend %s=%.3fs", name, time.perf_counter() - start)

    t = time.perf_counter()

    # 1) RAG 검색 (감정/상황을 검색 키워드로 확장해 의미 매칭 정확도 향상)
    search_query = _expand_search_query(inp.mood)
    _lap("expand", t)
    t = time.perf_counter()
    q = model.encode([f"query: {search_query}"], normalize_embeddings=True).astype("float32")
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

    # 2) OpenAI 생성
    limits = _style_to_limits(COMMENT_STYLE)
    system = _RECOMMEND_SYSTEM
    user = _build_user_prompt(inp.mood, cands, PICKS, limits)
    _lap("prompt", t)
    t = time.perf_counter()

    try:
        answer_str = _call_openai_as_json(system, user, max_tokens=limits["max_tokens"])
        _lap("openai", t)
        t = time.perf_counter()
    except Exception as e:
        log.exception("/recommend openai_failed after %.3fs", time.perf_counter() - t0)
        return {
            "mood": inp.mood,
            "error": f"OpenAI 호출 실패: {e}",
            "candidates": cands[:3]
        }

    # 3) JSON 파싱 + (선택) 한글 후처리
    # - OpenAI가 response_format 때문에 {"result": [...]} / {"results": [...]} / {"data": [...]} 같은
    #   "객체" 형태로 응답할 때가 있어, 항상 List[dict]로 정규화한다.
    try:
        parsed = json.loads(answer_str)

        # ✅ 1) 모델이 바로 JSON 배열을 준 경우
        if isinstance(parsed, list):
            results = parsed

        # ✅ 2) 모델이 JSON 객체로 감싼 경우: results/result/data 키를 우선 탐색
        elif isinstance(parsed, dict):
            results = (
                parsed.get("results")
                or parsed.get("result")
                or parsed.get("data")
                or []
            )

        # ✅ 3) 그 외 타입은 빈 리스트로 처리
        else:
            results = []

        # ✅ 최종 방어: results는 반드시 list여야 한다
        if not isinstance(results, list):
            results = []

    except Exception:
        results = [{"error": "응답 파싱 실패", "raw": answer_str}]
    # 한글 후처리(한자/가나 제거): results가 리스트일 때만 안전하게 수행
    if KOREAN_ONLY and isinstance(results, list):
        for item in results:
            if not isinstance(item, dict):
                continue
            if "text" in item:
                item["text"] = _keep_korean_only(str(item["text"]))
            if "comment" in item:
                item["comment"] = _keep_korean_only(str(item["comment"]))

    log.info("/recommend total=%.3fs", time.perf_counter() - t0)

    return {
        "mood": inp.mood,
        "model": OPENAI_MODEL,
        "style": COMMENT_STYLE,
        "results": results
    }


def _search_candidates(mood: str, top_k: int) -> List[dict]:
    q = model.encode([f"query: {mood}"], normalize_embeddings=True).astype("float32")
    D, I = index.search(q, top_k)
    cands = []
    for s, i in zip(D[0], I[0]):
        r = df.iloc[int(i)]
        cands.append({
            "ref": f"{r['book']} {int(r['chapter'])}:{int(r['verse'])}",
            "text": str(r["text"]),
            "score": float(s)
        })
    return cands


def _expand_search_query(mood: str) -> str:
    """사용자의 감정/상황 문장을 성경 검색에 적합한 '감정·주제 키워드'로 확장한다.

    성경 본문은 옛 문어체라 사용자의 일상어와 표면 어휘가 겹치지 않는다.
    LLM으로 핵심 감정 + 그에 응답하는 신앙 주제 키워드를 뽑아 원문에 덧붙여
    임베딩 검색의 의미 매칭 정확도를 높인다. 실패 시 원문 그대로 검색(무중단).
    """
    if not OPENAI_API_KEY:
        return mood
    system = (
        "너는 사용자의 감정/상황 문장을 성경 구절 검색용 한국어 키워드로 바꾸는 도우미다. "
        "핵심 감정과, 그 감정에 성경이 건네는 위로/응답 주제를 함께 뽑아라. "
        "설명 없이 쉼표로 구분한 키워드만 출력한다."
    )
    user = (
        f'사용자 문장: "{mood}"\n\n'
        "위 문장의 (1) 핵심 감정과 (2) 그 감정에 성경이 건네는 위로·응답 주제를 "
        "한국어 키워드 6~10개로 확장해 쉼표로만 나열하라.\n"
        '예: "요즘 너무 지치고 힘들어요" → 지침, 피곤, 번아웃, 안식, 쉼, 위로, 회복, 하나님의 돌보심'
    )
    try:
        kws = _keep_korean_only(_call_openai_as_text(system, user, max_tokens=120)).strip()
        return f"{mood} {kws}" if kws else mood
    except Exception:
        log.exception("query expansion failed; fallback to raw mood")
        return mood


def _select_verses(mood: str, candidates: List[dict], picks: int) -> List[dict]:
    """후보 구절 중 사용자 입력의 '의미·정서'에 가장 맞는 picks개를 LLM이 재순위.

    유사도 상위를 그대로 확정하지 않고, 넓게 뽑은 후보를 LLM이 다시 평가해
    입력 맥락에 맞는 것만 고르게 한다. 실패 시 유사도 상위 picks개로 폴백.
    """
    fallback = candidates[:picks]
    if not OPENAI_API_KEY or len(candidates) <= picks:
        return fallback
    listed = "\n".join(
        f"{n + 1}. {c['ref']} :: {_clip(str(c['text']), 80)}"
        for n, c in enumerate(candidates)
    )
    system = (
        "너는 사용자의 감정/상황에 가장 잘 맞는 성경 구절을 고르는 목회적 도우미다. "
        "표면 단어의 일치가 아니라 '의미와 정서'가 통하는 구절을 우선한다."
    )
    user = (
        f'사용자 입력: "{mood}"\n\n'
        f"후보 구절({len(candidates)}개):\n{listed}\n\n"
        f"위 후보 중 사용자 입력의 감정·상황에 가장 잘 어울리는 {picks}개를 "
        "가장 잘 맞는 순서대로 골라라. 후보 번호만 JSON으로 출력하라. "
        '형식: {"picks": [번호, 번호, 번호]}'
    )
    try:
        parsed = json.loads(_call_openai_as_json(system, user, max_tokens=100))
        nums = parsed.get("picks") if isinstance(parsed, dict) else parsed
        selected: List[dict] = []
        seen: set[int] = set()
        for n in (nums or []):
            idx = int(n) - 1
            if 0 <= idx < len(candidates) and idx not in seen:
                seen.add(idx)
                selected.append(candidates[idx])
            if len(selected) >= picks:
                break
        # LLM이 부족하게 골랐으면 유사도 순으로 채운다.
        for i, c in enumerate(candidates):
            if len(selected) >= picks:
                break
            if i not in seen:
                selected.append(c)
        return selected[:picks] if selected else fallback
    except Exception:
        log.exception("verse selection failed; fallback to top-k")
        return fallback


def _prepare_recommendations(mood: str, search_k: int, picks: int) -> List[dict]:
    """쿼리 확장 → 넓게 검색 → LLM 재순위 를 한 번에 수행(동기, executor용)."""
    query = _expand_search_query(mood)
    candidates = _search_candidates(query, search_k)
    return _select_verses(mood, candidates, picks)


# ---------- /recommend/stream (SSE) ----------
def _recommend_stream_response(mood: str) -> StreamingResponse:
    # 넓게 뽑아(SEARCH_K) LLM이 재순위해서 PICKS개를 확정한다.
    SEARCH_K = 15
    PICKS = 3
    COMMENT_STYLE = "long"
    KOREAN_ONLY = True

    async def generate_sse():
        meta = {
            "event": "meta",
            "mood": mood,
            "model": OPENAI_MODEL,
            "style": COMMENT_STYLE,
        }
        yield f"data: {json.dumps(meta, ensure_ascii=False)}\n\n"

        loop = asyncio.get_event_loop()
        limits = _style_to_limits(COMMENT_STYLE)
        system = _RECOMMEND_SYSTEM
        per_card_tokens = max(300, limits["max_tokens"] // PICKS)

        # 준비 단계: 쿼리 확장 → 넓게 검색 → LLM 재순위. 진행 중엔 ping 으로 연결 유지.
        prep_task = loop.run_in_executor(
            None, _prepare_recommendations, mood, SEARCH_K, PICKS
        )
        while not prep_task.done():
            yield f"data: {json.dumps({'event': 'ping'}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(1)
        selected_verses = await prep_task

        if not selected_verses:
            yield f"data: {json.dumps({'event': 'done'}, ensure_ascii=False)}\n\n"
            return

        for idx, selected in enumerate(selected_verses):
            verse_data = {"text": str(selected["text"]), "ref": selected["ref"]}
            if KOREAN_ONLY:
                verse_data["text"] = _keep_korean_only(verse_data["text"])
            yield f"data: {json.dumps({'event': 'verse', 'index': idx, 'verse': verse_data}, ensure_ascii=False)}\n\n"

            user = _build_single_comment_prompt(mood, selected, limits)
            try:
                async for token in _stream_openai(system, user, per_card_tokens):
                    yield f"data: {json.dumps({'event': 'token', 'index': idx, 'content': token}, ensure_ascii=False)}\n\n"
            except Exception as e:
                log.exception("streaming error for card %d", idx)
                yield f"data: {json.dumps({'event': 'error', 'index': idx, 'message': str(e)}, ensure_ascii=False)}\n\n"
                break

        yield f"data: {json.dumps({'event': 'done'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # nginx 버퍼링 비활성화
        }
    )


@app.post(
    "/recommend/stream",
    responses={
        200: {
            "description": "SSE 스트리밍 응답 (text/event-stream)",
            "content": {
                "text/event-stream": {
                    "example": """data: {"event": "meta", "mood": "불안하고 잠이 안 와요", "model": null, "style": null}

data: {"event": "ping"}

data: {"event": "verse", "index": 0, "verse": {"text": "여호와는 나의 목자시니...", "ref": "시편 23:1"}}
data: {"event": "verse", "index": 1, "verse": {"text": "...", "ref": "..."}}
data: {"event": "verse", "index": 2, "verse": {"text": "...", "ref": "..."}}
data: {"event": "done"}"""
                }
            }
        },
        422: {"description": "Validation Error"}
    },
    summary="성경 구절 추천 (스트리밍)",
    description="""
SSE(Server-Sent Events) 방식으로 성경 구절과 코멘트를 카드 단위로 순차 스트리밍합니다.

## 이벤트 흐름
1. **meta** → 즉시 전송
2. **ping** → 각 카드의 RAG 처리 중 heartbeat (무시 가능)
3. **verse** (index=0) → 첫 번째 카드 text, ref
4. **token** (index=0) → 첫 번째 카드 tag, comment 스트리밍
5. **verse** (index=1) → 두 번째 카드 text, ref
6. **token** (index=1) → 두 번째 카드 tag, comment 스트리밍
7. **verse** (index=2) → 세 번째 카드 text, ref
8. **token** (index=2) → 세 번째 카드 tag, comment 스트리밍
9. **done** → 스트리밍 종료
10. **error** → 에러 발생 시

## 각 이벤트 형식
- **meta**: `{"event": "meta", "mood": "...", "model": "...", "style": "..."}`
- **ping**: `{"event": "ping"}`
- **verse**: `{"event": "verse", "index": 0, "verse": {"text": "...", "ref": "..."}}`
- **token**: `{"event": "token", "index": 0, "content": "..."}`
- **done**: `{"event": "done"}`
- **error**: `{"event": "error", "index": 0, "message": "..."}`

## React Native 사용 예시
```javascript
import EventSource from 'react-native-sse';

const es = new EventSource(url, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ mood: '오늘 힘들어요' }),
});

es.addEventListener('message', (e) => {
  const data = JSON.parse(e.data);
  switch (data.event) {
    case 'meta':
      // 연결 확인
      break;
    case 'ping':
      // 무시 (heartbeat)
      break;
    case 'verse':
      // data.index번째 카드에 text, ref 표시
      setCardVerse(data.index, data.verse);
      break;
    case 'token':
      // data.index번째 카드에 tag+comment 스트리밍 추가
      appendCardToken(data.index, data.content);
      break;
    case 'done':
      // 스트리밍 종료
      es.close();
      break;
    case 'error':
      setError(data.message);
      es.close();
      break;
  }
});
```
"""
)
async def recommend_stream(inp: RecommendIn):
    """POST 바디 기반 카드 순차 SSE 스트리밍."""
    return _recommend_stream_response(inp.mood)


def _comment_stream_response(inp: CommentStreamIn) -> StreamingResponse:
    COMMENT_STYLE = "long"
    KOREAN_ONLY = True

    async def generate_sse():
        index_value = int(inp.index or 0)
        limits = _style_to_limits(COMMENT_STYLE)
        system = _RECOMMEND_SYSTEM
        verse = {"ref": inp.ref, "text": inp.text}
        if KOREAN_ONLY:
            verse["text"] = _keep_korean_only(verse["text"])

        meta = {
            "event": "meta",
            "mood": inp.mood,
            "ref": verse["ref"],
            "index": index_value,
            "model": OPENAI_MODEL,
            "style": COMMENT_STYLE,
        }
        yield f"data: {json.dumps(meta, ensure_ascii=False)}\n\n"

        user = _build_single_comment_prompt(inp.mood, verse, limits)
        try:
            async for token in _stream_openai(system, user, limits["max_tokens"]):
                yield f"data: {json.dumps({'event': 'token', 'index': index_value, 'content': token}, ensure_ascii=False)}\n\n"
        except Exception as e:
            log.exception("comment streaming error for card %d", index_value)
            yield f"data: {json.dumps({'event': 'error', 'index': index_value, 'message': str(e)}, ensure_ascii=False)}\n\n"
            return

        yield f"data: {json.dumps({'event': 'done', 'index': index_value}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.post(
    "/comment/stream",
    responses={
        200: {
            "description": "SSE 스트리밍 응답 (text/event-stream)",
            "content": {
                "text/event-stream": {
                    "example": """data: {"event": "meta", "mood": "불안하고 잠이 안 와요", "ref": "시편 23:1", "index": 0, "model": "gpt-4o-mini", "style": "long"}

data: {"event": "token", "index": 0, "content": "{\\"tag\\": \\"두려움\\", \\"comment\\": \\"지금은..."}
...
data: {"event": "done", "index": 0}"""
                }
            }
        },
        422: {"description": "Validation Error"}
    },
    summary="성경 코멘트 생성 (스트리밍)",
    description="""
SSE(Server-Sent Events) 방식으로 성경 구절 1건에 대한 코멘트만 생성합니다.

## 요청 바디
- **mood**: 사용자의 기분/상태
- **ref**: 말씀 참조
- **text**: 말씀 본문
- **index**: 클라이언트 카드 인덱스

## 이벤트 흐름
1. **meta** → 즉시 전송
2. **token** → tag, comment JSON 스트리밍
3. **done** → 스트리밍 종료
4. **error** → 에러 발생 시
"""
)
async def comment_stream(inp: CommentStreamIn):
    """POST 바디 기반 comment-only SSE 스트리밍."""
    return _comment_stream_response(inp)


# 자체 지표: POST /telemetry/events(앱 수집) + GET /admin/analytics/*(대시보드)
app.include_router(analytics_router)
# 앱 버전 게이팅: GET /app-version (업데이트 안내 팝업용)
app.include_router(app_version_router)


@app.on_event("startup")
async def startup_notifications() -> None:
    manager = build_notification_manager(APP_SETTINGS)
    # /daily-verse 응답의 interpretation 을 위해 LLM 풀이 생성기를 주입한다.
    # 푸시 배치 경로(jobs.run_daily_verse_batch)는 interpreter 없이 동작하므로 풀이를 생성하지 않는다.
    manager.verse_interpreter = VerseInterpreter(
        store=VerseInterpretationStore(APP_SETTINGS.verse_interpretation_store_path),
        generate_fn=_generate_verse_interpretation,
    )
    scheduler = DailyVerseScheduler(
        manager=manager,
        poll_seconds=APP_SETTINGS.scheduler_poll_seconds,
    )
    scheduler.start()
    app.state.notification_manager = manager
    app.state.notification_scheduler = scheduler

    # 자체 지표 수집. 스키마 생성은 멱등이라 워커마다 호출돼도 안전하다.
    init_analytics_db(APP_SETTINGS.analytics_db_path)
    rollup_scheduler = AnalyticsRollupScheduler(
        db_path=APP_SETTINGS.analytics_db_path,
        hour=APP_SETTINGS.analytics_rollup_hour,
        raw_retention_days=APP_SETTINGS.analytics_raw_retention_days,
    )
    rollup_scheduler.start()
    app.state.analytics_scheduler = rollup_scheduler


@app.on_event("shutdown")
async def shutdown_notifications() -> None:
    scheduler = getattr(app.state, "notification_scheduler", None)
    if scheduler is not None:
        scheduler.stop()
    rollup_scheduler = getattr(app.state, "analytics_scheduler", None)
    if rollup_scheduler is not None:
        rollup_scheduler.stop()
