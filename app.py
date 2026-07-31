"""MASQUERADE '26 backend-only chatbot service.

The public API follows the Chat Completions format required by the event.  Groq
is used only as the upstream AI provider; no OpenAI account or API key is used.
"""

from __future__ import annotations

import hmac
import os
import time
import uuid
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field


load_dotenv()


GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"
DEFAULT_PUBLIC_MODEL_NAME = "masquerade-groq-chatbot"
DEFAULT_SYSTEM_PROMPT = """You are Masquerade, a warm, thoughtful, and naturally conversational AI companion.
Respond helpfully and clearly. Pay close attention to the conversation history, avoid repeating yourself,
and ask a brief, relevant follow-up question when it genuinely helps the conversation. Do not claim personal
experiences or emotions you do not have. Keep answers appropriately concise unless the user asks for detail."""


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class ChatCompletionRequest(BaseModel):
    model: str = Field(min_length=1)
    messages: list[ChatMessage] = Field(min_length=1)
    stream: bool = False
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=4096)


app = FastAPI(
    title="MASQUERADE '26 Groq Chatbot",
    version="1.0.0",
    docs_url="/docs",
    redoc_url=None,
)


def setting(name: str, default: str | None = None) -> str | None:
    return os.getenv(name, default)


def validate_judge_key(authorization: str | None) -> None:
    """Require a Bearer key only when JUDGE_API_KEY is configured."""
    expected_key = setting("JUDGE_API_KEY")
    if not expected_key:
        return

    expected_header = f"Bearer {expected_key}"
    if not authorization or not hmac.compare_digest(authorization, expected_header):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def upstream_messages(messages: list[ChatMessage]) -> list[dict[str, str]]:
    """Keep every submitted conversation turn and prepend the bot personality."""
    return [{"role": "system", "content": setting("SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT)}] + [
        message.model_dump() for message in messages
    ]


async def request_groq(request: ChatCompletionRequest) -> dict[str, Any]:
    groq_key = setting("GROQ_API_KEY")
    if not groq_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server configuration error: GROQ_API_KEY is not set.",
        )

    payload: dict[str, Any] = {
        "model": setting("GROQ_MODEL", DEFAULT_GROQ_MODEL),
        "messages": upstream_messages(request.messages),
        "stream": False,
        "temperature": request.temperature if request.temperature is not None else 0.8,
        "max_tokens": request.max_tokens or int(setting("MAX_COMPLETION_TOKENS", "700") or "700"),
    }
    timeout = float(setting("GROQ_TIMEOUT_SECONDS", "55") or "55")

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                GROQ_CHAT_URL,
                headers={
                    "Authorization": f"Bearer {groq_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Groq did not respond before the timeout.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Could not reach Groq.") from exc

    if response.status_code >= 400:
        # Do not expose provider internals or credentials to the judging client.
        raise HTTPException(status_code=502, detail="Groq could not complete this request.")

    data = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="Groq returned an invalid completion.") from exc

    if not isinstance(content, str) or not content.strip():
        raise HTTPException(status_code=502, detail="Groq returned an empty completion.")

    return data


@app.get("/")
@app.head("/")
async def health_check() -> dict[str, str]:
    """A small health endpoint for Render and manual deployment checks."""
    return {"status": "ok", "service": "masquerade-groq-chatbot"}


@app.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Accept the required OpenAI-compatible request, then generate through Groq."""
    validate_judge_key(authorization)
    if request.stream:
        raise HTTPException(status_code=400, detail="Streaming is not enabled for this endpoint.")

    data = await request_groq(request)
    usage = data.get("usage") or {}
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": setting("PUBLIC_MODEL_NAME", DEFAULT_PUBLIC_MODEL_NAME),
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": data["choices"][0]["message"]["content"]},
                "finish_reason": data["choices"][0].get("finish_reason", "stop"),
            }
        ],
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        },
    }
