# InvestSim — Fase 3a: Agente por reglas · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sustituir el "cerebro" de las predicciones por un agente por reglas determinista (`RuleBasedEngine`) que consume un `MarketSnapshot` con señales intradía reales de Finnhub y produce una `Recommendation`, cerrando el bucle central sin LLM, sin coste y sin claves de terceros nuevas.

**Architecture:** Dependency Rule ya establecida. Se añade un paquete `investsim/agent/` con el mismo rol que `providers/`: detalle enchufable tras una interfaz (`RecommendationEngine`). El motor de reglas no conoce Finnhub ni BD — recibe un `MarketSnapshot` (dato de dominio) y devuelve una `Recommendation` (dato de dominio). `AgentService` orquesta ambos lados: pide el snapshot al `MarketDataProvider` inyectado y se lo pasa al engine inyectado. Nada se persiste en esta fase.

**Tech Stack:** Python 3.11+, dataclasses frozen, `typing.Protocol`, pytest, `httpx.MockTransport` (para el provider real, sin red).

## Global Constraints

- Python **3.11 o superior** (sintaxis `X | None`).
- **`Quote` y `get_quote` no cambian.** El snapshot rico llega por un método **nuevo** `get_snapshot`; ningún test existente de Fase 1/2 debe modificarse.
- **Horizonte siempre `Horizon.ONE_DAY`.** El endpoint `/stock/candle` de Finnhub devuelve 403 en el plan gratuito, así que solo hay señal intradía fiable. `1W`/`1M` quedan fuera de alcance.
- **Sin persistencia** en esta fase: ni `MarketSnapshot` ni `AgentRun` van a BD. `AgentService` no escribe nada.
- **Sin red en el bucle rápido:** dominio testeado con `FakeMarketDataProvider`; el provider real con `httpx.MockTransport`. El único test con red lleva el marcador `integration` (excluido por defecto vía `addopts = "-m 'not integration'"`).
- Timestamps en **UTC**. Precios y porcentajes en `float`.
- Constantes del motor de reglas, fijadas por el spec y **encapsuladas dentro de `RuleBasedEngine`**: saturación de `dp` en `3.0`, mezcla `0.5 + confirmación/2`, `base_amount = 20.0`, clamp `[0.05, 0.95]`.
- Si falla el dato, **no hay recomendación**: `AgentService.propose` no atrapa excepciones; `UnknownSymbol`/`ProviderUnavailable` suben tal cual.
- Todos los comandos se ejecutan desde la **raíz del repo**. En el plan se escribe `python` por brevedad; en la máquina de desarrollo el intérprete real es `C:\Users\marcos\AppData\Local\Programs\Python\Python312\python.exe`.
- Punto de partida: **33 tests pasan, 1 deselected** (`python -m pytest backend/tests -q`).

---

### Task 1: `MarketSnapshot`, `get_snapshot` en la interfaz y en el fake

**Files:**
- Modify: `backend/investsim/providers/market_data.py`
- Test: `backend/tests/test_market_snapshot.py` (crear)

**Interfaces:**
- Consumes: `Quote`, `UnknownSymbol`, `FakeMarketDataProvider` (ya existen en `market_data.py`).
- Produces:
  - `MarketSnapshot(symbol: str, price: float, day_change_pct: float, day_high: float, day_low: float, day_open: float, prev_close: float, as_of: datetime)` — dataclass frozen.
  - `MarketDataProvider.get_snapshot(symbol: str) -> MarketSnapshot` en el Protocol.
  - `FakeMarketDataProvider.__init__(prices, as_of=None, snapshots: dict[str, MarketSnapshot] | None = None)` y `FakeMarketDataProvider.set_snapshot(snapshot: MarketSnapshot) -> None`.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `backend/tests/test_market_snapshot.py`:

```python
from datetime import datetime, timezone

import pytest

from investsim.providers.market_data import (
    FakeMarketDataProvider,
    MarketSnapshot,
    UnknownSymbol,
)

AS_OF = datetime(2026, 7, 19, 15, 0, tzinfo=timezone.utc)


def _snapshot(symbol: str = "AAPL") -> MarketSnapshot:
    return MarketSnapshot(
        symbol=symbol,
        price=102.0,
        day_change_pct=1.5,
        day_high=104.0,
        day_low=100.0,
        day_open=100.5,
        prev_close=100.5,
        as_of=AS_OF,
    )


def test_snapshot_is_frozen():
    snapshot = _snapshot()
    with pytest.raises(Exception):
        snapshot.price = 999.0  # type: ignore[misc]


def test_fake_returns_configured_snapshot():
    provider = FakeMarketDataProvider({}, snapshots={"AAPL": _snapshot()})
    assert provider.get_snapshot("AAPL") == _snapshot()


def test_set_snapshot_updates_it():
    provider = FakeMarketDataProvider({})
    provider.set_snapshot(_snapshot("MSFT"))
    assert provider.get_snapshot("MSFT").day_change_pct == 1.5


def test_fake_derives_flat_snapshot_from_price_only():
    provider = FakeMarketDataProvider({"AAPL": 100.0}, as_of=AS_OF)
    snapshot = provider.get_snapshot("AAPL")

    assert snapshot == MarketSnapshot(
        symbol="AAPL",
        price=100.0,
        day_change_pct=0.0,
        day_high=100.0,
        day_low=100.0,
        day_open=100.0,
        prev_close=100.0,
        as_of=AS_OF,
    )


def test_unknown_symbol_raises_on_snapshot():
    provider = FakeMarketDataProvider({})
    with pytest.raises(UnknownSymbol):
        provider.get_snapshot("NOPE")
```

