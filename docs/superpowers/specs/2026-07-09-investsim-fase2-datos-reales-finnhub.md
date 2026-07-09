# InvestSim — Fase 2: Datos reales (Finnhub) · Diseño

**Fecha:** 2026-07-09
**Estado:** Aprobado (diseño), pendiente de plan de implementación
**Depende de:** Fase 1 (núcleo de dominio + BD), ya integrada en `master`.

## Objetivo

Sustituir el proveedor de datos *fake* por datos de mercado **reales** de Finnhub,
implementando la interfaz `MarketDataProvider` que ya validó la Fase 1. Con esto, el
bucle central (abrir → vencer → liquidar → métricas) funciona igual pero con precios
reales, sin tocar el dominio ni los servicios ya probados.

## Alcance (decisión: opción A, estricta)

**Dentro:** `FinnhubMarketDataProvider` que cumple **exactamente** la interfaz actual
(`get_quote(symbol) -> Quote`), con caché corta, backoff ante límites/caídas y manejo de
errores. Configuración de la API key. Tests sin red + un test de integración real marcado
aparte.

**Fuera (se difiere a la Fase 3):** snapshot de mercado rico (variación, máx/mín,
indicadores, noticias). Esa forma la define el agente cuando exista, para no adivinarla
ahora. La interfaz `MarketDataProvider` **no se amplía** en esta fase.

## Principio rector

Fiel al orden de construcción del diseño global: "datos reales tras la interfaz que ya
validamos". La Fase 2 es **aditiva**: añade un detalle enchufable (Finnhub) detrás de una
frontera existente. El resto del sistema no se entera del cambio salvo por qué
implementación de `MarketDataProvider` se le inyecta.

## Decisiones tomadas (brainstorming)

| Tema | Decisión | Notas |
|------|----------|-------|
| Alcance | **A — estricta**: solo `get_quote` real | Snapshot rico → Fase 3 |
| Cliente HTTP | **httpx** (síncrono ahora) | httpx soporta async → facilita Fase 4 (FastAPI) sin cambiar de librería |
| API key | **`.env` + python-dotenv** | `.env` gitignored; `.env.example` commiteado como plantilla |
| TTL de caché | **60 s** | Cotización por símbolo cada minuto como máximo |
| Rate limiting | **Reactivo (429 + backoff), sin limiter proactivo** | YAGNI para un solo usuario bajo demanda (~60 llamadas/min de sobra) |
| Reintentos | **Backoff exponencial, 3 intentos (0,5 → 1 → 2 s)** | `sleep` inyectable para no esperar en tests |

## Componentes y ficheros

- **`investsim/config.py`** — carga `.env` con python-dotenv y expone la configuración.
  - `FinnhubConfig` (dataclass frozen): `api_key: str`, `base_url: str`
    (`"https://finnhub.io/api/v1"`), `timeout: float` (p. ej. 10.0 s),
    `ttl: timedelta` (60 s), `max_retries: int` (3).
  - `load_finnhub_config() -> FinnhubConfig`: lee `FINNHUB_API_KEY` del entorno; si
    falta, lanza un error claro (`MissingApiKey`) indicando cómo configurarla.
- **`investsim/providers/finnhub.py`** — `FinnhubMarketDataProvider`, implementa
  `MarketDataProvider.get_quote` con datos reales, caché y backoff.
- **`investsim/providers/market_data.py`** (existente, se amplía la taxonomía de errores):
  - `MarketDataError(Exception)` — base nueva.
  - `UnknownSymbol(MarketDataError)` — pasa a heredar de la base (era `Exception`).
  - `ProviderUnavailable(MarketDataError)` — Finnhub caído tras agotar reintentos.
  - `Quote` y el `Protocol` `MarketDataProvider` **no cambian**.
- **`.env.example`** — plantilla commiteada con `FINNHUB_API_KEY=`. **`.env`** real
  queda gitignored (ya cubierto por `.gitignore` si añadimos el patrón `.env`).

## Cómo funciona `get_quote(symbol)`

