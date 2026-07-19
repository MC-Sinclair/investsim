from __future__ import annotations

from investsim.agent.engine import Recommendation, RecommendationEngine
from investsim.providers.market_data import MarketDataProvider


class AgentService:
    """Orquesta datos → motor. No persiste nada y no atrapa errores del proveedor."""

    def __init__(
        self,
        market_data: MarketDataProvider,
        engine: RecommendationEngine,
    ) -> None:
        self.market_data = market_data
        self.engine = engine

    def propose(self, symbol: str) -> Recommendation:
        snapshot = self.market_data.get_snapshot(symbol)
        return self.engine.propose(snapshot)
