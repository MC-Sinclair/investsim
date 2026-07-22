from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Iterator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from investsim.agent.engine import RecommendationEngine
from investsim.db.repositories import PortfolioRepository, PredictionRepository
from investsim.providers.market_data import MarketDataProvider
from investsim.services.agent_service import AgentService
from investsim.services.portfolio_service import PortfolioService
from investsim.services.settlement_service import SettlementService


def get_session(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_market_data_provider(request: Request) -> MarketDataProvider:
    return request.app.state.market_data


def get_recommendation_engine(request: Request) -> RecommendationEngine:
    return request.app.state.engine


def get_agent_service(
    market_data: MarketDataProvider = Depends(get_market_data_provider),
    engine: RecommendationEngine = Depends(get_recommendation_engine),
) -> AgentService:
    return AgentService(market_data, engine)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_clock() -> Callable[[], datetime]:
    return _utcnow


def get_portfolio_service(
    session: Session = Depends(get_session),
    market_data: MarketDataProvider = Depends(get_market_data_provider),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> PortfolioService:
    return PortfolioService(
        PortfolioRepository(session),
        PredictionRepository(session),
        market_data,
        clock=clock,
    )


def get_portfolio_repo(session: Session = Depends(get_session)) -> PortfolioRepository:
    return PortfolioRepository(session)


def get_prediction_repo(session: Session = Depends(get_session)) -> PredictionRepository:
    return PredictionRepository(session)


def get_settlement_service(
    session: Session = Depends(get_session),
    market_data: MarketDataProvider = Depends(get_market_data_provider),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> SettlementService:
    return SettlementService(
        PortfolioRepository(session),
        PredictionRepository(session),
        market_data,
        clock=clock,
    )
