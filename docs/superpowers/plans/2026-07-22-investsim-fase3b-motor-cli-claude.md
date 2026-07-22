# InvestSim — Fase 3b: Motor LLM vía puente con el CLI de Claude Code — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir `ClaudeCliEngine`, una segunda implementación de `RecommendationEngine` que invoca el CLI `claude` por subproceso, seleccionable en la API vía `RECOMMENDATION_ENGINE=claude_cli`, sin modificar `AgentService` ni el resto de la API.

**Architecture:** Un único fichero nuevo `investsim/agent/claude_cli.py` (config, 3 excepciones, motor) que satisface el `Protocol RecommendationEngine` ya existente por *structural typing*. La API decide qué motor instanciar en el `lifespan` según una variable de entorno; las 3 excepciones nuevas se mapean a HTTP 503 igual que `ProviderUnavailable`.

**Tech Stack:** Python 3.11+, `subprocess` de la librería estándar (sin dependencias nuevas), `pytest` + `monkeypatch` para mockear `subprocess.run`/`shutil.which`.

## Global Constraints

- **Invocación del CLI verificada en Windows** (spec, sección "Hallazgos críticos") — cada uno de estos puntos es obligatorio, no cosmético:
  - Resolver el ejecutable con `shutil.which("claude")`; si devuelve `None`, no se invoca nada.
  - El JSON del `--json-schema` se serializa **compacto**: `json.dumps(schema, separators=(",", ":"))`.
  - `subprocess.run(..., encoding="utf-8", ...)` — sin esto se corrompen los acentos.
  - Se pasa `--safe-mode` en el comando (desactiva `CLAUDE.md`/skills/hooks, conserva la auth de suscripción).
  - `stdin=subprocess.DEVNULL` — la llamada es no interactiva.
  - Detección de fallo por `returncode != 0`, `is_error: true` en el JSON de stdout, o ausencia de `structured_output` — **nunca** por `subtype` (puede decir `"success"` en un fallo) ni por `stderr` (puede venir vacío en un fallo).
- **Modelo por defecto:** `claude-haiku-4-5`. **Timeout por defecto:** `60.0` segundos. **`base_amount` por defecto:** `20.0` (mismo default que `RuleBasedEngine`).
- **`confidence` se acota a `[0.05, 0.95]`**, reutilizando `_MIN_CONFIDENCE`/`_MAX_CONFIDENCE` de `investsim/agent/rules.py` (no se duplican los valores) — el schema permite `confidence: 0.0`, que sin acotar produciría `suggested_amount = 0`.
- **`horizon` siempre `Horizon.ONE_DAY`**; **`symbol` siempre `snapshot.symbol`** (nunca lo decide el LLM).
- **Tres excepciones nuevas**, ninguna se atrapa dentro de `ClaudeCliEngine`: `ClaudeCliUnavailable`, `ClaudeCliTimeout`, `InvalidClaudeCliResponse`. Las tres se mapean a **503** en `investsim/api/errors.py`.
- **`investsim/agent/engine.py`, `investsim/agent/rules.py` y `investsim/services/agent_service.py` no se modifican.**
- **Selección de motor:** `RECOMMENDATION_ENGINE` en el entorno — `"rules"` (o ausente) usa `RuleBasedEngine`, `"claude_cli"` usa `ClaudeCliEngine` — leída en el `lifespan` de `investsim/api/app.py`, mismo patrón que `DATABASE_URL`/`INITIAL_CAPITAL`.
- **Tests rápidos sin red/subproceso real:** `subprocess.run` y `shutil.which` se mockean con `monkeypatch`. Un único test de integración real, opt-in, con el marcador `integration` ya registrado en `backend/pyproject.toml` (`addopts = "-m 'not integration'"` lo excluye por defecto), siguiendo exactamente el patrón de `backend/tests/integration/test_finnhub_integration.py`.
- Todos los comandos se ejecutan desde la **raíz del repo**. El intérprete real es `C:\Users\marcos\AppData\Local\Programs\Python\Python312\python.exe`; en el plan se escribe `python` por brevedad.
- Punto de partida: **79 tests pasan, 2 deselected** (`python -m pytest backend/tests -q`).

---

### Task 1: `ClaudeCliConfig` y las 3 excepciones

