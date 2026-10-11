"""Turn service errors into HTTP responses without leaking internals."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.errors import DataUnavailableError, UnknownSymbolError


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(UnknownSymbolError)
    async def unknown_symbol(_: Request, __: UnknownSymbolError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": "We could not find that stock. Search by company name or stock code (for example TCS) to find a listed NSE stock."},
        )

    @app.exception_handler(DataUnavailableError)
    async def data_unavailable(_: Request, exc: DataUnavailableError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})
