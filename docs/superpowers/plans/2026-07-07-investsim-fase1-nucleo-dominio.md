# InvestSim — Fase 1: Núcleo de dominio + BD · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el bucle central de InvestSim (abrir operación simulada → vencer → liquidar → métricas) como dominio puro sobre SQLite, testeado de punta a punta sin red ni coste usando un proveedor de datos *fake*.

**Architecture:** Dominio en capas siguiendo la Dependency Rule. Los servicios de dominio (`PortfolioService`, `SettlementService`) y el cálculo de métricas no conocen Finnhub ni Claude ni FastAPI: dependen de la interfaz `MarketDataProvider` y de repositorios SQLAlchemy. En Fase 1 el proveedor real se sustituye por `FakeMarketDataProvider`.

**Tech Stack:** Python 3.11+, SQLAlchemy 2.x (ORM tipado con `Mapped`), pytest, SQLite (fichero en producción, en memoria en tests).

## Global Constraints

- Python **3.11 o superior** (se usa sintaxis `X | None`).
- SQLAlchemy **2.x** (API `DeclarativeBase` / `Mapped` / `mapped_column`).
- **Sin acceso a red en toda la Fase 1.** El único proveedor de datos es `FakeMarketDataProvider`.
- **Un solo `Portfolio`** en toda la app (uso personal, sin login).
- Capital y precios en **euros virtuales** (`float`). Nunca dinero real.
- Enums del dominio se persisten por su **valor string** (`"1D"`, `"up"`, `"open"`, …).
- Todos los timestamps en **UTC** (`datetime.now(timezone.utc)`), vía un `clock` inyectable para poder testear el paso del tiempo.
- Layout: raíz del proyecto Python en `backend/`, paquete importable `investsim`. Tests en `backend/tests/`.
- Todos los comandos se ejecutan desde la **raíz del repo** salvo que se indique. Tras la Tarea 1, `investsim` es importable vía `pip install -e backend`.

---

