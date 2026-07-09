from datetime import datetime, timedelta, timezone

from investsim.db.base import Base, make_engine, make_session_factory
from investsim.db.repositories import PortfolioRepository, PredictionRepository
from investsim.domain.enums import Direction, Horizon
from investsim.providers.market_data import FakeMarketDataProvider
from investsim.services.portfolio_service import PortfolioService
from investsim.services.settlement_service import SettlementService

T0 = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def _setup(cash=100.0, prices=None):
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = make_session_factory(engine)()
    portfolio_repo = PortfolioRepository(session)
    portfolio_repo.create(initial_capital=cash, created_at=T0)
    prediction_repo = PredictionRepository(session)
    market = FakeMarketDataProvider(prices or {"AAPL": 100.0}, as_of=T0)
    return portfolio_repo, prediction_repo, market


def test_settle_due_marks_settled_and_returns_cash_on_gain():
    portfolio_repo, prediction_repo, market = _setup(cash=100.0, prices={"AAPL": 100.0})
    opener = PortfolioService(
        portfolio_repo, prediction_repo, market, clock=lambda: T0
    )
    opener.open_prediction("AAPL", 10.0, Direction.UP, 0.9, Horizon.ONE_WEEK)

    # Una semana despues el precio sube a 134 -> +34%
    market.set_price("AAPL", 134.0)
    later = T0 + timedelta(weeks=1, minutes=1)
    settler = SettlementService(
        portfolio_repo, prediction_repo, market, clock=lambda: later
    )
    settled = settler.settle_due()

    assert len(settled) == 1
    pred = settled[0]
    assert pred.status == "settled"
    assert pred.exit_price == 134.0
    assert round(pred.pnl_pct, 2) == 34.0
    assert round(pred.final_value, 2) == 13.40
    assert pred.hit is True
    # cash: 100 - 10 (abrir) + 13.40 (liquidar)
    assert round(portfolio_repo.get().cash_balance, 2) == 103.40


def test_settle_due_marks_miss_when_direction_wrong():
    portfolio_repo, prediction_repo, market = _setup(prices={"AAPL": 100.0})
    opener = PortfolioService(portfolio_repo, prediction_repo, market, clock=lambda: T0)
    opener.open_prediction("AAPL", 10.0, Direction.UP, 0.6, Horizon.ONE_DAY)

    market.set_price("AAPL", 90.0)  # bajo, pero se predijo UP
    later = T0 + timedelta(days=2)
    settler = SettlementService(portfolio_repo, prediction_repo, market, clock=lambda: later)
    pred = settler.settle_due()[0]
    assert pred.hit is False
    assert round(pred.pnl_pct, 2) == -10.0


def test_settle_due_ignores_not_yet_due():
    portfolio_repo, prediction_repo, market = _setup(prices={"AAPL": 100.0})
    opener = PortfolioService(portfolio_repo, prediction_repo, market, clock=lambda: T0)
    opener.open_prediction("AAPL", 10.0, Direction.UP, 0.6, Horizon.ONE_MONTH)

    later = T0 + timedelta(days=1)  # aun no vence (1M)
    settler = SettlementService(portfolio_repo, prediction_repo, market, clock=lambda: later)
    assert settler.settle_due() == []


def test_mark_to_market_does_not_persist():
    portfolio_repo, prediction_repo, market = _setup(prices={"AAPL": 100.0})
    opener = PortfolioService(portfolio_repo, prediction_repo, market, clock=lambda: T0)
    pred = opener.open_prediction("AAPL", 10.0, Direction.UP, 0.6, Horizon.ONE_WEEK)

    market.set_price("AAPL", 150.0)
    settler = SettlementService(portfolio_repo, prediction_repo, market, clock=lambda: T0)
    value = settler.mark_to_market(pred)
    assert round(value, 2) == 15.0
    assert prediction_repo.get(pred.id).status == "open"  # no tocado
    assert prediction_repo.get(pred.id).final_value is None