**Files:**
- Create: `backend/investsim/agent/claude_cli.py`
- Test: `backend/tests/test_claude_cli_engine.py`

**Interfaces:**
- Consumes: nada.
- Produces: `ClaudeCliConfig` (dataclass congelado: `model: str = "claude-haiku-4-5"`, `timeout_seconds: float = 60.0`, `base_amount: float = 20.0`); `ClaudeCliUnavailable(Exception)`, `ClaudeCliTimeout(Exception)`, `InvalidClaudeCliResponse(Exception)`.

- [ ] **Step 1: Escribir el test que falla**

Crear `backend/tests/test_claude_cli_engine.py`:

```python
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
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `python -m pytest backend/tests/test_claude_cli_engine.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'investsim.agent.claude_cli'`.

- [ ] **Step 3: Crear `claude_cli.py`**

Crear `backend/investsim/agent/claude_cli.py`:

```python
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
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `python -m pytest backend/tests/test_claude_cli_engine.py -v`
Expected: PASS — 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/investsim/agent/claude_cli.py backend/tests/test_claude_cli_engine.py
git commit -m "feat(agent): ClaudeCliConfig y excepciones del motor CLI"
```

---

### Task 2: `ClaudeCliEngine` — prompt, invocación del subproceso y mapeo a `Recommendation`

**Files:**
- Modify: `backend/investsim/agent/claude_cli.py`
- Modify: `backend/tests/test_claude_cli_engine.py`

**Interfaces:**
- Consumes: `Recommendation` (`investsim.agent.engine`), `Direction`/`Horizon` (`investsim.domain.enums`), `MarketSnapshot` (`investsim.providers.market_data`), `_MIN_CONFIDENCE`/`_MAX_CONFIDENCE` (`investsim.agent.rules`), `ClaudeCliConfig` y las 3 excepciones (Task 1).
- Produces: `ClaudeCliEngine` — clase con `__init__(self, config: ClaudeCliConfig | None = None)` y `propose(self, snapshot: MarketSnapshot) -> Recommendation`. Satisface `RecommendationEngine` por *structural typing*, consumible por `AgentService` sin cambios.

- [ ] **Step 1: Escribir los tests que fallan**

Reemplazar `backend/tests/test_claude_cli_engine.py` completo:

```python
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
```

- [ ] **Step 2: Ejecutar los tests para verificar que fallan**

Run: `python -m pytest backend/tests/test_claude_cli_engine.py -q`
Expected: FAIL — error de recolección: el `import` a nivel de módulo falla con `ImportError: cannot import name 'ClaudeCliEngine'` (no existe todavía), así que pytest reporta las **15 pruebas del fichero como error**, incluidas las 3 que ya pasaban antes de este cambio — es un efecto secundario esperado de reemplazar el fichero completo con un import que aún no resuelve, no una regresión real.

- [ ] **Step 3: Ampliar `claude_cli.py`**

Reemplazar `backend/investsim/agent/claude_cli.py` completo:

```python
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
```

- [ ] **Step 4: Ejecutar los tests para verificar que pasan**

Run: `python -m pytest backend/tests/test_claude_cli_engine.py -v`
Expected: PASS — 15 passed.

- [ ] **Step 5: Ejecutar la suite completa**

Run: `python -m pytest backend/tests -q`
Expected: PASS — 94 passed, 2 deselected.

- [ ] **Step 6: Commit**

```bash
git add backend/investsim/agent/claude_cli.py backend/tests/test_claude_cli_engine.py
git commit -m "feat(agent): ClaudeCliEngine - puente con el CLI de Claude Code"
```

---

### Task 3: Test de integración real, opt-in

**Files:**
- Create: `backend/tests/integration/test_claude_cli_integration.py`

**Interfaces:**
- Consumes: `ClaudeCliConfig`, `ClaudeCliEngine` (Task 2), `MarketSnapshot` (`investsim.providers.market_data`), `Direction`/`Horizon` (`investsim.domain.enums`).
- Produces: nada importable; red de seguridad manual ante cambios de versión del CLI.

- [ ] **Step 1: Crear el test de integración**

Crear `backend/tests/integration/test_claude_cli_integration.py`:

```python
import shutil
from datetime import datetime, timezone

import pytest

from investsim.agent.claude_cli import ClaudeCliConfig, ClaudeCliEngine
from investsim.domain.enums import Direction, Horizon
from investsim.providers.market_data import MarketSnapshot

