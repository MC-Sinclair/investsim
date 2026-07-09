from datetime import datetime, timedelta, timezone

from investsim.db.base import Base, make_engine, make_session_factory
from investsim.db.repositories import PortfolioRepository, PredictionRepository
from investsim.db.tables import PredictionRow


def _session():
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return make_session_factory(engine)()


def test_portfolio_create_and_get():
    repo = PortfolioRepository(_session())
    now = datetime.now(timezone.utc)
    repo.create(initial_capital=10.0, created_at=now)
    got = repo.get()
    assert got is not None
    assert got.cash_balance == 10.0
    assert got.initial_capital == 10.0


def _make_prediction(symbol, evaluate_at, status="open"):
    now = datetime.now(timezone.utc)
    return PredictionRow(
        symbol=symbol,
        created_at=now,
        entry_price=100.0,
        amount=10.0,
        shares=0.1,
        horizon="1W",
        evaluate_at=evaluate_at,
        expected_direction="up",
        confidence=0.7,
        rationale="",
        status=status,
    )


def test_prediction_add_get_list():
    repo = PredictionRepository(_session())
    now = datetime.now(timezone.utc)
    added = repo.add(_make_prediction("AAPL", now))
    assert added.id is not None
    assert repo.get(added.id).symbol == "AAPL"
    assert len(repo.list_all()) == 1


def test_list_open_due_filters_by_status_and_time():
    session = _session()
    repo = PredictionRepository(session)
    now = datetime.now(timezone.utc)
    repo.add(_make_prediction("DUE", now - timedelta(hours=1)))          # vencida, open
    repo.add(_make_prediction("FUTURE", now + timedelta(days=1)))        # no vencida
    repo.add(_make_prediction("SETTLED", now - timedelta(hours=1),
                              status="settled"))                          # vencida pero ya liquidada
    due = repo.list_open_due(now)
    assert [p.symbol for p in due] == ["DUE"]
