# InvestSim — Fase 5: Frontend React Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el dashboard React (Vite + TypeScript) que consume los 5 endpoints de la API FastAPI de InvestSim (`investsim/api/`), permitiendo pedir/aceptar recomendaciones y ver portfolio, predicciones y métricas — todo en una sola pantalla.

**Architecture:** Tres capas finas dentro de `frontend/src/`: `api/` (fetch tipado + normalización de errores/fechas), `hooks/` (TanStack Query sobre `api/`), `components/` (presentación, con los hooks inyectados o consumidos directamente). `App.tsx` compone todo. Sin router, sin librería de componentes de terceros.

**Tech Stack:** Vite, React 19, TypeScript, TanStack Query v5, CSS Modules, Vitest, React Testing Library, `@testing-library/user-event`, `@testing-library/jest-dom`, jsdom.

## Global Constraints

- Node y npm ya están instalados en el entorno de desarrollo (verificado: Node v24, npm v11). Todos los comandos de este plan se ejecutan desde `frontend/` salvo que se indique lo contrario.
- El dashboard **debe abrirse en `http://localhost:5173`**, nunca en `http://127.0.0.1:5173` — el backend usa `allow_origin_regex=r"http://localhost:\d+"` (verificado en `investsim/api/app.py`) y bloquea cualquier otro origin. Esto se documenta en `frontend/README.md`.
- Aviso legal, texto exacto: `"Simulación educativa, no es asesoramiento financiero. Capital ficticio."` — visible de forma permanente (`LegalBanner`) y dentro de cada tarjeta de recomendación.
- **Todos** los timestamps de la API se tratan como UTC. Ningún componente llama `new Date(...)` directamente sobre un string de la API — siempre a través de `parseApiDate` (`src/api/dates.ts`), porque `POST /predictions` devuelve fechas con `Z` y `GET /predictions` las devuelve sin `Z` (columnas `DateTime` naive en SQLite, verificado ejecutando la API real).
- **Todos** los errores de la API se normalizan a `ApiError { status: number, message: string }` (`src/api/errors.ts`) antes de llegar a un componente. `detail` es un string en los errores de dominio (404/503/400) pero una lista de objetos en los 422 de validación de FastAPI (verificado ejecutando la API real) — los componentes solo leen `.message`, nunca `detail` crudo.
- `GET /predictions` no garantiza orden (`PredictionRepository.list_all()` no tiene `ORDER BY`, verificado en `investsim/db/repositories.py`). El frontend ordena por `id` descendente en `usePredictions`.
- Sin polling ni auto-refresco: las queries solo se piden al montar y se invalidan tras un `POST /predictions` exitoso.
- Aceptar una recomendación es siempre tal cual la propone el agente — no hay edición de `suggested_amount` en la UI.
- Ningún test toca la red real — `fetch` global se mockea/stubea siempre.
- CSS Modules por componente + variables compartidas en `src/styles/theme.css`; paleta oscura fintech (fondo oscuro, verde=ganancia/`up`, rojo=pérdida/`down`, cifras con `font-variant-numeric: tabular-nums`).
- `VITE_API_URL` (env var) apunta a la API; default `http://127.0.0.1:8000` si no está definida.
- Formato de dinero y porcentajes: locale `es-ES` (coma decimal) en todo el dashboard, vía los helpers compartidos de `src/format.ts` — nunca `Number.prototype.toFixed` suelto en un componente (produce punto decimal, inconsistente con el resto de la UI).

---

### Task 1: Scaffold — Vite + React + TypeScript + arnés de tests (Vitest + RTL)

**Files:**
- Create: `frontend/` (generado por `npm create vite@latest`)
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/package.json` (añadir script `test`)
- Create: `frontend/src/setupTests.ts`
- Test: `frontend/src/App.test.tsx`

**Interfaces:**
- Consumes: nada (primera tarea).
- Produces: proyecto Vite funcionando (`npm run dev`), arnés de tests funcionando (`npm test`). Las tareas siguientes asumen que `frontend/` existe con esta configuración de Vitest.

- [ ] **Step 1: Scaffold del proyecto Vite**

Desde la **raíz del repo**:

Run: `npm create vite@latest frontend -- --template react-ts`
Expected: crea `frontend/` con `package.json`, `src/App.tsx`, `src/main.tsx`, `index.html`, `tsconfig.json`, `tsconfig.app.json`, `vite.config.ts`, `.gitignore` (ya ignora `node_modules`, `dist`). Si pregunta algo de forma interactiva pese a los flags, confirmar los valores por defecto (react + TypeScript).

- [ ] **Step 2: Instalar dependencias base**

Run (desde `frontend/`): `npm install`
Expected: instala sin errores.

- [ ] **Step 3: Añadir TanStack Query**

Run: `npm install @tanstack/react-query`

- [ ] **Step 4: Añadir dependencias de testing**

Run: `npm install -D vitest @testing-library/react @testing-library/user-event @testing-library/jest-dom jsdom`

- [ ] **Step 5: Configurar Vitest en `vite.config.ts`**

Reemplazar `frontend/vite.config.ts` completo:

```ts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: './src/setupTests.ts',
  },
})
```

- [ ] **Step 6: Crear el setup de tests**

Crear `frontend/src/setupTests.ts`:

```ts
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'

afterEach(() => {
  cleanup()
})
```

- [ ] **Step 7: Añadir el script `test` a `package.json`**

En `frontend/package.json`, dentro del objeto `"scripts"`, añadir una línea:

```json
"test": "vitest run",
```

(el resto de scripts generados por el scaffold —`dev`, `build`, `lint`, `preview`— se quedan igual).

- [ ] **Step 8: Escribir el test de humo del arnés**

Crear `frontend/src/App.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('App scaffold', () => {
  it('renders the default Vite + React starter content', () => {
    render(<App />)
    expect(screen.getByText(/vite \+ react/i)).toBeInTheDocument()
  })
})
```

**Nota:** este test verifica que Vitest + jsdom + React Testing Library funcionan juntos, contra el `App.tsx` por defecto del scaffold. La Task 13 **reemplaza** tanto `App.tsx` como este fichero de test por el dashboard real.

- [ ] **Step 9: Ejecutar el test para verificar que pasa**

Run: `npm test`
Expected: PASS — 1 test.

- [ ] **Step 10: Commit**

```bash
git add frontend/
git commit -m "chore(frontend): scaffold Vite + React + TypeScript + Vitest/RTL"
```

---

### Task 2: `api/dates.ts` — normalización de timestamps

**Files:**
- Create: `frontend/src/api/dates.ts`
- Test: `frontend/src/api/dates.test.ts`

**Interfaces:**
- Consumes: nada.
- Produces: `parseApiDate(value: string): Date`.

- [ ] **Step 1: Escribir el test que falla**

Crear `frontend/src/api/dates.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { parseApiDate } from './dates'

describe('parseApiDate', () => {
  it('parses a timestamp that already has a timezone designator', () => {
    const result = parseApiDate('2026-07-22T19:53:03.555030Z')
    expect(result.toISOString()).toBe('2026-07-22T19:53:03.555Z')
  })

  it('treats a timestamp without a timezone designator as UTC', () => {
    const result = parseApiDate('2026-07-22T19:53:03.555030')
    expect(result.toISOString()).toBe('2026-07-22T19:53:03.555Z')
  })

  it('produces the same instant for both formats', () => {
    const withZone = parseApiDate('2026-07-22T19:53:03.555030Z')
    const withoutZone = parseApiDate('2026-07-22T19:53:03.555030')
    expect(withoutZone.getTime()).toBe(withZone.getTime())
  })
})
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `npm test -- src/api/dates.test.ts`
Expected: FAIL con `Cannot find module './dates'` (o similar — el fichero no existe).

- [ ] **Step 3: Implementar `parseApiDate`**

Crear `frontend/src/api/dates.ts`:

```ts
const HAS_TIMEZONE = /[zZ]|[+-]\d{2}:\d{2}$/

export function parseApiDate(value: string): Date {
  return new Date(HAS_TIMEZONE.test(value) ? value : `${value}Z`)
}
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `npm test -- src/api/dates.test.ts`
Expected: PASS — 3 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/dates.ts frontend/src/api/dates.test.ts
git commit -m "feat(frontend): parseApiDate normaliza timestamps naive/aware a UTC"
```

---

### Task 3: `api/errors.ts` — normalización de errores HTTP

**Files:**
- Create: `frontend/src/api/errors.ts`
- Test: `frontend/src/api/errors.test.ts`

**Interfaces:**
- Consumes: nada.
- Produces: `class ApiError extends Error { status: number }`, `toApiError(response: Response): Promise<ApiError>`.

- [ ] **Step 1: Escribir el test que falla**

