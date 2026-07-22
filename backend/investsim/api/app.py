from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from investsim.agent.claude_cli import ClaudeCliEngine
from investsim.agent.rules import RuleBasedEngine
from investsim.api.errors import register_exception_handlers
from investsim.api.routes import router
from investsim.config import load_finnhub_config
from investsim.db.base import Base, make_engine, make_session_factory
from investsim.db.repositories import PortfolioRepository
from investsim.providers.finnhub import FinnhubMarketDataProvider


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_url = os.environ.get("DATABASE_URL", "sqlite:///investsim.db")
    engine = make_engine(db_url)
    Base.metadata.create_all(engine)
    session_factory = make_session_factory(engine)

    session = session_factory()
    try:
        portfolio_repo = PortfolioRepository(session)
        if portfolio_repo.get() is None:
            initial_capital = float(os.environ.get("INITIAL_CAPITAL", "1000.0"))
            portfolio_repo.create(
                initial_capital=initial_capital, created_at=_utcnow()
            )
    finally:
        session.close()

    app.state.session_factory = session_factory
    app.state.market_data = FinnhubMarketDataProvider(load_finnhub_config())

    engine_name = os.environ.get("RECOMMENDATION_ENGINE", "rules")
    app.state.engine = (
        ClaudeCliEngine() if engine_name == "claude_cli" else RuleBasedEngine()
    )

    yield


def create_app() -> FastAPI:
    app = FastAPI(title="InvestSim API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"http://localhost:\d+",
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(router)
    return app


app = create_app()
