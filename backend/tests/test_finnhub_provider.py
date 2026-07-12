from datetime import datetime, timedelta, timezone

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


class _CountingHandler:
    """Cuenta cuántas peticiones HTTP se hacen y siempre devuelve el mismo precio."""

    def __init__(self, price: float = 100.0, ts: int = 1_752_000_000) -> None:
        self.calls = 0
        self.price = price
        self.ts = ts

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        return httpx.Response(200, json={"c": self.price, "t": self.ts})


def test_cache_avoids_second_http_call_within_ttl():
    handler = _CountingHandler()
    now = [datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc)]
    provider = FinnhubMarketDataProvider(
        _cfg(), client=_client(handler), clock=lambda: now[0]
    )

    provider.get_quote("AAPL")
    now[0] += timedelta(seconds=30)  # dentro del TTL (60s)
    provider.get_quote("AAPL")

    assert handler.calls == 1


def test_cache_refetches_after_ttl_expires():
    handler = _CountingHandler()
    now = [datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc)]
    provider = FinnhubMarketDataProvider(
        _cfg(), client=_client(handler), clock=lambda: now[0]
    )

    provider.get_quote("AAPL")
    now[0] += timedelta(seconds=61)  # pasado el TTL (60s)
    provider.get_quote("AAPL")

    assert handler.calls == 2
