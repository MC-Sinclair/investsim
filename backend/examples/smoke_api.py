"""Smoke manual: bucle completo via la API HTTP, con Finnhub real.

Uso (desde la raiz del repo, con FINNHUB_API_KEY en .env):
    python backend/examples/smoke_api.py AAPL
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from investsim.api.app import create_app

DISCLAIMER = (
    "Simulación educativa, no es asesoramiento financiero. Capital ficticio."
)


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_path = (Path(tmp) / "smoke_api.db").as_posix()
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"

        app = create_app()
        with TestClient(app) as client:
            rec = client.post("/recommendations", json={"symbol": symbol}).json()
            print("Recomendacion:", rec)

            pred = client.post(
                "/predictions",
                json={
                    "symbol": symbol,
                    "amount": rec["suggested_amount"],
                    "direction": rec["direction"],
                    "confidence": rec["confidence"],
                    "horizon": rec["horizon"],
                    "rationale": rec["rationale"],
                },
            ).json()
            print("Prediccion abierta:", pred)

            print("Portfolio:", client.get("/portfolio").json())
            print("Predicciones:", client.get("/predictions").json())
            print("Metricas:", client.get("/metrics").json())

    print()
    print(DISCLAIMER)


if __name__ == "__main__":
    main()
