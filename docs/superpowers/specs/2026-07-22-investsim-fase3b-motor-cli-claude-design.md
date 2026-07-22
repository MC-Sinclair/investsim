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
- **Latencia real, no despreciable:** 10-14s en el caso favorable (Haiku + `--safe-mode`). Muy por encima de las reglas deterministas (~100ms) o de lo típico en Ollama local (~1-3s).
- **`--safe-mode` reduce la latencia a un tercio.** Medido dentro del repo, misma llamada: **con `--safe-mode` 11,6s (2 turnos); sin él 33,4s (5 turnos)**. Desactiva `CLAUDE.md`, skills, plugins, hooks y MCP — nada de eso aporta a esta tarea, y su carga es lo que dispara turnos extra. A diferencia de `--bare`, **conserva la autenticación OAuth de la suscripción**. Además hace la llamada reproducible sea cual sea la configuración personal del usuario, y elimina la dependencia de desde qué directorio se invoque.
- **`--bare` NO sirve para este caso:** fuerza autenticación estricta por `ANTHROPIC_API_KEY` (nunca lee la sesión OAuth) — verificado en vivo: devuelve `"Not logged in · Please run /login"`. Usarlo rompería justo la ventaja de no pagar aparte.
- **Cuota compartida:** cada llamada consume la misma cuota de uso que el resto de la actividad del usuario en Claude Code. No es un recurso ilimitado ni aislado.

### Hallazgos críticos de invocación desde Python en Windows

Verificados ejecutando `subprocess` real contra el CLI instalado. Los tres primeros **romperían la implementación** si se ignoran:

- **`subprocess.run(["claude", ...])` falla SIEMPRE en Windows** con `FileNotFoundError: [WinError 2]`. El ejecutable es `claude.CMD` (shim de npm) y `CreateProcess` no resuelve `PATHEXT`. **Hay que resolver la ruta con `shutil.which("claude")`** (devuelve `C:\...\npm\claude.CMD`), que sí funciona. Consecuencia si se ignora: el motor reportaría "CLI no disponible" de forma permanente, aun estando instalado y operativo.
- **El JSON del schema debe serializarse compacto, sin espacios.** `json.dumps(schema)` por defecto produce `{"type": "object", ...}`; al pasar por el shim `.CMD`, cmd.exe parte el argumento por los espacios. Efecto observado: en una prueba **cuelgue hasta agotar el timeout de 60s**, en otra `returncode=0` pero **sin `structured_output`** (fallo silencioso, peor que el cuelgue). Con `json.dumps(schema, separators=(",", ":"))` funciona de forma estable.
- **`encoding="utf-8"` es obligatorio en `subprocess.run`.** El locale del sistema es `cp1252`; sin el encoding explícito, Python decodifica como ANSI la salida UTF-8 del CLI y corrompe todos los acentos. Comparativa real del mismo texto: sin encoding → `La acciÃ³n subiÃ³ segÃºn el anÃ¡lisis tÃ©cnico`; con `encoding="utf-8"` → `La acción subió según el análisis técnico`. El `rationale` se persiste en BD y se muestra en el dashboard, así que esto sería visible y permanente.
- **Detección de errores: no fiarse de `subtype` ni de `stderr`.** Con un modelo inválido, el CLI devuelve `returncode=1`, `is_error: true`, **`stderr` vacío** y — de forma engañosa — **`subtype: "success"`**. El mensaje de error viaja dentro del JSON de stdout (campo `result`). La detección debe basarse en `returncode != 0`, `is_error == true`, o ausencia de `structured_output`; nunca en `subtype` ni en `stderr`.
- **`stdin=subprocess.DEVNULL`** se pasa por higiene, para que el proceso nunca quede esperando entrada interactiva (no se observó cuelgue por esta causa en las pruebas, pero es una llamada estrictamente no interactiva).

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