Crear `frontend/src/api/errors.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { toApiError } from './errors'

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('toApiError', () => {
  it('uses detail directly when it is a string', async () => {
    const response = jsonResponse(404, { detail: 'Simbolo desconocido: NOPE' })
    const error = await toApiError(response)
    expect(error.status).toBe(404)
    expect(error.message).toBe('Simbolo desconocido: NOPE')
  })

  it('joins the msg fields when detail is a FastAPI validation array', async () => {
    const response = jsonResponse(422, {
      detail: [{ type: 'missing', loc: ['body', 'amount'], msg: 'Field required' }],
    })
    const error = await toApiError(response)
    expect(error.status).toBe(422)
    expect(error.message).toBe('Field required')
  })

  it('joins multiple validation errors with a separator', async () => {
    const response = jsonResponse(422, {
      detail: [
        { type: 'missing', loc: ['body', 'amount'], msg: 'Field required' },
        { type: 'missing', loc: ['body', 'symbol'], msg: 'Field required' },
      ],
    })
    const error = await toApiError(response)
    expect(error.message).toBe('Field required; Field required')
  })

  it('falls back to a generic message when there is no detail', async () => {
    const response = new Response('not json', { status: 500 })
    const error = await toApiError(response)
    expect(error.status).toBe(500)
    expect(error.message).toBe('Error 500 al llamar a la API')
  })
})
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `npm test -- src/api/errors.test.ts`
Expected: FAIL con `Cannot find module './errors'`.

- [ ] **Step 3: Implementar `ApiError` y `toApiError`**

Crear `frontend/src/api/errors.ts`:

```ts
export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

interface ValidationDetailItem {
  msg: string
}

function isValidationDetailArray(detail: unknown): detail is ValidationDetailItem[] {
  return (
    Array.isArray(detail) &&
    detail.every(
      (item) => typeof item === 'object' && item !== null && typeof (item as { msg?: unknown }).msg === 'string'
    )
  )
}

export async function toApiError(response: Response): Promise<ApiError> {
  let body: unknown = null
  try {
    body = await response.json()
  } catch {
    body = null
  }

  const detail = (body as { detail?: unknown } | null)?.detail

  if (typeof detail === 'string') {
    return new ApiError(response.status, detail)
  }

  if (isValidationDetailArray(detail)) {
    return new ApiError(response.status, detail.map((item) => item.msg).join('; '))
  }

  return new ApiError(response.status, `Error ${response.status} al llamar a la API`)
}
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `npm test -- src/api/errors.test.ts`
Expected: PASS — 4 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/errors.ts frontend/src/api/errors.test.ts
git commit -m "feat(frontend): ApiError normaliza detail string/array/ausente a message"
```

---

### Task 4: `api/types.ts` + `api/client.ts` — tipos y llamadas a los 5 endpoints

**Files:**
- Create: `frontend/src/api/types.ts`
- Create: `frontend/src/api/client.ts`
- Test: `frontend/src/api/client.test.ts`

**Interfaces:**
- Consumes: `parseApiDate` (Task 2, no se usa aún directamente aquí — los campos de fecha se dejan como `string` en los tipos, el parseo ocurre en los componentes que los muestran), `ApiError`/`toApiError` (Task 3).
- Produces: tipos `Direction`, `Horizon`, `PredictionStatus`, `RecommendationOut`, `OpenPredictionIn`, `PredictionOut`, `PortfolioOut`, `MetricsOut`; funciones `postRecommendation(symbol: string): Promise<RecommendationOut>`, `postPrediction(body: OpenPredictionIn): Promise<PredictionOut>`, `getPortfolio(): Promise<PortfolioOut>`, `getPredictions(): Promise<PredictionOut[]>`, `getMetrics(): Promise<MetricsOut>`.

- [ ] **Step 1: Crear los tipos**

Crear `frontend/src/api/types.ts`:

```ts
export type Direction = 'up' | 'down'
export type Horizon = '1D' | '1W' | '1M'
export type PredictionStatus = 'open' | 'settled'

export interface RecommendationOut {
  symbol: string
  direction: Direction
  confidence: number
  suggested_amount: number
  horizon: Horizon
  rationale: string
}

export interface OpenPredictionIn {
  symbol: string
  amount: number
  direction: Direction
  confidence: number
  horizon: Horizon
  rationale: string
}

export interface PredictionOut {
  id: number
  symbol: string
  created_at: string
  entry_price: number
  amount: number
  shares: number
  horizon: string
  evaluate_at: string
  expected_direction: string
  confidence: number
  rationale: string
  status: PredictionStatus
  exit_price: number | null
  final_value: number | null
  pnl_pct: number | null
  hit: boolean | null
  current_value: number | null
}

export interface PortfolioOut {
  cash_balance: number
  initial_capital: number
  open_predictions_value: number
  total_value: number
}

export interface MetricsOut {
  total_predictions: number
  settled: number
  hits: number
  hit_rate_pct: number
  total_invested: number
  total_final_value: number
  total_return_pct: number
}
```

(no lleva test propio — son solo declaraciones de tipo, sin comportamiento en tiempo de ejecución)

- [ ] **Step 2: Escribir el test que falla para `client.ts`**

Crear `frontend/src/api/client.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  getMetrics,
  getPortfolio,
  getPredictions,
  postPrediction,
  postRecommendation,
} from './client'

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('postRecommendation', () => {
  it('POSTs the symbol and returns the parsed recommendation', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(200, {
        symbol: 'AAPL',
        direction: 'up',
        confidence: 0.5,
        suggested_amount: 10,
        horizon: '1D',
        rationale: 'motivo',
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await postRecommendation('AAPL')

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/recommendations'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ symbol: 'AAPL' }),
      })
    )
    expect(result.symbol).toBe('AAPL')
    expect(result.direction).toBe('up')
  })

  it('throws an ApiError with the domain message on 404', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse(404, { detail: 'Simbolo desconocido: NOPE' }))
    )

    await expect(postRecommendation('NOPE')).rejects.toMatchObject({
      status: 404,
      message: 'Simbolo desconocido: NOPE',
    })
  })
})

describe('postPrediction', () => {
  it('POSTs the prediction body and returns the parsed prediction', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(200, {
        id: 1,
        symbol: 'AAPL',
        created_at: '2026-07-22T19:53:03.555030Z',
        entry_price: 100,
        amount: 10,
        shares: 0.1,
        horizon: '1D',
        evaluate_at: '2026-07-23T19:53:03.555030Z',
        expected_direction: 'up',
        confidence: 0.5,
        rationale: '',
        status: 'open',
        exit_price: null,
        final_value: null,
        pnl_pct: null,
        hit: null,
        current_value: null,
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await postPrediction({
      symbol: 'AAPL',
      amount: 10,
      direction: 'up',
      confidence: 0.5,
      horizon: '1D',
      rationale: '',
    })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/predictions'),
      expect.objectContaining({ method: 'POST' })
    )
    expect(result.id).toBe(1)
    expect(result.status).toBe('open')
  })

  it('throws an ApiError with the domain message on 400', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse(400, { detail: 'amount 10000.0 > cash 990.0' }))
    )

    await expect(
      postPrediction({
        symbol: 'AAPL',
        amount: 10000,
        direction: 'up',
        confidence: 0.5,
        horizon: '1D',
        rationale: '',
      })
    ).rejects.toMatchObject({ status: 400, message: 'amount 10000.0 > cash 990.0' })
  })
})

describe('getPortfolio', () => {
  it('GETs the portfolio', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(200, {
        cash_balance: 990,
        initial_capital: 1000,
        open_predictions_value: 15,
        total_value: 1005,
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await getPortfolio()

    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/portfolio'), expect.anything())
    expect(result.total_value).toBe(1005)
  })
})

describe('getPredictions', () => {
  it('GETs the predictions list', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(200, [])))

    const result = await getPredictions()

    expect(result).toEqual([])
  })
})

describe('getMetrics', () => {
  it('GETs the metrics', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(200, {
        total_predictions: 1,
        settled: 1,
        hits: 1,
        hit_rate_pct: 100,
        total_invested: 10,
        total_final_value: 13.4,
        total_return_pct: 34,
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await getMetrics()

    expect(result.hit_rate_pct).toBe(100)
  })
})
```

- [ ] **Step 3: Ejecutar el test para verificar que falla**

Run: `npm test -- src/api/client.test.ts`
Expected: FAIL con `Cannot find module './client'`.

- [ ] **Step 4: Implementar `client.ts`**

Crear `frontend/src/api/client.ts`:

```ts
import { toApiError } from './errors'
import type {
  MetricsOut,
  OpenPredictionIn,
  PortfolioOut,
  PredictionOut,
  RecommendationOut,
} from './types'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  })

  if (!response.ok) {
    throw await toApiError(response)
  }

  return (await response.json()) as T
}

export function postRecommendation(symbol: string): Promise<RecommendationOut> {
  return request<RecommendationOut>('/recommendations', {
    method: 'POST',
    body: JSON.stringify({ symbol }),
  })
}

