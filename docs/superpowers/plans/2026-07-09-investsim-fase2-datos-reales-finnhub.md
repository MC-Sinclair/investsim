# InvestSim — Fase 2: Datos reales (Finnhub) · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar `FinnhubMarketDataProvider`, que cumple la interfaz `MarketDataProvider.get_quote` de la Fase 1 con datos reales de Finnhub, con caché corta, backoff ante límites/caídas y configuración de la API key vía `.env`.

**Architecture:** Detalle enchufable tras una frontera existente (Dependency Rule). El provider real no cambia el dominio ni los servicios: solo añade una implementación de la interfaz que ya se validó con el *fake*. HTTP con httpx; los tests unitarios usan `httpx.MockTransport` (sin red) y la integración real va marcada aparte.

**Tech Stack:** Python 3.11+, httpx, python-dotenv, pytest (`httpx.MockTransport` para simular respuestas).

## Global Constraints

- Python **3.11 o superior** (sintaxis `X | None`).
- Alcance **A (estricto)**: solo se implementa `get_quote`. La interfaz `MarketDataProvider` y el dataclass `Quote` **no se amplían**.
- Cliente HTTP: **httpx** (uso síncrono en esta fase).
- API key: **`.env` + python-dotenv**; variable `FINNHUB_API_KEY`. `.env` gitignored, `.env.example` commiteado.
- TTL de caché por defecto: **60 s**. Reloj inyectable como `clock: Callable[[], datetime]` (mismo patrón que la Fase 1).
- Reintentos: **backoff exponencial, 3 intentos por defecto (esperas 0,5 → 1 → 2 s)**. `sleep` inyectable (`Callable[[float], None]`, por defecto `time.sleep`) para no esperar en tests.
- Timestamps en **UTC**. Precios en `float`.
- Endpoint Finnhub: `GET {base_url}/quote?symbol={SYM}&token={api_key}`, `base_url = "https://finnhub.io/api/v1"`. Respuesta: `c` (precio actual), `t` (unix segundos). `c == 0` ⇒ símbolo desconocido.
- Todos los comandos se ejecutan desde la **raíz del repo**. El intérprete se invoca con la ruta real de Python (en la máquina de desarrollo `C:\Users\marcos\AppData\Local\Programs\Python\Python312\python.exe`); en el plan se escribe `python` por brevedad.
- Sin red en el bucle rápido: los tests unitarios usan `httpx.MockTransport`. El test de integración lleva el marcador `integration` y se excluye por defecto.

---

### Task 1: Dependencias, secretos y marcador de pytest

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `.gitignore`
- Create: `.env.example`

**Interfaces:**
- Consumes: nada.
- Produces: `httpx` y `python-dotenv` instalables; marcador pytest `integration` registrado y excluido por defecto; plantilla `.env.example`.

- [ ] **Step 1: Añadir dependencias en `backend/pyproject.toml`**

Reemplazar el bloque `dependencies` para que quede así:

```toml
dependencies = [
    "sqlalchemy>=2.0,<3.0",
    "httpx>=0.27",
    "python-dotenv>=1.0",
]
```

- [ ] **Step 2: Registrar el marcador `integration` y excluirlo por defecto**

Añadir al final de `backend/pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "integration: tests que hacen llamadas reales a APIs externas (se excluyen por defecto)",
]
addopts = "-m 'not integration'"
```

- [ ] **Step 3: Ignorar `.env` en `.gitignore`**

Añadir estas líneas al final de `.gitignore`:

```gitignore
# Secretos
.env
```

- [ ] **Step 4: Crear la plantilla `.env.example`**

```dotenv
# Copia este fichero a .env y rellena tu clave de Finnhub (plan gratuito).
# Obtén una en https://finnhub.io/register
FINNHUB_API_KEY=
```

- [ ] **Step 5: Instalar las nuevas dependencias**

Run: `python -m pip install -e "backend[dev]"`
Expected: instala `httpx` y `python-dotenv` (además de lo ya presente) sin errores.

