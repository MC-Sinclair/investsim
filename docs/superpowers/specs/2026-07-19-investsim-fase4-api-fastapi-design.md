# InvestSim — Fase 4: API FastAPI · Diseño

**Fecha:** 2026-07-19
**Estado:** Aprobado (diseño), pendiente de plan de implementación
**Depende de:** Fase 1 (núcleo de dominio + BD), Fase 2 (`FinnhubMarketDataProvider`) y
Fase 3a (`AgentService` + `RuleBasedEngine`), ya integradas en `master`.

## Objetivo

Exponer el bucle central de InvestSim (pedir recomendación → aceptar → liquidar →
métricas) como una API REST con FastAPI, para que exista una superficie HTTP que el
futuro frontend (Fase 5) pueda consumir. Cierra la brecha entre "funciona por pytest y
un smoke manual de consola" y "hay algo que se puede ver y usar".

## Alcance

**Dentro:**
- Cinco endpoints: `POST /recommendations`, `POST /predictions`, `GET /portfolio`,
  `GET /predictions`, `GET /metrics`.
- Bootstrap automático del `Portfolio` (capital inicial configurable) al arrancar la API.
- Liquidación perezosa (`SettlementService.settle_due()`) disparada de forma transparente
  en cada `GET` relevante.
- Mapeo de las excepciones de dominio ya existentes a códigos HTTP.
- CORS habilitado para orígenes de desarrollo local (preparación para Fase 5).
- Tests de los 5 endpoints con `TestClient`, sin red, usando `FakeMarketDataProvider`
  inyectado vía `app.dependency_overrides`.

**Fuera (aplazado):**
- Autenticación / multiusuario (definitivamente fuera, ver CLAUDE.md).
- Reescritura del dominio a async — se mantiene todo síncrono (ver Decisión 1).
- Multi-portfolio, liquidación activa por scheduler, watchlist configurable (Fase 6 o
  futuro).
- Endpoint de inicialización manual del portfolio (se sustituye por bootstrap
  automático).
- `GET /predictions/{id}` u otros endpoints de detalle: no hay consumidor todavía: se
  añaden si Fase 5 los necesita.

## Decisiones tomadas (brainstorming)

### Decisión 1 — Endpoints síncronos, no async

El spec original (`2026-07-07-investsim-design.md`) decía "FastAPI (async)", pero todo el
dominio construido en Fases 1-2 es síncrono: `Session` de SQLAlchemy normal,
`httpx.Client` normal. Reescribir a `AsyncSession`/`httpx.AsyncClient` tocaría fases ya
cerradas y probadas sin aportar nada tangible en una app de un solo usuario local.

**Se opta por:** rutas FastAPI definidas con `def` (no `async def`). FastAPI las ejecuta
automáticamente en un threadpool, así que no bloquean el event loop pese a ser
síncronas. Cero cambios en Fases 1-2.

### Decisión 2 — Bootstrap automático del portfolio

No existe hoy forma de crear un `Portfolio`. Al arrancar la API (evento `lifespan`), si
no existe ningún `PortfolioRow`, se crea uno con capital inicial tomado de la variable de
entorno `INITIAL_CAPITAL` (float, default `1000.0`). Sin endpoint manual de
inicialización — para un solo usuario, un solo portfolio, cero fricción.

### Decisión 3 — Liquidación perezosa en cada GET relevante

`GET /portfolio`, `GET /predictions` y `GET /metrics` llaman a
`SettlementService.settle_due()` antes de construir su respuesta, de forma transparente.
El frontend nunca tiene que acordarse de liquidar explícitamente; siempre ve datos al
día. Coherente con CLAUDE.md: *"Liquidación perezosa al abrir el dashboard"*.

### Decisión 4 — Provider y engine son singletons de la app, la Session es por request

`FinnhubMarketDataProvider` (con su caché TTL de 60s) y `RuleBasedEngine` se instancian
**una sola vez**, al arrancar la app, y se guardan en el estado de la aplicación
(`app.state`). Si se crease una instancia nueva por request, la caché nunca serviría de
nada: cada petición partiría de cero y golpearía Finnhub en cada llamada.

