from datetime import datetime, timezone

import httpx
import pytest

from investsim.config import FinnhubConfig
from investsim.providers.finnhub import FinnhubMarketDataProvider
from investsim.providers.market_data import UnknownSymbol

TS = 1_752_000_000

FULL_QUOTE = {
    "c": 102.0,
    "d": 1.5,
    "dp": 1.4925,
    "h": 104.0,
    "l": 100.0,
    "o": 100.5,
    "pc": 100.5,
    "t": TS,
}


def _client(handler) -> httpx.Client:
    return httpx.Client(
        base_url="https://finnhub.io/api/v1",
        transport=httpx.MockTransport(handler),
    )


def _cfg() -> FinnhubConfig:
    return FinnhubConfig(api_key="testkey")


def test_get_snapshot_parses_all_intraday_fields():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["symbol"] == "AAPL"
        return httpx.Response(200, json=FULL_QUOTE)

    provider = FinnhubMarketDataProvider(_cfg(), client=_client(handler))
    snapshot = provider.get_snapshot("AAPL")

    assert snapshot.symbol == "AAPL"
    assert snapshot.price == 102.0
    assert snapshot.day_change_pct == 1.4925
    assert snapshot.day_high == 104.0
    assert snapshot.day_low == 100.0
    assert snapshot.day_open == 100.5
    assert snapshot.prev_close == 100.5
    assert snapshot.as_of == datetime.fromtimestamp(TS, tz=timezone.utc)


def test_get_snapshot_unknown_symbol_when_price_zero():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"c": 0, "t": 0})

    provider = FinnhubMarketDataProvider(_cfg(), client=_client(handler))
    with pytest.raises(UnknownSymbol):
        provider.get_snapshot("NOPE")


def test_snapshot_and_quote_share_the_cache():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=FULL_QUOTE)

    now = [datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)]
    provider = FinnhubMarketDataProvider(
        _cfg(), client=_client(handler), clock=lambda: now[0]
    )

    provider.get_quote("AAPL")
    snapshot = provider.get_snapshot("AAPL")  # dentro del TTL (60s)

    assert calls["n"] == 1  # una sola llamada HTTP para ambos
    assert snapshot.day_high == 104.0


def test_snapshot_tolerates_missing_optional_fields():
    """Finnhub puede devolver null en dp/h/l/o/pc fuera de horario de mercado."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"c": 50.0, "dp": None, "h": None, "l": None, "o": None,
                  "pc": None, "t": TS},
        )

    provider = FinnhubMarketDataProvider(_cfg(), client=_client(handler))
    snapshot = provider.get_snapshot("QUIET")

    assert snapshot.day_change_pct == 0.0
    assert snapshot.day_high == 50.0
    assert snapshot.day_low == 50.0
    assert snapshot.day_open == 50.0
    assert snapshot.prev_close == 50.0