export function postPrediction(body: OpenPredictionIn): Promise<PredictionOut> {
  return request<PredictionOut>('/predictions', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function getPortfolio(): Promise<PortfolioOut> {
  return request<PortfolioOut>('/portfolio')
}

export function getPredictions(): Promise<PredictionOut[]> {
  return request<PredictionOut[]>('/predictions')
}

export function getMetrics(): Promise<MetricsOut> {
  return request<MetricsOut>('/metrics')
}
```

- [ ] **Step 5: Ejecutar el test para verificar que pasa**

Run: `npm test -- src/api/client.test.ts`
Expected: PASS — 7 tests.

- [ ] **Step 6: Ejecutar la suite completa**

Run: `npm test`
Expected: PASS — todos los tests de las Tasks 1-4.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts frontend/src/api/client.test.ts
git commit -m "feat(frontend): tipos y cliente HTTP tipado para los 5 endpoints"
```

---

### Task 5: Helper de tests para TanStack Query + hooks de lectura (`usePortfolio`, `usePredictions`, `useMetrics`)

**Files:**
- Create: `frontend/src/test/queryWrapper.tsx`
- Create: `frontend/src/hooks/usePortfolio.ts`
- Create: `frontend/src/hooks/usePredictions.ts`
- Create: `frontend/src/hooks/useMetrics.ts`
- Test: `frontend/src/hooks/usePortfolio.test.ts`
- Test: `frontend/src/hooks/usePredictions.test.ts`
- Test: `frontend/src/hooks/useMetrics.test.ts`

**Interfaces:**
- Consumes: `getPortfolio`, `getPredictions`, `getMetrics` (Task 4), tipos `PortfolioOut`/`PredictionOut`/`MetricsOut` (Task 4).
- Produces: `createTestQueryClient(): QueryClient`, `createQueryWrapper(client: QueryClient)` (helper de test reutilizado por la Task 6); `usePortfolio()`, `usePredictions()`, `useMetrics()` — cada uno un `useQuery` de TanStack Query con `queryKey` `['portfolio']`, `['predictions']`, `['metrics']` respectivamente.

- [ ] **Step 1: Crear el helper de test para TanStack Query**

Crear `frontend/src/test/queryWrapper.tsx`:

```tsx
import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
}

export function createQueryWrapper(client: QueryClient) {
  return function QueryWrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>
  }
}
```

(no lleva test propio — es infraestructura de test, se ejercita a través de los hooks que la usan)

- [ ] **Step 2: Escribir el test que falla para `usePortfolio`**

Crear `frontend/src/hooks/usePortfolio.test.ts`:

```ts
import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { usePortfolio } from './usePortfolio'
import * as client from '../api/client'
import { createQueryWrapper, createTestQueryClient } from '../test/queryWrapper'

describe('usePortfolio', () => {
  it('fetches the portfolio via getPortfolio', async () => {
    vi.spyOn(client, 'getPortfolio').mockResolvedValue({
      cash_balance: 990,
      initial_capital: 500,
      open_predictions_value: 15,
      total_value: 505,
    })
    const queryClient = createTestQueryClient()

    const { result } = renderHook(() => usePortfolio(), {
      wrapper: createQueryWrapper(queryClient),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.total_value).toBe(505)
  })
})
```

- [ ] **Step 3: Ejecutar el test para verificar que falla**

Run: `npm test -- src/hooks/usePortfolio.test.ts`
Expected: FAIL con `Cannot find module './usePortfolio'`.

- [ ] **Step 4: Implementar `usePortfolio`**

Crear `frontend/src/hooks/usePortfolio.ts`:

```ts
import { useQuery } from '@tanstack/react-query'
import { getPortfolio } from '../api/client'

export function usePortfolio() {
  return useQuery({
    queryKey: ['portfolio'],
    queryFn: getPortfolio,
  })
}
```

- [ ] **Step 5: Ejecutar el test para verificar que pasa**

Run: `npm test -- src/hooks/usePortfolio.test.ts`
Expected: PASS — 1 test.

- [ ] **Step 6: Escribir el test que falla para `usePredictions` (incluye el orden)**

Crear `frontend/src/hooks/usePredictions.test.ts`:

```ts
import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { usePredictions } from './usePredictions'
import * as client from '../api/client'
import { createQueryWrapper, createTestQueryClient } from '../test/queryWrapper'
import type { PredictionOut } from '../api/types'

function prediction(overrides: Partial<PredictionOut>): PredictionOut {
  return {
    id: 1,
    symbol: 'AAPL',
    created_at: '2026-07-22T00:00:00Z',
    entry_price: 100,
    amount: 10,
    shares: 0.1,
    horizon: '1D',
    evaluate_at: '2026-07-23T00:00:00Z',
    expected_direction: 'up',
    confidence: 0.5,
    rationale: '',
    status: 'open',
    exit_price: null,
    final_value: null,
    pnl_pct: null,
    hit: null,
    current_value: null,
    ...overrides,
  }
}

describe('usePredictions', () => {
  it('sorts predictions by id descending, most recent first', async () => {
    vi.spyOn(client, 'getPredictions').mockResolvedValue([
      prediction({ id: 1 }),
      prediction({ id: 3 }),
      prediction({ id: 2 }),
    ])
    const queryClient = createTestQueryClient()

    const { result } = renderHook(() => usePredictions(), {
      wrapper: createQueryWrapper(queryClient),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.map((p) => p.id)).toEqual([3, 2, 1])
  })
})
```

- [ ] **Step 7: Ejecutar el test para verificar que falla**

Run: `npm test -- src/hooks/usePredictions.test.ts`
Expected: FAIL con `Cannot find module './usePredictions'`.

- [ ] **Step 8: Implementar `usePredictions`**

Crear `frontend/src/hooks/usePredictions.ts`:

```ts
import { useQuery } from '@tanstack/react-query'
import { getPredictions } from '../api/client'
import type { PredictionOut } from '../api/types'

export function usePredictions() {
  return useQuery({
    queryKey: ['predictions'],
    queryFn: getPredictions,
    select: (predictions: PredictionOut[]) => [...predictions].sort((a, b) => b.id - a.id),
  })
}
```

- [ ] **Step 9: Ejecutar el test para verificar que pasa**

Run: `npm test -- src/hooks/usePredictions.test.ts`
Expected: PASS — 1 test.

- [ ] **Step 10: Escribir el test que falla para `useMetrics`**

Crear `frontend/src/hooks/useMetrics.test.ts`:

```ts
import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useMetrics } from './useMetrics'
import * as client from '../api/client'
import { createQueryWrapper, createTestQueryClient } from '../test/queryWrapper'

describe('useMetrics', () => {
  it('fetches the metrics via getMetrics', async () => {
    vi.spyOn(client, 'getMetrics').mockResolvedValue({
      total_predictions: 1,
      settled: 1,
      hits: 1,
      hit_rate_pct: 100,
      total_invested: 10,
      total_final_value: 13.4,
      total_return_pct: 34,
    })
    const queryClient = createTestQueryClient()

    const { result } = renderHook(() => useMetrics(), {
      wrapper: createQueryWrapper(queryClient),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.hit_rate_pct).toBe(100)
  })
})
```

- [ ] **Step 11: Ejecutar el test para verificar que falla**

Run: `npm test -- src/hooks/useMetrics.test.ts`
Expected: FAIL con `Cannot find module './useMetrics'`.

- [ ] **Step 12: Implementar `useMetrics`**

Crear `frontend/src/hooks/useMetrics.ts`:

```ts
import { useQuery } from '@tanstack/react-query'
import { getMetrics } from '../api/client'

export function useMetrics() {
  return useQuery({
    queryKey: ['metrics'],
    queryFn: getMetrics,
  })
}
```

- [ ] **Step 13: Ejecutar la suite completa**

Run: `npm test`
Expected: PASS — todos los tests de las Tasks 1-5.

- [ ] **Step 14: Commit**

```bash
git add frontend/src/test/queryWrapper.tsx frontend/src/hooks/usePortfolio.ts frontend/src/hooks/usePortfolio.test.ts frontend/src/hooks/usePredictions.ts frontend/src/hooks/usePredictions.test.ts frontend/src/hooks/useMetrics.ts frontend/src/hooks/useMetrics.test.ts
git commit -m "feat(frontend): hooks de lectura usePortfolio/usePredictions/useMetrics"
```

---

### Task 6: Hooks de escritura (`useRecommendation`, `useOpenPrediction`)

**Files:**
- Create: `frontend/src/hooks/useRecommendation.ts`
- Create: `frontend/src/hooks/useOpenPrediction.ts`
- Test: `frontend/src/hooks/useRecommendation.test.ts`
- Test: `frontend/src/hooks/useOpenPrediction.test.ts`

**Interfaces:**
- Consumes: `postRecommendation`, `postPrediction` (Task 4), `createTestQueryClient`/`createQueryWrapper` (Task 5).
- Produces: `useRecommendation()` — `useMutation` cuyo `mutate` acepta `(symbol: string)`; `useOpenPrediction()` — `useMutation` cuyo `mutate` acepta `(body: OpenPredictionIn)` e invalida `['portfolio']`, `['predictions']`, `['metrics']` al tener éxito.

- [ ] **Step 1: Escribir el test que falla para `useRecommendation`**

Crear `frontend/src/hooks/useRecommendation.test.ts`:

```ts
import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useRecommendation } from './useRecommendation'
import * as client from '../api/client'
import { createQueryWrapper, createTestQueryClient } from '../test/queryWrapper'

describe('useRecommendation', () => {
  it('calls postRecommendation with the given symbol', async () => {
    vi.spyOn(client, 'postRecommendation').mockResolvedValue({
      symbol: 'AAPL',
      direction: 'up',
      confidence: 0.5,
      suggested_amount: 10,
      horizon: '1D',
      rationale: 'motivo',
    })
    const queryClient = createTestQueryClient()

    const { result } = renderHook(() => useRecommendation(), {
      wrapper: createQueryWrapper(queryClient),
    })

    act(() => {
      result.current.mutate('AAPL')
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(client.postRecommendation).toHaveBeenCalledWith('AAPL')
    expect(result.current.data?.symbol).toBe('AAPL')
  })
})
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `npm test -- src/hooks/useRecommendation.test.ts`
Expected: FAIL con `Cannot find module './useRecommendation'`.

- [ ] **Step 3: Implementar `useRecommendation`**

Crear `frontend/src/hooks/useRecommendation.ts`:

```ts
import { useMutation } from '@tanstack/react-query'
import { postRecommendation } from '../api/client'

export function useRecommendation() {
  return useMutation({
    mutationFn: (symbol: string) => postRecommendation(symbol),
  })
}
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `npm test -- src/hooks/useRecommendation.test.ts`
Expected: PASS — 1 test.

- [ ] **Step 5: Escribir el test que falla para `useOpenPrediction`**

Crear `frontend/src/hooks/useOpenPrediction.test.ts`:

```ts
import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useOpenPrediction } from './useOpenPrediction'
import * as client from '../api/client'
import { createQueryWrapper, createTestQueryClient } from '../test/queryWrapper'

describe('useOpenPrediction', () => {
  it('invalidates portfolio, predictions and metrics queries on success', async () => {
    vi.spyOn(client, 'postPrediction').mockResolvedValue({
      id: 1,
      symbol: 'AAPL',
      created_at: '2026-07-22T00:00:00Z',
      entry_price: 100,
      amount: 10,
      shares: 0.1,
      horizon: '1D',
      evaluate_at: '2026-07-23T00:00:00Z',
      expected_direction: 'up',
      confidence: 0.5,
      rationale: '',
      status: 'open',
      exit_price: null,
      final_value: null,
      pnl_pct: null,
      hit: null,
      current_value: null,
    })
    const queryClient = createTestQueryClient()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useOpenPrediction(), {
      wrapper: createQueryWrapper(queryClient),
    })

    act(() => {
      result.current.mutate({
        symbol: 'AAPL',
        amount: 10,
        direction: 'up',
        confidence: 0.5,
        horizon: '1D',
        rationale: '',
      })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['portfolio'] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['predictions'] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['metrics'] })
  })
})
```

- [ ] **Step 6: Ejecutar el test para verificar que falla**

Run: `npm test -- src/hooks/useOpenPrediction.test.ts`
Expected: FAIL con `Cannot find module './useOpenPrediction'`.

- [ ] **Step 7: Implementar `useOpenPrediction`**

Crear `frontend/src/hooks/useOpenPrediction.ts`:

```ts
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { postPrediction } from '../api/client'
import type { OpenPredictionIn } from '../api/types'

export function useOpenPrediction() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (body: OpenPredictionIn) => postPrediction(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolio'] })
      queryClient.invalidateQueries({ queryKey: ['predictions'] })
      queryClient.invalidateQueries({ queryKey: ['metrics'] })
    },
  })
}
```

- [ ] **Step 8: Ejecutar el test para verificar que pasa**

Run: `npm test -- src/hooks/useOpenPrediction.test.ts`
Expected: PASS — 1 test.

- [ ] **Step 9: Ejecutar la suite completa**

Run: `npm test`
Expected: PASS — todos los tests de las Tasks 1-6.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/hooks/useRecommendation.ts frontend/src/hooks/useRecommendation.test.ts frontend/src/hooks/useOpenPrediction.ts frontend/src/hooks/useOpenPrediction.test.ts
git commit -m "feat(frontend): hooks de escritura useRecommendation/useOpenPrediction"
```

---

### Task 7: `format.ts` — formateo compartido de dinero y porcentajes

**Files:**
- Create: `frontend/src/format.ts`
- Test: `frontend/src/format.test.ts`

**Interfaces:**
- Consumes: nada.
- Produces: `formatEUR(value: number): string` (locale `es-ES`, símbolo `€`), `formatPercent(value: number): string` (un decimal, recibe el valor ya en escala 0-100, ej. `hit_rate_pct`).

- [ ] **Step 1: Escribir el test que falla**

Crear `frontend/src/format.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { formatEUR, formatPercent } from './format'

describe('formatEUR', () => {
  it('formats a euro amount using Spanish comma decimals', () => {
    expect(formatEUR(990)).toBe('990,00 €')
  })

  it('formats zero', () => {
    expect(formatEUR(0)).toBe('0,00 €')
  })
})

describe('formatPercent', () => {
  it('formats a percentage with one decimal place using a comma', () => {
    expect(formatPercent(66.666)).toBe('66,7%')
  })

  it('formats a negative percentage', () => {
    expect(formatPercent(-5.25)).toBe('-5,3%')
  })
})
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `npm test -- src/format.test.ts`
Expected: FAIL con `Cannot find module './format'`.

- [ ] **Step 3: Implementar `format.ts`**

Crear `frontend/src/format.ts`:

```ts
const eurFormatter = new Intl.NumberFormat('es-ES', {
  style: 'currency',
  currency: 'EUR',
})

const percentFormatter = new Intl.NumberFormat('es-ES', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
})

export function formatEUR(value: number): string {
  return eurFormatter.format(value)
}

export function formatPercent(value: number): string {
  return `${percentFormatter.format(value)}%`
}
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `npm test -- src/format.test.ts`
Expected: PASS — 4 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/format.ts frontend/src/format.test.ts
git commit -m "feat(frontend): formatEUR/formatPercent compartidos (locale es-ES)"
```

---

### Task 8: Tema oscuro + `LegalBanner`

**Files:**
- Create: `frontend/src/styles/theme.css`
- Create: `frontend/src/components/LegalBanner.tsx`
- Create: `frontend/src/components/LegalBanner.module.css`
- Test: `frontend/src/components/LegalBanner.test.tsx`

**Interfaces:**
- Consumes: nada.
- Produces: `LEGAL_DISCLAIMER: string` (el texto legal exacto, reutilizado por `RecommendationPanel` en la Task 12), componente `LegalBanner()`, variables CSS globales en `theme.css` (`--color-bg`, `--color-surface`, `--color-border`, `--color-text`, `--color-text-muted`, `--color-up`, `--color-down`, `--color-accent`, `--font-sans`, `--font-mono`, `--radius`, `--spacing-1..4`) y la clase utilitaria `.tabular-nums`.

- [ ] **Step 1: Crear el tema compartido**

Crear `frontend/src/styles/theme.css`:

```css
:root {
  --color-bg: #0d1117;
  --color-surface: #161b22;
  --color-border: #30363d;
  --color-text: #e6edf3;
  --color-text-muted: #8b949e;
  --color-up: #3fb950;
  --color-down: #f85149;
  --color-accent: #58a6ff;
  --font-sans: system-ui, -apple-system, 'Segoe UI', sans-serif;
  --font-mono: 'SFMono-Regular', Consolas, 'Liberation Mono', monospace;
  --radius: 8px;
  --spacing-1: 4px;
  --spacing-2: 8px;
  --spacing-3: 16px;
  --spacing-4: 24px;
}

body {
  background-color: var(--color-bg);
  color: var(--color-text);
  font-family: var(--font-sans);
  margin: 0;
}

.tabular-nums {
  font-variant-numeric: tabular-nums;
  font-family: var(--font-mono);
}
```

- [ ] **Step 2: Escribir el test que falla para `LegalBanner`**

Crear `frontend/src/components/LegalBanner.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { LegalBanner, LEGAL_DISCLAIMER } from './LegalBanner'

describe('LegalBanner', () => {
  it('renders the exact legal disclaimer text', () => {
    render(<LegalBanner />)
    expect(screen.getByText(LEGAL_DISCLAIMER)).toBeInTheDocument()
  })

  it('uses the exact required wording', () => {
    expect(LEGAL_DISCLAIMER).toBe(
      'Simulación educativa, no es asesoramiento financiero. Capital ficticio.'
    )
  })
})
```

- [ ] **Step 3: Ejecutar el test para verificar que falla**

Run: `npm test -- src/components/LegalBanner.test.tsx`
Expected: FAIL con `Cannot find module './LegalBanner'`.

- [ ] **Step 4: Implementar `LegalBanner`**

Crear `frontend/src/components/LegalBanner.module.css`:

```css
.banner {
  background-color: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  color: var(--color-text-muted);
  font-size: 0.85rem;
  padding: var(--spacing-2) var(--spacing-3);
  text-align: center;
}
```

Crear `frontend/src/components/LegalBanner.tsx`:

```tsx
import styles from './LegalBanner.module.css'

export const LEGAL_DISCLAIMER =
  'Simulación educativa, no es asesoramiento financiero. Capital ficticio.'

export function LegalBanner() {
  return <div className={styles.banner}>{LEGAL_DISCLAIMER}</div>
}
```

- [ ] **Step 5: Ejecutar el test para verificar que pasa**

Run: `npm test -- src/components/LegalBanner.test.tsx`
Expected: PASS — 2 tests.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/styles/theme.css frontend/src/components/LegalBanner.tsx frontend/src/components/LegalBanner.module.css frontend/src/components/LegalBanner.test.tsx
git commit -m "feat(frontend): tema oscuro compartido + LegalBanner"
```

---

### Task 9: `PortfolioSummary`

**Files:**
- Create: `frontend/src/components/PortfolioSummary.tsx`
- Create: `frontend/src/components/PortfolioSummary.module.css`
- Test: `frontend/src/components/PortfolioSummary.test.tsx`

**Interfaces:**
- Consumes: `PortfolioOut` (Task 4), `formatEUR` (Task 7).
- Produces: `PortfolioSummary(props: { portfolio: PortfolioOut | undefined; isLoading: boolean; isError: boolean; onRetry: () => void })`.

**Nota sobre los importes de prueba:** se usan valores por debajo de 1000 (`990`, `500`, `15`, `505`) a propósito — `Intl.NumberFormat('es-ES', ...)` inserta un separador de millar a partir de 4 cifras enteras, y ese comportamiento de agrupación puede variar entre versiones de ICU/Node. Con 1-3 cifras enteras el resultado es determinista en cualquier entorno.

- [ ] **Step 1: Escribir el test que falla**

Crear `frontend/src/components/PortfolioSummary.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { PortfolioSummary } from './PortfolioSummary'

const portfolio = {
  cash_balance: 990,
  initial_capital: 500,
  open_predictions_value: 15,
  total_value: 505,
}

describe('PortfolioSummary', () => {
  it('shows a loading state', () => {
    render(<PortfolioSummary portfolio={undefined} isLoading isError={false} onRetry={vi.fn()} />)
    expect(screen.getByText(/cargando portfolio/i)).toBeInTheDocument()
  })

  it('shows the portfolio values once loaded', () => {
    render(<PortfolioSummary portfolio={portfolio} isLoading={false} isError={false} onRetry={vi.fn()} />)
    expect(screen.getByText('990,00 €')).toBeInTheDocument()
    expect(screen.getByText('505,00 €')).toBeInTheDocument()
  })

  it('shows an error with a retry button that calls onRetry', async () => {
    const onRetry = vi.fn()
    render(<PortfolioSummary portfolio={undefined} isLoading={false} isError onRetry={onRetry} />)

    expect(screen.getByText(/no se pudo conectar/i)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /reintentar/i }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })
})
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `npm test -- src/components/PortfolioSummary.test.tsx`
Expected: FAIL con `Cannot find module './PortfolioSummary'`.

- [ ] **Step 3: Implementar `PortfolioSummary`**

Crear `frontend/src/components/PortfolioSummary.module.css`:

```css
.panel {
  background-color: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: var(--spacing-3);
}

.grid {
  column-gap: var(--spacing-3);
  display: grid;
  grid-template-columns: 1fr auto;
  margin: 0;
  row-gap: var(--spacing-2);
}

.grid dt {
  color: var(--color-text-muted);
}

.grid dd {
  margin: 0;
  text-align: right;
}
```

Crear `frontend/src/components/PortfolioSummary.tsx`:

```tsx
import type { PortfolioOut } from '../api/types'
import { formatEUR } from '../format'
import styles from './PortfolioSummary.module.css'

interface PortfolioSummaryProps {
  portfolio: PortfolioOut | undefined
  isLoading: boolean
  isError: boolean
  onRetry: () => void
}

export function PortfolioSummary({ portfolio, isLoading, isError, onRetry }: PortfolioSummaryProps) {
  if (isLoading) {
    return <section className={styles.panel}>Cargando portfolio...</section>
  }

  if (isError || !portfolio) {
    return (
      <section className={styles.panel}>
        <p>No se pudo conectar con la API.</p>
        <button type="button" onClick={onRetry}>
          Reintentar
        </button>
      </section>
    )
  }

  return (
    <section className={styles.panel}>
      <h2>Portfolio</h2>
      <dl className={styles.grid}>
        <dt>Caja</dt>
        <dd className="tabular-nums">{formatEUR(portfolio.cash_balance)}</dd>
        <dt>Capital inicial</dt>
        <dd className="tabular-nums">{formatEUR(portfolio.initial_capital)}</dd>
        <dt>Valor abierto</dt>
        <dd className="tabular-nums">{formatEUR(portfolio.open_predictions_value)}</dd>
        <dt>Valor total</dt>
        <dd className="tabular-nums">{formatEUR(portfolio.total_value)}</dd>
      </dl>
    </section>
  )
}
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `npm test -- src/components/PortfolioSummary.test.tsx`
Expected: PASS — 3 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/PortfolioSummary.tsx frontend/src/components/PortfolioSummary.module.css frontend/src/components/PortfolioSummary.test.tsx
git commit -m "feat(frontend): componente PortfolioSummary"
```

---

### Task 10: `MetricsPanel`

**Files:**
- Create: `frontend/src/components/MetricsPanel.tsx`
- Create: `frontend/src/components/MetricsPanel.module.css`
- Test: `frontend/src/components/MetricsPanel.test.tsx`

**Interfaces:**
- Consumes: `MetricsOut` (Task 4), `formatPercent` (Task 7).
- Produces: `MetricsPanel(props: { metrics: MetricsOut | undefined; isLoading: boolean; isError: boolean; onRetry: () => void })`.

- [ ] **Step 1: Escribir el test que falla**

Crear `frontend/src/components/MetricsPanel.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MetricsPanel } from './MetricsPanel'

const metrics = {
  total_predictions: 5,
  settled: 3,
  hits: 2,
  hit_rate_pct: 66.7,
  total_invested: 30,
  total_final_value: 40,
  total_return_pct: 33.3,
}

describe('MetricsPanel', () => {
  it('shows a loading state', () => {
    render(<MetricsPanel metrics={undefined} isLoading isError={false} onRetry={vi.fn()} />)
    expect(screen.getByText(/cargando métricas/i)).toBeInTheDocument()
  })

  it('shows the metrics once loaded', () => {
    render(<MetricsPanel metrics={metrics} isLoading={false} isError={false} onRetry={vi.fn()} />)
    expect(screen.getByText('66,7%')).toBeInTheDocument()
    expect(screen.getByText('33,3%')).toBeInTheDocument()
    expect(screen.getByText('5')).toBeInTheDocument()
  })

  it('shows an error with a retry button that calls onRetry', async () => {
    const onRetry = vi.fn()
    render(<MetricsPanel metrics={undefined} isLoading={false} isError onRetry={onRetry} />)

    await userEvent.click(screen.getByRole('button', { name: /reintentar/i }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })
})
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `npm test -- src/components/MetricsPanel.test.tsx`
Expected: FAIL con `Cannot find module './MetricsPanel'`.

- [ ] **Step 3: Implementar `MetricsPanel`**

Crear `frontend/src/components/MetricsPanel.module.css`:

```css
.panel {
  background-color: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: var(--spacing-3);
}

.grid {
  column-gap: var(--spacing-3);
  display: grid;
  grid-template-columns: 1fr auto;
  margin: 0;
  row-gap: var(--spacing-2);
}

.grid dt {
  color: var(--color-text-muted);
}

.grid dd {
  margin: 0;
  text-align: right;
}

.up {
  color: var(--color-up);
}

.down {
  color: var(--color-down);
}
```

Crear `frontend/src/components/MetricsPanel.tsx`:

```tsx
import type { MetricsOut } from '../api/types'
import { formatPercent } from '../format'
import styles from './MetricsPanel.module.css'

interface MetricsPanelProps {
  metrics: MetricsOut | undefined
  isLoading: boolean
  isError: boolean
  onRetry: () => void
}

export function MetricsPanel({ metrics, isLoading, isError, onRetry }: MetricsPanelProps) {
  if (isLoading) {
    return <section className={styles.panel}>Cargando métricas...</section>
  }

  if (isError || !metrics) {
    return (
      <section className={styles.panel}>
        <p>No se pudo conectar con la API.</p>
        <button type="button" onClick={onRetry}>
          Reintentar
        </button>
      </section>
    )
  }

  return (
    <section className={styles.panel}>
      <h2>Métricas</h2>
      <dl className={styles.grid}>
        <dt>Predicciones totales</dt>
        <dd className="tabular-nums">{metrics.total_predictions}</dd>
        <dt>Liquidadas</dt>
        <dd className="tabular-nums">{metrics.settled}</dd>
        <dt>Aciertos</dt>
        <dd className="tabular-nums">{metrics.hits}</dd>
        <dt>Tasa de acierto</dt>
        <dd className="tabular-nums">{formatPercent(metrics.hit_rate_pct)}</dd>
        <dt>Retorno total</dt>
        <dd className={`tabular-nums ${metrics.total_return_pct >= 0 ? styles.up : styles.down}`}>
          {formatPercent(metrics.total_return_pct)}
        </dd>
      </dl>
    </section>
  )
}
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `npm test -- src/components/MetricsPanel.test.tsx`
Expected: PASS — 3 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/MetricsPanel.tsx frontend/src/components/MetricsPanel.module.css frontend/src/components/MetricsPanel.test.tsx
git commit -m "feat(frontend): componente MetricsPanel"
```

---

### Task 11: `PredictionsTable`

**Files:**
- Create: `frontend/src/components/PredictionsTable.tsx`
- Create: `frontend/src/components/PredictionsTable.module.css`
- Test: `frontend/src/components/PredictionsTable.test.tsx`

**Interfaces:**
- Consumes: `PredictionOut` (Task 4), `parseApiDate` (Task 2), `formatEUR` (Task 7).
- Produces: `PredictionsTable(props: { predictions: PredictionOut[] | undefined; isLoading: boolean; isError: boolean; onRetry: () => void })`. No reordena — el orden ya lo fija `usePredictions` (Task 5).

- [ ] **Step 1: Escribir el test que falla**

Crear `frontend/src/components/PredictionsTable.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { PredictionsTable } from './PredictionsTable'
import type { PredictionOut } from '../api/types'

function prediction(overrides: Partial<PredictionOut>): PredictionOut {
  return {
    id: 1,
    symbol: 'AAPL',
    created_at: '2026-07-22T10:00:00Z',
    entry_price: 100,
    amount: 10,
    shares: 0.1,
    horizon: '1D',
    evaluate_at: '2026-07-23T10:00:00Z',
    expected_direction: 'up',
    confidence: 0.5,
    rationale: '',
    status: 'open',
    exit_price: null,
    final_value: null,
    pnl_pct: null,
    hit: null,
    current_value: null,
    ...overrides,
  }
}

describe('PredictionsTable', () => {
  it('shows a loading state', () => {
    render(<PredictionsTable predictions={undefined} isLoading isError={false} onRetry={vi.fn()} />)
    expect(screen.getByText(/cargando predicciones/i)).toBeInTheDocument()
  })

  it('shows an empty state when there are no predictions', () => {
    render(<PredictionsTable predictions={[]} isLoading={false} isError={false} onRetry={vi.fn()} />)
    expect(screen.getByText(/todavía no hay predicciones/i)).toBeInTheDocument()
  })

  it('shows an error with a retry button that calls onRetry', async () => {
    const onRetry = vi.fn()
    render(<PredictionsTable predictions={undefined} isLoading={false} isError onRetry={onRetry} />)

    await userEvent.click(screen.getByRole('button', { name: /reintentar/i }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('shows current_value for an open prediction', () => {
    render(
      <PredictionsTable
        predictions={[prediction({ status: 'open', current_value: 12 })]}
        isLoading={false}
        isError={false}
        onRetry={vi.fn()}
      />
    )
    expect(screen.getByText('Abierta')).toBeInTheDocument()
    expect(screen.getByText('12,00 €')).toBeInTheDocument()
  })

  it('shows final_value for a settled prediction', () => {
    render(
      <PredictionsTable
        predictions={[
          prediction({ status: 'settled', current_value: null, final_value: 9, pnl_pct: -10, hit: false }),
        ]}
        isLoading={false}
        isError={false}
        onRetry={vi.fn()}
      />
    )
    expect(screen.getByText('Liquidada')).toBeInTheDocument()
    expect(screen.getByText('9,00 €')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `npm test -- src/components/PredictionsTable.test.tsx`
Expected: FAIL con `Cannot find module './PredictionsTable'`.

- [ ] **Step 3: Implementar `PredictionsTable`**

Crear `frontend/src/components/PredictionsTable.module.css`:

```css
.panel {
  background-color: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: var(--spacing-3);
}

.table {
  border-collapse: collapse;
  width: 100%;
}

.table th {
  color: var(--color-text-muted);
  font-weight: normal;
  text-align: left;
}

.table th,
.table td {
  border-bottom: 1px solid var(--color-border);
  padding: var(--spacing-2);
}

.open {
  color: var(--color-accent);
}

.settled {
  color: var(--color-text-muted);
}
```

Crear `frontend/src/components/PredictionsTable.tsx`:

```tsx
import type { PredictionOut } from '../api/types'
import { parseApiDate } from '../api/dates'
import { formatEUR } from '../format'
import styles from './PredictionsTable.module.css'

interface PredictionsTableProps {
  predictions: PredictionOut[] | undefined
  isLoading: boolean
  isError: boolean
  onRetry: () => void
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('es-ES', { dateStyle: 'short', timeStyle: 'short' }).format(
    parseApiDate(value)
  )
}

export function PredictionsTable({ predictions, isLoading, isError, onRetry }: PredictionsTableProps) {
  if (isLoading) {
    return <section className={styles.panel}>Cargando predicciones...</section>
  }

  if (isError || !predictions) {
    return (
      <section className={styles.panel}>
        <p>No se pudo conectar con la API.</p>
        <button type="button" onClick={onRetry}>
          Reintentar
        </button>
      </section>
    )
  }

  if (predictions.length === 0) {
    return (
      <section className={styles.panel}>
        <h2>Predicciones</h2>
        <p>Todavía no hay predicciones abiertas.</p>
      </section>
    )
  }

  return (
    <section className={styles.panel}>
      <h2>Predicciones</h2>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Símbolo</th>
            <th>Fecha</th>
            <th>Importe</th>
            <th>Estado</th>
            <th>Valor</th>
          </tr>
        </thead>
        <tbody>
          {predictions.map((prediction) => {
            const value =
              prediction.status === 'open' ? prediction.current_value : prediction.final_value
            return (
              <tr key={prediction.id}>
                <td>{prediction.symbol}</td>
                <td>{formatDate(prediction.created_at)}</td>
                <td className="tabular-nums">{formatEUR(prediction.amount)}</td>
                <td className={prediction.status === 'open' ? styles.open : styles.settled}>
                  {prediction.status === 'open' ? 'Abierta' : 'Liquidada'}
                </td>
                <td className="tabular-nums">{value !== null ? formatEUR(value) : '—'}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </section>
  )
}
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `npm test -- src/components/PredictionsTable.test.tsx`
Expected: PASS — 5 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/PredictionsTable.tsx frontend/src/components/PredictionsTable.module.css frontend/src/components/PredictionsTable.test.tsx
git commit -m "feat(frontend): componente PredictionsTable"
```

---

### Task 12: `RecommendationPanel` — el bucle recomendación → aceptar

**Files:**
- Create: `frontend/src/components/RecommendationPanel.tsx`
- Create: `frontend/src/components/RecommendationPanel.module.css`
- Test: `frontend/src/components/RecommendationPanel.test.tsx`

**Interfaces:**
- Consumes: `useRecommendation`, `useOpenPrediction` (Task 6), `LEGAL_DISCLAIMER` (Task 8), `formatEUR`/`formatPercent` (Task 7), `ApiError` (Task 3).
- Produces: `RecommendationPanel()` — sin props, autocontenido.

- [ ] **Step 1: Escribir el test que falla**

Crear `frontend/src/components/RecommendationPanel.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RecommendationPanel } from './RecommendationPanel'
import { useRecommendation } from '../hooks/useRecommendation'
import { useOpenPrediction } from '../hooks/useOpenPrediction'
import { ApiError } from '../api/errors'

vi.mock('../hooks/useRecommendation')
vi.mock('../hooks/useOpenPrediction')

const mockedUseRecommendation = vi.mocked(useRecommendation)
const mockedUseOpenPrediction = vi.mocked(useOpenPrediction)

function recommendationMutation(overrides: Record<string, unknown> = {}) {
  return {
    data: undefined,
    error: null,
    isPending: false,
    isError: false,
    mutate: vi.fn(),
    reset: vi.fn(),
    ...overrides,
  } as unknown as ReturnType<typeof useRecommendation>
}

function openPredictionMutation(overrides: Record<string, unknown> = {}) {
  return {
    data: undefined,
    error: null,
    isPending: false,
    isError: false,
    mutate: vi.fn(),
    reset: vi.fn(),
    ...overrides,
  } as unknown as ReturnType<typeof useOpenPrediction>
}

beforeEach(() => {
  mockedUseRecommendation.mockReturnValue(recommendationMutation())
  mockedUseOpenPrediction.mockReturnValue(openPredictionMutation())
})

describe('RecommendationPanel', () => {
  it('requests a recommendation for the typed symbol, uppercased', async () => {
    const mutate = vi.fn()
    mockedUseRecommendation.mockReturnValue(recommendationMutation({ mutate }))

    render(<RecommendationPanel />)
    await userEvent.type(screen.getByLabelText(/símbolo/i), 'aapl')
    await userEvent.click(screen.getByRole('button', { name: /pedir recomendación/i }))

    expect(mutate).toHaveBeenCalledWith('AAPL')
  })

  it('shows an error message when the recommendation request fails', () => {
    mockedUseRecommendation.mockReturnValue(
      recommendationMutation({ isError: true, error: new ApiError(404, 'Simbolo desconocido: NOPE') })
    )

    render(<RecommendationPanel />)

    expect(screen.getByRole('alert')).toHaveTextContent('Simbolo desconocido: NOPE')
  })

  it('shows the recommendation card with the legal disclaimer and an accept button once it resolves', () => {
    mockedUseRecommendation.mockReturnValue(
      recommendationMutation({
        data: {
          symbol: 'AAPL',
          direction: 'up',
          confidence: 0.5,
          suggested_amount: 10,
          horizon: '1D',
          rationale: 'motivo de prueba',
        },
      })
    )

    render(<RecommendationPanel />)

    expect(screen.getByText(/motivo de prueba/)).toBeInTheDocument()
    expect(
      screen.getByText('Simulación educativa, no es asesoramiento financiero. Capital ficticio.')
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /aceptar predicción/i })).toBeInTheDocument()
  })

  it('accepts the recommendation as-is when clicking Aceptar', async () => {
    const mutate = vi.fn()
    mockedUseRecommendation.mockReturnValue(
      recommendationMutation({
        data: {
          symbol: 'AAPL',
          direction: 'up',
          confidence: 0.5,
          suggested_amount: 10,
          horizon: '1D',
          rationale: 'motivo',
        },
      })
    )
    mockedUseOpenPrediction.mockReturnValue(openPredictionMutation({ mutate }))

    render(<RecommendationPanel />)
    await userEvent.click(screen.getByRole('button', { name: /aceptar predicción/i }))

    expect(mutate).toHaveBeenCalledWith(
      {
        symbol: 'AAPL',
        amount: 10,
        direction: 'up',
        confidence: 0.5,
        horizon: '1D',
        rationale: 'motivo',
      },
      expect.anything()
    )
  })

  it('shows an insufficient funds error without discarding the recommendation card', () => {
    mockedUseRecommendation.mockReturnValue(
      recommendationMutation({
        data: {
          symbol: 'AAPL',
          direction: 'up',
          confidence: 0.5,
          suggested_amount: 10,
          horizon: '1D',
          rationale: 'motivo',
        },
      })
    )
    mockedUseOpenPrediction.mockReturnValue(
      openPredictionMutation({ isError: true, error: new ApiError(400, 'amount 10000.0 > cash 990.0') })
    )

    render(<RecommendationPanel />)

    expect(screen.getByRole('alert')).toHaveTextContent('amount 10000.0 > cash 990.0')
    expect(screen.getByRole('button', { name: /aceptar predicción/i })).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `npm test -- src/components/RecommendationPanel.test.tsx`
Expected: FAIL con `Cannot find module './RecommendationPanel'`.

- [ ] **Step 3: Implementar `RecommendationPanel`**

Crear `frontend/src/components/RecommendationPanel.module.css`:

```css
.panel {
  background-color: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  padding: var(--spacing-3);
}

.form {
  align-items: center;
  display: flex;
  gap: var(--spacing-2);
}

.form input {
  background-color: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  color: var(--color-text);
  padding: var(--spacing-2);
  text-transform: uppercase;
}

.card {
  border-top: 1px solid var(--color-border);
  margin-top: var(--spacing-3);
  padding-top: var(--spacing-3);
}

.up {
  color: var(--color-up);
}

.down {
  color: var(--color-down);
}

.rationale {
  color: var(--color-text-muted);
}

.disclaimer {
  color: var(--color-text-muted);
  font-size: 0.75rem;
}

.error {
  color: var(--color-down);
}
```

Crear `frontend/src/components/RecommendationPanel.tsx`:

```tsx
import { useState, type FormEvent } from 'react'
import { useRecommendation } from '../hooks/useRecommendation'
import { useOpenPrediction } from '../hooks/useOpenPrediction'
import { LEGAL_DISCLAIMER } from './LegalBanner'
import { formatEUR, formatPercent } from '../format'
import styles from './RecommendationPanel.module.css'

export function RecommendationPanel() {
  const [symbol, setSymbol] = useState('')
  const recommendation = useRecommendation()
  const openPrediction = useOpenPrediction()

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmed = symbol.trim()
    if (!trimmed) return
    openPrediction.reset()
    recommendation.mutate(trimmed.toUpperCase())
  }

  function handleAccept() {
    const data = recommendation.data
    if (!data) return
    openPrediction.mutate(
      {
        symbol: data.symbol,
        amount: data.suggested_amount,
        direction: data.direction,
        confidence: data.confidence,
        horizon: data.horizon,
        rationale: data.rationale,
      },
      {
        onSuccess: () => {
          recommendation.reset()
          setSymbol('')
        },
      }
    )
  }

  return (
    <section className={styles.panel}>
      <h2>Nueva recomendación</h2>
      <form onSubmit={handleSubmit} className={styles.form}>
        <label htmlFor="symbol">Símbolo</label>
        <input
          id="symbol"
          value={symbol}
          onChange={(event) => setSymbol(event.target.value)}
          placeholder="AAPL"
        />
        <button type="submit" disabled={recommendation.isPending || !symbol.trim()}>
          {recommendation.isPending ? 'Pidiendo...' : 'Pedir recomendación'}
        </button>
      </form>

      {recommendation.isError && (
        <p role="alert" className={styles.error}>
          {recommendation.error.message}
        </p>
      )}

      {recommendation.data && (
        <div className={styles.card}>
          <p className={recommendation.data.direction === 'up' ? styles.up : styles.down}>
            {recommendation.data.symbol} {recommendation.data.direction === 'up' ? '↑' : '↓'} (
            {formatPercent(recommendation.data.confidence * 100)} confianza)
          </p>
          <p>Importe sugerido: {formatEUR(recommendation.data.suggested_amount)}</p>
          <p>Horizonte: {recommendation.data.horizon}</p>
          <p className={styles.rationale}>{recommendation.data.rationale}</p>
          <p className={styles.disclaimer}>{LEGAL_DISCLAIMER}</p>

          {openPrediction.isError && (
            <p role="alert" className={styles.error}>
              {openPrediction.error.message}
            </p>
          )}

          <button type="button" onClick={handleAccept} disabled={openPrediction.isPending}>
            {openPrediction.isPending ? 'Aceptando...' : 'Aceptar predicción'}
          </button>
        </div>
      )}
    </section>
  )
}
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `npm test -- src/components/RecommendationPanel.test.tsx`
Expected: PASS — 5 tests.

- [ ] **Step 5: Ejecutar la suite completa**

Run: `npm test`
Expected: PASS — todos los tests de las Tasks 1-12.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/RecommendationPanel.tsx frontend/src/components/RecommendationPanel.module.css frontend/src/components/RecommendationPanel.test.tsx
git commit -m "feat(frontend): RecommendationPanel - bucle recomendacion-aceptar"
```

---

### Task 13: `App.tsx` + `main.tsx` — composición final, README y cierre de fase

**Files:**
- Modify: `frontend/src/App.tsx` (reemplaza el scaffold)
- Create: `frontend/src/App.module.css`
- Modify: `frontend/src/App.test.tsx` (reemplaza el smoke test de la Task 1)
- Modify: `frontend/src/main.tsx`
- Delete: `frontend/src/App.css`, `frontend/src/index.css`
- Modify: `frontend/index.html` (título)
- Create: `frontend/README.md`
- Create: `frontend/.env.example`
- Modify: `CLAUDE.md` (raíz del repo)

**Interfaces:**
- Consumes: todo lo de las Tasks 1-12.
- Produces: dashboard completo funcionando; cierra la fase.

- [ ] **Step 1: Escribir el test que falla para el `App` real**

Reemplazar `frontend/src/App.test.tsx` completo:

```tsx
import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { usePortfolio } from './hooks/usePortfolio'
import { usePredictions } from './hooks/usePredictions'
import { useMetrics } from './hooks/useMetrics'
import { useRecommendation } from './hooks/useRecommendation'
import { useOpenPrediction } from './hooks/useOpenPrediction'
import { LEGAL_DISCLAIMER } from './components/LegalBanner'

vi.mock('./hooks/usePortfolio')
vi.mock('./hooks/usePredictions')
vi.mock('./hooks/useMetrics')
vi.mock('./hooks/useRecommendation')
vi.mock('./hooks/useOpenPrediction')

function query(overrides: Record<string, unknown> = {}) {
  return {
    data: undefined,
    isPending: false,
    isError: false,
    refetch: vi.fn(),
    ...overrides,
  } as unknown as ReturnType<typeof usePortfolio>
}

function mutation(overrides: Record<string, unknown> = {}) {
  return {
    data: undefined,
    error: null,
    isPending: false,
    isError: false,
    mutate: vi.fn(),
    reset: vi.fn(),
    ...overrides,
  } as unknown as ReturnType<typeof useRecommendation>
}

beforeEach(() => {
  vi.mocked(usePortfolio).mockReturnValue(
    query({
      data: { cash_balance: 990, initial_capital: 500, open_predictions_value: 15, total_value: 505 },
    })
  )
  vi.mocked(usePredictions).mockReturnValue(query({ data: [] }))
  vi.mocked(useMetrics).mockReturnValue(
    query({
      data: {
        total_predictions: 0,
        settled: 0,
        hits: 0,
        hit_rate_pct: 0,
        total_invested: 0,
        total_final_value: 0,
        total_return_pct: 0,
      },
    })
  )
  vi.mocked(useRecommendation).mockReturnValue(mutation())
  vi.mocked(useOpenPrediction).mockReturnValue(
    mutation() as unknown as ReturnType<typeof useOpenPrediction>
  )
})

describe('App', () => {
  it('renders the legal banner and every dashboard panel', () => {
    render(<App />)

    expect(screen.getAllByText(LEGAL_DISCLAIMER)[0]).toBeInTheDocument()
    expect(screen.getByText('Portfolio')).toBeInTheDocument()
    expect(screen.getByText('Métricas')).toBeInTheDocument()
    expect(screen.getByText(/todavía no hay predicciones/i)).toBeInTheDocument()
    expect(screen.getByText('505,00 €')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `npm test -- src/App.test.tsx`
Expected: FAIL — el `App.tsx` actual (scaffold) no usa ninguno de estos hooks ni renderiza estos textos.

- [ ] **Step 3: Reemplazar `App.tsx` y crear su hoja de estilos**

Crear `frontend/src/App.module.css`:

```css
.app {
  min-height: 100vh;
}

.main {
  display: grid;
  gap: var(--spacing-4);
  margin: 0 auto;
  max-width: 960px;
  padding: var(--spacing-4);
}

.main h1 {
  margin: 0;
}
```

Reemplazar `frontend/src/App.tsx` completo:

```tsx
import { LegalBanner } from './components/LegalBanner'
import { RecommendationPanel } from './components/RecommendationPanel'
import { PortfolioSummary } from './components/PortfolioSummary'
import { PredictionsTable } from './components/PredictionsTable'
import { MetricsPanel } from './components/MetricsPanel'
import { usePortfolio } from './hooks/usePortfolio'
import { usePredictions } from './hooks/usePredictions'
import { useMetrics } from './hooks/useMetrics'
import styles from './App.module.css'

function App() {
  const portfolio = usePortfolio()
  const predictions = usePredictions()
  const metrics = useMetrics()

  return (
    <div className={styles.app}>
      <LegalBanner />
      <main className={styles.main}>
        <h1>InvestSim</h1>
        <RecommendationPanel />
        <PortfolioSummary
          portfolio={portfolio.data}
          isLoading={portfolio.isPending}
          isError={portfolio.isError}
          onRetry={() => portfolio.refetch()}
        />
        <MetricsPanel
          metrics={metrics.data}
          isLoading={metrics.isPending}
          isError={metrics.isError}
          onRetry={() => metrics.refetch()}
        />
        <PredictionsTable
          predictions={predictions.data}
          isLoading={predictions.isPending}
          isError={predictions.isError}
          onRetry={() => predictions.refetch()}
        />
      </main>
    </div>
  )
}

export default App
```

- [ ] **Step 4: Eliminar CSS del scaffold que ya no se usa**

Run: `rm frontend/src/App.css frontend/src/index.css`

- [ ] **Step 5: Actualizar `main.tsx`**

Reemplazar `frontend/src/main.tsx` completo:

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App.tsx'
import './styles/theme.css'

const queryClient = new QueryClient()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>
)
```

- [ ] **Step 6: Actualizar el título de `index.html`**

En `frontend/index.html`, cambiar `<title>Vite + React + TS</title>` (o el título que traiga el scaffold) por:

```html
<title>InvestSim</title>
```

- [ ] **Step 7: Ejecutar el test para verificar que pasa**

Run: `npm test -- src/App.test.tsx`
Expected: PASS — 1 test.

- [ ] **Step 8: Ejecutar la suite completa**

Run: `npm test`
Expected: PASS — todos los tests de las Tasks 1-13.

- [ ] **Step 9: Crear `.env.example`**

Crear `frontend/.env.example`:

```
VITE_API_URL=http://127.0.0.1:8000
```

- [ ] **Step 10: Crear el README del frontend**

Crear `frontend/README.md`:

```markdown
# InvestSim — Frontend

Dashboard React (Vite) que consume la API FastAPI de InvestSim (`investsim/api/`).

## Desarrollo

Con el backend corriendo (desde la raíz del repo: `python -m uvicorn investsim.api.app:app --reload`):

\`\`\`bash
npm install
npm run dev
\`\`\`

**Importante:** abre el dashboard en `http://localhost:5173`, **no** en `http://127.0.0.1:5173`. El backend solo permite CORS desde orígenes que coincidan con `http://localhost:<puerto>` (`allow_origin_regex` en `investsim/api/app.py`). Si abres por `127.0.0.1`, todas las llamadas a la API se bloquean por CORS sin más explicación en la UI — solo se ve en la consola del navegador.

## Variables de entorno

- `VITE_API_URL` — URL base de la API FastAPI. Por defecto `http://127.0.0.1:8000` si no se define. Ver `.env.example`.

## Tests

\`\`\`bash
npm test
\`\`\`

Sin red real: `fetch` se mockea en todos los tests (ver `src/api/client.test.ts` y los tests de hooks/componentes).
```

- [ ] **Step 11: Smoke manual con el backend real**

Con el backend arrancado (`python -m uvicorn investsim.api.app:app --reload` desde la raíz del repo, con `FINNHUB_API_KEY` configurada):

Run: `npm run dev`
Luego abrir `http://localhost:5173` en el navegador.

Expected: se ve el aviso legal arriba, el formulario de recomendación, y los paneles de portfolio/métricas/predicciones (vacíos o con el estado inicial). Pedir una recomendación para `AAPL` debe mostrar la tarjeta con dirección/confianza/importe/motivo; al pulsar "Aceptar predicción" debe actualizarse el portfolio y aparecer la fila en la tabla de predicciones. Sin errores de CORS en la consola del navegador (si aparecen, comprobar que la URL es `localhost` y no `127.0.0.1`).

- [ ] **Step 12: Actualizar `CLAUDE.md` (raíz del repo)**

En la sección `## Layout`, reemplazar la línea de `frontend/`:

```markdown
- `frontend/` — dashboard React (Vite) que consume la API FastAPI (`investsim/api/`). Ver `frontend/README.md`.
```

En `## Comandos`, añadir al final:

```markdown
Frontend (desde `frontend/`, con el backend corriendo en paralelo vía uvicorn):

\`\`\`bash
npm install
npm run dev       # http://localhost:5173 -- IMPORTANTE: no uses 127.0.0.1 (ver frontend/README.md, CORS)
npm test          # suite de Vitest
\`\`\`
```

En `## Evolución futura`, reemplazar la línea de fases:

```markdown
Fases planificadas tras el núcleo de dominio (Fase 1): **F2** datos reales (Finnhub) · **F3a** agente por reglas (hecho: `RuleBasedEngine` + `AgentService`, sin LLM) · **F3b** motor LLM local (Ollama) como segunda implementación de `RecommendationEngine` · **F4** API FastAPI (hecho: 5 endpoints REST sobre `AgentService`/`PortfolioService`/`SettlementService`) · **F5** frontend React (hecho: dashboard único con TanStack Query, ver `frontend/README.md`) · **F6** pulido (observabilidad de coste, watchlist). Más adelante: agente híbrido ML+Claude, crypto/multi-activo, scheduler, Docker. Ver la sección "Evolución futura" del spec para el detalle.
```

- [ ] **Step 13: Commit de cierre**

```bash
git add frontend/ CLAUDE.md
git commit -m "feat(frontend): App.tsx compone el dashboard; README, .env.example y cierre de fase 5"
```