1. **Caché (in-memory):** `dict[str, tuple[Quote, datetime]]`. Si existe una entrada del
   símbolo con antigüedad `now - fetched_at < ttl` (reloj `clock: Callable[[], datetime]`
   inyectable, igual patrón que la Fase 1), la devuelve **sin llamar a red**.
2. **Llamada HTTP:** `GET {base_url}/quote?symbol={SYM}&token={api_key}` vía httpx con
   `timeout`. Respuesta JSON relevante: `c` (precio actual), `t` (timestamp unix en
   segundos). → `Quote(symbol=SYM, price=c, as_of=datetime.fromtimestamp(t, tz=UTC))`.
3. **Símbolo desconocido:** Finnhub responde `c == 0` y `t == 0` para símbolos inválidos
   → lanza `UnknownSymbol(symbol)`.
4. Guarda la `Quote` en caché con `fetched_at = now` y la devuelve.

## Backoff y manejo de errores

- **Reintentos con backoff exponencial** (`max_retries` intentos; esperas 0,5 → 1 → 2 s)
  ante:
  - **HTTP 429** (límite de llamadas).
  - **HTTP 5xx** y **errores de red/timeout** (`httpx.HTTPError`).
  - El `sleep: Callable[[float], None]` es inyectable (por defecto `time.sleep`) para que
    los tests no esperen de verdad.
- **Reintentos agotados** → `ProviderUnavailable` con mensaje claro. **No se crea nada a
  medias** (encaja con el manejo de errores del diseño global: si falla el dato, no hay
  operación).
- **4xx que no sea 429** (p. ej. **401** API key inválida) → error inmediato y explícito
  (`ProviderUnavailable` con el código), **sin** reintentar.
- **`c == 0`** → `UnknownSymbol` (no es un fallo de red, no se reintenta).

## Estrategia de testing

- **Unitarios sin red** (`backend/tests/test_finnhub_provider.py`) con
  `httpx.MockTransport` (se inyecta un `httpx.Client` con transporte simulado):
  - Parseo correcto: JSON `{c, t, ...}` → `Quote` con precio y `as_of` esperados.
  - **Símbolo desconocido:** `c == 0` → `UnknownSymbol`.
  - **Caché:** dos llamadas seguidas dentro del TTL producen **una sola** petición HTTP;
    pasado el TTL (avanzando el `clock`), se vuelve a pedir.
  - **Reintento:** primera respuesta 429, segunda 200 → devuelve la `Quote` (y usó
    `sleep`).
  - **Agotados:** 429/5xx repetidos → `ProviderUnavailable`.
  - **API key mala:** 401 → `ProviderUnavailable` sin reintentar.
- **Integración real** (`backend/tests/integration/test_finnhub_integration.py`, marcador
  `integration`): una llamada real a Finnhub para un símbolo conocido (p. ej. `AAPL`).
  **Se salta** (`pytest.mark.skipif`) si no hay `FINNHUB_API_KEY` en el entorno. El bucle
  rápido lo excluye por defecto (config de pytest: `-m "not integration"`).
- El resto de la suite de la Fase 1 **sigue igual y verde**: los servicios se testean con
  el fake; nada del dominio cambia.

## Dependencias

Añadir a `backend/pyproject.toml` (`[project].dependencies`):

- `httpx` — cliente HTTP.
- `python-dotenv` — carga de `.env`.

Registrar el marcador `integration` en la config de pytest y excluirlo del run por
defecto.

## Integración con el resto del sistema

- En **producción** (a partir de la Fase 4, API), a los servicios `PortfolioService` y
  `SettlementService` se les inyectará `FinnhubMarketDataProvider` en lugar de
  `FakeMarketDataProvider`. La construcción/cableado concreto (dónde se instancia el
  provider real) se define cuando exista la capa de aplicación; en la Fase 2 basta con
  que el provider real exista, cumpla la interfaz y esté probado.

## Fuera de alcance (Fase 2)

- Ampliar la interfaz con snapshot rico (Fase 3, con el agente).
- Rate-limiter proactivo (contar llamadas por minuto).
- Persistir cotizaciones o históricos en BD.
- Otros proveedores o crypto (evolución futura, tras la misma interfaz).
- Cableado de la app / endpoints (Fase 4).
