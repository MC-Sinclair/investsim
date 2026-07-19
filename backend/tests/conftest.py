from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from investsim.api.app import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = (tmp_path / "test.db").as_posix()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("FINNHUB_API_KEY", "testkey")
    monkeypatch.delenv("INITIAL_CAPITAL", raising=False)

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