**Invocación exacta** (esta forma está verificada funcionando en Windows; cada detalle responde a un hallazgo de la sección anterior):

```python
import json, shutil, subprocess

SCHEMA = json.dumps(
    {
        "type": "object",
        "properties": {
            "direction": {"type": "string", "enum": ["up", "down"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "rationale": {"type": "string"},
        },
        "required": ["direction", "confidence", "rationale"],
    },
    separators=(",", ":"),      # OBLIGATORIO: compacto, sin espacios (ver hallazgos)
)

executable = shutil.which("claude")   # OBLIGATORIO: resuelve claude.CMD en Windows
if executable is None:
    raise ClaudeCliUnavailable(...)

result = subprocess.run(
    [
        executable, "-p",
        "--safe-mode",                  # desactiva CLAUDE.md/skills/hooks: 3x más rápido
        "--output-format", "json",
        "--model", config.model,
        "--json-schema", SCHEMA,
        prompt,
    ],
    capture_output=True,
    text=True,
    encoding="utf-8",                   # OBLIGATORIO: si no, se corrompen los acentos
    stdin=subprocess.DEVNULL,
    timeout=config.timeout_seconds,     # 60.0
)
```

- **`shutil.which("claude")`** para resolver el ejecutable. Si devuelve `None`, se lanza `ClaudeCliUnavailable` sin llegar a invocar nada.
- **`--safe-mode`** en lugar de manipular el `cwd`: desactiva explícitamente `CLAUDE.md`, skills, plugins y hooks (3x más rápido, ver hallazgos), conserva la autenticación de suscripción y hace la llamada independiente del directorio de trabajo. **No se fija `cwd`** — con `--safe-mode` deja de ser relevante.
- **`separators=(",", ":")`** al serializar el schema — sin esto la llamada se cuelga o falla en silencio.
- **`encoding="utf-8"`** — sin esto los acentos del `rationale` se guardan corruptos.
- `timeout=60.0` — margen amplio sobre los ~11-14s observados; aceptable porque es una llamada bajo demanda (el usuario espera activamente su recomendación), no un bucle ni un scheduler.
- La respuesta exitosa es un JSON de nivel superior con `structured_output` (dict ya validado contra el schema) e `is_error` (bool). Se usa `structured_output` directamente — no se reparsea `result` como texto libre.

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
| `confidence` | `structured_output["confidence"]`, **acotado a `[0.05, 0.95]`** (ver abajo) |
| `rationale` | `structured_output["rationale"]`, tal cual |
| `suggested_amount` | `base_amount * confidence` — **mismo cálculo que `RuleBasedEngine`**, no lo decide el LLM |
| `horizon` | fijo `Horizon.ONE_DAY` — misma limitación de datos que Fase 3a (sin histórico multi-día de Finnhub gratuito) |

**Por qué se acota la confianza:** el schema permite `minimum: 0`, así que `confidence: 0.0` es una respuesta legal del LLM. Con ella, `suggested_amount = base_amount * 0 = 0` y se abriría una predicción de **0 €** — que `PortfolioService.open_prediction()` **acepta sin error** (solo valida `amount > cash_balance`, no `amount > 0`), quedando registrada y contando en `total_predictions` de las métricas pese a no representar ninguna apuesta real. `RuleBasedEngine` ya evita esto acotando a `[0.05, 0.95]` mediante `_MIN_CONFIDENCE`/`_MAX_CONFIDENCE`. `ClaudeCliEngine` aplica **los mismos límites**, reutilizando esas constantes de `investsim/agent/rules.py`, para que ambos motores garanticen la misma invariante y sigan siendo comparables.

## Manejo de errores

Tres excepciones nuevas en `investsim/agent/claude_cli.py`, ninguna atrapada dentro de `ClaudeCliEngine` ni de `AgentService` (mismo principio que las excepciones de `MarketDataProvider`: suben tal cual hasta la API):

