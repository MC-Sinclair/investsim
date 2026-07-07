# InvestSim — Agente de inversión simulada · Diseño

**Fecha:** 2026-07-07
**Estado:** Aprobado (diseño), pendiente de plan de implementación

## Objetivo

App con un agente de IA que sigue el mercado, hace predicciones de inversión con
**capital virtual** (sin dinero real) y después compara cada predicción con lo que
realmente ocurrió. Objetivo: aprender a entender mercados e inversión sin riesgo, y
evaluar cuán fiable sería seguir al agente.

Mensaje objetivo para el usuario: *"Si hubieras invertido 10 €, ahora tendrías 13,40 € (+34 %)"*.

## Principio rector

**v1 sencilla, con las costuras preparadas para crecer.** Se construye lo mínimo para
validar el bucle central cuanto antes, pero las fronteras (proveedor de datos, cliente
del agente, repositorios) se aíslan tras interfaces para que la evolución futura sea
**aditiva, no una reescritura**. Uso **personal, un solo usuario** — sin autenticación.

## Decisiones tomadas (brainstorming)

| Tema | Decisión v1 | Notas / futuro |
|------|-------------|----------------|
| Alcance | Producto completo, pero el bucle central primero | — |
| Cerebro del agente | **Claude API (LLM)** razonando sobre un snapshot de mercado | Futuro: **híbrido ML + Claude** |
| Activos | **Acciones / ETFs** | Futuro: **crypto** (Finnhub ya lo soporta) |
| Fuente de datos | **Finnhub** (plan gratuito ~60 llamadas/min) | Tras interfaz `MarketDataProvider` |
| Forma de la predicción | **Operación simulada de compra** (+ dirección y confianza para tasa de acierto) | Futuro: cartera multi-activo |
| Cadencia | **Bajo demanda** (el usuario la pide) | Futuro: scheduler automático |
| Usuarios | **Un solo usuario, local, sin login** | Definitivo |
| Base de datos | **SQLite** vía SQLAlchemy | Migrar a PostgreSQL **solo** si Docker lo requiere |
| Liquidación | **Perezosa** al abrir el dashboard | Futuro: liquidación activa por scheduler |

## Stack

- **Backend / agente:** Python + **FastAPI** (async; expone REST para el frontend).
- **Agente:** cliente **Claude API** (`claude-sonnet-5`); recibe snapshot de mercado y
  devuelve una recomendación estructurada en JSON validado por schema.
- **Datos de mercado:** **Finnhub**, encapsulado tras una interfaz `MarketDataProvider`.
- **BD:** **SQLite** vía SQLAlchemy (ORM permite migrar de proveedor sin reescribir dominio).
- **Frontend:** **React** (Vite) — dashboard, historial y métricas acumuladas.

## Arquitectura (Dependency Rule)

```
Frontend (React)
      │  REST/JSON
      ▼
API (FastAPI)  ──►  Servicios de dominio
                     ├─ AgentService     (orquesta datos → Claude → recomendación)
                     ├─ PortfolioService (capital virtual, abrir operación)
                     └─ SettlementService(liquidación perezosa, mark-to-market)
                              │
                     ┌────────┴─────────┐
                     ▼                  ▼
             MarketDataProvider   Repositorios (SQLAlchemy)
               (Finnhub)              (SQLite)
```

El núcleo de dominio (Prediction, Portfolio, lógica de liquidación y métricas) **no
depende** de Finnhub, Claude ni FastAPI: son detalles enchufables detrás de interfaces.
Esto permite testear el bucle completo sin red ni coste, usando *fakes*.

## Modelo de datos

**`Portfolio`** — el capital virtual (en v1 hay uno solo)
- `id`, `cash_balance`, `initial_capital`, `created_at`

**`Prediction`** — cada recomendación del agente (la "operación simulada")
- `id`, `symbol`, `created_at`
- `entry_price`, `amount` (€ virtuales), `shares` (= amount / entry_price)
- `horizon` (`1D` / `1W` / `1M`), `evaluate_at`
- `expected_direction` (`up` / `down`), `confidence` (0–1)
- `rationale` (texto de Claude)
- `status` (`open` / `settled`)
- `exit_price`, `final_value`, `pnl_pct`, `hit` (se rellenan al liquidar)

**`MarketSnapshot`** — datos que vio el agente al decidir
- `id`, `prediction_id`, `raw_json`
- Auditoría/depuración; futuro: alimentar el enfoque híbrido ML.

