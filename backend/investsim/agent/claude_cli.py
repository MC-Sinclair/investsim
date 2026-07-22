from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass

from investsim.agent.engine import Recommendation
from investsim.agent.rules import _MAX_CONFIDENCE, _MIN_CONFIDENCE
from investsim.domain.enums import Direction, Horizon
from investsim.providers.market_data import MarketSnapshot


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


_SCHEMA = json.dumps(
    {
        "type": "object",
        "properties": {
            "direction": {"type": "string", "enum": ["up", "down"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "rationale": {"type": "string"},
        },
        "required": ["direction", "confidence", "rationale"],
    },
    separators=(",", ":"),
)


def _build_prompt(snapshot: MarketSnapshot) -> str:
    return (
        "Eres un analista financiero educativo. Dato de mercado: "
        f"simbolo {snapshot.symbol}, precio {snapshot.price}, "
        f"cambio del dia {snapshot.day_change_pct:+.2f}%, "
        f"maximo del dia {snapshot.day_high}, minimo del dia {snapshot.day_low}, "
        f"apertura {snapshot.day_open}, cierre anterior {snapshot.prev_close}. "
        "Da una recomendacion de direccion (up/down) a 1 dia vista, "
        "con confianza 0-1 y una frase de motivo en espanol."
    )


def _invoke_cli(prompt: str, config: ClaudeCliConfig) -> dict:
    executable = shutil.which("claude")
    if executable is None:
        raise ClaudeCliUnavailable(
            "El CLI 'claude' no esta instalado o no esta en el PATH."
        )

    try:
        result = subprocess.run(
            [
                executable,
                "-p",
                "--safe-mode",
                "--output-format",
                "json",
                "--model",
                config.model,
                "--json-schema",
                _SCHEMA,
                prompt,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            stdin=subprocess.DEVNULL,
            timeout=config.timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise ClaudeCliUnavailable(str(exc)) from exc
    except subprocess.TimeoutExpired as exc:
        raise ClaudeCliTimeout(
            f"El CLI de Claude Code no respondio en {config.timeout_seconds}s."
        ) from exc

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise InvalidClaudeCliResponse(
            f"Salida no es JSON valido: {result.stdout[:200]!r}"
        ) from exc

    if result.returncode != 0 or payload.get("is_error"):
        raise InvalidClaudeCliResponse(
            str(payload.get("result", "El CLI de Claude Code devolvio un error."))
        )

    structured_output = payload.get("structured_output")
    if not isinstance(structured_output, dict) or not {
        "direction",
        "confidence",
        "rationale",
    } <= structured_output.keys():
        raise InvalidClaudeCliResponse(
            f"Respuesta sin structured_output valido: {payload!r}"
        )

    return structured_output


class ClaudeCliEngine:
    """Motor LLM via puente con el CLI de Claude Code (claude -p --json-schema)."""

    def __init__(self, config: ClaudeCliConfig | None = None) -> None:
        self.config = config or ClaudeCliConfig()

    def propose(self, snapshot: MarketSnapshot) -> Recommendation:
        prompt = _build_prompt(snapshot)
        structured_output = _invoke_cli(prompt, self.config)

        direction = Direction(structured_output["direction"])
        confidence = max(
            _MIN_CONFIDENCE,
            min(float(structured_output["confidence"]), _MAX_CONFIDENCE),
        )

        return Recommendation(
            symbol=snapshot.symbol,
            direction=direction,
            confidence=confidence,
            suggested_amount=self.config.base_amount * confidence,
            horizon=Horizon.ONE_DAY,
            rationale=structured_output["rationale"],
        )
