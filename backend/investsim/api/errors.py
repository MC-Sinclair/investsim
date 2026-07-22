from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from investsim.agent.claude_cli import (
    ClaudeCliTimeout,
    ClaudeCliUnavailable,
    InvalidClaudeCliResponse,
)
from investsim.providers.market_data import ProviderUnavailable, UnknownSymbol
from investsim.services.portfolio_service import InsufficientFunds


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(UnknownSymbol)
    async def _unknown_symbol_handler(
        request: Request, exc: UnknownSymbol
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404, content={"detail": f"Simbolo desconocido: {exc}"}
        )

    @app.exception_handler(ProviderUnavailable)
    async def _provider_unavailable_handler(
        request: Request, exc: ProviderUnavailable
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(InsufficientFunds)
    async def _insufficient_funds_handler(
        request: Request, exc: InsufficientFunds
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(ClaudeCliUnavailable)
    async def _claude_cli_unavailable_handler(
        request: Request, exc: ClaudeCliUnavailable
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(ClaudeCliTimeout)
    async def _claude_cli_timeout_handler(
        request: Request, exc: ClaudeCliTimeout
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(InvalidClaudeCliResponse)
    async def _invalid_claude_cli_response_handler(
        request: Request, exc: InvalidClaudeCliResponse
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})
