# InvestSim — Fase 4: API FastAPI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exponer el bucle central de InvestSim (pedir recomendación → aceptar → liquidar → métricas) como 5 endpoints REST con FastAPI, sobre los servicios de dominio ya existentes (`AgentService`, `PortfolioService`, `SettlementService`), sin modificar ninguno de ellos.

**Architecture:** Paquete nuevo `investsim/api/` (app, deps, schemas, errors, routes) que llama a los servicios de dominio ya construidos en Fases 1-3a. `FinnhubMarketDataProvider` y `RuleBasedEngine` se instancian una sola vez al arrancar la app (singletons en `app.state`, para que la caché TTL de Finnhub sirva de algo); la `Session` de SQLAlchemy es por request. Endpoints síncronos (`def`, no `async def`) — FastAPI los ejecuta en threadpool, cero cambios en el dominio síncrono existente.

**Tech Stack:** FastAPI, uvicorn (servidor), Pydantic (ya viene con FastAPI), `fastapi.testclient.TestClient` para tests (usa `httpx`, ya instalado desde Fase 2).

## Global Constraints

- Python **3.11+** (sintaxis `X | None`).
- Endpoints **síncronos** (`def`, no `async def`) — decisión tomada en brainstorming para no reescribir el dominio síncrono de Fases 1-2 a async.
- **Ningún fichero de dominio se modifica** (`services/`, `providers/`, `agent/`, `db/`, `metrics.py` quedan intactos) — la API solo los consume.
- `FinnhubMarketDataProvider` y `RuleBasedEngine` son **singletons de la app** (`app.state`, creados una vez en `lifespan`), no uno por request — si no, la caché TTL de Finnhub nunca serviría de nada.
- La `Session` de SQLAlchemy es **por request** (dependencia generadora con `yield` + cierre en `finally`).
- Bootstrap automático del `Portfolio`: si no existe ninguno al arrancar, se crea uno con capital inicial de la variable de entorno `INITIAL_CAPITAL` (float, default `1000.0`). Sin endpoint manual de inicialización.
- URL de la BD configurable por `DATABASE_URL` (default `sqlite:///investsim.db`), leída en el `lifespan`.
- `GET /portfolio`, `GET /predictions` y `GET /metrics` llaman a `SettlementService.settle_due()` antes de construir su respuesta (liquidación perezosa transparente).
- Mapeo de excepciones de dominio a HTTP: `UnknownSymbol`→404, `ProviderUnavailable`→503, `InsufficientFunds`→400. `MissingApiKey` no se mapea: debe hacer fallar el arranque de la app, no una request.
- CORS: `CORSMiddleware` con `allow_origin_regex=r"http://localhost:\d+"` (cualquier puerto de `localhost`, cubre el 5173 de Vite sin fijarlo).
- Tests sin red: `app.dependency_overrides` sustituye el provider real por `FakeMarketDataProvider` en cada test de endpoint. La BD de test es un fichero SQLite temporal (`tmp_path`), **no** `sqlite:///:memory:` — con `:memory:` cada hilo del threadpool de FastAPI abriría su propia base vacía y las tablas "desaparecerían" entre request y request.
- Todos los comandos se ejecutan desde la **raíz del repo**. El intérprete real es `C:\Users\marcos\AppData\Local\Programs\Python\Python312\python.exe`; en el plan se escribe `python` por brevedad.
- Punto de partida: **64 tests pasan, 2 deselected** (`python -m pytest backend/tests -q`).

---

### Task 1: Scaffold — dependencias, paquete `api/`, app con lifespan (bootstrap + singletons + CORS)

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/investsim/api/__init__.py`
- Create: `backend/investsim/api/routes.py` (router vacío, se rellena en tareas siguientes)
- Create: `backend/investsim/api/errors.py`
- Create: `backend/investsim/api/app.py`
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/test_api_bootstrap.py`

**Interfaces:**
- Consumes: `FinnhubMarketDataProvider`, `load_finnhub_config` (Fase 2); `RuleBasedEngine` (Fase 3a); `Base`, `make_engine`, `make_session_factory`, `PortfolioRepository` (Fase 1).
- Produces: `investsim.api.app.create_app() -> FastAPI` y `investsim.api.app.app` (instancia módulo); `investsim.api.errors.register_exception_handlers(app: FastAPI) -> None`; `investsim.api.routes.router` (`APIRouter` vacío, se amplía en Tareas 2-6). Tras el `lifespan`, `app.state.session_factory: sessionmaker[Session]`, `app.state.market_data: MarketDataProvider`, `app.state.engine: RecommendationEngine`. Fixture de test `client` en `conftest.py`, reutilizable por todas las tareas siguientes.

- [ ] **Step 1: Añadir `fastapi` y `uvicorn` a las dependencias**

Reemplazar el bloque `dependencies` en `backend/pyproject.toml`:

```toml
dependencies = [
    "sqlalchemy>=2.0,<3.0",
    "httpx>=0.27",
    "python-dotenv>=1.0",
    "fastapi>=0.110,<1.0",
    "uvicorn[standard]>=0.29",
]
```

- [ ] **Step 2: Instalar las nuevas dependencias**

Run: `python -m pip install -e "backend[dev]"`
Expected: instala `fastapi`, `uvicorn` y sus dependencias transitivas (incluye `pydantic`) sin errores.

- [ ] **Step 3: Escribir la fixture compartida de tests y el test que falla**

Crear `backend/tests/conftest.py`:

```python
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
```

Crear `backend/tests/test_api_bootstrap.py`:

```python
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
```

- [ ] **Step 4: Ejecutar los tests para verificar que fallan**

Run: `python -m pytest backend/tests/test_api_bootstrap.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'investsim.api'`.

- [ ] **Step 5: Crear el paquete `investsim/api/`**

Crear `backend/investsim/api/__init__.py` (vacío):

```python
```

Crear `backend/investsim/api/routes.py`:

```python
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()
```

Crear `backend/investsim/api/errors.py`:

```python
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

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
```

Crear `backend/investsim/api/app.py`:

```python
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    app.state.engine = RuleBasedEngine()

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

- [ ] **Step 6: Ejecutar los tests para verificar que pasan**

Run: `python -m pytest backend/tests/test_api_bootstrap.py -v`
Expected: PASS — 2 passed.

- [ ] **Step 7: Ejecutar la suite completa**

Run: `python -m pytest backend/tests -q`
Expected: PASS — 66 passed, 2 deselected (64 previos + 2 nuevos).

- [ ] **Step 8: Commit**

```bash
git add backend/pyproject.toml backend/investsim/api/ backend/tests/conftest.py backend/tests/test_api_bootstrap.py
git commit -m "feat(api): scaffold FastAPI - lifespan, bootstrap de portfolio, CORS"
```

---

### Task 2: `POST /recommendations`

**Files:**
- Create: `backend/investsim/api/deps.py`
- Create: `backend/investsim/api/schemas.py`
- Modify: `backend/investsim/api/routes.py`
- Test: `backend/tests/test_api_recommendations.py`

**Interfaces:**
- Consumes: `AgentService` (Fase 3a), `Recommendation`, `RecommendationEngine` (Fase 3a), `MarketDataProvider` (Fase 1/2), `Direction`/`Horizon` (Fase 1), fixture `client` (Task 1).
- Produces: `investsim.api.deps.get_session`, `get_market_data_provider`, `get_recommendation_engine`, `get_agent_service` (todas `Depends()`); `investsim.api.schemas.RecommendationIn`, `RecommendationOut`. Ruta `POST /recommendations`.

- [ ] **Step 1: Escribir el test que falla**

Crear `backend/tests/test_api_recommendations.py`:

```python
from datetime import datetime, timezone

import pytest

from investsim.api.deps import get_market_data_provider
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
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `python -m pytest backend/tests/test_api_recommendations.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'investsim.api.deps'`.

- [ ] **Step 3: Crear `deps.py` y `schemas.py`, ampliar `routes.py`**

Crear `backend/investsim/api/deps.py`:

```python
from __future__ import annotations

from typing import Iterator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from investsim.agent.engine import RecommendationEngine
from investsim.providers.market_data import MarketDataProvider
from investsim.services.agent_service import AgentService


def get_session(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_market_data_provider(request: Request) -> MarketDataProvider:
    return request.app.state.market_data


def get_recommendation_engine(request: Request) -> RecommendationEngine:
    return request.app.state.engine


def get_agent_service(
    market_data: MarketDataProvider = Depends(get_market_data_provider),
    engine: RecommendationEngine = Depends(get_recommendation_engine),
) -> AgentService:
    return AgentService(market_data, engine)
```

Crear `backend/investsim/api/schemas.py`:

```python
from __future__ import annotations

from pydantic import BaseModel

from investsim.domain.enums import Direction, Horizon


class RecommendationIn(BaseModel):
    symbol: str


class RecommendationOut(BaseModel):
    symbol: str
    direction: Direction
    confidence: float
    suggested_amount: float
    horizon: Horizon
    rationale: str
```

Reemplazar `backend/investsim/api/routes.py` completo:

```python
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends

from investsim.api.deps import get_agent_service
from investsim.api.schemas import RecommendationIn, RecommendationOut
from investsim.services.agent_service import AgentService

router = APIRouter()


@router.post("/recommendations", response_model=RecommendationOut)
def post_recommendation(
    body: RecommendationIn,
    agent_service: AgentService = Depends(get_agent_service),
) -> RecommendationOut:
    recommendation = agent_service.propose(body.symbol)
    return RecommendationOut(**asdict(recommendation))
```

- [ ] **Step 4: Ejecutar los tests para verificar que pasan**

Run: `python -m pytest backend/tests/test_api_recommendations.py -v`
Expected: PASS — 3 passed.

- [ ] **Step 5: Ejecutar la suite completa**

