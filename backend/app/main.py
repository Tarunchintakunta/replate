"""Local ReWords API."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import apply_model_env, get_settings
from app.errors import AppError
from app.services.document_service import get_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("rewords")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    apply_model_env(settings)
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    removed = get_service().storage.cleanup(settings.cleanup_hours)
    if removed:
        logger.info("Removed %s expired document directories", removed)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    apply_model_env(settings)
    app = FastAPI(title="Local ReWords", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")

    @app.exception_handler(AppError)
    async def app_error(_request: Request, exc: AppError) -> JSONResponse:
        logger.info("request error %s: %s", exc.code, exc.message)
        return JSONResponse(status_code=exc.status_code, content=exc.as_body())

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        parts: list[str] = []
        code = "VALIDATION_ERROR"
        for item in exc.errors():
            loc = ".".join(str(part) for part in item.get("loc", []) if part != "body")
            message = item.get("msg", "Invalid value")
            parts.append(f"{loc}: {message}" if loc else message)
            if "new_text" in loc:
                code = "INVALID_REPLACEMENT_TEXT"
        return JSONResponse(
            status_code=422,
            content={"error": {"code": code, "message": "; ".join(parts) or "Invalid request."}},
        )

    @app.exception_handler(Exception)
    async def unexpected(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error")
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL", "message": "The request failed."}},
        )

    return app


app = create_app()