- [ ] **Step 2: Ejecutar los tests para verificar que fallan**

Run: `python -m pytest backend/tests/test_market_snapshot.py -q`
Expected: FAIL con `ImportError: cannot import name 'MarketSnapshot' from 'investsim.providers.market_data'`.

- [ ] **Step 3: Añadir `MarketSnapshot` y `get_snapshot` en `market_data.py`**

Añadir el dataclass justo después de `Quote` (antes de la clase `MarketDataError`):

```python
@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    price: float
    day_change_pct: float
    day_high: float
    day_low: float
    day_open: float
    prev_close: float
    as_of: datetime
```

Ampliar el Protocol (sin tocar `get_quote`):

```python
class MarketDataProvider(Protocol):
    def get_quote(self, symbol: str) -> Quote: ...

    def get_snapshot(self, symbol: str) -> MarketSnapshot: ...
```

Reemplazar `FakeMarketDataProvider` completa por:

```python
class FakeMarketDataProvider:
    def __init__(
        self,
        prices: dict[str, float],
        as_of: datetime | None = None,
        snapshots: dict[str, MarketSnapshot] | None = None,
    ) -> None:
        self._prices = dict(prices)
        self._as_of = as_of or datetime.now(timezone.utc)
        self._snapshots = dict(snapshots or {})

    def set_price(self, symbol: str, price: float) -> None:
        self._prices[symbol] = price

    def set_snapshot(self, snapshot: MarketSnapshot) -> None:
        self._snapshots[snapshot.symbol] = snapshot

    def get_quote(self, symbol: str) -> Quote:
        if symbol not in self._prices:
            raise UnknownSymbol(symbol)
        return Quote(symbol=symbol, price=self._prices[symbol], as_of=self._as_of)

    def get_snapshot(self, symbol: str) -> MarketSnapshot:
        snapshot = self._snapshots.get(symbol)
        if snapshot is not None:
            return snapshot
        if symbol not in self._prices:
            raise UnknownSymbol(symbol)
        price = self._prices[symbol]
        return MarketSnapshot(
            symbol=symbol,
            price=price,
            day_change_pct=0.0,
            day_high=price,
            day_low=price,
            day_open=price,
            prev_close=price,
            as_of=self._as_of,
        )
```

- [ ] **Step 4: Ejecutar los tests para verificar que pasan**

Run: `python -m pytest backend/tests -q`
Expected: PASS — 38 passed, 1 deselected (33 previos + 5 nuevos). Ningún test antiguo se ha tocado.

- [ ] **Step 5: Commit**

```bash
git add backend/investsim/providers/market_data.py backend/tests/test_market_snapshot.py
git commit -m "feat(providers): MarketSnapshot y get_snapshot en interfaz y fake"
```

---

### Task 2: `FinnhubMarketDataProvider.get_snapshot`

**Files:**
- Modify: `backend/investsim/providers/finnhub.py`
- Test: `backend/tests/test_finnhub_snapshot.py` (crear)

**Interfaces:**
- Consumes: `MarketSnapshot` (Task 1); `FinnhubConfig`, `UnknownSymbol`, `ProviderUnavailable` (ya existen).
- Produces: `FinnhubMarketDataProvider.get_snapshot(symbol: str) -> MarketSnapshot`, compartiendo caché TTL y backoff con `get_quote`.

**Nota de diseño:** la caché pasa a guardar el **JSON crudo** de `/quote` en vez del `Quote` ya construido, de modo que `get_quote` y `get_snapshot` compartan una sola llamada HTTP. El comportamiento observable de `get_quote` no cambia y sus tests siguen verdes sin tocarlos.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `backend/tests/test_finnhub_snapshot.py`:

