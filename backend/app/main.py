"""App-Fabrik. Start: ``uvicorn app.main:create_app --factory``."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app import __version__
from app.api import areas, auth, events, feeds, meta, push, tasks
from app.config import Settings, load_settings
from app.resources import Resources, build_resources
from app.security.middleware import SecurityMiddleware


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
        title="Todoch API",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None if settings.environment == "production" else "/api/openapi.json",
        lifespan=lifespan,
    )
    if resources is not None:
        app.state.resources = resources

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Eingaben (z. B. Passwörter) nie in Fehlermeldungen zurückspiegeln.
        errors = [
            {"loc": list(err.get("loc", ())), "msg": err.get("msg", ""), "type": err.get("type")}
            for err in exc.errors()
        ]
        return JSONResponse({"detail": errors}, status_code=422)

    for module in (meta, auth, areas, tasks, events, feeds, push):
        app.include_router(module.router)

    app.add_middleware(SecurityMiddleware, settings=settings)
    return app
