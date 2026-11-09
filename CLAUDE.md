# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es esto

**InvestSim** — agente de IA que hace predicciones de inversión con **capital virtual** (sin dinero real) y luego compara cada predicción con lo que realmente ocurrió en el mercado. Herramienta **personal de un solo usuario**, para aprender inversión sin riesgo. Mensaje objetivo: *"Si hubieras invertido 10 €, ahora tendrías 13,40 € (+34 %)"*.

## Estado actual (importante)

Fases 1, 2, 3a, 3b, 4 y 5 **implementadas y probadas** (backend: 99 tests; frontend: 42 tests). Siguiente fase planificada: **F6** (pulido). Diseño y plan de cada fase en `docs/superpowers/specs/` y `docs/superpowers/plans/`: el diseño base es `docs/superpowers/specs/2026-07-07-investsim-design.md`.

Cualquier fase nueva sigue el mismo flujo (spec → plan → TDD); no improvises arquitectura por fuera de él. El `README.md` es la cara pública del repo: actualízalo cuando cambien funciones, endpoints o comandos.

## Decisiones de arquitectura (fijadas en brainstorming)

| Tema | v1 | Futuro |
|------|----|--------|
| Cerebro del agente | Agente por reglas determinista (`RuleBasedEngine`) sobre señales intradía | `ClaudeCliEngine`: puente con el CLI de Claude Code (misma interfaz `RecommendationEngine`); Ollama descartado por calidad limitada |
| Activos | Acciones / ETFs | Crypto (Finnhub ya lo soporta) |
| Fuente de datos | Finnhub, tras interfaz `MarketDataProvider` | Más proveedores tras la misma interfaz |
| Predicción | Operación simulada de compra + `direction`/`confidence` para tasa de acierto | Cartera multi-activo |
| Cadencia | Bajo demanda (el usuario la pide) | Scheduler automático |
| Usuarios | Uno solo, local, sin login | **Definitivo** (no habrá multiusuario) |
| BD | SQLite vía SQLAlchemy 2.x | PostgreSQL solo si Docker lo exige |
| Liquidación | Perezosa al abrir el dashboard | Liquidación activa por scheduler |

## Arquitectura (Dependency Rule)

El núcleo de dominio **no depende** de Finnhub, Claude ni FastAPI: son detalles enchufables tras interfaces. Esto permite testear el bucle completo sin red ni coste.

```
Frontend (React)  ──REST──►  API (FastAPI)  ──►  Servicios de dominio
                                                  ├─ AgentService     (datos → reglas → recomendación)
                                                  ├─ PortfolioService (capital virtual, abrir operación)
                                                  └─ SettlementService(liquidación perezosa, mark-to-market)
                                                          │
                                                 ┌────────┴─────────┐
                                                 ▼                  ▼
                                         MarketDataProvider   Repositorios (SQLAlchemy)
                                           (Finnhub)              (SQLite)
```

**Bucle central:** pedir recomendación (agente lee snapshot → propone) → aceptar (descuenta caja virtual, crea `Prediction` `open` con `entry_price`/`shares`/`evaluate_at`) → al abrir el dashboard `SettlementService` liquida las vencidas (calcula `pnl_pct`, `hit`, devuelve `final_value` a la caja) y marca a mercado las abiertas. Las **métricas se calculan** desde `Prediction`, nunca se duplican en BD.

## Layout

- `backend/` — raíz del proyecto Python, paquete `investsim` (dominio, db, providers, agent, services, api, metrics).
- `frontend/` — dashboard React (Vite) que consume la API FastAPI (`investsim/api/`). Ver `frontend/README.md`.
- `docs/superpowers/` — specs y plans. **Fuente de verdad del diseño.**

## Comandos (backend)

Ejecutar desde la **raíz del repo**. El paquete se instala editable, por eso los tests corren con `python -m pytest`.

```bash
pip install -e "backend[dev]"              # instala investsim + sqlalchemy + pytest
python -m pytest backend/tests -v          # toda la suite
python -m pytest backend/tests/test_settlement_service.py -v          # un fichero
python -m pytest backend/tests/test_settlement_service.py::test_mark_to_market_does_not_persist -v   # un solo test
```

Servidor de desarrollo de la API:

```bash
python -m uvicorn investsim.api.app:app --reload   # http://127.0.0.1:8000
```

Motor de recomendación seleccionable con `RECOMMENDATION_ENGINE` (`rules` por defecto, `claude_cli` para el motor LLM — requiere el CLI `claude` instalado y autenticado):

```bash
RECOMMENDATION_ENGINE=claude_cli python -m uvicorn investsim.api.app:app --reload
```

Frontend (desde `frontend/`, con el backend corriendo en paralelo vía uvicorn):

```bash
npm install
npm run dev       # http://localhost:5173 -- IMPORTANTE: no uses 127.0.0.1 (ver frontend/README.md, CORS)
npm test          # suite de Vitest
```

## Convenciones

- Python **3.11+** (se usa sintaxis `X | None`), SQLAlchemy **2.x** (`DeclarativeBase` / `Mapped` / `mapped_column`).
- Enums del dominio se persisten por su **valor string** (`"1D"`, `"up"`, `"open"`).
- Timestamps en **UTC**; el tiempo se inyecta como `clock: Callable[[], datetime]` en los servicios para poder testear el vencimiento de predicciones.
- **Tests del dominio sin red:** se usa `FakeMarketDataProvider`, nunca Finnhub/Claude reales. Los tests de integración con APIs reales van marcados aparte y no corren en el bucle rápido.
- **Aviso legal obligatorio en UI:** *"Simulación educativa, no es asesoramiento financiero. Capital ficticio."* — presente en el dashboard y en cada recomendación.
- Flujo de trabajo del repo: **spec → plan → implementación TDD** (skills `brainstorming` → `writing-plans` → ejecución). Cada fase produce software probado por sí solo; commits frecuentes por tarea.

## Evolución futura (documentar, no construir hasta que se pida)

Fases planificadas tras el núcleo de dominio (Fase 1): **F2** datos reales (Finnhub) · **F3a** agente por reglas (hecho: `RuleBasedEngine` + `AgentService`, sin LLM) · **F3b** motor LLM (hecho: `ClaudeCliEngine`, puente con el CLI de Claude Code — Ollama descartado por calidad limitada) como segunda implementación de `RecommendationEngine` · **F4** API FastAPI (hecho: 5 endpoints REST sobre `AgentService`/`PortfolioService`/`SettlementService`) · **F5** frontend React (hecho: dashboard único con TanStack Query, ver `frontend/README.md`) · **F6** pulido (observabilidad de coste, watchlist). Más adelante: agente híbrido ML+Claude, crypto/multi-activo, scheduler, Docker. Ver la sección "Evolución futura" del spec para el detalle.
