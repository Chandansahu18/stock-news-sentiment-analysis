"""FastAPI application entry point.  Run:  uvicorn app.main:app --host 127.0.0.1 --port 8010

SECURITY NOTE: this API has NO authentication. Keep it bound to 127.0.0.1 and do not expose it to the
internet without adding authentication and rate limiting.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

from .api.error_handlers import register_error_handlers
from .api.routes import router
from .warmup import start_background_warmup

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    start_background_warmup()
    yield


def create_app() -> FastAPI:
    application = FastAPI(
        title="Indian Stock News Sentiment API",
        version="2.0.0",
        description="News, FinBERT sentiment and prices for NSE stocks. Informational only, not investment advice.",
        lifespan=lifespan,
    )
    application.add_middleware(GZipMiddleware, minimum_size=1000)  # smaller JSON on the wire
    register_error_handlers(application)
    application.include_router(router)
    return application


app = create_app()