### Task 1: Scaffold del proyecto backend + enums del dominio

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/investsim/__init__.py`
- Create: `backend/investsim/domain/__init__.py`
- Create: `backend/investsim/domain/enums.py`
- Create: `backend/tests/__init__.py`
- Test: `backend/tests/test_enums.py`

**Interfaces:**
- Consumes: nada (primera tarea).
- Produces:
  - `Horizon(str, Enum)` con miembros `ONE_DAY="1D"`, `ONE_WEEK="1W"`, `ONE_MONTH="1M"` y método `to_timedelta() -> timedelta`.
  - `Direction(str, Enum)` con `UP="up"`, `DOWN="down"`.
  - `Status(str, Enum)` con `OPEN="open"`, `SETTLED="settled"`.

- [ ] **Step 1: Crear `backend/pyproject.toml`**

```toml
[project]
name = "investsim"
version = "0.1.0"
description = "Agente de inversion simulada - nucleo de dominio"
requires-python = ">=3.11"
dependencies = [
    "sqlalchemy>=2.0,<3.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["investsim*"]
```

- [ ] **Step 2: Crear los `__init__.py` vacíos**

Crear `backend/investsim/__init__.py`, `backend/investsim/domain/__init__.py` y `backend/tests/__init__.py`, los tres con contenido vacío.

- [ ] **Step 3: Instalar el paquete en modo editable**

Run: `pip install -e "backend[dev]"`
Expected: instala `investsim`, `sqlalchemy` y `pytest` sin errores.

- [ ] **Step 4: Escribir el test que falla**

Crear `backend/tests/test_enums.py`:

```python
from datetime import timedelta

from investsim.domain.enums import Direction, Horizon, Status


def test_horizon_values():
    assert Horizon.ONE_DAY.value == "1D"
    assert Horizon.ONE_WEEK.value == "1W"
    assert Horizon.ONE_MONTH.value == "1M"


def test_horizon_to_timedelta():
    assert Horizon.ONE_DAY.to_timedelta() == timedelta(days=1)
    assert Horizon.ONE_WEEK.to_timedelta() == timedelta(weeks=1)
    assert Horizon.ONE_MONTH.to_timedelta() == timedelta(days=30)


def test_direction_and_status_values():
    assert Direction.UP.value == "up"
    assert Direction.DOWN.value == "down"
    assert Status.OPEN.value == "open"
    assert Status.SETTLED.value == "settled"
```

- [ ] **Step 5: Ejecutar el test para verificar que falla**

Run: `python -m pytest backend/tests/test_enums.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'investsim.domain.enums'`.

- [ ] **Step 6: Implementar `backend/investsim/domain/enums.py`**

```python
from __future__ import annotations

from datetime import timedelta
from enum import Enum


class Horizon(str, Enum):
    ONE_DAY = "1D"
    ONE_WEEK = "1W"
    ONE_MONTH = "1M"

    def to_timedelta(self) -> timedelta:
        return {
            Horizon.ONE_DAY: timedelta(days=1),
            Horizon.ONE_WEEK: timedelta(weeks=1),
            Horizon.ONE_MONTH: timedelta(days=30),
        }[self]


class Direction(str, Enum):
    UP = "up"
    DOWN = "down"


class Status(str, Enum):
    OPEN = "open"
    SETTLED = "settled"
```

- [ ] **Step 7: Ejecutar el test para verificar que pasa**

Run: `python -m pytest backend/tests/test_enums.py -v`
Expected: PASS (3 tests).

- [ ] **Step 8: Commit**

```bash
git add backend/pyproject.toml backend/investsim backend/tests
git commit -m "feat(dominio): scaffold backend y enums Horizon/Direction/Status"
```

---

### Task 2: Capa de BD — tablas SQLAlchemy y sesión

**Files:**
- Create: `backend/investsim/db/__init__.py`
- Create: `backend/investsim/db/base.py`
- Create: `backend/investsim/db/tables.py`
- Test: `backend/tests/test_tables.py`

**Interfaces:**
- Consumes: nada del dominio (las tablas guardan enums como string).
- Produces:
  - `Base` (DeclarativeBase).
  - `make_engine(url: str = "sqlite:///investsim.db")` y `make_session_factory(engine)`.
  - `PortfolioRow` con columnas `id:int (pk)`, `cash_balance:float`, `initial_capital:float`, `created_at:datetime`.
  - `PredictionRow` con columnas `id:int (pk)`, `symbol:str`, `created_at:datetime`, `entry_price:float`, `amount:float`, `shares:float`, `horizon:str`, `evaluate_at:datetime`, `expected_direction:str`, `confidence:float`, `rationale:str`, `status:str`, `exit_price:float|None`, `final_value:float|None`, `pnl_pct:float|None`, `hit:bool|None`.

- [ ] **Step 1: Escribir el test que falla**

Crear `backend/tests/test_tables.py`:

```python
from datetime import datetime, timezone

from investsim.db.base import Base, make_engine, make_session_factory
from investsim.db.tables import PortfolioRow, PredictionRow


def _session():
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return make_session_factory(engine)()


def test_portfolio_roundtrip():
    session = _session()
    now = datetime.now(timezone.utc)
    session.add(PortfolioRow(cash_balance=10.0, initial_capital=10.0, created_at=now))
    session.commit()
    row = session.query(PortfolioRow).one()
    assert row.id is not None
    assert row.cash_balance == 10.0


def test_prediction_roundtrip_with_nullable_settlement_fields():
    session = _session()
    now = datetime.now(timezone.utc)
    session.add(
        PredictionRow(
            symbol="AAPL",
            created_at=now,
            entry_price=100.0,
            amount=10.0,
            shares=0.1,
            horizon="1W",
            evaluate_at=now,
            expected_direction="up",
            confidence=0.7,
            rationale="test",
            status="open",
        )
    )
    session.commit()
    row = session.query(PredictionRow).one()
    assert row.symbol == "AAPL"
    assert row.exit_price is None
    assert row.hit is None
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `python -m pytest backend/tests/test_tables.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'investsim.db'`.

- [ ] **Step 3: Crear `backend/investsim/db/__init__.py`** (vacío)

- [ ] **Step 4: Implementar `backend/investsim/db/base.py`**

```python
from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def make_engine(url: str = "sqlite:///investsim.db") -> Engine:
    return create_engine(url, future=True)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, future=True, expire_on_commit=False)
```

- [ ] **Step 5: Implementar `backend/investsim/db/tables.py`**

```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from investsim.db.base import Base


class PortfolioRow(Base):
    __tablename__ = "portfolios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cash_balance: Mapped[float] = mapped_column(Float, nullable=False)
    initial_capital: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class PredictionRow(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    shares: Mapped[float] = mapped_column(Float, nullable=False)
    horizon: Mapped[str] = mapped_column(String(4), nullable=False)
    evaluate_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expected_direction: Mapped[str] = mapped_column(String(4), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="open")
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    hit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
```

- [ ] **Step 6: Ejecutar el test para verificar que pasa**

Run: `python -m pytest backend/tests/test_tables.py -v`
Expected: PASS (2 tests).

- [ ] **Step 7: Commit**

```bash
git add backend/investsim/db backend/tests/test_tables.py
git commit -m "feat(db): tablas SQLAlchemy Portfolio y Prediction + sesion"
```

---

### Task 3: Interfaz `MarketDataProvider` y proveedor *fake*

**Files:**
- Create: `backend/investsim/providers/__init__.py`
- Create: `backend/investsim/providers/market_data.py`
- Test: `backend/tests/test_fake_market_data.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `Quote` (dataclass frozen) con `symbol:str`, `price:float`, `as_of:datetime`.
  - `MarketDataProvider` (Protocol) con `get_quote(symbol: str) -> Quote`.
  - `UnknownSymbol(Exception)`.
  - `FakeMarketDataProvider(prices: dict[str, float], as_of: datetime | None = None)` con métodos `set_price(symbol: str, price: float) -> None` y `get_quote(symbol: str) -> Quote` (lanza `UnknownSymbol` si falta el símbolo).

- [ ] **Step 1: Escribir el test que falla**

Crear `backend/tests/test_fake_market_data.py`:

```python
from datetime import datetime, timezone

import pytest

from investsim.providers.market_data import (
    FakeMarketDataProvider,
    Quote,
    UnknownSymbol,
)


def test_get_quote_returns_configured_price():
    as_of = datetime(2026, 7, 7, tzinfo=timezone.utc)
    provider = FakeMarketDataProvider({"AAPL": 100.0}, as_of=as_of)
    quote = provider.get_quote("AAPL")
    assert quote == Quote(symbol="AAPL", price=100.0, as_of=as_of)


def test_set_price_updates_quote():
    provider = FakeMarketDataProvider({"AAPL": 100.0})
    provider.set_price("AAPL", 120.0)
    assert provider.get_quote("AAPL").price == 120.0


def test_unknown_symbol_raises():
    provider = FakeMarketDataProvider({})
    with pytest.raises(UnknownSymbol):
        provider.get_quote("NOPE")
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `python -m pytest backend/tests/test_fake_market_data.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'investsim.providers'`.

- [ ] **Step 3: Crear `backend/investsim/providers/__init__.py`** (vacío)

- [ ] **Step 4: Implementar `backend/investsim/providers/market_data.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: float
    as_of: datetime


class UnknownSymbol(Exception):
    pass


class MarketDataProvider(Protocol):
    def get_quote(self, symbol: str) -> Quote: ...


class FakeMarketDataProvider:
    def __init__(
        self, prices: dict[str, float], as_of: datetime | None = None
    ) -> None:
        self._prices = dict(prices)
        self._as_of = as_of or datetime.now(timezone.utc)

    def set_price(self, symbol: str, price: float) -> None:
        self._prices[symbol] = price

    def get_quote(self, symbol: str) -> Quote:
        if symbol not in self._prices:
            raise UnknownSymbol(symbol)
        return Quote(symbol=symbol, price=self._prices[symbol], as_of=self._as_of)
```

- [ ] **Step 5: Ejecutar el test para verificar que pasa**

Run: `python -m pytest backend/tests/test_fake_market_data.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/investsim/providers backend/tests/test_fake_market_data.py
git commit -m "feat(providers): interfaz MarketDataProvider y FakeMarketDataProvider"
```

---

### Task 4: Repositorios de Portfolio y Prediction

**Files:**
- Create: `backend/investsim/db/repositories.py`
- Test: `backend/tests/test_repositories.py`

**Interfaces:**
- Consumes: `PortfolioRow`, `PredictionRow` (Task 2), sesión SQLAlchemy (Task 2).
- Produces:
  - `PortfolioRepository(session)` con:
    - `create(initial_capital: float, created_at: datetime) -> PortfolioRow`
    - `get() -> PortfolioRow | None` (el único portfolio)
    - `save(row: PortfolioRow) -> None`
  - `PredictionRepository(session)` con:
    - `add(row: PredictionRow) -> PredictionRow`
    - `get(prediction_id: int) -> PredictionRow | None`
    - `list_all() -> list[PredictionRow]`
    - `list_open_due(now: datetime) -> list[PredictionRow]` (status `"open"` y `evaluate_at <= now`)
    - `save(row: PredictionRow) -> None`

- [ ] **Step 1: Escribir el test que falla**

Crear `backend/tests/test_repositories.py`:

```python
from datetime import datetime, timedelta, timezone

from investsim.db.base import Base, make_engine, make_session_factory
from investsim.db.repositories import PortfolioRepository, PredictionRepository
from investsim.db.tables import PredictionRow


def _session():
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return make_session_factory(engine)()


def test_portfolio_create_and_get():
    repo = PortfolioRepository(_session())
    now = datetime.now(timezone.utc)
    repo.create(initial_capital=10.0, created_at=now)
    got = repo.get()
    assert got is not None
    assert got.cash_balance == 10.0
    assert got.initial_capital == 10.0


def _make_prediction(symbol, evaluate_at, status="open"):
    now = datetime.now(timezone.utc)
    return PredictionRow(
        symbol=symbol,
        created_at=now,
        entry_price=100.0,
        amount=10.0,
        shares=0.1,
        horizon="1W",
        evaluate_at=evaluate_at,
        expected_direction="up",
        confidence=0.7,
        rationale="",
        status=status,
    )


def test_prediction_add_get_list():
    repo = PredictionRepository(_session())
    now = datetime.now(timezone.utc)
    added = repo.add(_make_prediction("AAPL", now))
    assert added.id is not None
    assert repo.get(added.id).symbol == "AAPL"
    assert len(repo.list_all()) == 1


def test_list_open_due_filters_by_status_and_time():
    session = _session()
    repo = PredictionRepository(session)
    now = datetime.now(timezone.utc)
    repo.add(_make_prediction("DUE", now - timedelta(hours=1)))          # vencida, open
    repo.add(_make_prediction("FUTURE", now + timedelta(days=1)))        # no vencida
    repo.add(_make_prediction("SETTLED", now - timedelta(hours=1),
                              status="settled"))                          # vencida pero ya liquidada
    due = repo.list_open_due(now)
    assert [p.symbol for p in due] == ["DUE"]
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `python -m pytest backend/tests/test_repositories.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'investsim.db.repositories'`.

- [ ] **Step 3: Implementar `backend/investsim/db/repositories.py`**

```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from investsim.db.tables import PortfolioRow, PredictionRow


class PortfolioRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, initial_capital: float, created_at: datetime) -> PortfolioRow:
        row = PortfolioRow(
            cash_balance=initial_capital,
            initial_capital=initial_capital,
            created_at=created_at,
        )
        self.session.add(row)
        self.session.commit()
        return row

    def get(self) -> PortfolioRow | None:
        return self.session.scalars(select(PortfolioRow).limit(1)).first()

    def save(self, row: PortfolioRow) -> None:
        self.session.add(row)
        self.session.commit()


class PredictionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, row: PredictionRow) -> PredictionRow:
        self.session.add(row)
        self.session.commit()
        return row

    def get(self, prediction_id: int) -> PredictionRow | None:
        return self.session.get(PredictionRow, prediction_id)

    def list_all(self) -> list[PredictionRow]:
        return list(self.session.scalars(select(PredictionRow)))

    def list_open_due(self, now: datetime) -> list[PredictionRow]:
        stmt = select(PredictionRow).where(
            PredictionRow.status == "open",
            PredictionRow.evaluate_at <= now,
        )
        return list(self.session.scalars(stmt))

    def save(self, row: PredictionRow) -> None:
        self.session.add(row)
        self.session.commit()
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `python -m pytest backend/tests/test_repositories.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/investsim/db/repositories.py backend/tests/test_repositories.py
git commit -m "feat(db): repositorios Portfolio y Prediction"
```

---

### Task 5: `PortfolioService` — abrir operación simulada

**Files:**
- Create: `backend/investsim/services/__init__.py`
- Create: `backend/investsim/services/portfolio_service.py`
- Test: `backend/tests/test_portfolio_service.py`

**Interfaces:**
- Consumes: `PortfolioRepository`, `PredictionRepository` (Task 4), `MarketDataProvider` (Task 3), `Direction`, `Horizon` (Task 1), `PredictionRow` (Task 2).
- Produces:
  - `InsufficientFunds(Exception)`.
  - `PortfolioService(portfolio_repo, prediction_repo, market_data, clock)` donde `clock` es un callable `() -> datetime` (por defecto `lambda: datetime.now(timezone.utc)`).
  - Método `open_prediction(symbol: str, amount: float, direction: Direction, confidence: float, horizon: Horizon, rationale: str = "") -> PredictionRow`. Descuenta `amount` del `cash_balance`, fija `entry_price` desde el `Quote`, calcula `shares = amount / entry_price` y `evaluate_at = now + horizon.to_timedelta()`. Lanza `InsufficientFunds` si `amount > cash_balance`.

