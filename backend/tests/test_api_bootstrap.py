from datetime import datetime, timezone

from fastapi.testclient import TestClient

from investsim.api.app import create_app
from investsim.db.repositories import PortfolioRepository


def test_bootstrap_creates_portfolio_with_default_capital(client):
    session = client.app.state.session_factory()
    portfolio = PortfolioRepository(session).get()

    assert portfolio is not None
    assert portfolio.cash_balance == 1000.0
    assert portfolio.initial_capital == 1000.0


def test_bootstrap_respects_initial_capital_env_var(monkeypatch, tmp_path):
    db_path = (tmp_path / "custom.db").as_posix()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("FINNHUB_API_KEY", "testkey")
    monkeypatch.setenv("INITIAL_CAPITAL", "250.0")

    app = create_app()
    with TestClient(app) as custom_client:
        session = custom_client.app.state.session_factory()
        portfolio = PortfolioRepository(session).get()
        assert portfolio.initial_capital == 250.0
