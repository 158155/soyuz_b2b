from __future__ import annotations

from functools import lru_cache

from openai import AsyncOpenAI
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_base_url: str = Field(
        default="https://api.openai.com/v1",
        alias="LLM_BASE_URL",
    )
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")
    llm_timeout: float = Field(default=120.0, alias="LLM_TIMEOUT")
    llm_max_tokens: int | None = Field(default=None, alias="LLM_MAX_TOKENS")
    llm_max_concurrency: int = Field(default=1, alias="LLM_MAX_CONCURRENCY")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Возвращает настройки приложения (кэшировано)."""
    return Settings()


def _build_openai_client(
    base_url: str,
    api_key: str,
    timeout: float,
) -> AsyncOpenAI:
    """Создаёт async-клиент OpenAI."""
    if not api_key and "localhost" not in base_url and "127.0.0.1" not in base_url:
        raise RuntimeError("Для удалённого провайдера требуется LLM_API_KEY")
    return AsyncOpenAI(base_url=base_url, api_key=api_key or "local", timeout=timeout)


@lru_cache(maxsize=1)
def get_openai_client() -> AsyncOpenAI:
    """Возвращает кэшированный async-клиент OpenAI."""
    settings = get_settings()
    return _build_openai_client(
        settings.llm_base_url,
        settings.llm_api_key,
        settings.llm_timeout,
    )
