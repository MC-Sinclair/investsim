import pytest

from investsim.agent.claude_cli import (
    ClaudeCliConfig,
    ClaudeCliTimeout,
    ClaudeCliUnavailable,
    InvalidClaudeCliResponse,
)


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
