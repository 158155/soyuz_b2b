from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _clean_value(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return {
            str(key).strip(): _clean_value(item)
            for key, item in value.items()
            if str(key).strip()
        }
    if isinstance(value, list):
        return [_clean_value(item) for item in value]
    return value


class ProductInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str | None = None
    manufacturer: str | None = None
    description: str | None = None
    specs: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def _clean_input(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return _clean_value(data)
        return data


class ProductCard(BaseModel):
    seo_title: str
    seo_description: str
    key_features: list[str] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list, min_length=3, max_length=5)
    commercial_block: str
    missing_fields: list[str] = Field(default_factory=list)
    notes: str = ""

    @field_validator("seo_title")
    @classmethod
    def _title_len(cls, v: str) -> str:
        from app.constants import SEO_TITLE_MAX_LENGTH

        v = v.strip()
        if len(v) > SEO_TITLE_MAX_LENGTH:
            raise ValueError(
                f"SEO-заголовок не должен быть длиннее {SEO_TITLE_MAX_LENGTH} символов"
            )
        if not v:
            raise ValueError("SEO-заголовок обязателен")
        return v

    @field_validator("seo_description")
    @classmethod
    def _desc_len(cls, v: str) -> str:
        from app.constants import (
            SEO_DESCRIPTION_MAX_LENGTH,
            SEO_DESCRIPTION_MIN_LENGTH,
        )

        v = v.strip()
        if not (SEO_DESCRIPTION_MIN_LENGTH <= len(v) <= SEO_DESCRIPTION_MAX_LENGTH):
            raise ValueError(
                f"SEO-описание должно быть от {SEO_DESCRIPTION_MIN_LENGTH} "
                f"до {SEO_DESCRIPTION_MAX_LENGTH} символов"
            )
        return v


class GenerateRequest(BaseModel):
    product: ProductInput


class GenerateResponse(BaseModel):
    card: ProductCard
    raw: dict[str, Any] | None = None
