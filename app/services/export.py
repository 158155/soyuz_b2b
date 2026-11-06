from __future__ import annotations

import json
from pathlib import Path

from fastapi.responses import Response

from app.constants import OUTPUT_FORMATS, OutputFormat
from app.markdown import to_markdown
from app.schemas import ProductCard, ProductInput


def parse_output_format(value: str) -> OutputFormat:
    """Проверяет формат вывода."""
    if value not in OUTPUT_FORMATS:
        raise ValueError("Неподдерживаемый формат вывода")
    return value  # type: ignore[return-value]


def safe_stem(filename: str | None) -> str:
    """Подготавливает безопасное имя файла."""
    stem = Path(filename or "result").stem
    # Защита от path traversal и спецсимволов в имени файла.
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in stem)
    return safe or "result"


def output_filename(filename: str | None, output_format: OutputFormat) -> str:
    """Формирует имя файла результата."""
    return f"{safe_stem(filename)}_out.{output_format}"


def build_markdown(products: list[ProductInput], cards: list[ProductCard]) -> str:
    """Собирает Markdown для списка карточек."""
    if not cards:
        return ""
    # Объединяем только успешно сгенерированные карточки.
    return (
        "\n\n---\n\n".join(
            to_markdown(card, product) for card, product in zip(cards, products)
        )
        + "\n"
    )


def build_json(cards: list[ProductCard]) -> str:
    """Собирает JSON для списка карточек."""
    return (
        json.dumps(
            [card.model_dump() for card in cards],
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )


def build_result_content(
    products: list[ProductInput],
    cards: list[ProductCard],
    output_format: OutputFormat,
) -> str:
    """Собирает содержимое результата в выбранном формате."""
    if output_format == "md":
        return build_markdown(products, cards)
    return build_json(cards)


def download_response(content: str, filename: str, media_type: str) -> Response:
    """Создаёт HTTP-ответ для скачивания файла."""
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
