from datetime import datetime, timedelta, timezone

import pytest

from investsim.api.deps import get_clock, get_market_data_provider
from investsim.providers.market_data import FakeMarketDataProvider


def test_list_predictions_includes_current_value_for_open(client):
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
    fake.set_price("AAPL", 120.0)

    response = client.get("/predictions")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    pred = body[0]
    assert pred["status"] == "open"
    assert pred["current_value"] == pytest.approx(12.0)
    assert pred["final_value"] is None
    assert pred["exit_price"] is None


def test_list_predictions_settled_has_no_current_value(client):
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
    fake.set_price("AAPL", 90.0)
    now[0] += timedelta(days=1, minutes=1)

    response = client.get("/predictions")

    body = response.json()
    assert len(body) == 1
    pred = body[0]
    assert pred["status"] == "settled"
    assert pred["current_value"] is None
    assert pred["final_value"] == pytest.approx(9.0)
    assert pred["hit"] is False


def test_list_predictions_settles_due_first(client):
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
    now[0] += timedelta(days=1, minutes=1)

    response = client.get("/predictions")

    assert response.json()[0]["status"] == "settled"
