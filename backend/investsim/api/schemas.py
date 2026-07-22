from __future__ import annotations

from datetime import datetime

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


class OpenPredictionIn(BaseModel):
    symbol: str
    amount: float
    direction: Direction
    confidence: float
    horizon: Horizon
    rationale: str = ""


class PredictionOut(BaseModel):
    id: int
    symbol: str
    created_at: datetime
    entry_price: float
    amount: float
    shares: float
    horizon: str
    evaluate_at: datetime
    expected_direction: str
    confidence: float
    rationale: str
    status: str
    exit_price: float | None
    final_value: float | None
    pnl_pct: float | None
    hit: bool | None
    current_value: float | None = None


class PortfolioOut(BaseModel):
    cash_balance: float
    initial_capital: float
    open_predictions_value: float
    total_value: float
