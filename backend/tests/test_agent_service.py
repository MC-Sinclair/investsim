from datetime import datetime, timezone

import pytest

from investsim.agent.engine import Recommendation
from investsim.agent.rules import RuleBasedEngine
from investsim.domain.enums import Direction, Horizon
from investsim.providers.market_data import (
    FakeMarketDataProvider,
    MarketSnapshot,
    ProviderUnavailable,
    UnknownSymbol,
)
from investsim.services.agent_service import AgentService

AS_OF = datetime(2026, 7, 19, 15, 0, tzinfo=timezone.utc)

SNAPSHOT = MarketSnapshot(
    symbol="AAPL",
    price=102.0,
    day_change_pct=1.5,
    day_high=104.0,
    day_low=100.0,
    day_open=100.5,
    prev_close=100.5,
    as_of=AS_OF,
)


class _SpyEngine:
    """Registra el snapshot recibido y devuelve siempre la misma recomendación."""

    def __init__(self) -> None:
        self.seen: list[MarketSnapshot] = []
        self.recommendation = Recommendation(
            symbol="AAPL",
            direction=Direction.UP,
            confidence=0.4,
            suggested_amount=8.0,
            horizon=Horizon.ONE_DAY,
            rationale="fijo",
        )

    def propose(self, snapshot: MarketSnapshot) -> Recommendation:
        self.seen.append(snapshot)
        return self.recommendation


class _BrokenProvider:
    def get_quote(self, symbol: str):
        raise ProviderUnavailable(symbol)

    def get_snapshot(self, symbol: str) -> MarketSnapshot:
        raise ProviderUnavailable(symbol)


def test_propose_passes_snapshot_to_engine_and_returns_its_recommendation():
    provider = FakeMarketDataProvider({}, snapshots={"AAPL": SNAPSHOT})
    engine = _SpyEngine()
    service = AgentService(provider, engine)

    rec = service.propose("AAPL")

    assert engine.seen == [SNAPSHOT]
    assert rec is engine.recommendation


def test_propose_end_to_end_with_rule_based_engine():
    provider = FakeMarketDataProvider({}, snapshots={"AAPL": SNAPSHOT})
    service = AgentService(provider, RuleBasedEngine())

    rec = service.propose("AAPL")

    assert rec.symbol == "AAPL"
    assert rec.direction is Direction.UP
    assert rec.horizon is Horizon.ONE_DAY
    assert rec.confidence == pytest.approx(0.375)
    assert rec.suggested_amount == pytest.approx(7.5)


def test_unknown_symbol_propagates_without_recommendation():
    service = AgentService(FakeMarketDataProvider({}), RuleBasedEngine())
    with pytest.raises(UnknownSymbol):
        service.propose("NOPE")


def test_provider_unavailable_propagates_without_recommendation():
    engine = _SpyEngine()
    service = AgentService(_BrokenProvider(), engine)

    with pytest.raises(ProviderUnavailable):
        service.propose("AAPL")

    assert engine.seen == []  # el motor no llega a ejecutarse
