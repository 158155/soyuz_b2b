from __future__ import annotations

import logging
import urllib.parse
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response

from app.markdown import to_markdown
from app.schemas import GenerateRequest, GenerateResponse
from app.service import GenerationError, generate_card
from app.services.export import download_response
from app.services.file_ingest import InputFileError, process_upload
from app.templating import templates

logger = logging.getLogger(__name__)
router = APIRouter()

_LLM_ERROR_DETAIL = (
    "LLM недоступна или вернула невалидный ответ. Повторите попытку позже."
)
_INTERNAL_ERROR_DETAIL = "Внутренняя ошибка сервера."


@router.post("/generate-file", response_class=HTMLResponse)
async def generate_file(
    request: Request,
    file: Annotated[UploadFile, File(...)],
    output_format: str = Form("md"),
) -> HTMLResponse:
    try:
        processed = await process_upload(file, output_format)
    except (InputFileError, ValueError) as exc:
        return templates.TemplateResponse(
            request,
            "result.html",
            {
                "cards": [],
                "errors": [str(exc)],
                "output_name": None,
                "download_url": None,
                "output_format": output_format,
            },
            status_code=400,
        )

    cards = []
    for product, card in zip(processed.successful_products, processed.cards):
        if processed.output_format == "md":
            content = to_markdown(card, product)
        else:
            content = card.model_dump_json(indent=2, ensure_ascii=False)
        cards.append(
            {"name": getattr(product, "name", None) or "Товар", "content": content}
        )

    download_url = None
    # Ссылка позволяет скачать результат без записи файла на сервере.
    if processed.content:
        download_url = (
            f"data:{processed.media_type};charset=utf-8,"
            + urllib.parse.quote(processed.content)
        )

    return templates.TemplateResponse(
        request,
        "result.html",
        {
            "cards": cards,
            "errors": processed.errors,
            "output_name": processed.filename if processed.content else None,
            "download_url": download_url,
            "output_format": processed.output_format,
        },
    )


@router.post("/export")
async def export_file(
    file: Annotated[UploadFile, File(...)],
    output_format: str = Form("md"),
) -> Response:
    try:
        processed = await process_upload(file, output_format)
    except (InputFileError, ValueError) as exc:
        # API-эндпоинт: ошибки — в JSON, не в HTML.
        return JSONResponse({"detail": str(exc)}, status_code=400)
    if not processed.content:
        return JSONResponse({"detail": "Нет данных для экспорта."}, status_code=400)
    return download_response(
        processed.content, processed.filename, processed.media_type
    )


@router.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest) -> GenerateResponse:
    try:
        card = await generate_card(req.product)
    except GenerationError as exc:
        logger.warning("Ошибка генерации карточки: %s", exc)
        raise HTTPException(status_code=502, detail=_LLM_ERROR_DETAIL) from exc
    except Exception as exc:
        # Детали — в лог, наружу — нейтральный текст.
        logger.exception("Непредвиденная ошибка генерации карточки")
        raise HTTPException(status_code=500, detail=_INTERNAL_ERROR_DETAIL) from exc
    return GenerateResponse(card=card)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
