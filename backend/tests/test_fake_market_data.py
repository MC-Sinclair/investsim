from datetime import datetime, timezone

import pytest

from investsim.providers.market_data import (
    FakeMarketDataProvider,
    Quote,
    UnknownSymbol,
)


def test_get_quote_returns_configured_price():
    as_of = datetime(2026, 7, 7, tzinfo=timezone.utc)
    provider = FakeMarketDataProvider({"AAPL": 100.0}, as_of=as_of)
    quote = provider.get_quote("AAPL")
    assert quote == Quote(symbol="AAPL", price=100.0, as_of=as_of)


def test_set_price_updates_quote():
    provider = FakeMarketDataProvider({"AAPL": 100.0})
    provider.set_price("AAPL", 120.0)
    assert provider.get_quote("AAPL").price == 120.0


def test_unknown_symbol_raises():
    provider = FakeMarketDataProvider({})
    with pytest.raises(UnknownSymbol):
        provider.get_quote("NOPE")