pytestmark = pytest.mark.integration

_HAS_CLI = shutil.which("claude") is not None


@pytest.mark.skipif(not _HAS_CLI, reason="requiere el CLI 'claude' instalado y autenticado")
def test_real_recommendation_for_known_symbol():
    snapshot = MarketSnapshot(
        symbol="AAPL",
        price=230.5,
        day_change_pct=1.2,
        day_high=232.0,
        day_low=228.0,
        day_open=229.0,
        prev_close=227.8,
        as_of=datetime.now(timezone.utc),
    )
    engine = ClaudeCliEngine(ClaudeCliConfig())

    rec = engine.propose(snapshot)

    assert rec.symbol == "AAPL"
    assert rec.direction in (Direction.UP, Direction.DOWN)
    assert 0.05 <= rec.confidence <= 0.95
    assert rec.horizon is Horizon.ONE_DAY
    assert rec.suggested_amount > 0
    assert isinstance(rec.rationale, str) and len(rec.rationale) > 0
```

- [ ] **Step 2: Verificar que se excluye del bucle rápido**

Run: `python -m pytest backend/tests -q`
Expected: PASS — 94 passed, **3 deselected** (uno más que antes: los 2 de Finnhub + este nuevo). Sin llamada real al CLI.

- [ ] **Step 3: (Opcional, manual) Ejecutar la integración real**

Solo si tienes el CLI `claude` instalado y autenticado:
Run: `python -m pytest backend/tests/integration/test_claude_cli_integration.py -m integration -v`
Expected: PASS (una llamada real al CLI, ~11-14s). Sin el CLI disponible, el test se **salta**.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/integration/test_claude_cli_integration.py
git commit -m "test(claude-cli): integracion real marcada (opt-in, skip sin CLI)"
```

---

### Task 4: Selección de motor en la API y mapeo de errores a 503

**Files:**
- Modify: `backend/investsim/api/app.py`
- Modify: `backend/investsim/api/errors.py`
- Modify: `backend/tests/test_api_recommendations.py`
- Test: `backend/tests/test_api_engine_selection.py`

**Interfaces:**
- Consumes: `ClaudeCliEngine`, `ClaudeCliUnavailable`, `ClaudeCliTimeout`, `InvalidClaudeCliResponse` (Task 2), `RuleBasedEngine` (ya existente), `get_recommendation_engine`/`get_market_data_provider` (`investsim.api.deps`, ya existentes), `FakeMarketDataProvider` (ya existente).
- Produces: nada nuevo importable — cablea lo ya construido en el arranque de la API y en el manejo de errores.

- [ ] **Step 1: Escribir el test que falla para la selección de motor**

Crear `backend/tests/test_api_engine_selection.py`:

```python
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
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `python -m pytest backend/tests/test_api_engine_selection.py -q`
Expected: FAIL — `test_selects_claude_cli_engine_via_env_var` falla porque `app.state.engine` sigue siendo `RuleBasedEngine` (la variable de entorno todavía no se lee en `app.py`); `test_defaults_to_rule_based_engine` ya pasa.

- [ ] **Step 3: Añadir los tests de mapeo a 503**

Reemplazar `backend/tests/test_api_recommendations.py` completo:

```python
from datetime import datetime, timezone

import pytest

from investsim.agent.claude_cli import (
    ClaudeCliTimeout,
    ClaudeCliUnavailable,
    InvalidClaudeCliResponse,
)
from investsim.api.deps import get_market_data_provider, get_recommendation_engine
from investsim.providers.market_data import (
    FakeMarketDataProvider,
    MarketSnapshot,
    ProviderUnavailable,
)

AS_OF = datetime(2026, 7, 19, 15, 0, tzinfo=timezone.utc)


def _snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        symbol="AAPL",
        price=102.0,
        day_change_pct=1.5,
        day_high=104.0,
        day_low=100.0,
        day_open=100.0,
        prev_close=100.0,
        as_of=AS_OF,
    )


def test_post_recommendations_happy_path(client):
    fake = FakeMarketDataProvider({}, snapshots={"AAPL": _snapshot()})
    client.app.dependency_overrides[get_market_data_provider] = lambda: fake

    response = client.post("/recommendations", json={"symbol": "AAPL"})

    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "AAPL"
    assert body["direction"] == "up"
    assert body["confidence"] == pytest.approx(0.375)
    assert body["suggested_amount"] == pytest.approx(7.5)
    assert body["horizon"] == "1D"
    assert body["rationale"] == (
        "AAPL sube 1.50% hoy y cotiza en la zona media del rango diario."
    )