Run: `python -m pytest backend/tests -q`
Expected: PASS — 69 passed, 2 deselected.

- [ ] **Step 6: Commit**

```bash
git add backend/investsim/api/deps.py backend/investsim/api/schemas.py backend/investsim/api/routes.py backend/tests/test_api_recommendations.py
git commit -m "feat(api): POST /recommendations"
```

---

### Task 3: `POST /predictions`

**Files:**
- Modify: `backend/investsim/api/deps.py`
- Modify: `backend/investsim/api/schemas.py`
- Modify: `backend/investsim/api/routes.py`
- Test: `backend/tests/test_api_predictions.py`

**Interfaces:**
- Consumes: `PortfolioService`, `InsufficientFunds` (Fase 1); `PredictionRow` (Fase 1); todo lo de Task 2.
- Produces: `investsim.api.deps.get_clock`, `get_portfolio_service`; `investsim.api.schemas.OpenPredictionIn`, `PredictionOut`; `investsim.api.routes._prediction_to_out(pred, current_value)`. Ruta `POST /predictions`.

- [ ] **Step 1: Escribir el test que falla**

Crear `backend/tests/test_api_predictions.py`:

```python
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
    assert portfolio.status_code == 404  # /portfolio aun no existe (Task 4)


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
```

**Nota:** `test_post_predictions_happy_path_deducts_cash` comprueba `GET /portfolio` devuelve 404 a propósito — esa ruta no existe todavía (llega en la Task 4), así que FastAPI responde 404 automáticamente. Esto confirma que `POST /predictions` no depende de rutas futuras.

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `python -m pytest backend/tests/test_api_predictions.py -q`
Expected: FAIL con 404 en `POST /predictions` (la ruta no existe: `{"detail":"Not Found"}` para las tres, ninguna con el código esperado por el test — el primer test falla porque la respuesta de `POST /predictions` en sí es 404, no las aserciones sobre `entry_price`).

- [ ] **Step 3: Ampliar `deps.py`, `schemas.py` y `routes.py`**

Reemplazar `backend/investsim/api/deps.py` completo:

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Iterator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from investsim.agent.engine import RecommendationEngine
from investsim.db.repositories import PortfolioRepository, PredictionRepository
from investsim.providers.market_data import MarketDataProvider
from investsim.services.agent_service import AgentService
from investsim.services.portfolio_service import PortfolioService


