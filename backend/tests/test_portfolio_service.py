from datetime import datetime, timezone

import pytest

from investsim.db.base import Base, make_engine, make_session_factory
from investsim.db.repositories import PortfolioRepository, PredictionRepository
from investsim.domain.enums import Direction, Horizon
from investsim.providers.market_data import FakeMarketDataProvider
from investsim.services.portfolio_service import (
    InsufficientFunds,
    PortfolioService,
)

FIXED_NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def _service(cash=100.0, prices=None):
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = make_session_factory(engine)()
    portfolio_repo = PortfolioRepository(session)
    portfolio_repo.create(initial_capital=cash, created_at=FIXED_NOW)
    prediction_repo = PredictionRepository(session)
    market = FakeMarketDataProvider(prices or {"AAPL": 100.0}, as_of=FIXED_NOW)
    service = PortfolioService(
        portfolio_repo, prediction_repo, market, clock=lambda: FIXED_NOW
    )
    return service, portfolio_repo, prediction_repo


def test_open_prediction_records_trade_and_deducts_cash():
    service, portfolio_repo, _ = _service(cash=100.0, prices={"AAPL": 100.0})
    pred = service.open_prediction(
        symbol="AAPL",
        amount=10.0,
        direction=Direction.UP,
        confidence=0.8,
        horizon=Horizon.ONE_WEEK,
        rationale="momentum",
    )
    assert pred.entry_price == 100.0
    assert pred.shares == 0.1
    assert pred.status == "open"
    assert pred.expected_direction == "up"
    assert pred.evaluate_at == datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
    assert portfolio_repo.get().cash_balance == 90.0


def test_open_prediction_insufficient_funds_raises_and_keeps_cash():
    service, portfolio_repo, prediction_repo = _service(cash=5.0)
    with pytest.raises(InsufficientFunds):
        service.open_prediction(
            symbol="AAPL",
            amount=10.0,
            direction=Direction.UP,
            confidence=0.5,
            horizon=Horizon.ONE_DAY,
        )
    assert portfolio_repo.get().cash_balance == 5.0
    assert prediction_repo.list_all() == []
