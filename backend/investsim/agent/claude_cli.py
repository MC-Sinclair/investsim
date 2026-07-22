from __future__ import annotations

from dataclasses import dataclass


class ClaudeCliUnavailable(Exception):
    pass


class ClaudeCliTimeout(Exception):
    pass


class InvalidClaudeCliResponse(Exception):
    pass


@dataclass(frozen=True)
class ClaudeCliConfig:
    model: str = "claude-haiku-4-5"
    timeout_seconds: float = 60.0
    base_amount: float = 20.0