- [ ] **Step 1: Escribir el test que falla**

Crear `backend/tests/test_portfolio_service.py`:

```python
from datetime import datetime, timezone

import pytest

from investsim.db.base import Base, make_engine, make_session_factory
from investsim.db.repositories import PortfolioRepository, PredictionRepository
from investsim.domain.enums import Direction, Horizon
from investsim.providers.market_data import FakeMarketDataProvider
from investsim.services.portfolio_service import (
    InsufficientFunds,
    PortfolioService,
)

FIXED_NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def _service(cash=100.0, prices=None):
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = make_session_factory(engine)()
    portfolio_repo = PortfolioRepository(session)
    portfolio_repo.create(initial_capital=cash, created_at=FIXED_NOW)
    prediction_repo = PredictionRepository(session)
    market = FakeMarketDataProvider(prices or {"AAPL": 100.0}, as_of=FIXED_NOW)
    service = PortfolioService(
        portfolio_repo, prediction_repo, market, clock=lambda: FIXED_NOW
    )
    return service, portfolio_repo, prediction_repo


def test_open_prediction_records_trade_and_deducts_cash():
    service, portfolio_repo, _ = _service(cash=100.0, prices={"AAPL": 100.0})
    pred = service.open_prediction(
        symbol="AAPL",
        amount=10.0,
        direction=Direction.UP,
        confidence=0.8,
        horizon=Horizon.ONE_WEEK,
        rationale="momentum",
    )
    assert pred.entry_price == 100.0
    assert pred.shares == 0.1
    assert pred.status == "open"
    assert pred.expected_direction == "up"
    assert pred.evaluate_at == datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
    assert portfolio_repo.get().cash_balance == 90.0


def test_open_prediction_insufficient_funds_raises_and_keeps_cash():
    service, portfolio_repo, prediction_repo = _service(cash=5.0)
    with pytest.raises(InsufficientFunds):
        service.open_prediction(
            symbol="AAPL",
            amount=10.0,
            direction=Direction.UP,
            confidence=0.5,
            horizon=Horizon.ONE_DAY,
        )
    assert portfolio_repo.get().cash_balance == 5.0
    assert prediction_repo.list_all() == []
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `python -m pytest backend/tests/test_portfolio_service.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'investsim.services'`.

- [ ] **Step 3: Crear `backend/investsim/services/__init__.py`** (vacío)

- [ ] **Step 4: Implementar `backend/investsim/services/portfolio_service.py`**

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from investsim.db.repositories import PortfolioRepository, PredictionRepository
from investsim.db.tables import PredictionRow
from investsim.domain.enums import Direction, Horizon
from investsim.providers.market_data import MarketDataProvider


class InsufficientFunds(Exception):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PortfolioService:
    def __init__(
        self,
        portfolio_repo: PortfolioRepository,
        prediction_repo: PredictionRepository,
        market_data: MarketDataProvider,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self.portfolio_repo = portfolio_repo
        self.prediction_repo = prediction_repo
        self.market_data = market_data
        self.clock = clock

    def open_prediction(
        self,
        symbol: str,
        amount: float,
        direction: Direction,
        confidence: float,
        horizon: Horizon,
        rationale: str = "",
    ) -> PredictionRow:
        portfolio = self.portfolio_repo.get()
        if portfolio is None:
            raise InsufficientFunds("no portfolio")
        if amount > portfolio.cash_balance:
            raise InsufficientFunds(
                f"amount {amount} > cash {portfolio.cash_balance}"
            )

        quote = self.market_data.get_quote(symbol)
        now = self.clock()
        row = PredictionRow(
            symbol=symbol,
            created_at=now,
            entry_price=quote.price,
            amount=amount,
            shares=amount / quote.price,
            horizon=horizon.value,
            evaluate_at=now + horizon.to_timedelta(),
            expected_direction=direction.value,
            confidence=confidence,
            rationale=rationale,
            status="open",
        )
        portfolio.cash_balance -= amount
        self.portfolio_repo.save(portfolio)
        return self.prediction_repo.add(row)
```

