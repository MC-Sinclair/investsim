from datetime import datetime, timezone

import pytest

from investsim.agent.engine import Recommendation, RecommendationEngine
from investsim.domain.enums import Direction, Horizon
from investsim.providers.market_data import MarketSnapshot


def _recommendation() -> Recommendation:
    return Recommendation(
        symbol="AAPL",
        direction=Direction.UP,
        confidence=0.375,
        suggested_amount=7.5,
        horizon=Horizon.ONE_DAY,
        rationale="AAPL sube 1.50% hoy.",
    )


def test_recommendation_is_frozen():
    rec = _recommendation()
    with pytest.raises(Exception):
        rec.confidence = 0.9  # type: ignore[misc]


def test_recommendation_carries_domain_enums():
    rec = _recommendation()
    assert rec.direction is Direction.UP
    assert rec.horizon is Horizon.ONE_DAY
    assert rec.direction.value == "up"
    assert rec.horizon.value == "1D"


def test_engine_protocol_is_structural():
    """Cualquier objeto con propose(snapshot) cumple la interfaz, sin heredar."""

    class StubEngine:
        def propose(self, snapshot: MarketSnapshot) -> Recommendation:
            return _recommendation()

    engine: RecommendationEngine = StubEngine()
    snapshot = MarketSnapshot(
        symbol="AAPL",
        price=102.0,
        day_change_pct=1.5,
        day_high=104.0,
        day_low=100.0,
        day_open=100.5,
        prev_close=100.5,
        as_of=datetime(2026, 7, 19, tzinfo=timezone.utc),
    )
    assert engine.propose(snapshot) == _recommendation()
