from datetime import datetime, timedelta, timezone

import pytest

from investsim.api.deps import get_clock, get_market_data_provider
from investsim.providers.market_data import FakeMarketDataProvider


def test_get_metrics_matches_compute_metrics(client):
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
            "confidence": 0.9,
            "horizon": "1D",
            "rationale": "",
        },
    )
    fake.set_price("AAPL", 134.0)
    now[0] += timedelta(days=1, minutes=1)

    response = client.get("/metrics")

    assert response.status_code == 200
    body = response.json()
    assert body["total_predictions"] == 1
    assert body["settled"] == 1
    assert body["hits"] == 1
    assert body["hit_rate_pct"] == pytest.approx(100.0)
    assert body["total_invested"] == pytest.approx(10.0)
    assert body["total_final_value"] == pytest.approx(13.4)
    assert body["total_return_pct"] == pytest.approx(34.0)


def test_get_metrics_settles_due_first(client):
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

    response = client.get("/metrics")

    body = response.json()
    assert body["total_predictions"] == 1
    assert body["settled"] == 0