- [ ] **Step 6: Verificar que la exclusión del marcador funciona**

Run: `python -m pytest backend/tests -q`
Expected: PASS (los 19 tests de la Fase 1 siguen verdes; no hay tests `integration` todavía).

- [ ] **Step 7: Commit**

```bash
git add backend/pyproject.toml .gitignore .env.example
git commit -m "chore(fase2): deps httpx/python-dotenv, marcador integration y .env"
```

---

### Task 2: Taxonomía de errores del proveedor

**Files:**
- Modify: `backend/investsim/providers/market_data.py`
- Test: `backend/tests/test_market_data_errors.py`

**Interfaces:**
- Consumes: `UnknownSymbol` (Fase 1, actualmente hereda de `Exception`).
- Produces:
  - `MarketDataError(Exception)` — base de todos los errores del proveedor.
  - `UnknownSymbol(MarketDataError)` — símbolo sin datos (pasa a heredar de la base).
  - `ProviderUnavailable(MarketDataError)` — proveedor caído / no recuperable.

- [ ] **Step 1: Escribir el test que falla**

Crear `backend/tests/test_market_data_errors.py`:

```python
from investsim.providers.market_data import (
    MarketDataError,
    ProviderUnavailable,
    UnknownSymbol,
)


def test_unknown_symbol_is_market_data_error():
    assert issubclass(UnknownSymbol, MarketDataError)


def test_provider_unavailable_is_market_data_error():
    assert issubclass(ProviderUnavailable, MarketDataError)


def test_errors_are_distinct():
    assert UnknownSymbol is not ProviderUnavailable
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `python -m pytest backend/tests/test_market_data_errors.py -v`
Expected: FAIL con `ImportError: cannot import name 'MarketDataError'`.

- [ ] **Step 3: Ampliar la taxonomía en `market_data.py`**

En `backend/investsim/providers/market_data.py`, sustituir la definición actual de
`UnknownSymbol` (`class UnknownSymbol(Exception): pass`) por:

```python
class MarketDataError(Exception):
    pass


class UnknownSymbol(MarketDataError):
    pass


class ProviderUnavailable(MarketDataError):
    pass
```

(El resto del fichero —`Quote`, `MarketDataProvider`, `FakeMarketDataProvider`— no se toca.)

- [ ] **Step 4: Ejecutar los tests para verificar que pasan**

Run: `python -m pytest backend/tests/test_market_data_errors.py backend/tests/test_fake_market_data.py -v`
Expected: PASS (los 3 nuevos + los 3 de `FakeMarketDataProvider`, que siguen funcionando porque `UnknownSymbol` sigue existiendo).

- [ ] **Step 5: Commit**

```bash
git add backend/investsim/providers/market_data.py backend/tests/test_market_data_errors.py
git commit -m "feat(providers): taxonomia de errores MarketDataError/ProviderUnavailable"
```

---

### Task 3: Configuración de Finnhub (`config.py`)

**Files:**
- Create: `backend/investsim/config.py`
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Consumes: nada del dominio.
- Produces:
  - `MissingApiKey(Exception)`.
  - `FinnhubConfig` (dataclass frozen): `api_key: str`, `base_url: str = "https://finnhub.io/api/v1"`, `timeout: float = 10.0`, `ttl: timedelta = timedelta(seconds=60)`, `max_retries: int = 3`.
  - `load_finnhub_config(env: Mapping[str, str] | None = None) -> FinnhubConfig`: si `env` es `None`, carga `.env` (python-dotenv) y usa `os.environ`; lee `FINNHUB_API_KEY`; si falta o está vacía, lanza `MissingApiKey` con mensaje claro.

- [ ] **Step 1: Escribir el test que falla**

Crear `backend/tests/test_config.py`:

```python
from datetime import timedelta

import pytest

from investsim.config import FinnhubConfig, MissingApiKey, load_finnhub_config


