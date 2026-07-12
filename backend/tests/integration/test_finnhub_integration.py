import os

import pytest

from investsim.config import load_finnhub_config
from investsim.providers.finnhub import FinnhubMarketDataProvider
from investsim.providers.market_data import Quote

pytestmark = pytest.mark.integration

_HAS_KEY = bool(os.environ.get("FINNHUB_API_KEY", "").strip())


@pytest.mark.skipif(not _HAS_KEY, reason="requiere FINNHUB_API_KEY en el entorno")
def test_real_quote_for_known_symbol():
    provider = FinnhubMarketDataProvider(load_finnhub_config())
    quote = provider.get_quote("AAPL")

    assert isinstance(quote, Quote)
    assert quote.symbol == "AAPL"
    assert quote.price > 0
