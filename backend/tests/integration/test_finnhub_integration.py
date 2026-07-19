import os

import pytest

from investsim.config import load_finnhub_config
from investsim.providers.finnhub import FinnhubMarketDataProvider
from investsim.providers.market_data import MarketSnapshot, Quote

pytestmark = pytest.mark.integration

_HAS_KEY = bool(os.environ.get("FINNHUB_API_KEY", "").strip())


@pytest.mark.skipif(not _HAS_KEY, reason="requiere FINNHUB_API_KEY en el entorno")
def test_real_quote_for_known_symbol():
    provider = FinnhubMarketDataProvider(load_finnhub_config())
    quote = provider.get_quote("AAPL")

    assert isinstance(quote, Quote)
    assert quote.symbol == "AAPL"
    assert quote.price > 0


@pytest.mark.skipif(not _HAS_KEY, reason="requiere FINNHUB_API_KEY en el entorno")
def test_real_snapshot_for_known_symbol():
    provider = FinnhubMarketDataProvider(load_finnhub_config())
    snapshot = provider.get_snapshot("AAPL")

    assert isinstance(snapshot, MarketSnapshot)
    assert snapshot.symbol == "AAPL"
    assert snapshot.price > 0
    assert snapshot.day_low <= snapshot.price <= snapshot.day_high
