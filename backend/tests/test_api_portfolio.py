from datetime import datetime, timedelta, timezone

import pytest

from investsim.api.deps import get_clock, get_market_data_provider
from investsim.providers.market_data import FakeMarketDataProvider


def test_get_portfolio_returns_cash_and_total_value(client):
    fake = FakeMarketDataProvider({"AAPL": 100.0})
    client.app.dependency_overrides[get_market_data_provider] = lambda: fake

    client.post(
        "/predictions",
        json={
            "symbol": "AAPL",
            "amount": 10.0,
            "direction": "up",
            "confidence": 0.8,
            "horizon": "1W",
            "rationale": "",
        },
    )
    fake.set_price("AAPL", 150.0)

    response = client.get("/portfolio")

    assert response.status_code == 200
    body = response.json()
    assert body["cash_balance"] == pytest.approx(990.0)
    assert body["initial_capital"] == pytest.approx(1000.0)
    assert body["open_predictions_value"] == pytest.approx(15.0)
    assert body["total_value"] == pytest.approx(1005.0)


def test_get_portfolio_settles_due_predictions_first(client):
    now = [datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)]
    client.app.dependency_overrides[get_clock] = lambda: (lambda: now[0])

    fake = FakeMarketDataProvider({"AAPL": 100.0})
    client.app.dependency_overrides[get_market_data_provider] = lambda: fake

    client.post(
        "/predictions",
        json={
            "symbol": "AAPL",
            "amount": 10.0,
            "direction": "up",
            "confidence": 0.8,
            "horizon": "1D",
            "rationale": "",
        },
    )

    fake.set_price("AAPL", 110.0)
    now[0] += timedelta(days=1, minutes=1)

    response = client.get("/portfolio")

    assert response.status_code == 200
    body = response.json()
    assert body["cash_balance"] == pytest.approx(1001.0)  # 1000 - 10 + 11
    assert body["open_predictions_value"] == pytest.approx(0.0)
