# InvestSim — Fase 5: Frontend React — Diseño

**Estado:** Aprobado. Precede al plan de implementación TDD.

## Contexto

La Fase 4 dejó la API FastAPI completa (`docs/superpowers/specs/2026-07-19-investsim-fase4-api-fastapi-design.md`), con 5 endpoints sobre los servicios de dominio:

- `POST /recommendations` — pide una recomendación para un símbolo.
- `POST /predictions` — abre una predicción (descuenta caja virtual).
- `GET /portfolio` — caja, capital inicial, valor de posiciones abiertas, valor total. Liquida vencidas antes de responder.
- `GET /predictions` — lista de predicciones (abiertas y liquidadas). Liquida vencidas antes de responder.
- `GET /metrics` — métricas acumuladas (hit rate, retorno total, etc.). Liquida vencidas antes de responder.

Esta fase construye el frontend React (Vite) que consume esa API. Herramienta personal de un solo usuario, sin login, uso bajo demanda (sin scheduler ni polling).

## Alcance

- Un **dashboard único** (una sola pantalla, sin rutas/navegación) que integra: pedir y aceptar recomendaciones, ver portfolio, ver historial de predicciones, ver métricas.
- Aviso legal visible de forma permanente y en cada recomendación.
- Fuera de alcance: autenticación, multi-usuario, edición del importe sugerido antes de aceptar, polling/auto-refresco periódico, tests end-to-end contra el backend real.

## Stack

- **Vite + React + TypeScript.**
- **TanStack Query** para las 5 llamadas a la API (mutations para `POST`, queries para `GET`); da manejo de loading/error e invalidación de queries sin escribir esa lógica a mano.
- **CSS Modules** por componente + variables compartidas en `src/styles/theme.css`. Paleta oscura estilo fintech (fondo oscuro, verde/rojo para ganancias/pérdidas, tipografía tabular para cifras). Sin librería de componentes de terceros.
- **Vitest + React Testing Library** para tests (unitarios de `api/`/`hooks/`, de comportamiento para componentes). Sin red real en la suite — mismo principio que el backend (`FakeMarketDataProvider` allá, fetch mockeado aquí).
- `VITE_API_URL` como variable de entorno apuntando a `http://127.0.0.1:8000` en desarrollo. El backend ya expone CORS abierto a cualquier puerto de `localhost` (`allow_origin_regex=r"http://localhost:\d+"`).

## Estructura de carpetas

Organización por tipo (capas finas), no por feature — el alcance (un dashboard, 5 endpoints) no justifica más estructura:

```
frontend/
├── src/
│   ├── api/
│   │   ├── client.ts          # fetch wrapper: baseURL, JSON, errores HTTP tipados
│   │   └── types.ts           # tipos TS reflejando schemas.py (RecommendationOut, PredictionOut, PortfolioOut, MetricsOut)
│   ├── hooks/
│   │   ├── useRecommendation.ts   # mutation: POST /recommendations
│   │   ├── useOpenPrediction.ts   # mutation: POST /predictions
│   │   ├── usePortfolio.ts        # query: GET /portfolio
│   │   ├── usePredictions.ts      # query: GET /predictions
│   │   └── useMetrics.ts          # query: GET /metrics
│   ├── components/
│   │   ├── RecommendationPanel.tsx
│   │   ├── PortfolioSummary.tsx
│   │   ├── PredictionsTable.tsx
│   │   ├── MetricsPanel.tsx
│   │   └── LegalBanner.tsx
│   ├── styles/
│   │   └── theme.css
│   ├── App.tsx
│   └── main.tsx
├── vite.config.ts
└── package.json
```

## Flujo de datos y estados

**Carga inicial:** al montar `App.tsx`, `usePortfolio()`, `usePredictions()` y `useMetrics()` se disparan en paralelo. Cada panel gestiona su propio estado `loading`/`error`/`data` de forma independiente — un fallo en un panel no bloquea los demás. Loading: skeleton simple. Error: mensaje inline en ese panel, con botón de reintento (`refetch()` de TanStack Query).

