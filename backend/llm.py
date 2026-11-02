"""생성 LLM 호출 — Anthropic Claude.

2026-11 OpenAI(gpt-4o-mini)에서 옮겼다. 9/18 OpenAI 결제가 막혀 AI 기능이 전부 멈췄다.
키는 ANTHROPIC_API_KEY, 모델은 LLM_MODEL(기본 claude-haiku-5-5).

Haiku 5.5 의 규칙:
- temperature·top_p·top_k 를 보내면 400 이다. 말투는 프롬프트로만 정한다.
- 생각(thinking)이 기본으로 켜져 있다. 코멘트·키워드처럼 바로 나와야 하는 호출은 끈다
  (끌 때 effort 는 high 이하여야 한다). 생각을 켜면 그 토큰도 max_tokens 에 들어간다.
- 응답 첫 블록이 생각일 수 있어서 글은 type 이 text 인 블록에서만 읽는다.
- JSON 은 output_config.format 의 스키마로 강제한다. 코드펜스 없이 JSON 만 온다.

app.py 가 load_dotenv() 뒤에 import 하므로 모듈 상수로 읽어도 .env 값이 들어온다.
"""
from __future__ import annotations

import os
from typing import AsyncIterator

import anthropic

LLM_MODEL = os.getenv("LLM_MODEL", "claude-haiku-5-5")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
TIMEOUT_SECONDS = 60.0

# 짧은 호출용 — 생각을 끄고 가장 낮은 강도로 부른다.
_FAST = {"thinking": {"type": "disabled"}, "output_config": {"effort": "low"}}

_client: anthropic.Anthropic | None = None
_async_client: anthropic.AsyncAnthropic | None = None


def configured() -> bool:
    return bool(ANTHROPIC_API_KEY)


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=TIMEOUT_SECONDS)
    return _client


def _async() -> anthropic.AsyncAnthropic:
    global _async_client
    if _async_client is None:
        _async_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY, timeout=TIMEOUT_SECONDS)
    return _async_client


def response_text(resp) -> str:
    """응답에서 글만 모은다(생각 블록은 건너뛴다)."""
    return "".join(b.text for b in resp.content if b.type == "text").strip()


def json_format(schema: dict) -> dict:
    return {"format": {"type": "json_schema", "schema": schema}}


def complete_text(system: str, user: str, max_tokens: int, model: str | None = None) -> str:
    resp = client().messages.create(
        model=model or LLM_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        **_FAST,
    )
    return response_text(resp)


def complete_json(
    system: str, user: str, max_tokens: int, schema: dict, model: str | None = None
) -> str:
    resp = client().messages.create(
        model=model or LLM_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        thinking=_FAST["thinking"],
        output_config={**_FAST["output_config"], **json_format(schema)},
    )
    return response_text(resp)


async def stream_json(
    system: str, user: str, max_tokens: int, schema: dict, model: str | None = None
) -> AsyncIterator[str]:
    """JSON 응답을 글 조각 단위로 흘려보낸다(앱이 조각을 이어 붙여 comment 를 그린다)."""
    async with _async().messages.stream(
        model=model or LLM_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        thinking=_FAST["thinking"],
        output_config={**_FAST["output_config"], **json_format(schema)},
    ) as stream:
        async for text in stream.text_stream:
            yield text