def test_post_recommendations_unknown_symbol_404(client):
    fake = FakeMarketDataProvider({})
    client.app.dependency_overrides[get_market_data_provider] = lambda: fake

    response = client.post("/recommendations", json={"symbol": "NOPE"})

    assert response.status_code == 404


def test_post_recommendations_provider_unavailable_503(client):
    class _BrokenProvider:
        def get_quote(self, symbol):
            raise ProviderUnavailable(symbol)

        def get_snapshot(self, symbol):
            raise ProviderUnavailable(symbol)

    client.app.dependency_overrides[get_market_data_provider] = lambda: _BrokenProvider()

    response = client.post("/recommendations", json={"symbol": "AAPL"})

    assert response.status_code == 503


def test_post_recommendations_claude_cli_unavailable_503(client):
    fake = FakeMarketDataProvider({}, snapshots={"AAPL": _snapshot()})
    client.app.dependency_overrides[get_market_data_provider] = lambda: fake

    class _BrokenEngine:
        def propose(self, snapshot):
            raise ClaudeCliUnavailable("CLI no encontrado")

    client.app.dependency_overrides[get_recommendation_engine] = lambda: _BrokenEngine()

    response = client.post("/recommendations", json={"symbol": "AAPL"})

    assert response.status_code == 503


def test_post_recommendations_claude_cli_timeout_503(client):
    fake = FakeMarketDataProvider({}, snapshots={"AAPL": _snapshot()})
    client.app.dependency_overrides[get_market_data_provider] = lambda: fake

    class _BrokenEngine:
        def propose(self, snapshot):
            raise ClaudeCliTimeout("timeout")

    client.app.dependency_overrides[get_recommendation_engine] = lambda: _BrokenEngine()

    response = client.post("/recommendations", json={"symbol": "AAPL"})

    assert response.status_code == 503


def test_post_recommendations_invalid_claude_cli_response_503(client):
    fake = FakeMarketDataProvider({}, snapshots={"AAPL": _snapshot()})
    client.app.dependency_overrides[get_market_data_provider] = lambda: fake

    class _BrokenEngine:
        def propose(self, snapshot):
            raise InvalidClaudeCliResponse("respuesta invalida")

    client.app.dependency_overrides[get_recommendation_engine] = lambda: _BrokenEngine()

    response = client.post("/recommendations", json={"symbol": "AAPL"})

    assert response.status_code == 503
