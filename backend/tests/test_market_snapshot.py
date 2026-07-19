from datetime import datetime, timezone

import pytest

from investsim.providers.market_data import (
    FakeMarketDataProvider,
    MarketSnapshot,
    UnknownSymbol,
)

AS_OF = datetime(2026, 7, 19, 15, 0, tzinfo=timezone.utc)


def _snapshot(symbol: str = "AAPL") -> MarketSnapshot:
    return MarketSnapshot(
        symbol=symbol,
        price=102.0,
        day_change_pct=1.5,
        day_high=104.0,
        day_low=100.0,
        day_open=100.5,
        prev_close=100.5,
        as_of=AS_OF,
    )


def test_snapshot_is_frozen():
    snapshot = _snapshot()
    with pytest.raises(Exception):
        snapshot.price = 999.0  # type: ignore[misc]


def test_fake_returns_configured_snapshot():
    provider = FakeMarketDataProvider({}, snapshots={"AAPL": _snapshot()})
    assert provider.get_snapshot("AAPL") == _snapshot()


def test_set_snapshot_updates_it():
    provider = FakeMarketDataProvider({})
    provider.set_snapshot(_snapshot("MSFT"))
    assert provider.get_snapshot("MSFT").day_change_pct == 1.5


def test_fake_derives_flat_snapshot_from_price_only():
    provider = FakeMarketDataProvider({"AAPL": 100.0}, as_of=AS_OF)
    snapshot = provider.get_snapshot("AAPL")

    assert snapshot == MarketSnapshot(
        symbol="AAPL",
        price=100.0,
        day_change_pct=0.0,
        day_high=100.0,
        day_low=100.0,
        day_open=100.0,
        prev_close=100.0,
        as_of=AS_OF,
    )


def test_unknown_symbol_raises_on_snapshot():
    provider = FakeMarketDataProvider({})
    with pytest.raises(UnknownSymbol):
        provider.get_snapshot("NOPE")