- [ ] **Step 5: Ejecutar el test para verificar que pasa**

Run: `python -m pytest backend/tests/test_portfolio_service.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/investsim/services backend/tests/test_portfolio_service.py
git commit -m "feat(servicios): PortfolioService.open_prediction con capital virtual"
```

---

### Task 6: `SettlementService` — liquidación perezosa y mark-to-market

**Files:**
- Create: `backend/investsim/services/settlement_service.py`
- Test: `backend/tests/test_settlement_service.py`

**Interfaces:**
- Consumes: `PortfolioRepository`, `PredictionRepository` (Task 4), `MarketDataProvider` (Task 3), `PredictionRow` (Task 2).
- Produces:
  - `SettlementService(portfolio_repo, prediction_repo, market_data, clock)` (`clock` como en Task 5).
  - `settle_due() -> list[PredictionRow]`: para cada predicción `open` vencida fija `exit_price`, `final_value = shares * exit_price`, `pnl_pct = (exit_price - entry_price) / entry_price * 100`, `hit = (expected_direction coincide con el movimiento real)`, marca `status = "settled"` y **devuelve** `final_value` al `cash_balance`. Devuelve la lista de predicciones liquidadas.
  - `mark_to_market(prediction: PredictionRow) -> float`: valor actual `shares * precio_actual` **sin persistir**.
  - Regla de acierto: dirección real es `UP` si `exit_price >= entry_price`, si no `DOWN`. `hit` es `True` cuando `expected_direction` coincide con la dirección real.