La `Session` de SQLAlchemy, en cambio, **sí es por request** — no es segura para
compartir entre peticiones concurrentes. Se crea con una `sessionmaker` guardada también
en `app.state`, vía una dependencia generadora (`yield session` + cierre en `finally`).

**Riesgo aceptado:** la caché interna de `FinnhubMarketDataProvider` es un `dict` no
protegido por lock. Con tráfico concurrente real esto sería una condición de carrera;
para una app personal de un solo usuario sin ese tráfico, el riesgo es aceptable y no
justifica añadir sincronización.

## Arquitectura

Sigue la Dependency Rule ya establecida. Paquete nuevo `investsim/api/`, mismo rol de
"detalle enchufable" que `providers/`: la API llama a los servicios de dominio
existentes, no los modifica.

```
Frontend (futuro, F5)  ──REST/JSON──►  investsim/api/
                                            │
                        ┌───────────────────┼────────────────────┐
                        ▼                   ▼                    ▼
                 AgentService        PortfolioService     SettlementService
                 (ya existe)          (ya existe)            (ya existe)
                        │                   │                    │
                        └─────────┬─────────┴──────────┬─────────┘
                                  ▼                     ▼
                         MarketDataProvider      Repositorios (SQLAlchemy)
                          (Finnhub, singleton)      (SQLite, Session/request)
```

## Componentes y ficheros

- **`investsim/api/app.py`** — crea la instancia `FastAPI`. `lifespan`: crea el engine
  SQLite (reutilizando `make_engine`/`make_session_factory` de `db/base.py`),
  `Base.metadata.create_all`, bootstrap del portfolio (Decisión 2), instancia el
  `FinnhubMarketDataProvider` y `RuleBasedEngine` como singletons guardados en
  `app.state`. Registra `CORSMiddleware` con
  `allow_origin_regex=r"http://localhost:\d+"` (cualquier puerto de `localhost`, cubre el
  puerto por defecto de Vite —5173— sin tener que fijarlo de antemano).
- **`investsim/api/deps.py`** — dependencias FastAPI (`Depends`):
  - `get_session()`: generador que abre una `Session` desde `app.state.session_factory`
    y la cierra al terminar la request.
  - `get_portfolio_service(session, market_data)`, `get_settlement_service(...)`,
    `get_agent_service(...)`: construyen el servicio de dominio correspondiente a partir
    de la sesión de la request y los singletons de `app.state`.
- **`investsim/api/schemas.py`** — modelos Pydantic de entrada/salida: `RecommendationOut`,
  `OpenPredictionIn`, `PredictionOut`, `PortfolioOut`, `MetricsOut`. El dominio no importa
  Pydantic; estos modelos solo envuelven/proyectan los dataclasses y filas ya existentes.
- **`investsim/api/errors.py`** — un `exception_handler` por tipo de excepción de dominio
  ya existente (`UnknownSymbol`→404, `ProviderUnavailable`→503, `InsufficientFunds`→400),
  registrado sobre la app. Las rutas no llevan try/except propio.
- **`investsim/api/routes.py`** — los 5 endpoints. Cada uno llama a un único método de
  servicio y proyecta el resultado al schema de salida correspondiente.

## Contratos de los endpoints

**`POST /recommendations`**
- Body: `{"symbol": "AAPL"}`
- 200 → `{"symbol", "direction", "confidence", "suggested_amount", "horizon", "rationale"}`
  (campos de `Recommendation`; no se persiste nada)
- 404 si `UnknownSymbol` · 503 si `ProviderUnavailable`

**`POST /predictions`** — acepta la recomendación (importe ya puede venir ajustado)
- Body: `{"symbol", "amount", "direction", "confidence", "horizon", "rationale"}`
  (mismos parámetros que `PortfolioService.open_prediction`)
- 200 → la `Prediction` creada (`id`, `entry_price`, `shares`, `evaluate_at`,
  `status: "open"`, ...)
- 400 si `InsufficientFunds` · 404/503 igual que arriba (abrir también pide cotización)

