from datetime import datetime, timezone

import httpx
import pytest

from investsim.config import FinnhubConfig
from investsim.providers.finnhub import FinnhubMarketDataProvider
from investsim.providers.market_data import UnknownSymbol


def _client(handler) -> httpx.Client:
    return httpx.Client(
        base_url="https://finnhub.io/api/v1",
        transport=httpx.MockTransport(handler),
    )


def _cfg() -> FinnhubConfig:
    return FinnhubConfig(api_key="testkey")


def test_get_quote_parses_price_and_timestamp():
    ts = 1_752_000_000  # unix segundos

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["symbol"] == "AAPL"
        assert request.url.params["token"] == "testkey"
        return httpx.Response(200, json={"c": 134.0, "t": ts})

    provider = FinnhubMarketDataProvider(_cfg(), client=_client(handler))
    quote = provider.get_quote("AAPL")

    assert quote.symbol == "AAPL"
    assert quote.price == 134.0
    assert quote.as_of == datetime.fromtimestamp(ts, tz=timezone.utc)


def test_unknown_symbol_when_price_zero():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"c": 0, "t": 0})

    provider = FinnhubMarketDataProvider(_cfg(), client=_client(handler))
    with pytest.raises(UnknownSymbol):
        provider.get_quote("NOPE")