```

- [ ] **Step 4: Ejecutar los tests para verificar que fallan**

Run: `python -m pytest backend/tests/test_api_recommendations.py backend/tests/test_api_engine_selection.py -q`
Expected: FAIL — 3 errors. **No** es un simple `500` en vez de `503`: sin un `@app.exception_handler` registrado para una excepción, `TestClient` **re-lanza la excepción tal cual dentro del propio test** en lugar de convertirla en una respuesta HTTP (verificado: una excepción sin handler se propaga a la línea que llama a `client.post(...)`, no llega a ejecutarse el `assert`). Los 3 tests nuevos de `test_api_recommendations.py` terminan en **ERROR** con `ClaudeCliUnavailable`/`ClaudeCliTimeout`/`InvalidClaudeCliResponse` sin capturar; `test_selects_claude_cli_engine_via_env_var` sigue fallando igual que en el Step 2.

- [ ] **Step 5: Mapear las 3 excepciones a 503**

Reemplazar `backend/investsim/api/errors.py` completo:

```python
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from investsim.agent.claude_cli import (
    ClaudeCliTimeout,
    ClaudeCliUnavailable,
    InvalidClaudeCliResponse,
)
from investsim.providers.market_data import ProviderUnavailable, UnknownSymbol
from investsim.services.portfolio_service import InsufficientFunds


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(UnknownSymbol)
    async def _unknown_symbol_handler(
        request: Request, exc: UnknownSymbol
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404, content={"detail": f"Simbolo desconocido: {exc}"}
        )

    @app.exception_handler(ProviderUnavailable)
    async def _provider_unavailable_handler(
        request: Request, exc: ProviderUnavailable
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(InsufficientFunds)
    async def _insufficient_funds_handler(
        request: Request, exc: InsufficientFunds
    ) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(ClaudeCliUnavailable)
    async def _claude_cli_unavailable_handler(
        request: Request, exc: ClaudeCliUnavailable
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(ClaudeCliTimeout)
    async def _claude_cli_timeout_handler(
        request: Request, exc: ClaudeCliTimeout
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(InvalidClaudeCliResponse)
    async def _invalid_claude_cli_response_handler(
        request: Request, exc: InvalidClaudeCliResponse
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})
```

- [ ] **Step 6: Leer `RECOMMENDATION_ENGINE` en el `lifespan`**

Reemplazar `backend/investsim/api/app.py` completo:

```python
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from investsim.agent.claude_cli import ClaudeCliEngine
from investsim.agent.rules import RuleBasedEngine
from investsim.api.errors import register_exception_handlers
from investsim.api.routes import router
from investsim.config import load_finnhub_config
from investsim.db.base import Base, make_engine, make_session_factory
from investsim.db.repositories import PortfolioRepository
from investsim.providers.finnhub import FinnhubMarketDataProvider


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_url = os.environ.get("DATABASE_URL", "sqlite:///investsim.db")
    engine = make_engine(db_url)
    Base.metadata.create_all(engine)
    session_factory = make_session_factory(engine)

    session = session_factory()
    try:
        portfolio_repo = PortfolioRepository(session)
        if portfolio_repo.get() is None:
            initial_capital = float(os.environ.get("INITIAL_CAPITAL", "1000.0"))
            portfolio_repo.create(
                initial_capital=initial_capital, created_at=_utcnow()
            )
    finally:
        session.close()

    app.state.session_factory = session_factory
    app.state.market_data = FinnhubMarketDataProvider(load_finnhub_config())

    engine_name = os.environ.get("RECOMMENDATION_ENGINE", "rules")
    app.state.engine = (
        ClaudeCliEngine() if engine_name == "claude_cli" else RuleBasedEngine()
    )

    yield


def create_app() -> FastAPI:
    app = FastAPI(title="InvestSim API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"http://localhost:\d+",
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(router)
    return app


app = create_app()
```

- [ ] **Step 7: Ejecutar los tests para verificar que pasan**

Run: `python -m pytest backend/tests/test_api_recommendations.py backend/tests/test_api_engine_selection.py -v`
Expected: PASS — 8 passed (6 en `test_api_recommendations.py` + 2 en `test_api_engine_selection.py`).

- [ ] **Step 8: Ejecutar la suite completa**

Run: `python -m pytest backend/tests -q`
Expected: PASS — 99 passed, 3 deselected.

- [ ] **Step 9: Commit**

```bash
git add backend/investsim/api/app.py backend/investsim/api/errors.py backend/tests/test_api_recommendations.py backend/tests/test_api_engine_selection.py
git commit -m "feat(api): selecciona motor via RECOMMENDATION_ENGINE, mapea errores del CLI a 503"
```

---

### Task 5: Smoke manual y cierre de fase

**Files:**
- Create: `backend/examples/smoke_claude_cli.py`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: `ClaudeCliEngine` (Task 2), `AgentService`, `FinnhubMarketDataProvider`, `load_finnhub_config` (ya existentes).
- Produces: nada de código nuevo importable; cierra la fase.

- [ ] **Step 1: Crear el smoke manual con datos reales**

Crear `backend/examples/smoke_claude_cli.py`:

```python
"""Smoke manual: pide una recomendacion real al motor LLM (puente CLI de Claude Code).

Uso (desde la raiz del repo, con FINNHUB_API_KEY en .env y el CLI 'claude'
instalado y autenticado):
    python backend/examples/smoke_claude_cli.py AAPL
"""

from __future__ import annotations

import sys

from investsim.agent.claude_cli import ClaudeCliEngine
from investsim.config import load_finnhub_config
from investsim.providers.finnhub import FinnhubMarketDataProvider
from investsim.services.agent_service import AgentService

DISCLAIMER = (
    "Simulación educativa, no es asesoramiento financiero. Capital ficticio."
)


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    service = AgentService(
        FinnhubMarketDataProvider(load_finnhub_config()), ClaudeCliEngine()
    )
    rec = service.propose(symbol)

    print(f"Simbolo:   {rec.symbol}")
    print(f"Direccion: {rec.direction.value}  ({rec.horizon.value})")
    print(f"Confianza: {rec.confidence:.2%}")
    print(f"Importe:   {rec.suggested_amount:.2f} EUR")
    print(f"Motivo:    {rec.rationale}")
    print()
    print(DISCLAIMER)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Ejecutar el smoke a mano**

Run: `python backend/examples/smoke_claude_cli.py AAPL`
Expected: imprime la recomendación real (dirección/confianza/importe/motivo, generada por el CLI de Claude Code sobre datos reales de Finnhub), termina con el aviso legal. Tarda ~11-14s. Sin `FINNHUB_API_KEY`, falla al construir la app con `MissingApiKey`. Sin el CLI `claude` disponible, falla con `ClaudeCliUnavailable` — ambos comportamientos esperados.

- [ ] **Step 3: Actualizar `CLAUDE.md`**

En la tabla de `## Decisiones de arquitectura`, reemplazar la fila de "Cerebro del agente":

```markdown
| Cerebro del agente | Agente por reglas determinista (`RuleBasedEngine`) sobre señales intradía | `ClaudeCliEngine`: puente con el CLI de Claude Code (misma interfaz `RecommendationEngine`); Ollama descartado por calidad limitada |
```

En `## Comandos`, añadir una línea después del bloque del servidor de desarrollo de la API:

```markdown
Motor de recomendación seleccionable con `RECOMMENDATION_ENGINE` (`rules` por defecto, `claude_cli` para el motor LLM — requiere el CLI `claude` instalado y autenticado):

```bash
RECOMMENDATION_ENGINE=claude_cli python -m uvicorn investsim.api.app:app --reload
```
```

En `## Evolución futura`, reemplazar la línea de fases:

```markdown
Fases planificadas tras el núcleo de dominio (Fase 1): **F2** datos reales (Finnhub) · **F3a** agente por reglas (hecho: `RuleBasedEngine` + `AgentService`, sin LLM) · **F3b** motor LLM (hecho: `ClaudeCliEngine`, puente con el CLI de Claude Code — Ollama descartado por calidad limitada) como segunda implementación de `RecommendationEngine` · **F4** API FastAPI (hecho: 5 endpoints REST sobre `AgentService`/`PortfolioService`/`SettlementService`) · **F5** frontend React (hecho: dashboard único con TanStack Query, ver `frontend/README.md`) · **F6** pulido (observabilidad de coste, watchlist). Más adelante: agente híbrido ML+Claude, crypto/multi-activo, scheduler, Docker. Ver la sección "Evolución futura" del spec para el detalle.
```

- [ ] **Step 4: Suite completa final**

Run: `python -m pytest backend/tests -v`
Expected: PASS — 99 passed, 3 deselected. Sin warnings nuevos.

- [ ] **Step 5: Commit de cierre**

```bash
git add backend/examples/smoke_claude_cli.py CLAUDE.md
git commit -m "test(fase3b): smoke manual del motor CLI y cierre de fase"
```

---

## Resumen de ficheros

| Fichero | Acción | Responsabilidad |
|---------|--------|------------------|
| `backend/investsim/agent/claude_cli.py` | Crear (ampliado en Task 2) | `ClaudeCliConfig`, 3 excepciones, `ClaudeCliEngine` |
| `backend/tests/test_claude_cli_engine.py` | Crear (ampliado en Task 2) | Tests rápidos del motor, sin red/subproceso real |
| `backend/tests/integration/test_claude_cli_integration.py` | Crear | Test de integración real, opt-in |
| `backend/investsim/api/errors.py` | Modificar | Mapea las 3 excepciones nuevas a 503 |
| `backend/investsim/api/app.py` | Modificar | Selecciona motor vía `RECOMMENDATION_ENGINE` |
| `backend/tests/test_api_engine_selection.py` | Crear | Verifica qué motor instancia el `lifespan` |
| `backend/tests/test_api_recommendations.py` | Modificar | Añade los 3 tests de mapeo a 503 |
| `backend/examples/smoke_claude_cli.py` | Crear | Smoke manual con datos y CLI reales |
| `CLAUDE.md` | Modificar | Decisiones de arquitectura, comandos, estado de fases |
