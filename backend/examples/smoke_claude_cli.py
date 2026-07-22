"""Smoke manual: pide una recomendacion real al motor LLM (puente CLI de Claude Code).

Uso (desde la raiz del repo, con FINNHUB_API_KEY en .env y el CLI 'claude'
instalado y autenticado):
    python backend/examples/smoke_claude_cli.py AAPL
"""

from __future__ import annotations

import sys

from investsim.agent.claude_cli import ClaudeCliEngine
from investsim.config import load_finnhub_config
from investsim.providers.finnhub import FinnhubMarketDataProvider
from investsim.services.agent_service import AgentService

DISCLAIMER = (
    "Simulación educativa, no es asesoramiento financiero. Capital ficticio."
)


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    service = AgentService(
        FinnhubMarketDataProvider(load_finnhub_config()), ClaudeCliEngine()
    )
    rec = service.propose(symbol)

    print(f"Simbolo:   {rec.symbol}")
    print(f"Direccion: {rec.direction.value}  ({rec.horizon.value})")
    print(f"Confianza: {rec.confidence:.2%}")
    print(f"Importe:   {rec.suggested_amount:.2f} EUR")
    print(f"Motivo:    {rec.rationale}")
    print()
    print(DISCLAIMER)


if __name__ == "__main__":
    main()