```python
from datetime import datetime, timezone

import httpx
import pytest

from investsim.config import FinnhubConfig
from investsim.providers.finnhub import FinnhubMarketDataProvider
from investsim.providers.market_data import UnknownSymbol

TS = 1_752_000_000

FULL_QUOTE = {
    "c": 102.0,
    "d": 1.5,
    "dp": 1.4925,
    "h": 104.0,
    "l": 100.0,
    "o": 100.5,
    "pc": 100.5,
    "t": TS,
}


def _client(handler) -> httpx.Client:
    return httpx.Client(
        base_url="https://finnhub.io/api/v1",
        transport=httpx.MockTransport(handler),
    )


def _cfg() -> FinnhubConfig:
    return FinnhubConfig(api_key="testkey")


def test_get_snapshot_parses_all_intraday_fields():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["symbol"] == "AAPL"
        return httpx.Response(200, json=FULL_QUOTE)

    provider = FinnhubMarketDataProvider(_cfg(), client=_client(handler))
    snapshot = provider.get_snapshot("AAPL")

    assert snapshot.symbol == "AAPL"
    assert snapshot.price == 102.0
    assert snapshot.day_change_pct == 1.4925
    assert snapshot.day_high == 104.0
    assert snapshot.day_low == 100.0
    assert snapshot.day_open == 100.5
    assert snapshot.prev_close == 100.5
    assert snapshot.as_of == datetime.fromtimestamp(TS, tz=timezone.utc)


def test_get_snapshot_unknown_symbol_when_price_zero():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"c": 0, "t": 0})

    provider = FinnhubMarketDataProvider(_cfg(), client=_client(handler))
    with pytest.raises(UnknownSymbol):
        provider.get_snapshot("NOPE")


def test_snapshot_and_quote_share_the_cache():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=FULL_QUOTE)

    now = [datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)]
    provider = FinnhubMarketDataProvider(
        _cfg(), client=_client(handler), clock=lambda: now[0]
    )

    provider.get_quote("AAPL")
    snapshot = provider.get_snapshot("AAPL")  # dentro del TTL (60s)

    assert calls["n"] == 1  # una sola llamada HTTP para ambos
    assert snapshot.day_high == 104.0


def test_snapshot_tolerates_missing_optional_fields():
    """Finnhub puede devolver null en dp/h/l/o/pc fuera de horario de mercado."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"c": 50.0, "dp": None, "h": None, "l": None, "o": None,
                  "pc": None, "t": TS},
        )

    provider = FinnhubMarketDataProvider(_cfg(), client=_client(handler))
    snapshot = provider.get_snapshot("QUIET")

    assert snapshot.day_change_pct == 0.0
    assert snapshot.day_high == 50.0
    assert snapshot.day_low == 50.0
    assert snapshot.day_open == 50.0
    assert snapshot.prev_close == 50.0
```

- [ ] **Step 2: Ejecutar los tests para verificar que fallan**

Run: `python -m pytest backend/tests/test_finnhub_snapshot.py -q`
Expected: FAIL con `AttributeError: 'FinnhubMarketDataProvider' object has no attribute 'get_snapshot'`.

- [ ] **Step 3: Refactorizar la caché y añadir `get_snapshot`**

En `backend/investsim/providers/finnhub.py`, ampliar el import de `market_data`:

```python
from investsim.providers.market_data import (
    MarketSnapshot,
    ProviderUnavailable,
    Quote,
    UnknownSymbol,
)
```

Cambiar el tipo de la caché en `__init__` (línea 35):

```python
        self._cache: dict[str, tuple[dict, datetime]] = {}
```

Reemplazar el método `get_quote` completo (líneas 37-52) por estos tres métodos, dejando `_fetch_quote_data` intacto debajo:

```python
    def _quote_data(self, symbol: str) -> dict:
        now = self.clock()
        cached = self._cache.get(symbol)
        if cached is not None:
            data, fetched_at = cached
            if now - fetched_at < self.config.ttl:
                return data

        data = self._fetch_quote_data(symbol)
        if data.get("c", 0) == 0:
            raise UnknownSymbol(symbol)
        self._cache[symbol] = (data, now)
        return data

    def get_quote(self, symbol: str) -> Quote:
        data = self._quote_data(symbol)
        return Quote(
            symbol=symbol,
            price=float(data["c"]),
            as_of=datetime.fromtimestamp(data["t"], tz=timezone.utc),
        )

    def get_snapshot(self, symbol: str) -> MarketSnapshot:
        data = self._quote_data(symbol)
        price = float(data["c"])
        return MarketSnapshot(
            symbol=symbol,
            price=price,
            day_change_pct=float(data.get("dp") or 0.0),
            day_high=float(data.get("h") or price),
            day_low=float(data.get("l") or price),
            day_open=float(data.get("o") or price),
            prev_close=float(data.get("pc") or price),
            as_of=datetime.fromtimestamp(data["t"], tz=timezone.utc),
        )
```

