import json
import subprocess
from datetime import datetime, timezone

import pytest

from investsim.agent.claude_cli import (
    ClaudeCliConfig,
    ClaudeCliEngine,
    ClaudeCliTimeout,
    ClaudeCliUnavailable,
    InvalidClaudeCliResponse,
)
from investsim.agent.engine import RecommendationEngine
from investsim.domain.enums import Direction, Horizon
from investsim.providers.market_data import FakeMarketDataProvider, MarketSnapshot
from investsim.services.agent_service import AgentService

AS_OF = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)


def test_claude_cli_config_defaults():
    config = ClaudeCliConfig()
    assert config.model == "claude-haiku-4-5"
    assert config.timeout_seconds == 60.0
    assert config.base_amount == 20.0


def test_claude_cli_config_is_frozen():
    config = ClaudeCliConfig()
    with pytest.raises(Exception):
        config.model = "otro-modelo"  # type: ignore[misc]


def test_exceptions_are_exception_subclasses():
    assert issubclass(ClaudeCliUnavailable, Exception)
    assert issubclass(ClaudeCliTimeout, Exception)
    assert issubclass(InvalidClaudeCliResponse, Exception)


def _snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        symbol="AAPL",
        price=230.5,
        day_change_pct=1.2,
        day_high=232.0,
        day_low=228.0,
        day_open=229.0,
        prev_close=227.8,
        as_of=AS_OF,
    )


