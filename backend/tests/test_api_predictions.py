import pytest

from investsim.api.deps import get_market_data_provider
from investsim.providers.market_data import FakeMarketDataProvider


def test_post_predictions_happy_path_deducts_cash(client):
    fake = FakeMarketDataProvider({"AAPL": 100.0})
    client.app.dependency_overrides[get_market_data_provider] = lambda: fake

    response = client.post(
        "/predictions",
        json={
            "symbol": "AAPL",
            "amount": 10.0,
            "direction": "up",
            "confidence": 0.8,
            "horizon": "1W",
            "rationale": "momentum",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["entry_price"] == 100.0
    assert body["shares"] == 0.1
    assert body["status"] == "open"

    portfolio = client.get("/portfolio")
    assert portfolio.status_code == 200
    assert portfolio.json()["cash_balance"] == pytest.approx(990.0)


def test_post_predictions_insufficient_funds_400(client):
    fake = FakeMarketDataProvider({"AAPL": 100.0})
    client.app.dependency_overrides[get_market_data_provider] = lambda: fake

    response = client.post(
        "/predictions",
        json={
            "symbol": "AAPL",
            "amount": 10000.0,
            "direction": "up",
            "confidence": 0.5,
            "horizon": "1D",
            "rationale": "",
        },
    )

    assert response.status_code == 400


def test_post_predictions_unknown_symbol_404(client):
    fake = FakeMarketDataProvider({})
    client.app.dependency_overrides[get_market_data_provider] = lambda: fake

    response = client.post(
        "/predictions",
        json={
            "symbol": "NOPE",
            "amount": 10.0,
            "direction": "up",
            "confidence": 0.5,
            "horizon": "1D",
            "rationale": "",
        },
    )

    assert response.status_code == 404