- [ ] **Step 4: Ejecutar los tests para verificar que pasan**

Run: `python -m pytest backend/tests -q`
Expected: PASS — 42 passed, 1 deselected. Los 7 tests de `test_finnhub_provider.py` (caché, backoff, 401) siguen verdes **sin haberlos modificado**.

- [ ] **Step 5: Commit**

```bash
git add backend/investsim/providers/finnhub.py backend/tests/test_finnhub_snapshot.py
git commit -m "feat(finnhub): get_snapshot con señales intradia, cache compartida con get_quote"
```

---

### Task 3: `Recommendation` y la interfaz `RecommendationEngine`

**Files:**
- Create: `backend/investsim/agent/__init__.py`
- Create: `backend/investsim/agent/engine.py`
- Test: `backend/tests/test_recommendation.py` (crear)

**Interfaces:**
- Consumes: `MarketSnapshot` (Task 1); `Direction`, `Horizon` de `investsim.domain.enums`.
- Produces:
  - `Recommendation(symbol: str, direction: Direction, confidence: float, suggested_amount: float, horizon: Horizon, rationale: str)` — dataclass frozen en `investsim.agent.engine`.
  - `RecommendationEngine` (Protocol) con `propose(snapshot: MarketSnapshot) -> Recommendation`.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `backend/tests/test_recommendation.py`:

```python
from datetime import datetime, timezone

import pytest

from investsim.agent.engine import Recommendation, RecommendationEngine
from investsim.domain.enums import Direction, Horizon
from investsim.providers.market_data import MarketSnapshot


def _recommendation() -> Recommendation:
    return Recommendation(
        symbol="AAPL",
        direction=Direction.UP,
        confidence=0.375,
        suggested_amount=7.5,
        horizon=Horizon.ONE_DAY,
        rationale="AAPL sube 1.50% hoy.",
    )


def test_recommendation_is_frozen():
    rec = _recommendation()
    with pytest.raises(Exception):
        rec.confidence = 0.9  # type: ignore[misc]


def test_recommendation_carries_domain_enums():
    rec = _recommendation()
    assert rec.direction is Direction.UP
    assert rec.horizon is Horizon.ONE_DAY
    assert rec.direction.value == "up"
    assert rec.horizon.value == "1D"


def test_engine_protocol_is_structural():
    """Cualquier objeto con propose(snapshot) cumple la interfaz, sin heredar."""

    class StubEngine:
        def propose(self, snapshot: MarketSnapshot) -> Recommendation:
            return _recommendation()

    engine: RecommendationEngine = StubEngine()
    snapshot = MarketSnapshot(
        symbol="AAPL",
        price=102.0,
        day_change_pct=1.5,
        day_high=104.0,
        day_low=100.0,
        day_open=100.5,
        prev_close=100.5,
        as_of=datetime(2026, 7, 19, tzinfo=timezone.utc),
    )
    assert engine.propose(snapshot) == _recommendation()
```

- [ ] **Step 2: Ejecutar los tests para verificar que fallan**

Run: `python -m pytest backend/tests/test_recommendation.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'investsim.agent'`.

- [ ] **Step 3: Crear el paquete `agent` con el dataclass y el Protocol**

Crear `backend/investsim/agent/__init__.py` vacío (mismo patrón que `investsim/providers/__init__.py`):

```python
```

Crear `backend/investsim/agent/engine.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from investsim.domain.enums import Direction, Horizon
from investsim.providers.market_data import MarketSnapshot


@dataclass(frozen=True)
class Recommendation:
    symbol: str
    direction: Direction
    confidence: float
    suggested_amount: float
    horizon: Horizon
    rationale: str


class RecommendationEngine(Protocol):
    def propose(self, snapshot: MarketSnapshot) -> Recommendation: ...
```

- [ ] **Step 4: Ejecutar los tests para verificar que pasan**

Run: `python -m pytest backend/tests -q`
Expected: PASS — 45 passed, 1 deselected.

- [ ] **Step 5: Commit**

```bash
git add backend/investsim/agent/ backend/tests/test_recommendation.py
git commit -m "feat(agent): Recommendation e interfaz RecommendationEngine"
```

---

### Task 4: `RuleBasedEngine`

**Files:**
- Create: `backend/investsim/agent/rules.py`
- Test: `backend/tests/test_rule_based_engine.py` (crear)

**Interfaces:**
- Consumes: `MarketSnapshot` (Task 1); `Recommendation`, `RecommendationEngine` (Task 3); `Direction`, `Horizon`.
- Produces: `RuleBasedEngine(base_amount: float = 20.0)` con `propose(snapshot: MarketSnapshot) -> Recommendation`.

