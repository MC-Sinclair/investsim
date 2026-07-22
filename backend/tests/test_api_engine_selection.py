from fastapi.testclient import TestClient

from investsim.agent.claude_cli import ClaudeCliEngine
from investsim.agent.rules import RuleBasedEngine
from investsim.api.app import create_app


def test_defaults_to_rule_based_engine(monkeypatch, tmp_path):
    db_path = (tmp_path / "default.db").as_posix()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("FINNHUB_API_KEY", "testkey")
    monkeypatch.delenv("RECOMMENDATION_ENGINE", raising=False)

    app = create_app()
    with TestClient(app) as test_client:
        assert isinstance(test_client.app.state.engine, RuleBasedEngine)


def test_selects_claude_cli_engine_via_env_var(monkeypatch, tmp_path):
    db_path = (tmp_path / "claude.db").as_posix()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("FINNHUB_API_KEY", "testkey")
    monkeypatch.setenv("RECOMMENDATION_ENGINE", "claude_cli")

    app = create_app()
    with TestClient(app) as test_client:
        assert isinstance(test_client.app.state.engine, ClaudeCliEngine)
