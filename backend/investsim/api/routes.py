from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends

from investsim.api.deps import get_agent_service
from investsim.api.schemas import RecommendationIn, RecommendationOut
from investsim.services.agent_service import AgentService

router = APIRouter()


@router.post("/recommendations", response_model=RecommendationOut)
def post_recommendation(
    body: RecommendationIn,
    agent_service: AgentService = Depends(get_agent_service),
) -> RecommendationOut:
    recommendation = agent_service.propose(body.symbol)
    return RecommendationOut(**asdict(recommendation))
