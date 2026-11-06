from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes_api import router as api_router
from app.api.routes_pages import router as pages_router

logger = logging.getLogger(__name__)

_VALIDATION_DETAIL = "Некорректные входные данные"


def _is_api_request(request: Request) -> bool:
    path = request.url.path
    return path.startswith("/generate") and not path.startswith("/generate-file")


def _error_response(request: Request, detail: str, status_code: int) -> Response:
    if _is_api_request(request):
        return JSONResponse({"detail": detail}, status_code=status_code)
    return HTMLResponse(f"<p>{detail}</p>", status_code=status_code)


def create_app() -> FastAPI:
    """Создаёт и настраивает приложение FastAPI."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app = FastAPI(title="AI Product Card Generator")

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> Response:
        # Детали валидации — в лог, наружу — нейтральный текст.
        logger.warning("Ошибка валидации запроса: %s", exc.errors())
        status = 422 if _is_api_request(request) else 400
        return _error_response(request, _VALIDATION_DETAIL, status)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> Response:
        detail = exc.detail if isinstance(exc.detail, str) else "Ошибка запроса"
        return _error_response(request, detail, exc.status_code)

    app.include_router(pages_router)
    app.include_router(api_router)
    return app


app = create_app()
