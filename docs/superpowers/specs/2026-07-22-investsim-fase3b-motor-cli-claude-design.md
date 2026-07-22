# InvestSim — Fase 3b: Motor LLM vía puente con el CLI de Claude Code — Diseño

**Estado:** Aprobado. Precede al plan de implementación TDD.

## Contexto

`AgentService` (Fase 3a) orquesta datos de mercado → motor de recomendación, a través de la interfaz `RecommendationEngine`:

```python
class RecommendationEngine(Protocol):
    def propose(self, snapshot: MarketSnapshot) -> Recommendation: ...
```

Hoy la única implementación es `RuleBasedEngine` (reglas deterministas sobre `dp` y posición en el rango diario, sin LLM, sin coste, ver `docs/superpowers/specs/2026-07-12-investsim-fase3a-agente-reglas.md`). El diseño original de InvestSim contemplaba Claude API o Ollama local como alternativas — ambas descartadas: la API por coste, Ollama por calidad limitada de un modelo pequeño local.

Durante el brainstorming de esta fase surgió una tercera opción no evaluada hasta ahora: usar el **CLI de Claude Code** (`claude`), ya instalado y autenticado en la máquina del usuario vía suscripción de pago (no API key), como motor de recomendación invocado por subproceso desde Python.

## Viabilidad verificada empíricamente

Antes de diseñar, se probó en vivo `claude -p --output-format json --json-schema '...'` contra la cuenta real del usuario. Hallazgos que fijan las decisiones de este diseño:

- **Sin coste adicional de dinero.** La cuenta usa `billingType: "stripe_subscription"` (verificado en `~/.claude/.claude.json` → `oauthAccount`), sin `ANTHROPIC_API_KEY` en el entorno. Las llamadas consumen la cuota de la suscripción, no facturación por token.
- **`--json-schema` funciona:** devuelve un campo `structured_output` con el JSON ya validado contra el schema pedido, sin necesidad de parsear texto libre.
- **Latencia real, no despreciable:** 10-14s como mínimo incluso en el caso más favorable (modelo Haiku, directorio sin contexto de proyecto). Muy por encima de las reglas deterministas (~100ms) o de lo típico en Ollama local (~1-3s).
- **El directorio de trabajo importa muchísimo:** invocar el comando dentro del repo del proyecto (con `CLAUDE.md` presente) disparó carga de contexto adicional y más turnos, subiendo la latencia a ~28s — el doble, sin ningún beneficio para esta tarea. Invocarlo desde un directorio neutro (sin `CLAUDE.md`) evita esa sobrecarga.
- **`--bare` no sirve para este caso:** fuerza autenticación estricta por `ANTHROPIC_API_KEY` (nunca lee la sesión OAuth de la suscripción) — usarlo rompería justo la ventaja de no pagar aparte.
- **Cuota compartida:** cada llamada consume la misma cuota de uso que el resto de tu actividad en Claude Code (programar, este propio asistente, etc.). No es un recurso ilimitado ni aislado.

## Alcance

- Nueva implementación `ClaudeCliEngine` de `RecommendationEngine`, en `investsim/agent/claude_cli.py`.
- Selección de motor en la API vía variable de entorno `RECOMMENDATION_ENGINE` (`rules` por defecto, `claude_cli` para activar este motor).
- Fuera de alcance: cambios en `AgentService`, en la API pública (`RecommendationOut` no cambia de forma), en el frontend (consume la misma respuesta, no necesita saber qué motor la generó), en Ollama (descartado, no se retoma en esta fase), y en el histórico multi-día (`horizon` sigue fijo en `1D`, misma limitación de datos que Fase 3a).

## Arquitectura

```
investsim/agent/
├── engine.py       (ya existe: Recommendation, RecommendationEngine — sin tocar)
├── rules.py        (ya existe: RuleBasedEngine — sin tocar)
├── claude_cli.py   (nuevo: ClaudeCliEngine, ClaudeCliConfig, excepciones)
```

