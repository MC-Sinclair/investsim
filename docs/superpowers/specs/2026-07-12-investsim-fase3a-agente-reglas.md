# InvestSim — Fase 3a: Agente por reglas · Diseño

**Fecha:** 2026-07-12
**Estado:** Aprobado (diseño), pendiente de plan de implementación
**Depende de:** Fase 1 (núcleo de dominio + BD) y Fase 2 (`FinnhubMarketDataProvider`), ya integradas en `master`.

## Objetivo

Sustituir el "cerebro" de las predicciones por un **agente por reglas determinista**,
sin LLM, sin red adicional y sin coste. Con esto, el bucle central (abrir → vencer →
liquidar → métricas) queda cerrado de punta a punta **con datos reales** (Finnhub +
reglas), sin depender de una API de Claude que hoy no se tiene ni se quiere pagar.

## Contexto de la decisión

El diseño original preveía Claude API como cerebro. Sin acceso a esa API, se evaluaron
varias vías (LLM local vía Ollama, proveedores gratuitos alternativos, CLI de Claude Code
como subproceso, agente por reglas, aplazar la fase). Se eligió una **estrategia en dos
tiempos**:

- **Fase 3a (este documento):** agente por reglas, ya con datos reales. Desbloquea el
  bucle completo hoy mismo, sin clave de terceros.
- **Fase 3b (futura):** LLM local vía Ollama como segunda implementación de la misma
  interfaz — cambio aditivo, no una reescritura.

Verificación previa relevante: el endpoint de velas históricas de Finnhub
(`/stock/candle`) devuelve `403` en el plan gratuito (confirmado contra la clave real del
proyecto), y las fuentes gratuitas alternativas de histórico multi-día (p. ej. Stooq) se
mostraron frágiles (bloqueo anti-bot verificado en vivo). Por eso las reglas de Fase 3a
se limitan a **señales intradía** (los campos que sí devuelve `/quote` de forma fiable:
`d`, `dp`, `h`, `l`, `o`, `pc`), y el horizonte de toda predicción es **`1D`**. Horizontes
`1W`/`1M` con reglas multi-día se aplazan a cuando exista histórico real (de pago o
acumulado).

## Alcance

**Dentro:**
- Interfaz `RecommendationEngine` (análoga a `MarketDataProvider`) + `RuleBasedEngine`
  como primera implementación.
- `MarketSnapshot`, tipo de dato rico con señales intradía, obtenido vía un método nuevo
  `get_snapshot` en `MarketDataProvider` (no se amplía `Quote`; `get_quote` sigue igual).
- `AgentService`, que orquesta: pide el snapshot → se lo pasa al engine inyectado →
  devuelve la `Recommendation`.
- Tests sin red (fakes) + tests del `get_snapshot` de Finnhub con `httpx.MockTransport`.

**Fuera (aplazado, documentado como futuro):**
- Persistencia de `MarketSnapshot`/`AgentRun` en BD — sin consumidor todavía; se añadirá
  cuando exista un flujo real de aceptación de recomendaciones (Fase 4, API).
- `PriceHistory` acumulado y reglas con horizonte `1W`/`1M` — necesitan histórico
  multi-día que hoy no se puede obtener gratis y de forma fiable.
- Motor LLM local vía Ollama (Fase 3b), como segunda implementación de
  `RecommendationEngine`.
- Cableado a la API/endpoints (Fase 4).

## Decisiones tomadas (brainstorming)