- [ ] **Step 1: Escribir el test que falla**

Crear `backend/tests/test_settlement_service.py`:

```python
from datetime import datetime, timedelta, timezone

from investsim.db.base import Base, make_engine, make_session_factory
from investsim.db.repositories import PortfolioRepository, PredictionRepository
from investsim.domain.enums import Direction, Horizon
from investsim.providers.market_data import FakeMarketDataProvider
from investsim.services.portfolio_service import PortfolioService
from investsim.services.settlement_service import SettlementService

T0 = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def _setup(cash=100.0, prices=None):
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = make_session_factory(engine)()
    portfolio_repo = PortfolioRepository(session)
    portfolio_repo.create(initial_capital=cash, created_at=T0)
    prediction_repo = PredictionRepository(session)
    market = FakeMarketDataProvider(prices or {"AAPL": 100.0}, as_of=T0)
    return portfolio_repo, prediction_repo, market


def test_settle_due_marks_settled_and_returns_cash_on_gain():
    portfolio_repo, prediction_repo, market = _setup(cash=100.0, prices={"AAPL": 100.0})
    opener = PortfolioService(
        portfolio_repo, prediction_repo, market, clock=lambda: T0
    )
    opener.open_prediction("AAPL", 10.0, Direction.UP, 0.9, Horizon.ONE_WEEK)

    # Una semana despues el precio sube a 134 -> +34%
    market.set_price("AAPL", 134.0)
    later = T0 + timedelta(weeks=1, minutes=1)
    settler = SettlementService(
        portfolio_repo, prediction_repo, market, clock=lambda: later
    )
    settled = settler.settle_due()

    assert len(settled) == 1
    pred = settled[0]
    assert pred.status == "settled"
    assert pred.exit_price == 134.0
    assert round(pred.pnl_pct, 2) == 34.0
    assert round(pred.final_value, 2) == 13.40
    assert pred.hit is True
    # cash: 100 - 10 (abrir) + 13.40 (liquidar)
    assert round(portfolio_repo.get().cash_balance, 2) == 103.40


def test_settle_due_marks_miss_when_direction_wrong():
    portfolio_repo, prediction_repo, market = _setup(prices={"AAPL": 100.0})
    opener = PortfolioService(portfolio_repo, prediction_repo, market, clock=lambda: T0)
    opener.open_prediction("AAPL", 10.0, Direction.UP, 0.6, Horizon.ONE_DAY)

    market.set_price("AAPL", 90.0)  # bajo, pero se predijo UP
    later = T0 + timedelta(days=2)
    settler = SettlementService(portfolio_repo, prediction_repo, market, clock=lambda: later)
    pred = settler.settle_due()[0]
    assert pred.hit is False
    assert round(pred.pnl_pct, 2) == -10.0


def test_settle_due_ignores_not_yet_due():
    portfolio_repo, prediction_repo, market = _setup(prices={"AAPL": 100.0})
    opener = PortfolioService(portfolio_repo, prediction_repo, market, clock=lambda: T0)
    opener.open_prediction("AAPL", 10.0, Direction.UP, 0.6, Horizon.ONE_MONTH)

    later = T0 + timedelta(days=1)  # aun no vence (1M)
    settler = SettlementService(portfolio_repo, prediction_repo, market, clock=lambda: later)
    assert settler.settle_due() == []


def test_mark_to_market_does_not_persist():
    portfolio_repo, prediction_repo, market = _setup(prices={"AAPL": 100.0})
    opener = PortfolioService(portfolio_repo, prediction_repo, market, clock=lambda: T0)
    pred = opener.open_prediction("AAPL", 10.0, Direction.UP, 0.6, Horizon.ONE_WEEK)

    market.set_price("AAPL", 150.0)
    settler = SettlementService(portfolio_repo, prediction_repo, market, clock=lambda: T0)
    value = settler.mark_to_market(pred)
    assert round(value, 2) == 15.0
    assert prediction_repo.get(pred.id).status == "open"  # no tocado
    assert prediction_repo.get(pred.id).final_value is None
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `python -m pytest backend/tests/test_settlement_service.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'investsim.services.settlement_service'`.

- [ ] **Step 3: Implementar `backend/investsim/services/settlement_service.py`**

```python
from __future__ import annotations