**`GET /portfolio`** (liquida vencidas antes de responder — Decisión 3)
- 200 → `{"cash_balance", "initial_capital", "open_predictions_value", "total_value"}`
  — `total_value = cash_balance + open_predictions_value` (mark-to-market de las abiertas
  vía `SettlementService.mark_to_market`)

**`GET /predictions`** (liquida vencidas antes de responder)
- 200 → lista de predicciones; cada una con sus campos base
  (`id`, `symbol`, `created_at`, `entry_price`, `amount`, `shares`, `horizon`,
  `evaluate_at`, `expected_direction`, `confidence`, `rationale`, `status`) más
  `exit_price`/`final_value`/`pnl_pct`/`hit` (`null` si sigue abierta) y `current_value`
  (mark-to-market en vivo; `null` si ya está liquidada, porque `final_value` ya cubre eso)

**`GET /metrics`** (liquida vencidas antes de responder)
- 200 → campos de `Metrics` tal cual (`total_predictions`, `settled`, `hits`,
  `hit_rate_pct`, `total_invested`, `total_final_value`, `total_return_pct`)

## Manejo de errores

Las excepciones de dominio ya existen (`UnknownSymbol`, `ProviderUnavailable` de Fase 2;
`InsufficientFunds` de Fase 1) y suben sin capturar desde los servicios, igual que hasta
ahora. La API las traduce a HTTP mediante `exception_handler`s registrados en `app.py`,
sin try/except repetido en cada ruta:

| Excepción de dominio | Código HTTP |
|---|---|
| `UnknownSymbol` | 404 |
| `ProviderUnavailable` | 503 |
| `InsufficientFunds` | 400 |

`MissingApiKey` (falta `FINNHUB_API_KEY`) no se mapea a HTTP: ocurre durante el arranque
de la app (`lifespan`), antes de aceptar ninguna request, y debe hacer fallar el arranque
con un mensaje claro — no un endpoint devolviendo error en cada llamada.

## Estrategia de testing

Sin red: `app.dependency_overrides` sustituye `get_portfolio_service`/
`get_settlement_service`/`get_agent_service` (o directamente el provider/engine que
consumen) por versiones construidas con `FakeMarketDataProvider` y, cuando haga falta un
motor de recomendación determinista y fácil de aserto en tests de la API, un engine fake
con salida fija — sin reimplementar `RuleBasedEngine`, que ya tiene su propia cobertura en
Fase 3a. Sesión de BD también sobreescrita a `sqlite:///:memory:`, recreando tablas en
cada test — mismo aislamiento que ya usan `test_portfolio_service.py`/
`test_settlement_service.py`.

Casos a cubrir por endpoint: flujo feliz de los 5; `UnknownSymbol`→404,
`ProviderUnavailable`→503, `InsufficientFunds`→400; bootstrap automático del portfolio en
el primer arranque; que `GET /portfolio` y `GET /predictions` liquidan vencidas antes de
responder (con reloj inyectado, igual que en los tests de `SettlementService`).

No se añade test de integración nuevo contra Finnhub real: esa cobertura opt-in ya existe
desde Fase 2/3a: la API solo confía en que sus dependencias ya están probadas.

## Integración con el resto del sistema

Esta fase no modifica ningún fichero de dominio de Fases 1-3a (`services/`, `providers/`,
`agent/`, `db/`, `metrics.py`): solo añade el paquete `investsim/api/` por encima, más las
dos dependencias nuevas (`fastapi`, `uvicorn[standard]`) en `pyproject.toml`. `httpx` ya es
dependencia desde Fase 2, así que `fastapi.testclient.TestClient` no requiere ninguna
librería de test adicional.

## Fuera de alcance (Fase 4)

- Autenticación / multiusuario.
- Reescritura async del dominio.
- Multi-portfolio, liquidación activa por scheduler, watchlist configurable.
- Endpoint de inicialización manual del portfolio.
- Endpoints de detalle (`GET /predictions/{id}`) sin consumidor todavía.
- Frontend (Fase 5).
