# InvestSim

> Agente de IA que hace predicciones de inversión con **capital virtual** y después las
> contrasta con lo que de verdad hizo el mercado.

*"Si hubieras invertido 10 €, ahora tendrías 13,40 € (+34 %)."* Esa es la pregunta que
responde InvestSim: aprender a invertir viendo aciertos y fallos reales, sin arriesgar
dinero.

> ⚠️ Simulación educativa, no es asesoramiento financiero. Capital ficticio.

---

## Qué hace

1. **Pides una recomendación** para un activo (acciones o ETFs) indicando su símbolo.
2. **El agente lee el mercado** —cotización e indicadores intradía reales de
   [Finnhub](https://finnhub.io)— y propone una operación: dirección (`up`/`down`),
   confianza, importe, horizonte (`1D`, `1W`, `1M`) y una explicación de por qué.
3. **La aceptas**: se descuenta de tu caja virtual y queda abierta una predicción con su
   precio de entrada y su fecha de evaluación.
4. **Al abrir el dashboard**, las predicciones vencidas se liquidan contra el precio real
   (rentabilidad, acierto/fallo, devolución a caja) y las abiertas se valoran a mercado.
5. **Las métricas** —tasa de acierto y rendimiento acumulado del agente— se calculan
   siempre a partir de las predicciones, nunca se guardan duplicadas.

## Dos cerebros intercambiables

El agente tiene una interfaz única, `RecommendationEngine`, con dos implementaciones que
se eligen con la variable `RECOMMENDATION_ENGINE`:

| Motor | Valor | Cómo decide |
|---|---|---|
| `RuleBasedEngine` | `rules` (por defecto) | Determinista: variación del día y posición del precio dentro del rango diario. Explica cada recomendación en lenguaje natural. |
| `ClaudeCliEngine` | `claude_cli` | Razona con un LLM a través de un puente con el CLI de Claude Code. Si el CLI falla, la API responde `503` con un error claro. |

## Arquitectura

El núcleo de dominio **no depende** de Finnhub, Claude ni FastAPI: son detalles
enchufables detrás de interfaces (*Dependency Rule*). Por eso el bucle completo se puede
testear sin red y sin coste.

```
Frontend (React)  ──REST──►  API (FastAPI)  ──►  Servicios de dominio
                                                  ├─ AgentService      (datos → motor → recomendación)
                                                  ├─ PortfolioService  (capital virtual, abrir operación)
                                                  └─ SettlementService (liquidación perezosa, mark-to-market)
                                                          │
                                                 ┌────────┴─────────┐
                                                 ▼                  ▼
                                         MarketDataProvider   Repositorios (SQLAlchemy)
                                           (Finnhub)              (SQLite)
```

- **`MarketDataProvider`**: Finnhub en producción y un *fake* en los tests. El
  proveedor real incluye caché con TTL y reintentos con *backoff* ante `429`/`5xx`/fallos
  de red (un `401` no se reintenta).
- **Tiempo inyectado** (`clock`) en los servicios, para testear el vencimiento de
  predicciones sin esperar días.
- **Timestamps en UTC** de extremo a extremo; el frontend normaliza fechas *naive* y *aware*.

## Stack

**Backend:** Python 3.11+, FastAPI, SQLAlchemy 2.x, SQLite, httpx, pytest
**Frontend:** React 19, TypeScript, Vite, TanStack Query, Vitest + Testing Library

## API

| Método | Ruta | Qué hace |
|---|---|---|
| `POST` | `/recommendations` | Pide al agente una recomendación para un símbolo |
| `POST` | `/predictions` | Acepta una recomendación y abre la operación simulada |
| `GET` | `/portfolio` | Caja, valor a mercado de las operaciones abiertas y total de la cartera virtual |
| `GET` | `/predictions` | Lista las predicciones (abiertas y liquidadas) |
| `GET` | `/metrics` | Tasa de acierto y rendimiento acumulado |

Con el servidor en marcha, la documentación interactiva está en `http://127.0.0.1:8000/docs`.

## Puesta en marcha

Necesitas una clave gratuita de Finnhub: <https://finnhub.io/register>.

```bash
# 1. Backend (desde la raíz del repo)
cp .env.example .env                 # y pon tu FINNHUB_API_KEY
pip install -e "backend[dev]"
python -m uvicorn investsim.api.app:app --reload     # http://127.0.0.1:8000

# 2. Frontend (en otra terminal)
cd frontend
npm install
npm run dev                          # abre http://localhost:5173 (no 127.0.0.1, por CORS)
```

Variables opcionales del backend: `RECOMMENDATION_ENGINE` (`rules` | `claude_cli`),
`INITIAL_CAPITAL` (por defecto `1000`), `DATABASE_URL` (por defecto `sqlite:///investsim.db`).
El motor `claude_cli` requiere el CLI `claude` instalado y autenticado.

## Tests

```bash
python -m pytest backend/tests        # backend: 99 tests, sin red
cd frontend && npm test               # frontend: 42 tests, fetch mockeado
```

Los tests de integración contra Finnhub y el CLI de Claude reales están marcados como
`integration` y quedan fuera del ciclo rápido. Se lanzan a propósito con
`python -m pytest backend/tests -m integration` y se saltan solos si falta la clave o el CLI.

## Cómo se construyó

Por fases, cada una con su diseño y su plan en [`docs/superpowers/`](docs/superpowers/)
y desarrollada con TDD:

| Fase | Contenido |
|---|---|
| 1 | Núcleo de dominio y base de datos: cartera virtual, predicciones, liquidación, métricas |
| 2 | Datos reales con Finnhub (caché, reintentos, taxonomía de errores) |
| 3a | Agente por reglas sobre señales intradía |
| 3b | Motor LLM mediante puente con el CLI de Claude Code |
| 4 | API REST con FastAPI |
| 5 | Dashboard en React |

**Próximos pasos:** observabilidad del coste del motor LLM, *watchlist*, *scheduler* de
liquidación automática, crypto y cartera multi-activo.

## Licencia

[MIT](LICENSE)