def test_load_from_explicit_env():
    cfg = load_finnhub_config({"FINNHUB_API_KEY": "abc123"})
    assert cfg.api_key == "abc123"
    assert cfg.base_url == "https://finnhub.io/api/v1"
    assert cfg.ttl == timedelta(seconds=60)
    assert cfg.max_retries == 3


def test_missing_api_key_raises():
    with pytest.raises(MissingApiKey):
        load_finnhub_config({})


def test_empty_api_key_raises():
    with pytest.raises(MissingApiKey):
        load_finnhub_config({"FINNHUB_API_KEY": ""})


def test_defaults_are_sensible():
    cfg = FinnhubConfig(api_key="x")
    assert cfg.timeout == 10.0
    assert cfg.max_retries == 3
    assert cfg.ttl == timedelta(seconds=60)
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `python -m pytest backend/tests/test_config.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'investsim.config'`.

- [ ] **Step 3: Implementar `backend/investsim/config.py`**

```python
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Mapping

from dotenv import load_dotenv


class MissingApiKey(Exception):
    pass


@dataclass(frozen=True)
class FinnhubConfig:
    api_key: str
    base_url: str = "https://finnhub.io/api/v1"
    timeout: float = 10.0
    ttl: timedelta = field(default_factory=lambda: timedelta(seconds=60))
    max_retries: int = 3


def load_finnhub_config(
    env: Mapping[str, str] | None = None,
) -> FinnhubConfig:
    if env is None:
        load_dotenv()
        env = os.environ
    api_key = env.get("FINNHUB_API_KEY", "").strip()
    if not api_key:
        raise MissingApiKey(
            "Falta FINNHUB_API_KEY. Copia .env.example a .env y pon tu clave "
            "de Finnhub (https://finnhub.io/register)."
        )
    return FinnhubConfig(api_key=api_key)
```

- [ ] **Step 4: Ejecutar los tests para verificar que pasan**

Run: `python -m pytest backend/tests/test_config.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/investsim/config.py backend/tests/test_config.py
git commit -m "feat(config): FinnhubConfig y carga de .env con python-dotenv"
```

---

### Task 4: `FinnhubMarketDataProvider` — parseo de cotización y símbolo desconocido

**Files:**
- Create: `backend/investsim/providers/finnhub.py`
- Test: `backend/tests/test_finnhub_provider.py`

**Interfaces:**
- Consumes: `Quote`, `UnknownSymbol` (Fase 1 / Task 2), `FinnhubConfig` (Task 3).
- Produces:
  - `FinnhubMarketDataProvider(config: FinnhubConfig, client: httpx.Client | None = None, clock: Callable[[], datetime] = _utcnow, sleep: Callable[[float], None] = time.sleep)`.
    - Si `client` es `None`, crea `httpx.Client(base_url=config.base_url, timeout=config.timeout)`.
  - `get_quote(symbol: str) -> Quote`: llama a `/quote`, mapea `c`→`price`, `t`→`as_of` (UTC). `c == 0` ⇒ `UnknownSymbol`.

**Nota de testing:** los tests inyectan un `httpx.Client` construido con `httpx.MockTransport`, de modo que **no hay red**. El handler del transporte inspecciona `request.url.params["symbol"]` y devuelve un `httpx.Response` simulado.

- [ ] **Step 1: Escribir el test que falla**

Crear `backend/tests/test_finnhub_provider.py`:

```python
from datetime import datetime, timezone

import httpx
import pytest

from investsim.config import FinnhubConfig
from investsim.providers.finnhub import FinnhubMarketDataProvider
from investsim.providers.market_data import UnknownSymbol


def _client(handler) -> httpx.Client:
    return httpx.Client(
        base_url="https://finnhub.io/api/v1",
        transport=httpx.MockTransport(handler),
    )


def _cfg() -> FinnhubConfig:
    return FinnhubConfig(api_key="testkey")


def test_get_quote_parses_price_and_timestamp():
    ts = 1_752_000_000  # unix segundos

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["symbol"] == "AAPL"
        assert request.url.params["token"] == "testkey"
        return httpx.Response(200, json={"c": 134.0, "t": ts})

    provider = FinnhubMarketDataProvider(_cfg(), client=_client(handler))
    quote = provider.get_quote("AAPL")

    assert quote.symbol == "AAPL"
    assert quote.price == 134.0
    assert quote.as_of == datetime.fromtimestamp(ts, tz=timezone.utc)


def test_unknown_symbol_when_price_zero():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"c": 0, "t": 0})

    provider = FinnhubMarketDataProvider(_cfg(), client=_client(handler))
    with pytest.raises(UnknownSymbol):
        provider.get_quote("NOPE")
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `python -m pytest backend/tests/test_finnhub_provider.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'investsim.providers.finnhub'`.

- [ ] **Step 3: Implementar la primera versión de `finnhub.py`**

```python
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable

import httpx

from investsim.config import FinnhubConfig
from investsim.providers.market_data import (
    Quote,
    UnknownSymbol,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FinnhubMarketDataProvider:
    def __init__(
        self,
        config: FinnhubConfig,
        client: httpx.Client | None = None,
        clock: Callable[[], datetime] = _utcnow,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self.client = client or httpx.Client(
            base_url=config.base_url, timeout=config.timeout
        )
        self.clock = clock
        self.sleep = sleep

    def get_quote(self, symbol: str) -> Quote:
        response = self.client.get(
            "/quote", params={"symbol": symbol, "token": self.config.api_key}
        )
        data = response.json()
        price = data.get("c", 0)
        if price == 0:
            raise UnknownSymbol(symbol)
        as_of = datetime.fromtimestamp(data["t"], tz=timezone.utc)
        return Quote(symbol=symbol, price=float(price), as_of=as_of)
```

- [ ] **Step 4: Ejecutar los tests para verificar que pasan**

Run: `python -m pytest backend/tests/test_finnhub_provider.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/investsim/providers/finnhub.py backend/tests/test_finnhub_provider.py
git commit -m "feat(finnhub): FinnhubMarketDataProvider.get_quote (parseo + simbolo desconocido)"
```

---

### Task 5: Caché con TTL

**Files:**
- Modify: `backend/investsim/providers/finnhub.py`
- Test: `backend/tests/test_finnhub_provider.py` (añadir tests)

**Interfaces:**
- Consumes: `FinnhubMarketDataProvider` (Task 4), `clock` inyectable.
- Produces: `get_quote` cachea por símbolo durante `config.ttl`; dentro del TTL no hace petición HTTP; pasado el TTL vuelve a pedir.

- [ ] **Step 1: Añadir los tests que fallan**

Añadir a `backend/tests/test_finnhub_provider.py`:

```python
from datetime import timedelta


class _CountingHandler:
    """Cuenta cuántas peticiones HTTP se hacen y siempre devuelve el mismo precio."""

    def __init__(self, price: float = 100.0, ts: int = 1_752_000_000) -> None:
        self.calls = 0
        self.price = price
        self.ts = ts

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        return httpx.Response(200, json={"c": self.price, "t": self.ts})


def test_cache_avoids_second_http_call_within_ttl():
    handler = _CountingHandler()
    now = [datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc)]
    provider = FinnhubMarketDataProvider(
        _cfg(), client=_client(handler), clock=lambda: now[0]
    )

    provider.get_quote("AAPL")
    now[0] += timedelta(seconds=30)  # dentro del TTL (60s)
    provider.get_quote("AAPL")

    assert handler.calls == 1


def test_cache_refetches_after_ttl_expires():
    handler = _CountingHandler()
    now = [datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc)]
    provider = FinnhubMarketDataProvider(
        _cfg(), client=_client(handler), clock=lambda: now[0]
    )

    provider.get_quote("AAPL")
    now[0] += timedelta(seconds=61)  # pasado el TTL (60s)
    provider.get_quote("AAPL")

    assert handler.calls == 2