| Tema | Decisión | Notas |
|------|----------|-------|
| Cerebro (interino) | **Agente por reglas determinista** | LLM (Ollama) se añade en Fase 3b, aditivo |
| Snapshot rico | **Método nuevo `get_snapshot`**, `Quote`/`get_quote` intactos | Separa lo que necesita cada consumidor |
| Horizonte | **Siempre `1D`** | Solo hay señal intradía fiable; `1W`/`1M` requieren histórico que no tenemos |
| Señales de las reglas | **Dos: `dp` (dirección/confianza base) + posición en rango del día (confirmación)** | Más matiz que una sola señal, sigue siendo aritmética simple y determinista |
| Importe sugerido | **Escalado por confianza** (`base_amount * confidence`) | Es solo punto de partida; el usuario ajusta antes de aceptar |
| Interfaz del motor | **Definir `RecommendationEngine` ya** (no esperar a Fase 3b) | El swap reglas→LLM ya está planeado, no es hipotético |
| Persistencia (`MarketSnapshot`/`AgentRun`) | **Aplazada** | Sin consumidor en esta fase; se añade con la API (Fase 4) |
| `PriceHistory` | **Aplazada** | Sin consumidor hasta que existan reglas multi-día |

## Arquitectura

Sigue la Dependency Rule ya establecida: el motor de reglas no conoce Finnhub ni BD;
recibe un `MarketSnapshot` (dato de dominio) y devuelve una `Recommendation` (dato de
dominio).

```
AgentService.propose(symbol)
        │
        ├─► MarketDataProvider.get_snapshot(symbol) -> MarketSnapshot   (Finnhub o Fake)
        │
        └─► RecommendationEngine.propose(snapshot) -> Recommendation    (RuleBasedEngine hoy, Ollama mañana)
```

## Componentes y ficheros

- **`investsim/providers/market_data.py`** (se amplía, sin romper lo existente):
  - `MarketSnapshot` (dataclass frozen): `symbol: str`, `price: float`,
    `day_change_pct: float` (`dp`), `day_high: float` (`h`), `day_low: float` (`l`),
    `day_open: float` (`o`), `prev_close: float` (`pc`), `as_of: datetime`.
  - `MarketDataProvider` (Protocol) gana `get_snapshot(symbol: str) -> MarketSnapshot`.
    `get_quote` y `Quote` **no cambian**.
  - `FakeMarketDataProvider` aprende a devolver snapshots configurables por símbolo
    (además de los precios simples que ya maneja para `get_quote`).
- **`investsim/providers/finnhub.py`**: `FinnhubMarketDataProvider.get_snapshot`
  reutiliza la misma llamada a `/quote` que ya usa `get_quote` (el JSON ya trae
  `d`/`dp`/`h`/`l`/`o`/`pc`) — no hay endpoint nuevo que integrar, solo parseo adicional.
  Comparte la caché TTL y el backoff ya existentes.
- **`investsim/agent/__init__.py`**, **`investsim/agent/engine.py`** (paquete nuevo,
  mismo rol que `providers/`: detalle enchufable):
  - `Recommendation` (dataclass frozen): `symbol: str`, `direction: Direction`,
    `confidence: float`, `suggested_amount: float`, `horizon: Horizon`,
    `rationale: str`.
  - `RecommendationEngine` (Protocol): `propose(snapshot: MarketSnapshot) -> Recommendation`.
- **`investsim/agent/rules.py`**: `RuleBasedEngine`, implementación concreta de Fase 3a
  (ver lógica más abajo).
- **`investsim/services/agent_service.py`**: `AgentService(market_data, engine)` con
  `propose(symbol: str) -> Recommendation`, junto a `PortfolioService`/
  `SettlementService`.

## Lógica de las reglas (`RuleBasedEngine`)

**Señal 1 — dirección y confianza base, desde `dp` (% de cambio del día):**
- `direction = UP` si `dp >= 0`, si no `DOWN`. (`dp == 0`: se trata como `UP` con
  confianza mínima — "sin movimiento" es evidencia débil, no ausencia de recomendación.)
- `base_confidence = min(abs(dp) / 3.0, 1.0)` — un movimiento del ±3% satura la
  confianza de esta señal a 1.0.

**Señal 2 — confirmación por posición en el rango del día:**
- `range_position = (price - day_low) / (day_high - day_low)`, con `range_position = 0.5`
  (neutral) si `day_high == day_low` (sin rango, evita división por cero).