**Lógica (del spec, para referencia del implementador):**
- `direction = UP` si `dp >= 0`, si no `DOWN`.
- `base_confidence = min(abs(dp) / 3.0, 1.0)`.
- `range_position = (price - day_low) / (day_high - day_low)`, o `0.5` si `day_high == day_low`.
- `confirmation = range_position` si UP, `1 - range_position` si DOWN.
- `confidence = clamp(base_confidence * (0.5 + confirmation / 2), 0.05, 0.95)`.
- `suggested_amount = base_amount * confidence`.
- `horizon = Horizon.ONE_DAY` siempre.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `backend/tests/test_rule_based_engine.py`:

```python
from datetime import datetime, timezone

import pytest

from investsim.agent.rules import RuleBasedEngine
from investsim.domain.enums import Direction, Horizon
from investsim.providers.market_data import MarketSnapshot

AS_OF = datetime(2026, 7, 19, 15, 0, tzinfo=timezone.utc)


def _snapshot(
    dp: float,
    price: float,
    high: float,
    low: float,
    symbol: str = "AAPL",
) -> MarketSnapshot:
    return MarketSnapshot(
        symbol=symbol,
        price=price,
        day_change_pct=dp,
        day_high=high,
        day_low=low,
        day_open=low,
        prev_close=low,
        as_of=AS_OF,
    )


def test_positive_change_gives_direction_up():
    rec = RuleBasedEngine().propose(_snapshot(dp=1.5, price=102, high=104, low=100))
    assert rec.direction is Direction.UP
    assert rec.symbol == "AAPL"


def test_negative_change_gives_direction_down():
    rec = RuleBasedEngine().propose(_snapshot(dp=-2.0, price=100.5, high=105, low=100))
    assert rec.direction is Direction.DOWN


def test_horizon_is_always_one_day():
    rec = RuleBasedEngine().propose(_snapshot(dp=-2.0, price=100.5, high=105, low=100))
    assert rec.horizon is Horizon.ONE_DAY


def test_confidence_mid_range():
    """dp=1.5 => base 0.5; precio en mitad del rango => factor 0.75."""
    rec = RuleBasedEngine().propose(_snapshot(dp=1.5, price=102, high=104, low=100))
    assert rec.confidence == pytest.approx(0.375)


def test_range_position_confirms_direction_up():
    """Mismo dp, pero cotizando en máximos: confianza reforzada."""
    rec = RuleBasedEngine().propose(_snapshot(dp=1.5, price=104, high=104, low=100))
    assert rec.confidence == pytest.approx(0.5)


def test_range_position_contradicts_direction_up():
    """Mismo dp, pero cotizando en mínimos: confianza atenuada."""
    rec = RuleBasedEngine().propose(_snapshot(dp=1.5, price=100, high=104, low=100))
    assert rec.confidence == pytest.approx(0.25)


def test_range_position_confirms_direction_down():
    """dp=-2.0 => base 2/3; precio cerca del mínimo (rp=0.1) => factor 0.95."""
    rec = RuleBasedEngine().propose(_snapshot(dp=-2.0, price=100.5, high=105, low=100))
    assert rec.confidence == pytest.approx(0.6333333, abs=1e-6)


def test_zero_change_is_up_with_minimum_confidence():
    rec = RuleBasedEngine().propose(_snapshot(dp=0.0, price=100, high=104, low=100))
    assert rec.direction is Direction.UP
    assert rec.confidence == pytest.approx(0.05)


def test_flat_range_uses_neutral_position():
    """day_high == day_low: rp=0.5 neutral, sin división por cero."""
    rec = RuleBasedEngine().propose(_snapshot(dp=3.0, price=110, high=110, low=110))
    assert rec.confidence == pytest.approx(0.75)


def test_confidence_is_clamped_at_upper_bound():
    """dp enorme y precio en máximos saturarían a 1.0; el clamp lo deja en 0.95."""
    rec = RuleBasedEngine().propose(_snapshot(dp=10.0, price=110, high=110, low=105))
    assert rec.confidence == pytest.approx(0.95)


def test_suggested_amount_scales_with_confidence():
    rec = RuleBasedEngine().propose(_snapshot(dp=1.5, price=102, high=104, low=100))
    assert rec.suggested_amount == pytest.approx(20.0 * 0.375)


def test_base_amount_is_configurable():
    engine = RuleBasedEngine(base_amount=50.0)
    rec = engine.propose(_snapshot(dp=1.5, price=102, high=104, low=100))
    assert rec.suggested_amount == pytest.approx(50.0 * 0.375)


def test_rationale_mentions_symbol_change_and_range_high():
    rec = RuleBasedEngine().propose(_snapshot(dp=1.24, price=104, high=104, low=100))
    assert rec.rationale == (
        "AAPL sube 1.24% hoy y cotiza cerca de máximos del rango diario."
    )


def test_rationale_for_down_near_lows():
    rec = RuleBasedEngine().propose(_snapshot(dp=-2.0, price=100.5, high=105, low=100))
    assert rec.rationale == (
        "AAPL baja 2.00% hoy y cotiza cerca de mínimos del rango diario."
    )


def test_rationale_for_mid_range():
    rec = RuleBasedEngine().propose(_snapshot(dp=1.5, price=102, high=104, low=100))
    assert rec.rationale == (
        "AAPL sube 1.50% hoy y cotiza en la zona media del rango diario."
    )
```