def _completed_process(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


def _cli_success_stdout(direction: str, confidence: float, rationale: str) -> str:
    return json.dumps(
        {
            "is_error": False,
            "subtype": "success",
            "result": json.dumps(
                {"direction": direction, "confidence": confidence, "rationale": rationale}
            ),
            "structured_output": {
                "direction": direction,
                "confidence": confidence,
                "rationale": rationale,
            },
        }
    )


def test_maps_valid_response_to_recommendation(monkeypatch):
    monkeypatch.setattr(
        "investsim.agent.claude_cli.shutil.which", lambda name: "C:/fake/claude.CMD"
    )
    monkeypatch.setattr(
        "investsim.agent.claude_cli.subprocess.run",
        lambda *a, **kw: _completed_process(
            _cli_success_stdout("up", 0.6, "Motivo de prueba.")
        ),
    )

    rec = ClaudeCliEngine(ClaudeCliConfig(base_amount=20.0)).propose(_snapshot())

    assert rec.symbol == "AAPL"
    assert rec.direction is Direction.UP
    assert rec.confidence == pytest.approx(0.6)
    assert rec.suggested_amount == pytest.approx(12.0)
    assert rec.horizon is Horizon.ONE_DAY
    assert rec.rationale == "Motivo de prueba."


def test_command_uses_safe_mode_compact_schema_and_utf8_encoding(monkeypatch):
    monkeypatch.setattr(
        "investsim.agent.claude_cli.shutil.which", lambda name: "C:/fake/claude.CMD"
    )
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return _completed_process(_cli_success_stdout("down", 0.4, "motivo"))

    monkeypatch.setattr("investsim.agent.claude_cli.subprocess.run", fake_run)

    ClaudeCliEngine().propose(_snapshot())

    assert "--safe-mode" in captured["cmd"]
    assert captured["kwargs"]["encoding"] == "utf-8"
    assert captured["kwargs"]["stdin"] == subprocess.DEVNULL
    schema_arg = captured["cmd"][captured["cmd"].index("--json-schema") + 1]
    assert " " not in schema_arg


def test_confidence_is_clamped_to_minimum(monkeypatch):
    monkeypatch.setattr(
        "investsim.agent.claude_cli.shutil.which", lambda name: "C:/fake/claude.CMD"
    )
    monkeypatch.setattr(
        "investsim.agent.claude_cli.subprocess.run",
        lambda *a, **kw: _completed_process(_cli_success_stdout("up", 0.0, "motivo")),
    )

    rec = ClaudeCliEngine(ClaudeCliConfig(base_amount=20.0)).propose(_snapshot())

    assert rec.confidence == pytest.approx(0.05)
    assert rec.suggested_amount == pytest.approx(1.0)


def test_confidence_is_clamped_to_maximum(monkeypatch):
    monkeypatch.setattr(
        "investsim.agent.claude_cli.shutil.which", lambda name: "C:/fake/claude.CMD"
    )
    monkeypatch.setattr(
        "investsim.agent.claude_cli.subprocess.run",
        lambda *a, **kw: _completed_process(_cli_success_stdout("up", 1.0, "motivo")),
    )

    rec = ClaudeCliEngine(ClaudeCliConfig(base_amount=20.0)).propose(_snapshot())

    assert rec.confidence == pytest.approx(0.95)
    assert rec.suggested_amount == pytest.approx(19.0)


def test_raises_unavailable_when_cli_not_on_path(monkeypatch):
    monkeypatch.setattr("investsim.agent.claude_cli.shutil.which", lambda name: None)

    with pytest.raises(ClaudeCliUnavailable):
        ClaudeCliEngine().propose(_snapshot())


def test_raises_unavailable_when_subprocess_raises_file_not_found(monkeypatch):
    monkeypatch.setattr(
        "investsim.agent.claude_cli.shutil.which", lambda name: "C:/fake/claude.CMD"
    )

    def fake_run(*a, **kw):
        raise FileNotFoundError("no such file")

    monkeypatch.setattr("investsim.agent.claude_cli.subprocess.run", fake_run)

    with pytest.raises(ClaudeCliUnavailable):
        ClaudeCliEngine().propose(_snapshot())


def test_raises_timeout_when_subprocess_times_out(monkeypatch):
    monkeypatch.setattr(
        "investsim.agent.claude_cli.shutil.which", lambda name: "C:/fake/claude.CMD"
    )

    def fake_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout", 60.0))

    monkeypatch.setattr("investsim.agent.claude_cli.subprocess.run", fake_run)

    with pytest.raises(ClaudeCliTimeout):
        ClaudeCliEngine().propose(_snapshot())


def test_raises_invalid_response_when_returncode_nonzero(monkeypatch):
    monkeypatch.setattr(
        "investsim.agent.claude_cli.shutil.which", lambda name: "C:/fake/claude.CMD"
    )
    stdout = json.dumps(
        {"is_error": True, "subtype": "success", "result": "modelo invalido"}
    )
    monkeypatch.setattr(
        "investsim.agent.claude_cli.subprocess.run",
        lambda *a, **kw: _completed_process(stdout, returncode=1),
    )

    with pytest.raises(InvalidClaudeCliResponse):
        ClaudeCliEngine().propose(_snapshot())


def test_raises_invalid_response_when_is_error_true(monkeypatch):
    monkeypatch.setattr(
        "investsim.agent.claude_cli.shutil.which", lambda name: "C:/fake/claude.CMD"
    )
    stdout = json.dumps({"is_error": True, "result": "algo fallo"})
    monkeypatch.setattr(
        "investsim.agent.claude_cli.subprocess.run",
        lambda *a, **kw: _completed_process(stdout, returncode=0),
    )

    with pytest.raises(InvalidClaudeCliResponse):
        ClaudeCliEngine().propose(_snapshot())


def test_raises_invalid_response_when_stdout_not_json(monkeypatch):
    monkeypatch.setattr(
        "investsim.agent.claude_cli.shutil.which", lambda name: "C:/fake/claude.CMD"
    )
    monkeypatch.setattr(
        "investsim.agent.claude_cli.subprocess.run",
        lambda *a, **kw: _completed_process("no es json en absoluto"),
    )

    with pytest.raises(InvalidClaudeCliResponse):
        ClaudeCliEngine().propose(_snapshot())


def test_raises_invalid_response_when_structured_output_missing(monkeypatch):
    monkeypatch.setattr(
        "investsim.agent.claude_cli.shutil.which", lambda name: "C:/fake/claude.CMD"
    )
    stdout = json.dumps({"is_error": False, "result": "texto libre sin schema"})
    monkeypatch.setattr(
        "investsim.agent.claude_cli.subprocess.run",
        lambda *a, **kw: _completed_process(stdout),
    )

    with pytest.raises(InvalidClaudeCliResponse):
        ClaudeCliEngine().propose(_snapshot())


def test_agent_service_works_with_claude_cli_engine_without_changes(monkeypatch):
    monkeypatch.setattr(
        "investsim.agent.claude_cli.shutil.which", lambda name: "C:/fake/claude.CMD"
    )
    monkeypatch.setattr(
        "investsim.agent.claude_cli.subprocess.run",
        lambda *a, **kw: _completed_process(
            _cli_success_stdout("up", 0.6, "motivo")
        ),
    )

    provider = FakeMarketDataProvider({}, snapshots={"AAPL": _snapshot()})
    engine: RecommendationEngine = ClaudeCliEngine()
    service = AgentService(provider, engine)

    rec = service.propose("AAPL")

    assert rec.symbol == "AAPL"
    assert rec.direction is Direction.UP