**Bucle recomendación → aceptar:**

1. El usuario escribe un símbolo (campo de texto libre) en `RecommendationPanel` y pulsa "Pedir recomendación" → `useRecommendation()` llama `POST /recommendations`.
2. Mientras resuelve, el botón queda en estado *loading*. Si la API responde 404 (símbolo desconocido) o 503 (proveedor de datos caído), se muestra el `detail` del error en el propio panel.
3. Si resuelve, se muestra una tarjeta con dirección (↑/↓, coloreada), confianza (%), importe sugerido, horizonte, motivo, y el aviso legal en pequeño — con un botón "Aceptar predicción".
4. Al pulsar "Aceptar": `useOpenPrediction()` llama `POST /predictions` con los datos de la recomendación tal cual (sin edición del importe). Si la API responde 400 (fondos insuficientes), el error se muestra en la misma tarjeta sin descartar la recomendación, permitiendo reintentar o abandonar.
5. Si la apertura tiene éxito: la tarjeta se limpia y se invalidan las queries `portfolio`, `predictions` y `metrics` (`queryClient.invalidateQueries`), que TanStack Query vuelve a pedir automáticamente. No hay polling ni refresco periódico — solo carga inicial y tras acciones, como pidió el usuario.

**Tabla de predicciones (`PredictionsTable`):** una fila por predicción con símbolo, fecha, importe, estado (`open`/`settled`, coloreado) y, según estado: `current_value` (abiertas) o `final_value`/`pnl_pct`/`hit` (liquidadas) — campos que `GET /predictions` ya calcula.

## Manejo de errores

- `api/client.ts` centraliza el `fetch`: toda respuesta no-`2xx` lanza un error tipado con `status` y `detail` (el shape `{"detail": "..."}` que ya produce `investsim/api/errors.py`).
- Cada hook expone ese error vía TanStack Query (`error`/`isError`); cada componente decide cómo mostrarlo — sin un manejador global que homogeneice contextos distintos (un fallo al pedir recomendación no es lo mismo que un fallo al cargar el portfolio).
- Backend inalcanzable (no solo error HTTP, sino sin respuesta): mismo camino, TanStack Query lo captura como error de red; el panel afectado muestra "No se pudo conectar con la API" con reintento manual.

## Aviso legal

`LegalBanner.tsx`: banner fijo en la parte superior del dashboard con el texto exacto *"Simulación educativa, no es asesoramiento financiero. Capital ficticio."* — presente de forma permanente. El mismo texto, en tamaño reducido, aparece también dentro de la tarjeta de recomendación (paso 3 del flujo), cumpliendo el requisito de `CLAUDE.md` de que esté "presente en el dashboard y en cada recomendación".

## Estrategia de testing

- **`api/client.ts`:** tests unitarios con `fetch` mockeado — verifica construcción de URL/body y traducción de errores HTTP al shape tipado.
- **Hooks (`hooks/*.ts`):** tests unitarios con `api/client` mockeado — verifican que llaman al endpoint correcto y exponen loading/error/data como se espera.
- **Componentes (`components/*.tsx`):** tests de comportamiento con React Testing Library + `userEvent`, con los hooks mockeados. Ejemplos: "al aceptar con éxito, la tarjeta de recomendación se limpia"; "un 404 al pedir recomendación muestra el mensaje de error sin romper el resto del dashboard".
- Sin tests visuales/CSS (el pulido se verifica a ojo) ni tests de integración contra el backend real en la suite rápida — mismo principio que el backend (sin red en el bucle de tests).

## Fuera de alcance (documentar, no construir ahora)

- Edición del importe antes de aceptar una predicción.
- Polling o auto-refresco periódico.
- Múltiples pantallas/rutas (historial separado, etc.) — todo vive en el dashboard único.
- Autenticación / multi-usuario (fuera de alcance del proyecto entero, ver spec original).