- [ ] **Step 2: Ejecutar los tests para verificar que fallan**

Run: `python -m pytest backend/tests/test_rule_based_engine.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'investsim.agent.rules'`.

- [ ] **Step 3: Implementar `RuleBasedEngine`**

Crear `backend/investsim/agent/rules.py`:

```python
from __future__ import annotations

from investsim.agent.engine import Recommendation
from investsim.domain.enums import Direction, Horizon
from investsim.providers.market_data import MarketSnapshot

# Un movimiento del ±3% satura la confianza de la señal de dp.
_DP_SATURATION = 3.0
_MIN_CONFIDENCE = 0.05
_MAX_CONFIDENCE = 0.95


def _range_label(range_position: float) -> str:
    if range_position >= 0.66:
        return "cerca de máximos del rango diario"
    if range_position <= 0.33:
        return "cerca de mínimos del rango diario"
    return "en la zona media del rango diario"


class RuleBasedEngine:
    """Motor determinista sobre señales intradía: dp + posición en el rango del día."""

    def __init__(self, base_amount: float = 20.0) -> None:
        self.base_amount = base_amount

    def propose(self, snapshot: MarketSnapshot) -> Recommendation:
        dp = snapshot.day_change_pct
        direction = Direction.UP if dp >= 0 else Direction.DOWN
        base_confidence = min(abs(dp) / _DP_SATURATION, 1.0)

        span = snapshot.day_high - snapshot.day_low
        if span == 0:
            range_position = 0.5
        else:
            range_position = (snapshot.price - snapshot.day_low) / span

        confirmation = (
            range_position if direction is Direction.UP else 1 - range_position
        )
        confidence = base_confidence * (0.5 + confirmation / 2)
        confidence = max(_MIN_CONFIDENCE, min(confidence, _MAX_CONFIDENCE))

        verb = "sube" if direction is Direction.UP else "baja"
        rationale = (
            f"{snapshot.symbol} {verb} {abs(dp):.2f}% hoy y cotiza "
            f"{_range_label(range_position)}."
        )

        return Recommendation(
            symbol=snapshot.symbol,
            direction=direction,
            confidence=confidence,
            suggested_amount=self.base_amount * confidence,
            horizon=Horizon.ONE_DAY,
            rationale=rationale,
        )
```

- [ ] **Step 4: Ejecutar los tests para verificar que pasan**

Run: `python -m pytest backend/tests/test_rule_based_engine.py -q`
Expected: PASS — 15 passed.

- [ ] **Step 5: Ejecutar la suite completa**

Run: `python -m pytest backend/tests -q`
Expected: PASS — 60 passed, 1 deselected.

- [ ] **Step 6: Commit**

```bash
git add backend/investsim/agent/rules.py backend/tests/test_rule_based_engine.py
git commit -m "feat(agent): RuleBasedEngine con señales dp y posicion en rango diario"
```

---

### Task 5: `AgentService`

**Files:**
- Create: `backend/investsim/services/agent_service.py`
- Test: `backend/tests/test_agent_service.py` (crear)

**Interfaces:**
- Consumes: `MarketDataProvider`, `MarketSnapshot`, `FakeMarketDataProvider`, `UnknownSymbol`, `ProviderUnavailable` (Task 1 / Fase 2); `Recommendation`, `RecommendationEngine` (Task 3); `RuleBasedEngine` (Task 4).
- Produces: `AgentService(market_data: MarketDataProvider, engine: RecommendationEngine)` con `propose(symbol: str) -> Recommendation`.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `backend/tests/test_agent_service.py`:

```python
from datetime import datetime, timezone

import pytest

from investsim.agent.engine import Recommendation
from investsim.agent.rules import RuleBasedEngine
from investsim.domain.enums import Direction, Horizon
from investsim.providers.market_data import (
    FakeMarketDataProvider,
    MarketSnapshot,
    ProviderUnavailable,
    UnknownSymbol,
)
from investsim.services.agent_service import AgentService

AS_OF = datetime(2026, 7, 19, 15, 0, tzinfo=timezone.utc)

SNAPSHOT = MarketSnapshot(
    symbol="AAPL",
    price=102.0,
    day_change_pct=1.5,
    day_high=104.0,
    day_low=100.0,
    day_open=100.5,
    prev_close=100.5,
    as_of=AS_OF,
)


class _SpyEngine:
    """Registra el snapshot recibido y devuelve siempre la misma recomendación."""

    def __init__(self) -> None:
        self.seen: list[MarketSnapshot] = []
        self.recommendation = Recommendation(
            symbol="AAPL",
            direction=Direction.UP,
            confidence=0.4,
            suggested_amount=8.0,
            horizon=Horizon.ONE_DAY,
            rationale="fijo",
        )

    def propose(self, snapshot: MarketSnapshot) -> Recommendation:
        self.seen.append(snapshot)
        return self.recommendation


class _BrokenProvider:
    def get_quote(self, symbol: str):
        raise ProviderUnavailable(symbol)

    def get_snapshot(self, symbol: str) -> MarketSnapshot:
        raise ProviderUnavailable(symbol)


def test_propose_passes_snapshot_to_engine_and_returns_its_recommendation():
    provider = FakeMarketDataProvider({}, snapshots={"AAPL": SNAPSHOT})
    engine = _SpyEngine()
    service = AgentService(provider, engine)

    rec = service.propose("AAPL")

    assert engine.seen == [SNAPSHOT]
    assert rec is engine.recommendation


def test_propose_end_to_end_with_rule_based_engine():
    provider = FakeMarketDataProvider({}, snapshots={"AAPL": SNAPSHOT})
    service = AgentService(provider, RuleBasedEngine())

    rec = service.propose("AAPL")

    assert rec.symbol == "AAPL"
    assert rec.direction is Direction.UP
    assert rec.horizon is Horizon.ONE_DAY
    assert rec.confidence == pytest.approx(0.375)
    assert rec.suggested_amount == pytest.approx(7.5)


def test_unknown_symbol_propagates_without_recommendation():
    service = AgentService(FakeMarketDataProvider({}), RuleBasedEngine())
    with pytest.raises(UnknownSymbol):
        service.propose("NOPE")


def test_provider_unavailable_propagates_without_recommendation():
    engine = _SpyEngine()
    service = AgentService(_BrokenProvider(), engine)

    with pytest.raises(ProviderUnavailable):
        service.propose("AAPL")

    assert engine.seen == []  # el motor no llega a ejecutarse
```

- [ ] **Step 2: Ejecutar los tests para verificar que fallan**

Run: `python -m pytest backend/tests/test_agent_service.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'investsim.services.agent_service'`.

- [ ] **Step 3: Implementar `AgentService`**

Crear `backend/investsim/services/agent_service.py`:

```python
from __future__ import annotations

from investsim.agent.engine import Recommendation, RecommendationEngine
from investsim.providers.market_data import MarketDataProvider


class AgentService:
    """Orquesta datos → motor. No persiste nada y no atrapa errores del proveedor."""

    def __init__(
        self,
        market_data: MarketDataProvider,
        engine: RecommendationEngine,
    ) -> None:
        self.market_data = market_data
        self.engine = engine

    def propose(self, symbol: str) -> Recommendation:
        snapshot = self.market_data.get_snapshot(symbol)
        return self.engine.propose(snapshot)
```

- [ ] **Step 4: Ejecutar los tests para verificar que pasan**

Run: `python -m pytest backend/tests/test_agent_service.py -q`
Expected: PASS — 4 passed.

- [ ] **Step 5: Ejecutar la suite completa**

Run: `python -m pytest backend/tests -q`
Expected: PASS — 64 passed, 1 deselected.

- [ ] **Step 6: Commit**

```bash
git add backend/investsim/services/agent_service.py backend/tests/test_agent_service.py
git commit -m "feat(servicios): AgentService orquesta snapshot y motor de recomendacion"
```

---

### Task 6: Integración real opt-in y cierre de fase

**Files:**
- Modify: `backend/tests/integration/test_finnhub_integration.py`
- Create: `backend/examples/smoke_agent.py`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: todo lo anterior (`AgentService`, `RuleBasedEngine`, `FinnhubMarketDataProvider.get_snapshot`, `load_finnhub_config`).
- Produces: nada de código nuevo importable; cierra la fase.

- [ ] **Step 1: Añadir el test de integración real de `get_snapshot`**

Añadir al final de `backend/tests/integration/test_finnhub_integration.py` (y ampliar el import de `market_data` de la línea 7 a `from investsim.providers.market_data import MarketSnapshot, Quote`):

```python
@pytest.mark.skipif(not _HAS_KEY, reason="requiere FINNHUB_API_KEY en el entorno")
def test_real_snapshot_for_known_symbol():
    provider = FinnhubMarketDataProvider(load_finnhub_config())
    snapshot = provider.get_snapshot("AAPL")

    assert isinstance(snapshot, MarketSnapshot)
    assert snapshot.symbol == "AAPL"
    assert snapshot.price > 0
    assert snapshot.day_low <= snapshot.price <= snapshot.day_high
```

