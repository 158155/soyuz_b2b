from __future__ import annotations

import json
from dataclasses import dataclass

from fastapi import UploadFile
from pydantic import ValidationError

from app.constants import OutputFormat
from app.schemas import ProductCard, ProductInput
from app.service import GenerationError, generate_card
from app.services.export import (
    build_result_content,
    output_filename,
    parse_output_format,
)


class InputFileError(Exception):
    """Ошибка чтения или валидации входного файла."""


FIELD_NAMES = {
    "name": "название",
    "manufacturer": "производитель",
    "specs": "характеристики",
    "description": "описание",
}


async def read_products(file: UploadFile) -> list[ProductInput]:
    """Читает и валидирует товары из JSON-файла."""
    try:
        raw = await file.read()
        text = raw.decode("utf-8")
        data = json.loads(text)
    except UnicodeDecodeError as exc:
        raise InputFileError("Файл должен быть в кодировке UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise InputFileError("Некорректный JSON: проверьте синтаксис файла") from exc
    except Exception as exc:
        raise InputFileError("Не удалось прочитать файл") from exc

    if not isinstance(data, (list, dict)):
        raise InputFileError("JSON должен содержать объект товара или массив товаров")

    items = data if isinstance(data, list) else [data]
    products: list[ProductInput] = []
    for idx, item in enumerate(items, start=1):
        try:
            products.append(ProductInput.model_validate(item))
        except ValidationError as exc:
            # Переводим ошибки Pydantic в понятные названия полей.
            fields = ", ".join(
                FIELD_NAMES.get(
                    str(error.get("loc", ("",))[-1]), str(error.get("loc", ("",))[-1])
                )
                for error in exc.errors()
            )
            raise InputFileError(
                f"Товар {idx}: ошибка валидации полей: {fields}"
            ) from exc

    if not products:
        raise InputFileError("Файл не содержит товаров")
    return products


@dataclass
class ProcessedUpload:
    products: list[ProductInput]
    cards: list[ProductCard]
    successful_products: list[ProductInput]
    errors: list[str]
    output_format: OutputFormat
    content: str
    filename: str
    media_type: str


async def process_upload(
    file: UploadFile,
    output_format: str,
) -> ProcessedUpload:
    """Обрабатывает загруженный файл и генерирует карточки."""
    parsed_format = parse_output_format(output_format)
    products = await read_products(file)
    cards: list[ProductCard] = []
    successful_products: list[ProductInput] = []
    errors: list[str] = []

    for idx, product in enumerate(products, start=1):
        name = getattr(product, "name", None) or "без названия"
        try:
            # Ошибка одной карточки не прерывает обработку остальных.
            card = await generate_card(product)
        except GenerationError as exc:
            errors.append(f"Товар {idx} ({name}): {exc}")
            continue
        except Exception:  # noqa: BLE001
            errors.append(f"Товар {idx} ({name}): непредвиденная ошибка генерации")
            continue
        cards.append(card)
        successful_products.append(product)

    content = (
        build_result_content(successful_products, cards, parsed_format) if cards else ""
    )
    filename = output_filename(file.filename, parsed_format) if cards else ""
    return ProcessedUpload(
        products=products,
        cards=cards,
        successful_products=successful_products,
        errors=errors,
        output_format=parsed_format,
        content=content,
        filename=filename,
        media_type="text/markdown" if parsed_format == "md" else "application/json",
    )
