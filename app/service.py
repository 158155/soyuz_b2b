from __future__ import annotations

import logging

from pydantic import ValidationError

from app import fields
from app.constants import (
    SEO_DESCRIPTION_MAX_LENGTH,
    SEO_DESCRIPTION_MIN_LENGTH,
    SEO_TITLE_MAX_LENGTH,
)
from app.llm import LLMResponseError, chat_json
from app.prompts import SYSTEM_PROMPT, build_user_prompt
from app.schemas import ProductCard, ProductInput

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 2
SEARCH_QUERIES_MIN = 3
SEARCH_QUERIES_MAX = 5


class GenerationError(Exception):
    """Ошибка генерации карточки товара."""


class CardValidationError(Exception):
    """Ответ LLM — валидный JSON, но не проходит схему ProductCard."""

    def __init__(self, problem: str) -> None:
        super().__init__(problem)
        self.problem = problem


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _collect_missing(value: object, path: str, missing: list[str]) -> None:
    if _is_missing(value):
        missing.append(path)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _collect_missing(item, f"{path}.{key}", missing)
    elif isinstance(value, (list, tuple, set)):
        for index, item in enumerate(value):
            _collect_missing(item, f"{path}[{index}]", missing)


def detect_missing(product: ProductInput) -> list[str]:
    """Определяет отсутствующие поля товара (пути входного JSON)."""
    missing: list[str] = []
    for key, value in product.model_dump().items():
        _collect_missing(value, key, missing)
    return sorted(set(missing))


def _normalize_features(raw_features: list) -> list[str]:
    """Нормализует key_features из ответа LLM."""
    result: list[str] = []
    for feature in raw_features:
        feature = str(feature).strip()
        if not feature:
            continue
        label, separator, value = feature.partition(":")
        label = fields.feature_label(label.strip())
        if not label or fields.is_metadata_label(label):
            continue
        normalized = f"{label}: {value.strip()}" if separator else label
        if normalized not in result:
            result.append(normalized)
    return result


def _merge_missing(detected: list[str], llm_missing: list) -> list[str]:
    """Объединяет отсутствующие поля из detect_missing и ответа LLM."""
    allowed = set(detected)
    filtered = [str(x) for x in llm_missing if str(x) in allowed]
    return sorted(set(detected) | set(filtered))


def _ensure_missing_features(
    features: list[str], merged_missing: list[str]
) -> list[str]:
    """Дополняет key_features строками '<поле>: данных нет' для missing-полей."""
    for path in merged_missing:
        if fields.is_metadata_path(path):
            continue
        label = fields.feature_label(path)
        if not label:
            continue
        if not any(feature.startswith(f"{label}:") for feature in features):
            features.append(f"{label}: данных нет")
    return features


def _problem_for_title(raw: dict) -> str | None:
    value = str(raw.get("seo_title", "")).strip()
    length = len(value)
    if not value:
        return "seo_title: пусто (нужен непустой заголовок)"
    if length > SEO_TITLE_MAX_LENGTH:
        return (
            f"seo_title: {length} символов "
            f"(макс {SEO_TITLE_MAX_LENGTH}, сократи на ~{length - SEO_TITLE_MAX_LENGTH})"
        )
    return None


def _problem_for_description(raw: dict) -> str | None:
    value = str(raw.get("seo_description", "")).strip()
    length = len(value)
    if length < SEO_DESCRIPTION_MIN_LENGTH:
        return (
            f"seo_description: {length} символов "
            f"(нужно {SEO_DESCRIPTION_MIN_LENGTH}–{SEO_DESCRIPTION_MAX_LENGTH}, "
            f"добавь ~{SEO_DESCRIPTION_MIN_LENGTH - length})"
        )
    if length > SEO_DESCRIPTION_MAX_LENGTH:
        return (
            f"seo_description: {length} символов "
            f"(нужно {SEO_DESCRIPTION_MIN_LENGTH}–{SEO_DESCRIPTION_MAX_LENGTH}, "
            f"сократи на ~{length - SEO_DESCRIPTION_MAX_LENGTH})"
        )
    return None


def _problem_for_queries(raw: dict) -> str | None:
    queries = [str(x).strip() for x in (raw.get("search_queries") or [])]
    queries = [q for q in queries if q]
    count = len(queries)
    if count < SEARCH_QUERIES_MIN:
        return (
            f"search_queries: {count} непустых запросов "
            f"(нужно {SEARCH_QUERIES_MIN}–{SEARCH_QUERIES_MAX})"
        )
    if count > SEARCH_QUERIES_MAX:
        return (
            f"search_queries: {count} запросов "
            f"(нужно {SEARCH_QUERIES_MIN}–{SEARCH_QUERIES_MAX})"
        )
    return None


def _describe_card_problem(raw: dict) -> str:
    """Формирует конкретное описание проблемы для retry-промпта."""
    problems = [
        _problem_for_title(raw),
        _problem_for_description(raw),
        _problem_for_queries(raw),
    ]
    parts = [p for p in problems if p]
    if not parts:
        # Валидатор упал по причине, которую мы не предвидели, — общий текст.
        return "ответ не соответствует схеме карточки"
    return "; ".join(parts)


def _build_card(raw: dict, missing: list[str]) -> ProductCard:
    """Собирает карточку из ответа LLM."""
    merged_missing = _merge_missing(missing, raw.get("missing_fields") or [])
    key_features = _normalize_features(raw.get("key_features") or [])
    key_features = _ensure_missing_features(key_features, merged_missing)
    try:
        return ProductCard(
            seo_title=str(raw.get("seo_title", "")).strip(),
            seo_description=str(raw.get("seo_description", "")).strip(),
            key_features=key_features,
            search_queries=[str(x).strip() for x in (raw.get("search_queries") or [])],
            commercial_block=str(raw.get("commercial_block", "")).strip(),
            missing_fields=merged_missing,
            notes=str(raw.get("notes", "")).strip(),
        )
    except ValidationError as exc:
        raise CardValidationError(_describe_card_problem(raw)) from exc


def _retry_prompt(base_prompt: str, problem: str) -> str:
    return (
        base_prompt
        + "\n\nВАЖНО: предыдущий ответ не прошёл валидацию: "
        + problem
        + ".\n"
        "Перепиши ТОЛЬКО проблемные поля. "
        "Не меняй key_features, missing_fields, commercial_block и notes, "
        "если они уже корректны. "
        "Верни строго валидный JSON по схеме."
    )


async def generate_card(product: ProductInput) -> ProductCard:
    """Генерирует карточку товара."""
    missing = detect_missing(product)
    base_prompt = build_user_prompt(product.model_dump())

    last_exc: Exception | None = None
    last_problem = ""
    for attempt in range(MAX_ATTEMPTS):
        prompt = (
            base_prompt if attempt == 0 else _retry_prompt(base_prompt, last_problem)
        )
        try:
            raw = await chat_json(SYSTEM_PROMPT, prompt)
            return _build_card(raw, missing)
        except LLMResponseError as exc:
            last_exc = exc
            last_problem = "ответ не является валидным JSON"
            logger.warning("Попытка %s: %s", attempt + 1, last_problem)
        except CardValidationError as exc:
            last_exc = exc
            last_problem = exc.problem
            logger.warning("Попытка %s: %s", attempt + 1, last_problem)
    raise GenerationError(
        "Не удалось сгенерировать карточку товара: LLM вернула невалидный ответ."
    ) from last_exc