```

- [ ] **Step 2: Ejecutar los tests para verificar que fallan**

Run: `python -m pytest backend/tests/test_finnhub_provider.py -k cache -v`
Expected: FAIL — `test_cache_avoids_second_http_call_within_ttl` obtiene `handler.calls == 2` (aún no hay caché).

- [ ] **Step 3: Añadir la caché a `finnhub.py`**

En `FinnhubMarketDataProvider.__init__`, añadir el almacén de caché (al final del cuerpo del `__init__`):

```python
        self._cache: dict[str, tuple[Quote, datetime]] = {}
```

Reescribir `get_quote` para consultar/rellenar la caché:

```python
    def get_quote(self, symbol: str) -> Quote:
        now = self.clock()
        cached = self._cache.get(symbol)
        if cached is not None:
            quote, fetched_at = cached
            if now - fetched_at < self.config.ttl:
                return quote

        response = self.client.get(
            "/quote", params={"symbol": symbol, "token": self.config.api_key}
        )
        data = response.json()
        price = data.get("c", 0)
        if price == 0:
            raise UnknownSymbol(symbol)
        as_of = datetime.fromtimestamp(data["t"], tz=timezone.utc)
        quote = Quote(symbol=symbol, price=float(price), as_of=as_of)
        self._cache[symbol] = (quote, now)
        return quote
```

- [ ] **Step 4: Ejecutar los tests para verificar que pasan**

Run: `python -m pytest backend/tests/test_finnhub_provider.py -v`
Expected: PASS (los 2 de Task 4 + los 2 de caché).

- [ ] **Step 5: Commit**

```bash
git add backend/investsim/providers/finnhub.py backend/tests/test_finnhub_provider.py
git commit -m "feat(finnhub): cache de cotizaciones con TTL"
```

---

### Task 6: Backoff y reintentos ante 429 / 5xx / red

**Files:**
- Modify: `backend/investsim/providers/finnhub.py`
- Test: `backend/tests/test_finnhub_provider.py` (añadir tests)

**Interfaces:**
- Consumes: `FinnhubMarketDataProvider` (Task 5), `sleep` inyectable, `ProviderUnavailable` (Task 2), `config.max_retries`.
- Produces:
  - `get_quote` reintenta ante HTTP 429, HTTP 5xx y `httpx.HTTPError` (red/timeout) con backoff exponencial (`0.5 * 2**intento`), hasta `config.max_retries` intentos totales.
  - Reintentos agotados ⇒ `ProviderUnavailable`.
  - HTTP 4xx distinto de 429 (p. ej. 401) ⇒ `ProviderUnavailable` inmediato, sin reintentar.

- [ ] **Step 1: Añadir los tests que fallan**

Añadir a `backend/tests/test_finnhub_provider.py`:

```python
from investsim.providers.market_data import ProviderUnavailable


def test_retries_on_429_then_succeeds():
    responses = [
        httpx.Response(429, json={}),
        httpx.Response(200, json={"c": 120.0, "t": 1_752_000_000}),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return responses.pop(0)

    slept: list[float] = []
    provider = FinnhubMarketDataProvider(
        _cfg(), client=_client(handler), sleep=slept.append
    )
    quote = provider.get_quote("AAPL")

    assert quote.price == 120.0
    assert slept == [0.5]  # esperó una vez antes del reintento con éxito


def test_raises_provider_unavailable_after_exhausting_retries():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={})

    slept: list[float] = []
    provider = FinnhubMarketDataProvider(
        _cfg(), client=_client(handler), sleep=slept.append
    )
    with pytest.raises(ProviderUnavailable):
        provider.get_quote("AAPL")

    assert slept == [0.5, 1.0]  # 3 intentos => 2 esperas entre ellos


def test_client_error_401_does_not_retry():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(401, json={})

    slept: list[float] = []
    provider = FinnhubMarketDataProvider(
        _cfg(), client=_client(handler), sleep=slept.append
    )
    with pytest.raises(ProviderUnavailable):
        provider.get_quote("AAPL")

    assert calls["n"] == 1  # una sola petición, sin reintentos
    assert slept == []