`ClaudeCliEngine` implementa el mismo método `propose(self, snapshot: MarketSnapshot) -> Recommendation` que `RuleBasedEngine`. Al ser `RecommendationEngine` un `Protocol` (structural typing, ya verificado por el test `test_engine_protocol_is_structural` de Fase 3a), **`AgentService` no requiere ningún cambio**: cualquier objeto con ese método encaja.

En `investsim/api/app.py`, el `lifespan` decide qué motor instanciar:

```python
engine_name = os.environ.get("RECOMMENDATION_ENGINE", "rules")
app.state.engine = ClaudeCliEngine() if engine_name == "claude_cli" else RuleBasedEngine()
```

El resto de la API (`routes.py`, `schemas.py`, `deps.py`, tests existentes) no cambia — `RecommendationOut` tiene la misma forma independientemente del motor que la generó.

## El puente CLI

**Comando invocado vía `subprocess.run`:**

```
claude -p --output-format json --model claude-haiku-4-5 \
  --json-schema '{"type":"object","properties":{"direction":{"type":"string","enum":["up","down"]},"confidence":{"type":"number","minimum":0,"maximum":1},"rationale":{"type":"string"}},"required":["direction","confidence","rationale"]}' \
  '<prompt con los datos del snapshot>'
```

- `timeout=60.0` (segundos) pasado a `subprocess.run` — margen amplio sobre los 10-14s observados, aceptable porque es una llamada bajo demanda (el usuario ya espera activamente su recomendación), no un bucle ni un scheduler.
- **`cwd` fijado a `tempfile.gettempdir()`** — directorio neutro sin `CLAUDE.md` ni contexto de proyecto, evitando la sobrecarga de latencia verificada arriba. Nunca se invoca con `cwd` igual a la raíz del repo.
- `capture_output=True, text=True` para leer stdout como texto y parsearlo como JSON.
- La respuesta exitosa es un JSON de nivel superior con un campo `structured_output` (dict ya validado contra el schema) y un campo `is_error` (bool). Se usa `structured_output` directamente — no se reparsea `result` como texto libre.

**Prompt** (plantilla en español, con los campos crudos del `MarketSnapshot`, sin reducirlos antes a una fórmula — se aprovecha que un LLM puede razonar directamente sobre los números):

```python
def _build_prompt(snapshot: MarketSnapshot) -> str:
    return (
        "Eres un analista financiero educativo. Dato de mercado: "
        f"simbolo {snapshot.symbol}, precio {snapshot.price}, "
        f"cambio del dia {snapshot.day_change_pct:+.2f}%, "
        f"maximo del dia {snapshot.day_high}, minimo del dia {snapshot.day_low}, "
        f"apertura {snapshot.day_open}, cierre anterior {snapshot.prev_close}. "
        "Da una recomendacion de direccion (up/down) a 1 dia vista, "
        "con confianza 0-1 y una frase de motivo en espanol."
    )
```

**Mapeo de la respuesta a `Recommendation`:**

| Campo de `Recommendation` | Origen |
|---|---|
| `symbol` | `snapshot.symbol` (nunca del LLM — evita que invente o altere el símbolo) |
| `direction` | `structured_output["direction"]`, convertido a `Direction` |
| `confidence` | `structured_output["confidence"]`, tal cual (el schema ya acota 0-1) |
| `rationale` | `structured_output["rationale"]`, tal cual |
| `suggested_amount` | `base_amount * confidence` — **mismo cálculo que `RuleBasedEngine`**, no lo decide el LLM |
| `horizon` | fijo `Horizon.ONE_DAY` — misma limitación de datos que Fase 3a (sin histórico multi-día de Finnhub gratuito) |

## Manejo de errores

Tres excepciones nuevas en `investsim/agent/claude_cli.py`, ninguna atrapada dentro de `ClaudeCliEngine` ni de `AgentService` (mismo principio que las excepciones de `MarketDataProvider`: suben tal cual hasta la API):

