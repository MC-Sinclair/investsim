from datetime import datetime, timezone

import pytest

from investsim.api.deps import get_market_data_provider
from investsim.providers.market_data import (
    FakeMarketDataProvider,
    MarketSnapshot,
    ProviderUnavailable,
)

AS_OF = datetime(2026, 7, 19, 15, 0, tzinfo=timezone.utc)


def _snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        symbol="AAPL",
        price=102.0,
        day_change_pct=1.5,
        day_high=104.0,
        day_low=100.0,
        day_open=100.0,
        prev_close=100.0,
        as_of=AS_OF,
    )


def test_post_recommendations_happy_path(client):
    fake = FakeMarketDataProvider({}, snapshots={"AAPL": _snapshot()})
    client.app.dependency_overrides[get_market_data_provider] = lambda: fake

    response = client.post("/recommendations", json={"symbol": "AAPL"})

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "AAPL"
    assert body["direction"] == "up"
    assert body["confidence"] == pytest.approx(0.375)
    assert body["suggested_amount"] == pytest.approx(7.5)
    assert body["horizon"] == "1D"
    assert body["rationale"] == (
        "AAPL sube 1.50% hoy y cotiza en la zona media del rango diario."
    )


def test_post_recommendations_unknown_symbol_404(client):
    fake = FakeMarketDataProvider({})
    client.app.dependency_overrides[get_market_data_provider] = lambda: fake

    response = client.post("/recommendations", json={"symbol": "NOPE"})

    assert response.status_code == 404


def test_post_recommendations_provider_unavailable_503(client):
    class _BrokenProvider:
        def get_quote(self, symbol):
            raise ProviderUnavailable(symbol)

        def get_snapshot(self, symbol):
            raise ProviderUnavailable(symbol)

    client.app.dependency_overrides[get_market_data_provider] = lambda: _BrokenProvider()

    response = client.post("/recommendations", json={"symbol": "AAPL"})

    assert response.status_code == 503
