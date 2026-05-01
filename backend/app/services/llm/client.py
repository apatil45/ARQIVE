"""Ollama HTTP client bound to localhost only."""
from __future__ import annotations

import logging
from typing import Any, AsyncIterator

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
OLLAMA_BASE_URL = "http://127.0.0.1:11434"


def _ollama_params() -> dict[str, Any]:
    s = get_settings()
    return {
        "model": s.OLLAMA_MODEL,
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "repeat_penalty": 1.1,
            "num_ctx": 4096,
            "num_predict": 512,
            "stop": ["</s>", "[INST]"],
        },
        "stream": True,
        "format": "json",
    }


async def stream_completion(messages: list[dict[str, str]]) -> AsyncIterator[str]:
    """Stream tokens from Ollama /api/chat. Yields content strings."""
    s = get_settings()
    base = OLLAMA_BASE_URL
    async with httpx.AsyncClient(timeout=s.OLLAMA_TIMEOUT) as client:
        try:
            async with client.stream(
                "POST",
                f"{base}/api/chat",
                json={"messages": messages, **_ollama_params()},
            ) as resp:
                if resp.status_code == 404:
                    raise RuntimeError(
                        f"Ollama model '{s.OLLAMA_MODEL}' not found. "
                        f"Pull it: docker compose exec ollama ollama pull {s.OLLAMA_MODEL}"
                    )
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or line.strip() == "":
                        continue
                    try:
                        import json
                        obj = json.loads(line)
                        if "message" in obj and "content" in obj["message"]:
                            yield obj["message"]["content"]
                    except Exception:
                        continue
        except httpx.ConnectError as e:
            raise RuntimeError(
                "Cannot connect to Ollama. Is it running? "
                "Ensure Ollama is bound on 127.0.0.1:11434."
            ) from e


async def complete(messages: list[dict[str, str]]) -> str:
    """Non-streaming: return full response text."""
    out = []
    async for token in stream_completion(messages):
        out.append(token)
    return "".join(out)
