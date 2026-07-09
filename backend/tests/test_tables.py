from datetime import datetime, timezone

from investsim.db.base import Base, make_engine, make_session_factory
from investsim.db.tables import PortfolioRow, PredictionRow


def _session():
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return make_session_factory(engine)()


def test_portfolio_roundtrip():
    session = _session()
    now = datetime.now(timezone.utc)
    session.add(PortfolioRow(cash_balance=10.0, initial_capital=10.0, created_at=now))
    session.commit()
    row = session.query(PortfolioRow).one()
    assert row.id is not None
    assert row.cash_balance == 10.0


def test_prediction_roundtrip_with_nullable_settlement_fields():
    session = _session()
    now = datetime.now(timezone.utc)
    session.add(
        PredictionRow(
            symbol="AAPL",
            created_at=now,
            entry_price=100.0,
            amount=10.0,
            shares=0.1,
            horizon="1W",
            evaluate_at=now,
            expected_direction="up",
            confidence=0.7,
            rationale="test",
            status="open",
        )
    )
    session.commit()
    row = session.query(PredictionRow).one()
    assert row.symbol == "AAPL"
    assert row.exit_price is None
    assert row.hit is None