```

- [ ] **Step 2: Ejecutar los tests para verificar que fallan**

Run: `python -m pytest backend/tests/test_finnhub_provider.py -k "retries or provider_unavailable or 401" -v`
Expected: FAIL (aún no hay lógica de reintentos; p. ej. `test_retries_on_429_then_succeeds` intenta parsear `{}` como cotización).

- [ ] **Step 3: Extraer la petición con reintentos en `finnhub.py`**

Añadir el import de `ProviderUnavailable` (junto a los imports de `market_data`):

```python
from investsim.providers.market_data import (
    ProviderUnavailable,
    Quote,
    UnknownSymbol,
)
```

Añadir un método privado `_fetch_quote_data` que hace la petición con backoff, y hacer que `get_quote` lo use en lugar de llamar a `self.client.get` directamente:

```python
    def _fetch_quote_data(self, symbol: str) -> dict:
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries):
            try:
                response = self.client.get(
                    "/quote",
                    params={"symbol": symbol, "token": self.config.api_key},
                )
            except httpx.HTTPError as exc:  # red / timeout
                last_error = exc
            else:
                if response.status_code == 200:
                    return response.json()
                if response.status_code == 429 or response.status_code >= 500:
                    last_error = ProviderUnavailable(
                        f"Finnhub HTTP {response.status_code}"
                    )
                else:  # 4xx que no es 429 (p. ej. 401): no reintentar
                    raise ProviderUnavailable(
                        f"Finnhub HTTP {response.status_code} para {symbol}"
                    )

            if attempt < self.config.max_retries - 1:
                self.sleep(0.5 * 2**attempt)

        raise ProviderUnavailable(
            f"Finnhub no disponible tras {self.config.max_retries} intentos"
        ) from last_error
```

Y en `get_quote`, sustituir el bloque que hacía `response = self.client.get(...)` y
`data = response.json()` por:

```python
        data = self._fetch_quote_data(symbol)
```

(El resto de `get_quote` —consulta de caché arriba, chequeo `price == 0`, construcción del
`Quote` y guardado en caché— no cambia.)

- [ ] **Step 4: Ejecutar toda la suite del provider para verificar que pasa**

Run: `python -m pytest backend/tests/test_finnhub_provider.py -v`
Expected: PASS (parseo, símbolo desconocido, 2 de caché, 2 de reintentos, 1 de 401).

- [ ] **Step 5: Commit**

```bash
git add backend/investsim/providers/finnhub.py backend/tests/test_finnhub_provider.py
git commit -m "feat(finnhub): backoff y reintentos ante 429/5xx/red; 401 sin reintento"
```

---

### Task 7: Test de integración real (marcado, opt-in)

**Files:**
- Create: `backend/tests/integration/__init__.py`
- Create: `backend/tests/integration/test_finnhub_integration.py`

**Interfaces:**
- Consumes: `load_finnhub_config`, `FinnhubMarketDataProvider`, `Quote`.
- Produces: un test marcado `integration` que hace una llamada real a Finnhub y se salta si no hay `FINNHUB_API_KEY`.

- [ ] **Step 1: Crear el paquete de integración**

Crear `backend/tests/integration/__init__.py` (vacío).

- [ ] **Step 2: Escribir el test de integración**

Crear `backend/tests/integration/test_finnhub_integration.py`:

```python
import os

import pytest

from investsim.config import load_finnhub_config
from investsim.providers.finnhub import FinnhubMarketDataProvider
from investsim.providers.market_data import Quote

pytestmark = pytest.mark.integration

_HAS_KEY = bool(os.environ.get("FINNHUB_API_KEY", "").strip())


@pytest.mark.skipif(not _HAS_KEY, reason="requiere FINNHUB_API_KEY en el entorno")
def test_real_quote_for_known_symbol():
    provider = FinnhubMarketDataProvider(load_finnhub_config())
    quote = provider.get_quote("AAPL")

    assert isinstance(quote, Quote)
    assert quote.symbol == "AAPL"
    assert quote.price > 0