- Si `direction == UP`: `confirmation = range_position` (cerca del máximo refuerza la
  subida).
- Si `direction == DOWN`: `confirmation = 1 - range_position` (cerca del mínimo refuerza
  la bajada).

**Combinación:**
- `confidence = clamp(base_confidence * (0.5 + confirmation / 2), 0.05, 0.95)` — la
  confirmación escala la confianza entre la mitad y el 100% de la base; nunca se satura
  a 0 o 1 exactos.

**Importe sugerido:**
- `suggested_amount = 20.0 * confidence` (constante `base_amount = 20.0€`, ajustable).

**Horizonte:** siempre `Horizon.ONE_DAY`.

**Rationale (texto generado):** combina ambas señales, p. ej.: *"AAPL sube 1.24% hoy y
cotiza cerca de máximos del rango diario."*

Estas constantes (`3.0`, `0.5`/`0.5`, `20.0`, límites `0.05`/`0.95`) son una primera
versión razonable — viven solo dentro de `RuleBasedEngine`, así que ajustarlas después no
afecta a nada más del sistema.

## Manejo de errores

`AgentService.propose` no atrapa nada: si `MarketDataProvider.get_snapshot` lanza
`UnknownSymbol` o `ProviderUnavailable`, la excepción sube tal cual — no se genera
ninguna `Recommendation` a medias. Coherente con la regla ya establecida en Fase 2: *"si
falla el dato, no hay operación"*.

## Estrategia de testing

Todo el dominio (`RuleBasedEngine`, `AgentService`) se testea **sin red**, con
`FakeMarketDataProvider` devolviendo `MarketSnapshot` configurados a medida — mismo
patrón que `PortfolioService`/`SettlementService` en Fase 1. Casos a cubrir:

- Dirección `UP`/`DOWN` según signo de `dp`.
- Confianza reforzada cuando la posición en el rango confirma la dirección, atenuada
  cuando la contradice.
- Empate `dp == 0`.
- Caso límite `day_high == day_low` (sin rango).
- `suggested_amount` proporcional a la confianza calculada.
- Propagación de `UnknownSymbol`/`ProviderUnavailable` desde el provider, sin generar
  `Recommendation`.

`FinnhubMarketDataProvider.get_snapshot` se testea con `httpx.MockTransport`,
reutilizando la infraestructura de caché/backoff ya probada en Fase 2.

## Integración con el resto del sistema

`AgentService` queda listo para ser invocado desde la futura capa de API (Fase 4): el
usuario pide una recomendación → `AgentService.propose(symbol)` → se muestra la
`Recommendation` como propuesta → si el usuario acepta (ajustando el importe si quiere),
se llama a `PortfolioService.open_prediction(...)` con esos datos, tal como ya funciona
desde la Fase 1. `AgentService` no persiste nada por sí mismo.

## Evolución futura (documentar, no construir ahora)

- **Fase 3b — motor LLM local (Ollama):** segunda implementación de
  `RecommendationEngine`, sin tocar `AgentService` ni el resto del sistema.
- **`PriceHistory`:** tabla de cotizaciones acumuladas, sembrada a partir de cada
  `get_quote`/`get_snapshot`, para alimentar reglas o modelos con horizonte multi-día.
- **Horizontes `1W`/`1M` con reglas reales:** una vez exista histórico fiable (de pago o
  acumulado).
- **Persistencia de `MarketSnapshot`/`AgentRun`:** cuando la capa de API (Fase 4)
  necesite trazabilidad de qué vio el agente en cada `Prediction` aceptada.

## Fuera de alcance (Fase 3a)

- Motor LLM (Fase 3b).
- `PriceHistory`, reglas multi-día, horizontes `1W`/`1M`.
- Persistencia de snapshot/traza del agente.
- Cableado de la API/endpoints (Fase 4).
