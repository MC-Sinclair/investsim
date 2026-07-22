from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends

from investsim.api.deps import get_agent_service, get_portfolio_service
from investsim.api.schemas import (
    OpenPredictionIn,
    PredictionOut,
    RecommendationIn,
    RecommendationOut,
)
from investsim.db.tables import PredictionRow
from investsim.services.agent_service import AgentService
from investsim.services.portfolio_service import PortfolioService

router = APIRouter()


def _prediction_to_out(
    pred: PredictionRow, current_value: float | None
) -> PredictionOut:
    return PredictionOut(
        id=pred.id,
        symbol=pred.symbol,
        created_at=pred.created_at,
        entry_price=pred.entry_price,
        amount=pred.amount,
        shares=pred.shares,
        horizon=pred.horizon,
        evaluate_at=pred.evaluate_at,
        expected_direction=pred.expected_direction,
        confidence=pred.confidence,
        rationale=pred.rationale,
        status=pred.status,
        exit_price=pred.exit_price,
        final_value=pred.final_value,
        pnl_pct=pred.pnl_pct,
        hit=pred.hit,
        current_value=current_value,
    )


@router.post("/recommendations", response_model=RecommendationOut)
def post_recommendation(
    body: RecommendationIn,
    agent_service: AgentService = Depends(get_agent_service),
) -> RecommendationOut:
    recommendation = agent_service.propose(body.symbol)
    return RecommendationOut(**asdict(recommendation))


@router.post("/predictions", response_model=PredictionOut)
def post_prediction(
    body: OpenPredictionIn,
    portfolio_service: PortfolioService = Depends(get_portfolio_service),
) -> PredictionOut:
    pred = portfolio_service.open_prediction(
        symbol=body.symbol,
        amount=body.amount,
        direction=body.direction,
        confidence=body.confidence,
        horizon=body.horizon,
        rationale=body.rationale,
    )
    return _prediction_to_out(pred, current_value=None)