- **`ClaudeCliUnavailable`** — el binario `claude` no está en el PATH (`FileNotFoundError` al invocar `subprocess.run`), o el CLI responde indicando que no hay sesión autenticada.
- **`ClaudeCliTimeout`** — `subprocess.TimeoutExpired` al superar los 60s.
- **`InvalidClaudeCliResponse`** — el subproceso devuelve `is_error: true`, stdout no es JSON válido, o el JSON no trae `structured_output` con las claves esperadas.

En `investsim/api/errors.py`, las tres se mapean a **503** (mismo tratamiento que `ProviderUnavailable`: "inténtalo más tarde", el motor de recomendación no está disponible ahora mismo).

## Configuración

`ClaudeCliConfig` — dataclass simple, sin credenciales que gestionar (la autenticación la resuelve la sesión de `claude` ya logueada en la máquina, no hay API key que cargar de `.env`):

```python
@dataclass(frozen=True)
class ClaudeCliConfig:
    model: str = "claude-haiku-4-5"
    timeout_seconds: float = 60.0
    base_amount: float = 20.0
```

No requiere `load_claude_cli_config()` ni variables de entorno propias — se instancia con los defaults salvo que se necesite ajustar en tests.

**Selección de motor en la API:** variable de entorno `RECOMMENDATION_ENGINE` (`rules` por defecto, `claude_cli` para activar este motor), leída en el `lifespan` de `investsim/api/app.py` — mismo patrón que `DATABASE_URL`/`INITIAL_CAPITAL`.

## Estrategia de testing

Mismo patrón que ya se sigue con Finnhub: tests rápidos sin red/subproceso real + un test de integración real, opt-in, aparte.

- **Tests rápidos:** se sustituye `subprocess.run` (vía monkeypatch/mock) por una respuesta controlada — un `subprocess.CompletedProcess` fabricado con el `stdout` que produciría el CLI real. Cubren:
  - Mapeo correcto de una respuesta válida a `Recommendation` (incluyendo que `suggested_amount` sale de `base_amount * confidence`, no del LLM, y que `horizon` es siempre `1D`).
  - `ClaudeCliTimeout` cuando `subprocess.run` lanza `subprocess.TimeoutExpired`.
  - `ClaudeCliUnavailable` cuando `subprocess.run` lanza `FileNotFoundError`.
  - `InvalidClaudeCliResponse` cuando `is_error: true`, cuando stdout no es JSON, y cuando falta `structured_output`.
  - Que `AgentService.propose()` funciona con `ClaudeCliEngine` sin ningún cambio en `AgentService` (mismo test estructural que ya existe para `RuleBasedEngine`, reutilizando el patrón).
- **Un test de integración real, marcado `integration` y opt-in** (mismo marcador que el test real de Finnhub, no corre en el bucle rápido): invoca el CLI de verdad una vez contra un snapshot fijo, verificando que la respuesta sigue teniendo la forma esperada — red de seguridad ante un cambio futuro de versión del CLI (flags renombrados, formato de salida distinto, etc.), no se ejecuta en cada `pytest` normal porque cuesta 10-14s reales y consume cuota de la suscripción.

## Fuera de alcance (documentar, no construir ahora)

- Ollama local (descartado en esta fase, no se retoma).
- Que el LLM decida `suggested_amount` u `horizon` — quedan deterministas por diseño, para mantener comparable el tamaño de la apuesta entre motores.
- Fallback automático a `RuleBasedEngine` si `ClaudeCliEngine` falla — un fallo es un fallo visible, no un cambio de motor silencioso.
- Selección de motor por request (vía la API) — es una decisión de despliegue vía variable de entorno, no una opción que el usuario cambie desde el dashboard.
- Caché de respuestas del LLM entre peticiones — cada `propose()` es una llamada nueva.