```

- [ ] **Step 3: Verificar que se excluye del bucle rápido**

Run: `python -m pytest backend/tests -q`
Expected: PASS; el resumen indica algún test **deselected** (el de integración), porque `addopts = -m 'not integration'` lo excluye. No se hace ninguna llamada de red.

- [ ] **Step 4: (Opcional, manual) Ejecutar la integración real**

Solo si hay `.env` con `FINNHUB_API_KEY` válida:
Run: `python -m pytest backend/tests/integration -m integration -v`
Expected: PASS (una llamada real a Finnhub para `AAPL`). Sin clave, el test se **salta**.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/integration
git commit -m "test(finnhub): integracion real marcada (opt-in, skip sin API key)"
```

---

### Task 8: Suite completa y cierre de fase

**Files:**
- (ninguno nuevo)

- [ ] **Step 1: Ejecutar toda la suite rápida**

Run: `python -m pytest backend/tests -v`
Expected: PASS. Tests de la Fase 1 (19) + Fase 2 (errores, config, provider: parseo, símbolo desconocido, caché ×2, reintentos ×2, 401) verdes; el de integración aparece como deselected.

- [ ] **Step 2: Ejecutar el smoke test del bucle (regresión de la Fase 1)**

Run: `python backend/examples/smoke_loop.py`
Expected: imprime el flujo completo con el mensaje "Si hubieras invertido 10 EUR, ahora tendrias 13.40 EUR (+34%)". (Sigue usando el *fake*; confirma que no rompimos nada del dominio.)

- [ ] **Step 3: Commit (si hubo algún ajuste)**

Si todo estaba verde sin cambios, no hay nada que commitear. Si hubo ajustes menores:

```bash
git add -A
git commit -m "chore(fase2): cierre - suite completa verde"
```

---

## Fuera de esta fase (planes futuros)

- **Fase 3 — Agente:** `AgentService` con Claude API, salida JSON validada por schema, y aquí se decidirá si la interfaz necesita un `get_snapshot` rico (variación, máx/mín, indicadores, noticias) además de `get_quote`. Persistencia de `MarketSnapshot` y `AgentRun`.
- **Fase 4 — API:** endpoints FastAPI que cablean `FinnhubMarketDataProvider` real a los servicios.
- **Fase 5 — Frontend React.**
- **Fase 6 — Pulido:** observabilidad de coste, watchlist.

## Self-Review (hecho)

- **Cobertura del spec:** deps httpx/python-dotenv + marcador integration + `.env` (Task 1) ✓; taxonomía `MarketDataError`/`ProviderUnavailable`, `UnknownSymbol` reparentada (Task 2) ✓; `FinnhubConfig` + carga `.env` + `MissingApiKey` (Task 3) ✓; `get_quote` real con parseo `c`/`t` y `c==0`⇒`UnknownSymbol` (Task 4) ✓; caché TTL 60 s con reloj inyectable (Task 5) ✓; backoff 3 intentos 0,5→1→2 s ante 429/5xx/red, 401 sin reintento, agotados⇒`ProviderUnavailable` (Task 6) ✓; integración real marcada y opt-in, excluida del bucle rápido (Task 7) ✓; interfaz `MarketDataProvider`/`Quote` sin cambios (alcance A) ✓.
- **Placeholders:** ninguno; cada step lleva código o comando reales.
- **Consistencia de tipos:** `FinnhubConfig(api_key, base_url, timeout, ttl, max_retries)`, `FinnhubMarketDataProvider(config, client, clock, sleep)`, `get_quote(symbol) -> Quote`, `load_finnhub_config(env)`, y los errores `MarketDataError`/`UnknownSymbol`/`ProviderUnavailable` coinciden entre tareas y con la Fase 1. El backoff usa `0.5 * 2**attempt`, coherente con los tests (`[0.5]`, `[0.5, 1.0]`).
