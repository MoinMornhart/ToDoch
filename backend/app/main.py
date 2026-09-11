"""App-Fabrik. Start: ``uvicorn app.main:create_app --factory``."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api import (
    area_members,
    areas,
    auth,
    calendar_sync,
    calendars,
    contacts,
    events,
    feeds,
    mail,
    mail_oauth,
    mail_rules,
    meta,
    passkeys,
    push,
    tasks,
    totp,
)
from app.config import Settings, load_settings
from app.i18n import language_from, translate
from app.resources import Resources, build_resources
from app.security.middleware import SecurityMiddleware

VALUE_ERROR = "Value error, "


def _translate_msg(message: str, language: str) -> str:
    """Pydantic-Meldungen aus eigenen Validatoren tragen das Präfix „Value error, “."""
    if message.startswith(VALUE_ERROR):
        return VALUE_ERROR + translate(message.removeprefix(VALUE_ERROR), language)
    return translate(message, language)


def create_app(settings: Settings | None = None, resources: Resources | None = None) -> FastAPI:
    settings = settings or (resources.settings if resources else load_settings())
    logging.basicConfig(level=settings.log_level.upper())

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owned = resources is None
        app.state.resources = resources or build_resources(settings)
        try:
            yield
        finally:
            if owned:
                await app.state.resources.close()

    app = FastAPI(
        title="ToDoch API",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None if settings.environment == "production" else "/api/openapi.json",
        lifespan=lifespan,
    )
    if resources is not None:
        app.state.resources = resources

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Eingaben (z. B. Passwörter) nie in Fehlermeldungen zurückspiegeln.
        language = language_from(request.headers.get("accept-language"))
        errors = [
            {
                "loc": list(err.get("loc", ())),
                "msg": _translate_msg(str(err.get("msg", "")), language),
                "type": err.get("type"),
            }
            for err in exc.errors()
        ]
        return JSONResponse({"detail": errors}, status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Meldungen in der Sprache der Oberfläche (Accept-Language), Header wie Retry-After bleiben
        detail = exc.detail
        if isinstance(detail, str):
            detail = translate(detail, language_from(request.headers.get("accept-language")))
        return JSONResponse({"detail": detail}, status_code=exc.status_code, headers=exc.headers)

    modules = (
        meta,
        auth,
        passkeys,
        totp,
        areas,
        area_members,
        tasks,
        events,
        feeds,
        calendars,
        calendar_sync,
        push,
        contacts,
        mail_rules,
        mail_oauth,
        mail,
    )
    for module in modules:
        app.include_router(module.router)

    app.add_middleware(SecurityMiddleware, settings=settings)
    return app
