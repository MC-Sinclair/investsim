# InvestSim — Frontend

Dashboard React (Vite) que consume la API FastAPI de InvestSim (`investsim/api/`).

## Desarrollo

Con el backend corriendo (desde la raíz del repo: `python -m uvicorn investsim.api.app:app --reload`):

```bash
npm install
npm run dev
```

**Importante:** abre el dashboard en `http://localhost:5173`, **no** en `http://127.0.0.1:5173`. El backend solo permite CORS desde orígenes que coincidan con `http://localhost:<puerto>` (`allow_origin_regex` en `investsim/api/app.py`). Si abres por `127.0.0.1`, todas las llamadas a la API se bloquean por CORS sin más explicación en la UI — solo se ve en la consola del navegador.

## Variables de entorno

- `VITE_API_URL` — URL base de la API FastAPI. Por defecto `http://127.0.0.1:8000` si no se define. Ver `.env.example`.

## Tests

```bash
npm test
```

Sin red real: `fetch` se mockea en todos los tests (ver `src/api/client.test.ts` y los tests de hooks/componentes).