from datetime import datetime
from typing import Callable

from investsim.db.repositories import PortfolioRepository, PredictionRepository
from investsim.db.tables import PredictionRow
from investsim.domain.enums import Direction
from investsim.providers.market_data import MarketDataProvider
from investsim.services.portfolio_service import _utcnow


class SettlementService:
    def __init__(
        self,
        portfolio_repo: PortfolioRepository,
        prediction_repo: PredictionRepository,
        market_data: MarketDataProvider,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self.portfolio_repo = portfolio_repo
        self.prediction_repo = prediction_repo
        self.market_data = market_data
        self.clock = clock

    def settle_due(self) -> list[PredictionRow]:
        now = self.clock()
        due = self.prediction_repo.list_open_due(now)
        if not due:
            return []

        portfolio = self.portfolio_repo.get()
        settled: list[PredictionRow] = []
        for pred in due:
            quote = self.market_data.get_quote(pred.symbol)
            pred.exit_price = quote.price
            pred.final_value = pred.shares * quote.price
            pred.pnl_pct = (
                (quote.price - pred.entry_price) / pred.entry_price * 100
            )
            actual = Direction.UP if quote.price >= pred.entry_price else Direction.DOWN
            pred.hit = pred.expected_direction == actual.value
            pred.status = "settled"
            portfolio.cash_balance += pred.final_value
            self.prediction_repo.save(pred)
            settled.append(pred)

        self.portfolio_repo.save(portfolio)
        return settled

    def mark_to_market(self, prediction: PredictionRow) -> float:
        quote = self.market_data.get_quote(prediction.symbol)
        return prediction.shares * quote.price
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `python -m pytest backend/tests/test_settlement_service.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/investsim/services/settlement_service.py backend/tests/test_settlement_service.py
git commit -m "feat(servicios): SettlementService liquidacion perezosa y mark-to-market"
```

---

### Task 7: Métricas acumuladas

**Files:**
- Create: `backend/investsim/metrics.py`
- Test: `backend/tests/test_metrics.py`

**Interfaces:**
- Consumes: `PredictionRow` (Task 2).
- Produces:
  - `Metrics` (dataclass) con `total_predictions:int`, `settled:int`, `hits:int`, `hit_rate_pct:float`, `total_invested:float`, `total_final_value:float`, `total_return_pct:float`.
  - `compute_metrics(predictions: list[PredictionRow]) -> Metrics`. Solo considera predicciones `settled` para acierto y rendimiento. Con cero liquidadas, `hit_rate_pct` y `total_return_pct` son `0.0`.

- [ ] **Step 1: Escribir el test que falla**

Crear `backend/tests/test_metrics.py`:

```python
from datetime import datetime, timezone

from investsim.db.tables import PredictionRow
from investsim.metrics import Metrics, compute_metrics

NOW = datetime(2026, 7, 7, tzinfo=timezone.utc)


def _settled(pnl_pct, hit, amount=10.0):
    final = amount * (1 + pnl_pct / 100)
    return PredictionRow(
        symbol="AAPL", created_at=NOW, entry_price=100.0, amount=amount,
        shares=amount / 100.0, horizon="1W", evaluate_at=NOW,
        expected_direction="up", confidence=0.7, rationale="", status="settled",
        exit_price=100.0 * (1 + pnl_pct / 100), final_value=final,
        pnl_pct=pnl_pct, hit=hit,
    )


def _open():
    return PredictionRow(
        symbol="AAPL", created_at=NOW, entry_price=100.0, amount=10.0,
        shares=0.1, horizon="1W", evaluate_at=NOW, expected_direction="up",
        confidence=0.7, rationale="", status="open",
    )


def test_empty_metrics():
    m = compute_metrics([])
    assert m == Metrics(0, 0, 0, 0.0, 0.0, 0.0, 0.0)


def test_metrics_ignores_open_and_computes_hit_rate_and_return():
    preds = [
        _settled(pnl_pct=34.0, hit=True),    # 10 -> 13.40
        _settled(pnl_pct=-10.0, hit=False),  # 10 -> 9.00
        _open(),                             # se ignora
    ]
    m = compute_metrics(preds)
    assert m.total_predictions == 3
    assert m.settled == 2
    assert m.hits == 1
    assert m.hit_rate_pct == 50.0
    assert round(m.total_invested, 2) == 20.0
    assert round(m.total_final_value, 2) == 22.40
    assert round(m.total_return_pct, 2) == 12.0
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `python -m pytest backend/tests/test_metrics.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'investsim.metrics'`.

- [ ] **Step 3: Implementar `backend/investsim/metrics.py`**

```python
from __future__ import annotations

from dataclasses import dataclass

from investsim.db.tables import PredictionRow


@dataclass(frozen=True)
class Metrics:
    total_predictions: int
    settled: int
    hits: int
    hit_rate_pct: float
    total_invested: float
    total_final_value: float
    total_return_pct: float


def compute_metrics(predictions: list[PredictionRow]) -> Metrics:
    settled = [p for p in predictions if p.status == "settled"]
    hits = sum(1 for p in settled if p.hit)
    hit_rate = (hits / len(settled) * 100) if settled else 0.0
    invested = sum(p.amount for p in settled)
    final_value = sum((p.final_value or 0.0) for p in settled)
    total_return = (
        (final_value - invested) / invested * 100 if invested else 0.0
    )
    return Metrics(
        total_predictions=len(predictions),
        settled=len(settled),
        hits=hits,
        hit_rate_pct=hit_rate,
        total_invested=invested,
        total_final_value=final_value,
        total_return_pct=total_return,
    )
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `python -m pytest backend/tests/test_metrics.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Ejecutar toda la suite de la Fase 1**

Run: `python -m pytest backend/tests -v`
Expected: PASS (todos los tests de las Tareas 1–7).

- [ ] **Step 6: Commit**

```bash
git add backend/investsim/metrics.py backend/tests/test_metrics.py
git commit -m "feat(metricas): tasa de acierto y rendimiento acumulado del agente"
```

---

## Fuera de esta fase (planes futuros)

Cada una tendrá su propio spec/plan cuando lleguemos, siguiendo el orden de construcción del diseño:

- **Fase 2 — Datos reales:** `FinnhubMarketDataProvider` implementando `MarketDataProvider`, con cacheo, backoff y manejo de límites de llamadas.
- **Fase 3 — Agente:** `AgentService` con Claude API, salida JSON validada por schema, persistencia de `MarketSnapshot` y `AgentRun`.
- **Fase 4 — API:** endpoints FastAPI (pedir recomendación, aceptar, dashboard, historial, métricas) que orquestan estos servicios.
- **Fase 5 — Frontend React:** dashboard, historial, métricas y aviso legal.
- **Fase 6 — Pulido:** observabilidad de coste, watchlist configurable.

## Self-Review (hecho)

- **Cobertura del spec (Fase 1):** modelo `Portfolio`/`Prediction` (Tasks 2, 4) ✓; operación simulada de compra con dirección+confianza (Task 5) ✓; liquidación perezosa + mark-to-market (Task 6) ✓; métricas calculadas, no duplicadas (Task 7) ✓; interfaz `MarketDataProvider` desacoplada + fake para testear sin red (Task 3) ✓; SQLite/SQLAlchemy (Task 2) ✓. `MarketSnapshot`/`AgentRun` se difieren a la Fase 3 (los escribe el agente); anotado arriba.
- **Placeholders:** ninguno; cada step lleva código o comando reales.
- **Consistencia de tipos:** `get_quote`, `Quote(symbol, price, as_of)`, `open_prediction(...)`, `settle_due()`, `mark_to_market()`, `compute_metrics()` y los nombres de columnas coinciden entre tareas.
