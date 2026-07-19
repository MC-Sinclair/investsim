from __future__ import annotations

from pydantic import BaseModel

from investsim.domain.enums import Direction, Horizon


class RecommendationIn(BaseModel):
    symbol: str


class RecommendationOut(BaseModel):
    symbol: str
    direction: Direction
    confidence: float
    suggested_amount: float
    horizon: Horizon
    rationale: str