**`AgentRun`** — traza de cada invocación a Claude
- `id`, `prompt`, `response`, `model`, `tokens`, `created_at`, `latency_ms`
- Observabilidad y control de coste.

Las **métricas acumuladas** (tasa de acierto, rendimiento total, "si hubieras
invertido X…") se **calculan** a partir de `Prediction`; no se almacenan duplicadas.

## Flujo del bucle central

**A) Pedir recomendación (bajo demanda)**
1. Usuario pulsa "Pedir recomendación" (símbolo concreto o elección del agente sobre una
   watchlist configurable).
2. `AgentService` pide a `MarketDataProvider` (Finnhub) un snapshot: precio actual,
   variación, máx/mín, indicadores básicos y quizá noticias.
3. Se construye el prompt y se llama a Claude → **JSON estructurado**: `symbol`,
   `direction`, `confidence`, `suggested_amount`, `horizon`, `rationale`.
4. Se valida la respuesta (schema). Se muestra como *propuesta* (aún no ejecutada).

**B) Aceptar la operación**
5. Usuario confirma (ajusta importe si quiere). `PortfolioService` comprueba
   `cash_balance` suficiente, descuenta el importe y crea la `Prediction`
   (`status=open`) con `entry_price`, `shares`, `evaluate_at`. Se guardan
   `MarketSnapshot` y `AgentRun`.

**C) Liquidación perezosa (al abrir el dashboard)**
6. `SettlementService` busca predicciones `open` con `evaluate_at <= now`. Para cada una
   pide el precio actual, calcula `exit_price`, `final_value`, `pnl_pct`, `hit`, marca
   `status=settled` y **devuelve el efectivo** (`final_value`) al `cash_balance`.
7. Para las `open` no vencidas, calcula valor *mark-to-market* al vuelo (no se persiste)
   para mostrar "valor actual" en el dashboard.

## Manejo de errores

- **Finnhub caído / límite de llamadas:** reintentos con backoff; si falla, error claro y
  **no** se crea operación a medias. Cacheo corto de cotizaciones para no gastar llamadas.
- **Claude devuelve JSON inválido:** un reintento con instrucción de corrección; si vuelve
  a fallar, se informa sin crear predicción.
- **Símbolo sin datos / mercado cerrado:** se usa el último precio disponible, marcando la
  hora del dato; se avisa en la UI.
- **Aviso legal:** banner permanente *"Simulación educativa, no es asesoramiento
  financiero. Capital ficticio."* en la UI y en cada recomendación.

## Estrategia de testing

- **Dominio con fakes:** `MarketDataProvider` y cliente Claude falsos → el bucle completo
  (abrir → vencer → liquidar → métricas) se testea sin red ni coste.
- **Integración (marcados aparte):** tests reales contra Finnhub/Claude, ejecutados bajo
  demanda, no en el bucle rápido.

## Orden de construcción

1. **Núcleo de dominio + BD:** entidades, repositorios SQLAlchemy, `PortfolioService` y
   `SettlementService` con fakes. Tests del bucle completo. Sin red.
2. **Capa de datos real:** `MarketDataProvider` con Finnhub (cacheo, backoff, límites).
3. **Agente:** `AgentService` con Claude API, salida JSON validada,
   `AgentRun`/`MarketSnapshot`.
4. **API FastAPI:** endpoints (pedir recomendación, aceptar, dashboard, historial,
   métricas).
5. **Frontend React:** dashboard, historial, métricas, aviso legal.
6. **Pulido:** observabilidad de coste, watchlist configurable.

Cada paso es entregable y testeable por sí mismo.

## Evolución futura (documentar, no construir ahora)

- **Agente híbrido ML + Claude:** señales de indicadores/modelo interpretadas por Claude;
  `MarketSnapshot` ya guarda los datos para entrenar.
- **Multi-activo:** añadir crypto (Finnhub lo soporta) y más proveedores tras
  `MarketDataProvider`.
- **Automatización:** scheduler para predicciones programadas y liquidación activa (en vez
  de perezosa).
- **Cartera recomendada:** repartir capital entre varios activos.
- **Docker:** compose multi-servicio (frontend + backend + BD) cuando madure; en ese caso
  se valoraría PostgreSQL.

## Fuera de alcance (v1)

- Multiusuario / autenticación (uso personal, definitivo).
- Dinero real o integración con brókers.
- Crypto, cartera multi-activo, scheduler, Docker (ver evolución futura).