- **`ClaudeCliUnavailable`** — `shutil.which("claude")` devuelve `None` (no está instalado / no está en el PATH), o `subprocess.run` lanza `FileNotFoundError`.
- **`ClaudeCliTimeout`** — `subprocess.TimeoutExpired` al superar los 60s.
- **`InvalidClaudeCliResponse`** — `returncode != 0`, `is_error: true`, stdout no parseable como JSON, o JSON sin `structured_output` con las claves esperadas. El mensaje de la excepción incluye el campo `result` del JSON cuando existe, que es donde el CLI pone la explicación del fallo.

**Detección (verificada en vivo):** ante un error, el CLI devuelve `returncode=1`, `is_error: true`, `stderr` **vacío** y `subtype: "success"` — este último es engañoso. La lógica **no debe** basarse en `subtype` ni en `stderr`; solo en `returncode`, `is_error` y la presencia de `structured_output`.

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

- **Tests rápidos** (`backend/tests/test_claude_cli_engine.py`): se sustituyen `subprocess.run` y `shutil.which` (vía `monkeypatch`) por respuestas controladas — un `subprocess.CompletedProcess` fabricado con el `stdout` que produciría el CLI real. Cubren:
  - Mapeo correcto de una respuesta válida a `Recommendation` (incluyendo que `suggested_amount` sale de `base_amount * confidence`, no del LLM, y que `horizon` es siempre `1D`).
  - **Acotado de la confianza:** `confidence: 0.0` del LLM produce `0.05` (y por tanto `suggested_amount > 0`), y `confidence: 1.0` produce `0.95`.
  - **Construcción del comando:** el schema pasado a `subprocess.run` no contiene espacios, e incluye `--safe-mode` y `encoding="utf-8"` — son requisitos de correctitud verificados, no detalles cosméticos, así que se comprueban explícitamente.
  - `ClaudeCliTimeout` cuando `subprocess.run` lanza `subprocess.TimeoutExpired`.
  - `ClaudeCliUnavailable` cuando `shutil.which` devuelve `None` y cuando `subprocess.run` lanza `FileNotFoundError`.
  - `InvalidClaudeCliResponse` en los cuatro casos: `returncode != 0`, `is_error: true`, stdout no parseable, y JSON sin `structured_output`.
  - Que `AgentService.propose()` funciona con `ClaudeCliEngine` sin ningún cambio en `AgentService`.
- **Un test de integración real, opt-in** en `backend/tests/integration/test_claude_cli_integration.py`, siguiendo exactamente el patrón ya establecido en `backend/tests/integration/test_finnhub_integration.py`: `pytestmark = pytest.mark.integration` a nivel de módulo más un `@pytest.mark.skipif` que lo salta si `shutil.which("claude")` es `None`. El marcador `integration` ya está registrado en `backend/pyproject.toml` y **excluido por defecto** vía `addopts = "-m 'not integration'"`, así que no corre en el bucle rápido. Invoca el CLI de verdad una vez contra un snapshot fijo y verifica que la respuesta mantiene la forma esperada — red de seguridad ante un cambio futuro de versión del CLI (flags renombrados, formato de salida distinto). No se ejecuta en cada `pytest` normal porque cuesta ~11-14s reales y consume cuota de la suscripción.

## Fuera de alcance (documentar, no construir ahora)

- Ollama local (descartado en esta fase, no se retoma).
- Que el LLM decida `suggested_amount` u `horizon` — quedan deterministas por diseño, para mantener comparable el tamaño de la apuesta entre motores.
- Fallback automático a `RuleBasedEngine` si `ClaudeCliEngine` falla — un fallo es un fallo visible, no un cambio de motor silencioso.
- Selección de motor por request (vía la API) — es una decisión de despliegue vía variable de entorno, no una opción que el usuario cambie desde el dashboard.
- Caché de respuestas del LLM entre peticiones — cada `propose()` es una llamada nueva.