def get_session(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_market_data_provider(request: Request) -> MarketDataProvider:
    return request.app.state.market_data


def get_recommendation_engine(request: Request) -> RecommendationEngine:
    return request.app.state.engine


def get_agent_service(
    market_data: MarketDataProvider = Depends(get_market_data_provider),
    engine: RecommendationEngine = Depends(get_recommendation_engine),
) -> AgentService:
    return AgentService(market_data, engine)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_clock() -> Callable[[], datetime]:
    return _utcnow


def get_portfolio_service(
    session: Session = Depends(get_session),
    market_data: MarketDataProvider = Depends(get_market_data_provider),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> PortfolioService:
    return PortfolioService(
        PortfolioRepository(session),
        PredictionRepository(session),
        market_data,
        clock=clock,
    )
```

Reemplazar `backend/investsim/api/schemas.py` completo:

```python
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from investsim.domain.enums import Direction, Horizon


class RecommendationIn(BaseModel):
    symbol: str


class RecommendationOut(BaseModel):
    symbol: str
    direction: Direction
    confidence: float
    suggested_amount: float
    horizon: Horizon
    rationale: str


class OpenPredictionIn(BaseModel):
    symbol: str
    amount: float
    direction: Direction
    confidence: float
    horizon: Horizon
    rationale: str = ""


class PredictionOut(BaseModel):
    id: int
    symbol: str
    created_at: datetime
    entry_price: float
    amount: float
    shares: float
    horizon: str
    evaluate_at: datetime
    expected_direction: str
    confidence: float
    rationale: str
    status: str
    exit_price: float | None
    final_value: float | None
    pnl_pct: float | None
    hit: bool | None
    current_value: float | None = None
```

Reemplazar `backend/investsim/api/routes.py` completo:

```python
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends

from investsim.api.deps import get_agent_service, get_portfolio_service
from investsim.api.schemas import (
    OpenPredictionIn,
    PredictionOut,
    RecommendationIn,
    RecommendationOut,
)
from investsim.db.tables import PredictionRow
from investsim.services.agent_service import AgentService
from investsim.services.portfolio_service import PortfolioService

router = APIRouter()


def _prediction_to_out(
    pred: PredictionRow, current_value: float | None
) -> PredictionOut:
    return PredictionOut(
        id=pred.id,
        symbol=pred.symbol,
        created_at=pred.created_at,
        entry_price=pred.entry_price,
        amount=pred.amount,
        shares=pred.shares,
        horizon=pred.horizon,
        evaluate_at=pred.evaluate_at,
        expected_direction=pred.expected_direction,
        confidence=pred.confidence,
        rationale=pred.rationale,
        status=pred.status,
        exit_price=pred.exit_price,
        final_value=pred.final_value,
        pnl_pct=pred.pnl_pct,
        hit=pred.hit,
        current_value=current_value,
    )


@router.post("/recommendations", response_model=RecommendationOut)
def post_recommendation(
    body: RecommendationIn,
    agent_service: AgentService = Depends(get_agent_service),
) -> RecommendationOut:
    recommendation = agent_service.propose(body.symbol)
    return RecommendationOut(**asdict(recommendation))


@router.post("/predictions", response_model=PredictionOut)
def post_prediction(
    body: OpenPredictionIn,
    portfolio_service: PortfolioService = Depends(get_portfolio_service),
) -> PredictionOut:
    pred = portfolio_service.open_prediction(
        symbol=body.symbol,
        amount=body.amount,
        direction=body.direction,
        confidence=body.confidence,
        horizon=body.horizon,
        rationale=body.rationale,
    )
    return _prediction_to_out(pred, current_value=None)
```

- [ ] **Step 4: Ejecutar los tests para verificar que pasan**

Run: `python -m pytest backend/tests/test_api_predictions.py -v`
Expected: PASS — 3 passed.

- [ ] **Step 5: Ejecutar la suite completa**

Run: `python -m pytest backend/tests -q`
Expected: PASS — 72 passed, 2 deselected.

- [ ] **Step 6: Commit**

```bash
git add backend/investsim/api/deps.py backend/investsim/api/schemas.py backend/investsim/api/routes.py backend/tests/test_api_predictions.py
git commit -m "feat(api): POST /predictions"
```

---

### Task 4: `GET /portfolio`

**Files:**
- Modify: `backend/investsim/api/deps.py`
- Modify: `backend/investsim/api/schemas.py`
- Modify: `backend/investsim/api/routes.py`
- Test: `backend/tests/test_api_portfolio.py`

**Interfaces:**
- Consumes: `SettlementService`, `PortfolioRepository`, `PredictionRepository` (Fase 1); todo lo de Task 3.
- Produces: `investsim.api.deps.get_portfolio_repo`, `get_prediction_repo`, `get_settlement_service`; `investsim.api.schemas.PortfolioOut`. Ruta `GET /portfolio`.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `backend/tests/test_api_portfolio.py`:

```python
from datetime import datetime, timedelta, timezone

import pytest

from investsim.api.deps import get_clock, get_market_data_provider
from investsim.providers.market_data import FakeMarketDataProvider


def test_get_portfolio_returns_cash_and_total_value(client):
    fake = FakeMarketDataProvider({"AAPL": 100.0})
    client.app.dependency_overrides[get_market_data_provider] = lambda: fake

    client.post(
        "/predictions",
        json={
            "symbol": "AAPL",
            "amount": 10.0,
            "direction": "up",
            "confidence": 0.8,
            "horizon": "1W",
            "rationale": "",
        },
    )
    fake.set_price("AAPL", 150.0)

    response = client.get("/portfolio")

    assert response.status_code == 200
    body = response.json()
    assert body["cash_balance"] == pytest.approx(990.0)
    assert body["initial_capital"] == pytest.approx(1000.0)
    assert body["open_predictions_value"] == pytest.approx(15.0)
    assert body["total_value"] == pytest.approx(1005.0)


def test_get_portfolio_settles_due_predictions_first(client):
    now = [datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)]
    client.app.dependency_overrides[get_clock] = lambda: now[0]

    fake = FakeMarketDataProvider({"AAPL": 100.0})
    client.app.dependency_overrides[get_market_data_provider] = lambda: fake

    client.post(
        "/predictions",
        json={
            "symbol": "AAPL",
            "amount": 10.0,
            "direction": "up",
            "confidence": 0.8,
            "horizon": "1D",
            "rationale": "",
        },
    )

    fake.set_price("AAPL", 110.0)
    now[0] += timedelta(days=1, minutes=1)

    response = client.get("/portfolio")

    assert response.status_code == 200
    body = response.json()
    assert body["cash_balance"] == pytest.approx(1001.0)  # 1000 - 10 + 11
    assert body["open_predictions_value"] == pytest.approx(0.0)
```

- [ ] **Step 2: Ejecutar los tests para verificar que fallan**

Run: `python -m pytest backend/tests/test_api_portfolio.py -q`
Expected: FAIL con 404 (la ruta `GET /portfolio` no existe todavía).

- [ ] **Step 3: Ampliar `deps.py`, `schemas.py` y `routes.py`**

Reemplazar `backend/investsim/api/deps.py` completo:

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Iterator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from investsim.agent.engine import RecommendationEngine
from investsim.db.repositories import PortfolioRepository, PredictionRepository
from investsim.providers.market_data import MarketDataProvider
from investsim.services.agent_service import AgentService
from investsim.services.portfolio_service import PortfolioService
from investsim.services.settlement_service import SettlementService


def get_session(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_market_data_provider(request: Request) -> MarketDataProvider:
    return request.app.state.market_data


def get_recommendation_engine(request: Request) -> RecommendationEngine:
    return request.app.state.engine


def get_agent_service(
    market_data: MarketDataProvider = Depends(get_market_data_provider),
    engine: RecommendationEngine = Depends(get_recommendation_engine),
) -> AgentService:
    return AgentService(market_data, engine)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_clock() -> Callable[[], datetime]:
    return _utcnow


def get_portfolio_service(
    session: Session = Depends(get_session),
    market_data: MarketDataProvider = Depends(get_market_data_provider),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> PortfolioService:
    return PortfolioService(
        PortfolioRepository(session),
        PredictionRepository(session),
        market_data,
        clock=clock,
    )


def get_portfolio_repo(session: Session = Depends(get_session)) -> PortfolioRepository:
    return PortfolioRepository(session)


def get_prediction_repo(session: Session = Depends(get_session)) -> PredictionRepository:
    return PredictionRepository(session)


def get_settlement_service(
    session: Session = Depends(get_session),
    market_data: MarketDataProvider = Depends(get_market_data_provider),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> SettlementService:
    return SettlementService(
        PortfolioRepository(session),
        PredictionRepository(session),
        market_data,
        clock=clock,
    )
```

Añadir al final de `backend/investsim/api/schemas.py`:

```python


class PortfolioOut(BaseModel):
    cash_balance: float
    initial_capital: float
    open_predictions_value: float
    total_value: float
```

Reemplazar `backend/investsim/api/routes.py` completo:

```python
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends

from investsim.api.deps import (
    get_agent_service,
    get_portfolio_repo,
    get_portfolio_service,
    get_prediction_repo,
    get_settlement_service,
)
from investsim.api.schemas import (
    OpenPredictionIn,
    PortfolioOut,
    PredictionOut,
    RecommendationIn,
    RecommendationOut,
)
from investsim.db.repositories import PortfolioRepository, PredictionRepository
from investsim.db.tables import PredictionRow
from investsim.services.agent_service import AgentService
from investsim.services.portfolio_service import PortfolioService
from investsim.services.settlement_service import SettlementService

router = APIRouter()


def _prediction_to_out(
    pred: PredictionRow, current_value: float | None
) -> PredictionOut:
    return PredictionOut(
        id=pred.id,
        symbol=pred.symbol,
        created_at=pred.created_at,
        entry_price=pred.entry_price,
        amount=pred.amount,
        shares=pred.shares,
        horizon=pred.horizon,
        evaluate_at=pred.evaluate_at,
        expected_direction=pred.expected_direction,
        confidence=pred.confidence,
        rationale=pred.rationale,
        status=pred.status,
        exit_price=pred.exit_price,
        final_value=pred.final_value,
        pnl_pct=pred.pnl_pct,
        hit=pred.hit,
        current_value=current_value,
    )


@router.post("/recommendations", response_model=RecommendationOut)
def post_recommendation(
    body: RecommendationIn,
    agent_service: AgentService = Depends(get_agent_service),
) -> RecommendationOut:
    recommendation = agent_service.propose(body.symbol)
    return RecommendationOut(**asdict(recommendation))


@router.post("/predictions", response_model=PredictionOut)
def post_prediction(
    body: OpenPredictionIn,
    portfolio_service: PortfolioService = Depends(get_portfolio_service),
) -> PredictionOut:
    pred = portfolio_service.open_prediction(
        symbol=body.symbol,
        amount=body.amount,
        direction=body.direction,
        confidence=body.confidence,
        horizon=body.horizon,
        rationale=body.rationale,
    )
    return _prediction_to_out(pred, current_value=None)


@router.get("/portfolio", response_model=PortfolioOut)
def get_portfolio(
    settlement_service: SettlementService = Depends(get_settlement_service),
    portfolio_repo: PortfolioRepository = Depends(get_portfolio_repo),
    prediction_repo: PredictionRepository = Depends(get_prediction_repo),
) -> PortfolioOut:
    settlement_service.settle_due()
    portfolio = portfolio_repo.get()
    open_value = sum(
        settlement_service.mark_to_market(p)
        for p in prediction_repo.list_all()
        if p.status == "open"
    )
    return PortfolioOut(
        cash_balance=portfolio.cash_balance,
        initial_capital=portfolio.initial_capital,
        open_predictions_value=open_value,
        total_value=portfolio.cash_balance + open_value,
    )
```

- [ ] **Step 4: Ejecutar los tests para verificar que pasan**

Run: `python -m pytest backend/tests/test_api_portfolio.py -v`
Expected: PASS — 2 passed.

**Nota:** el test `test_post_predictions_happy_path_deducts_cash` de la Task 3 esperaba `404` en `GET /portfolio` porque la ruta no existía. Ahora existe: ese test empezará a fallar. Corrígelo en este mismo Step reemplazando, en `backend/tests/test_api_predictions.py`, la función completa por:

```python
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
```

Este cambio necesita `import pytest` al principio del fichero (añádelo si no está ya). Vuelve a ejecutar `python -m pytest backend/tests/test_api_predictions.py -v` para confirmar que sigue en verde (3 passed) antes de continuar.

- [ ] **Step 5: Ejecutar la suite completa**

Run: `python -m pytest backend/tests -q`
Expected: PASS — 74 passed, 2 deselected.

- [ ] **Step 6: Commit**

```bash
git add backend/investsim/api/deps.py backend/investsim/api/schemas.py backend/investsim/api/routes.py backend/tests/test_api_portfolio.py backend/tests/test_api_predictions.py
git commit -m "feat(api): GET /portfolio"
```

---

### Task 5: `GET /predictions`

**Files:**
- Modify: `backend/investsim/api/routes.py`
- Test: `backend/tests/test_api_predictions_list.py`

**Interfaces:**
- Consumes: todo lo de Task 4 (`get_settlement_service`, `get_prediction_repo`, `PredictionOut`, `_prediction_to_out`).
- Produces: Ruta `GET /predictions` → `list[PredictionOut]`.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `backend/tests/test_api_predictions_list.py`:

```python
from datetime import datetime, timedelta, timezone

import pytest

from investsim.api.deps import get_clock, get_market_data_provider
from investsim.providers.market_data import FakeMarketDataProvider


def test_list_predictions_includes_current_value_for_open(client):
    fake = FakeMarketDataProvider({"AAPL": 100.0})
    client.app.dependency_overrides[get_market_data_provider] = lambda: fake

    client.post(
        "/predictions",
        json={
            "symbol": "AAPL",
            "amount": 10.0,
            "direction": "up",
            "confidence": 0.8,
            "horizon": "1W",
            "rationale": "",
        },
    )
    fake.set_price("AAPL", 120.0)

    response = client.get("/predictions")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    pred = body[0]
    assert pred["status"] == "open"
    assert pred["current_value"] == pytest.approx(12.0)
    assert pred["final_value"] is None
    assert pred["exit_price"] is None


def test_list_predictions_settled_has_no_current_value(client):
    now = [datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)]
    client.app.dependency_overrides[get_clock] = lambda: now[0]

    fake = FakeMarketDataProvider({"AAPL": 100.0})
    client.app.dependency_overrides[get_market_data_provider] = lambda: fake

    client.post(
        "/predictions",
        json={
            "symbol": "AAPL",
            "amount": 10.0,
            "direction": "up",
            "confidence": 0.8,
            "horizon": "1D",
            "rationale": "",
        },
    )
    fake.set_price("AAPL", 90.0)
    now[0] += timedelta(days=1, minutes=1)

    response = client.get("/predictions")

    body = response.json()
    assert len(body) == 1
    pred = body[0]
    assert pred["status"] == "settled"
    assert pred["current_value"] is None
    assert pred["final_value"] == pytest.approx(9.0)
    assert pred["hit"] is False


def test_list_predictions_settles_due_first(client):
    now = [datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)]
    client.app.dependency_overrides[get_clock] = lambda: now[0]

    fake = FakeMarketDataProvider({"AAPL": 100.0})
    client.app.dependency_overrides[get_market_data_provider] = lambda: fake

    client.post(
        "/predictions",
        json={
            "symbol": "AAPL",
            "amount": 10.0,
            "direction": "up",
            "confidence": 0.8,
            "horizon": "1D",
            "rationale": "",
        },
    )
    now[0] += timedelta(days=1, minutes=1)

    response = client.get("/predictions")

    assert response.json()[0]["status"] == "settled"
```

- [ ] **Step 2: Ejecutar los tests para verificar que fallan**

Run: `python -m pytest backend/tests/test_api_predictions_list.py -q`
Expected: FAIL con 404 (la ruta `GET /predictions` no existe todavía).

- [ ] **Step 3: Añadir la ruta al final de `routes.py`**

Añadir al final de `backend/investsim/api/routes.py`:

```python


@router.get("/predictions", response_model=list[PredictionOut])
def list_predictions(
    settlement_service: SettlementService = Depends(get_settlement_service),
    prediction_repo: PredictionRepository = Depends(get_prediction_repo),
) -> list[PredictionOut]:
    settlement_service.settle_due()
    result: list[PredictionOut] = []
    for pred in prediction_repo.list_all():
        current_value = (
            settlement_service.mark_to_market(pred)
            if pred.status == "open"
            else None
        )
        result.append(_prediction_to_out(pred, current_value))
    return result
```

- [ ] **Step 4: Ejecutar los tests para verificar que pasan**

Run: `python -m pytest backend/tests/test_api_predictions_list.py -v`
Expected: PASS — 3 passed.

- [ ] **Step 5: Ejecutar la suite completa**

Run: `python -m pytest backend/tests -q`
Expected: PASS — 77 passed, 2 deselected.

- [ ] **Step 6: Commit**

```bash
git add backend/investsim/api/routes.py backend/tests/test_api_predictions_list.py
git commit -m "feat(api): GET /predictions"
```

---

### Task 6: `GET /metrics`

**Files:**
- Modify: `backend/investsim/api/schemas.py`
- Modify: `backend/investsim/api/routes.py`
- Test: `backend/tests/test_api_metrics.py`

**Interfaces:**
- Consumes: `compute_metrics`, `Metrics` (Fase 1); todo lo de Task 5.
- Produces: `investsim.api.schemas.MetricsOut`. Ruta `GET /metrics`.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `backend/tests/test_api_metrics.py`:

```python
from datetime import datetime, timedelta, timezone

import pytest

from investsim.api.deps import get_clock, get_market_data_provider
from investsim.providers.market_data import FakeMarketDataProvider


def test_get_metrics_matches_compute_metrics(client):
    now = [datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)]
    client.app.dependency_overrides[get_clock] = lambda: now[0]

    fake = FakeMarketDataProvider({"AAPL": 100.0})
    client.app.dependency_overrides[get_market_data_provider] = lambda: fake

    client.post(
        "/predictions",
        json={
            "symbol": "AAPL",
            "amount": 10.0,
            "direction": "up",
            "confidence": 0.9,
            "horizon": "1D",
            "rationale": "",
        },
    )
    fake.set_price("AAPL", 134.0)
    now[0] += timedelta(days=1, minutes=1)

    response = client.get("/metrics")

    assert response.status_code == 200
    body = response.json()
    assert body["total_predictions"] == 1
    assert body["settled"] == 1
    assert body["hits"] == 1
    assert body["hit_rate_pct"] == pytest.approx(100.0)
    assert body["total_invested"] == pytest.approx(10.0)
    assert body["total_final_value"] == pytest.approx(13.4)
    assert body["total_return_pct"] == pytest.approx(34.0)


def test_get_metrics_settles_due_first(client):
    fake = FakeMarketDataProvider({"AAPL": 100.0})
    client.app.dependency_overrides[get_market_data_provider] = lambda: fake

    client.post(
        "/predictions",
        json={
            "symbol": "AAPL",
            "amount": 10.0,
            "direction": "up",
            "confidence": 0.8,
            "horizon": "1W",
            "rationale": "",
        },
    )

    response = client.get("/metrics")

    body = response.json()
    assert body["total_predictions"] == 1
    assert body["settled"] == 0
```

- [ ] **Step 2: Ejecutar los tests para verificar que fallan**

Run: `python -m pytest backend/tests/test_api_metrics.py -q`
Expected: FAIL con 404 (la ruta `GET /metrics` no existe todavía).

- [ ] **Step 3: Ampliar `schemas.py` y `routes.py`**

Añadir al final de `backend/investsim/api/schemas.py`:

```python


class MetricsOut(BaseModel):
    total_predictions: int
    settled: int
    hits: int
    hit_rate_pct: float
    total_invested: float
    total_final_value: float
    total_return_pct: float
```

En `backend/investsim/api/routes.py`, ampliar el bloque de imports de `investsim.api.schemas` para incluir `MetricsOut`:

```python
from investsim.api.schemas import (
    MetricsOut,
    OpenPredictionIn,
    PortfolioOut,
    PredictionOut,
    RecommendationIn,
    RecommendationOut,
)
```

Añadir el import de `compute_metrics` junto a los demás imports:

```python
from investsim.metrics import compute_metrics
```

Añadir al final de `backend/investsim/api/routes.py`:

```python


@router.get("/metrics", response_model=MetricsOut)
def get_metrics(
    settlement_service: SettlementService = Depends(get_settlement_service),
    prediction_repo: PredictionRepository = Depends(get_prediction_repo),
) -> MetricsOut:
    settlement_service.settle_due()
    metrics = compute_metrics(prediction_repo.list_all())
    return MetricsOut(**asdict(metrics))
```

- [ ] **Step 4: Ejecutar los tests para verificar que pasan**

Run: `python -m pytest backend/tests/test_api_metrics.py -v`
Expected: PASS — 2 passed.

- [ ] **Step 5: Ejecutar la suite completa**

Run: `python -m pytest backend/tests -q`
Expected: PASS — 79 passed, 2 deselected.

- [ ] **Step 6: Commit**

```bash
git add backend/investsim/api/schemas.py backend/investsim/api/routes.py backend/tests/test_api_metrics.py
git commit -m "feat(api): GET /metrics"
```

---

### Task 7: Smoke manual y cierre de fase

**Files:**
- Create: `backend/examples/smoke_api.py`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: `investsim.api.app.create_app` (Task 1).
- Produces: nada de código nuevo importable; cierra la fase.

- [ ] **Step 1: Crear el smoke manual de la API completa**

Crear `backend/examples/smoke_api.py`:

```python
"""Smoke manual: bucle completo via la API HTTP, con Finnhub real.

Uso (desde la raiz del repo, con FINNHUB_API_KEY en .env):
    python backend/examples/smoke_api.py AAPL
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from investsim.api.app import create_app

DISCLAIMER = (
    "Simulación educativa, no es asesoramiento financiero. Capital ficticio."
)


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"

    with tempfile.TemporaryDirectory() as tmp:
        db_path = (Path(tmp) / "smoke_api.db").as_posix()
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

        app = create_app()
        with TestClient(app) as client:
            rec = client.post("/recommendations", json={"symbol": symbol}).json()
            print("Recomendacion:", rec)

            pred = client.post(
                "/predictions",
                json={
                    "symbol": symbol,
                    "amount": rec["suggested_amount"],
                    "direction": rec["direction"],
                    "confidence": rec["confidence"],
                    "horizon": rec["horizon"],
                    "rationale": rec["rationale"],
                },
            ).json()
            print("Prediccion abierta:", pred)

            print("Portfolio:", client.get("/portfolio").json())
            print("Predicciones:", client.get("/predictions").json())
            print("Metricas:", client.get("/metrics").json())

    print()
    print(DISCLAIMER)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Ejecutar el smoke a mano**

Run: `python backend/examples/smoke_api.py AAPL`
Expected: imprime la recomendación real de Finnhub, la predicción abierta, el portfolio, la lista de predicciones y las métricas, terminando con el aviso legal. Usa una BD temporal (se borra al salir del script) para no tocar `investsim.db`. Si no hay `FINNHUB_API_KEY`, falla al construir la app con `MissingApiKey` y sus instrucciones — comportamiento esperado.

- [ ] **Step 3: Actualizar `CLAUDE.md`**

En la tabla de `## Layout`, reemplazar la línea de `backend/`:

```markdown
- `backend/` — raíz del proyecto Python, paquete `investsim` (dominio, db, providers, agent, services, api, metrics).
```

En `## Comandos`, añadir una línea después del bloque de pytest existente:

```markdown
Servidor de desarrollo de la API:

```bash
python -m uvicorn investsim.api.app:app --reload   # http://127.0.0.1:8000
```
```

En `## Evolución futura`, reemplazar la línea de fases:

```markdown
Fases planificadas tras el núcleo de dominio (Fase 1): **F2** datos reales (Finnhub) · **F3a** agente por reglas (hecho: `RuleBasedEngine` + `AgentService`, sin LLM) · **F3b** motor LLM local (Ollama) como segunda implementación de `RecommendationEngine` · **F4** API FastAPI (hecho: 5 endpoints REST sobre `AgentService`/`PortfolioService`/`SettlementService`) · **F5** frontend React · **F6** pulido (observabilidad de coste, watchlist). Más adelante: agente híbrido ML+Claude, crypto/multi-activo, scheduler, Docker. Ver la sección "Evolución futura" del spec para el detalle.
```

- [ ] **Step 4: Suite completa final**

Run: `python -m pytest backend/tests -v`
Expected: PASS — 79 passed, 2 deselected. Sin warnings nuevos.

- [ ] **Step 5: Commit de cierre**

```bash
git add backend/examples/smoke_api.py CLAUDE.md
git commit -m "test(fase4): smoke manual de la API completa y cierre de fase"
```

---

## Resumen de ficheros

| Fichero | Acción | Responsabilidad |
|---------|--------|------------------|
| `backend/pyproject.toml` | Modificar | Dependencias `fastapi`, `uvicorn` |
| `backend/investsim/api/__init__.py` | Crear | Paquete de la API |
| `backend/investsim/api/app.py` | Crear | `create_app()`, `lifespan` (bootstrap, singletons, CORS) |
| `backend/investsim/api/errors.py` | Crear | Mapeo de excepciones de dominio → HTTP |
| `backend/investsim/api/deps.py` | Crear (ampliado en Tasks 3-4) | Dependencias FastAPI: sesión, provider, engine, servicios, reloj |
| `backend/investsim/api/schemas.py` | Crear (ampliado en Tasks 3,4,6) | Modelos Pydantic de entrada/salida |
| `backend/investsim/api/routes.py` | Crear (ampliado en Tasks 2-6) | Los 5 endpoints |
| `backend/tests/conftest.py` | Crear | Fixture `client` compartida (BD temporal + Finnhub dummy) |
| `backend/tests/test_api_bootstrap.py` | Crear | Bootstrap del portfolio |
| `backend/tests/test_api_recommendations.py` | Crear | `POST /recommendations` |
| `backend/tests/test_api_predictions.py` | Crear (1 aserción corregida en Task 4) | `POST /predictions` |
| `backend/tests/test_api_portfolio.py` | Crear | `GET /portfolio` |
| `backend/tests/test_api_predictions_list.py` | Crear | `GET /predictions` |
| `backend/tests/test_api_metrics.py` | Crear | `GET /metrics` |
| `backend/examples/smoke_api.py` | Crear | Smoke manual con datos reales |
| `CLAUDE.md` | Modificar | Layout, comando de servidor, estado de fases |
