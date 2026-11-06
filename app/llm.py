from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from openai.types.chat import ChatCompletionMessageParam

from app.config import get_openai_client, get_settings

logger = logging.getLogger(__name__)

_semaphore_loop: asyncio.AbstractEventLoop | None = None
_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    """Возвращает семафор, привязанный к текущему event loop."""
    global _semaphore_loop, _semaphore
    loop = asyncio.get_running_loop()

    if _semaphore is None or _semaphore_loop is not loop:
        # Для тестов llm_max_concurrency ограничивается 1 вызовом к ллм,
        # если модель может принимать одновременно енесколько вызовов
        # можно увеличить
        _semaphore = asyncio.Semaphore(get_settings().llm_max_concurrency)
        _semaphore_loop = loop
    return _semaphore


class LLMResponseError(Exception):
    """LLM вернула ответ, который не удалось разобрать как JSON."""


def get_model() -> str:
    """Возвращает настроенную модель."""
    return get_settings().llm_model


def _extract_json(text: str) -> dict[str, Any]:
    """Извлекает JSON из ответа модели."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMResponseError("LLM вернула невалидный JSON") from exc


async def _request(
    messages: list[ChatCompletionMessageParam],
    temperature: float,
    **extra: Any,
) -> str:
    client = get_openai_client()
    settings = get_settings()
    kwargs: dict[str, Any] = {
        "model": settings.llm_model,
        "temperature": temperature,
        "messages": messages,
        **extra,
    }
    if settings.llm_max_tokens is not None:
        kwargs["max_tokens"] = settings.llm_max_tokens
    async with _get_semaphore():
        resp = await client.chat.completions.create(**kwargs)  # type: ignore[arg-type]
    return resp.choices[0].message.content or "{}"


async def chat_json(system: str, user: str, temperature: float = 0.3) -> dict[str, Any]:
    """Запрашивает у LLM структурированный JSON-ответ."""
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    try:
        content = await _request(
            messages, temperature, response_format={"type": "json_object"}
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("JSON mode недоступен, повтор без response_format: %s", exc)
        content = await _request(messages, temperature)
    return _extract_json(content)