- [ ] **Step 2: Verificar que el test de integración sigue excluido del bucle rápido**

Run: `python -m pytest backend/tests -q`
Expected: PASS — 64 passed, **2 deselected** (los dos tests `integration`).

- [ ] **Step 3: Crear el smoke manual del agente con datos reales**

Crear `backend/examples/smoke_agent.py`:

```python
"""Smoke manual: pide una recomendación real a Finnhub + reglas.

Uso (desde la raíz del repo, con FINNHUB_API_KEY en .env):
    python backend/examples/smoke_agent.py AAPL
"""

import sys

from investsim.agent.rules import RuleBasedEngine
from investsim.config import load_finnhub_config
from investsim.providers.finnhub import FinnhubMarketDataProvider
from investsim.services.agent_service import AgentService

DISCLAIMER = (
    "Simulación educativa, no es asesoramiento financiero. Capital ficticio."
)


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    service = AgentService(
        FinnhubMarketDataProvider(load_finnhub_config()), RuleBasedEngine()
    )
    rec = service.propose(symbol)

    print(f"Símbolo:   {rec.symbol}")
    print(f"Dirección: {rec.direction.value}  ({rec.horizon.value})")
    print(f"Confianza: {rec.confidence:.2%}")
    print(f"Importe:   {rec.suggested_amount:.2f} €")
    print(f"Motivo:    {rec.rationale}")
    print()
    print(DISCLAIMER)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Ejecutar el smoke a mano**

Run: `python backend/examples/smoke_agent.py AAPL`
Expected: imprime dirección, confianza, importe sugerido, motivo y el aviso legal. Si el mercado está cerrado, `dp` puede ser 0 y la confianza salir al mínimo (5%) — es correcto. Si no hay `FINNHUB_API_KEY`, lanza `MissingApiKey` con instrucciones.

- [ ] **Step 5: Actualizar el estado de fases en `CLAUDE.md`**

En la sección "Evolución futura", reemplazar `**F3** agente Claude (con persistencia de `MarketSnapshot` y `AgentRun`)` por:

```markdown
**F3a** agente por reglas (hecho: `RuleBasedEngine` + `AgentService`, sin LLM) · **F3b** motor LLM local (Ollama) como segunda implementación de `RecommendationEngine`
```

En la tabla "Decisiones de arquitectura", reemplazar la fila del cerebro del agente por:

```markdown
| Cerebro del agente | Agente por reglas determinista (`RuleBasedEngine`) sobre señales intradía | LLM local (Ollama) tras la misma interfaz `RecommendationEngine`; Claude API si algún día hay presupuesto |
```

- [ ] **Step 6: Suite completa final**

Run: `python -m pytest backend/tests -v`
Expected: PASS — 64 passed, 2 deselected. Sin warnings nuevos.

- [ ] **Step 7: Commit de cierre**

```bash
git add backend/tests/integration/test_finnhub_integration.py backend/examples/smoke_agent.py CLAUDE.md
git commit -m "test(fase3a): integracion real de get_snapshot, smoke del agente y cierre de fase"
```

---

## Resumen de ficheros

| Fichero | Acción | Responsabilidad |
|---------|--------|-----------------|
| `backend/investsim/providers/market_data.py` | Modificar | `MarketSnapshot`, `get_snapshot` en Protocol y fake |
| `backend/investsim/providers/finnhub.py` | Modificar | `get_snapshot` real; caché de JSON crudo compartida |
| `backend/investsim/agent/__init__.py` | Crear | Paquete del motor de recomendación |
| `backend/investsim/agent/engine.py` | Crear | `Recommendation` + interfaz `RecommendationEngine` |
| `backend/investsim/agent/rules.py` | Crear | `RuleBasedEngine` (única implementación en 3a) |
| `backend/investsim/services/agent_service.py` | Crear | Orquestación datos → motor |
| `backend/examples/smoke_agent.py` | Crear | Smoke manual con datos reales |
| `backend/tests/test_market_snapshot.py` | Crear | Snapshot + fake |
| `backend/tests/test_finnhub_snapshot.py` | Crear | Parseo real con `MockTransport` |
| `backend/tests/test_recommendation.py` | Crear | Dataclass + Protocol |
| `backend/tests/test_rule_based_engine.py` | Crear | Toda la aritmética de las reglas |
| `backend/tests/test_agent_service.py` | Crear | Orquestación y propagación de errores |
| `backend/tests/integration/test_finnhub_integration.py` | Modificar | Snapshot real, opt-in |
| `CLAUDE.md` | Modificar | Estado de fases y decisión del cerebro |
