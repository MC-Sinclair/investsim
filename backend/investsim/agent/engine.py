from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from investsim.domain.enums import Direction, Horizon
from investsim.providers.market_data import MarketSnapshot


@dataclass(frozen=True)
class Recommendation:
    symbol: str
    direction: Direction
    confidence: float
    suggested_amount: float
    horizon: Horizon
    rationale: str


class RecommendationEngine(Protocol):
    def propose(self, snapshot: MarketSnapshot) -> Recommendation: ...
