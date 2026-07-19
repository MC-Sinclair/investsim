from __future__ import annotations

from investsim.agent.engine import Recommendation
from investsim.domain.enums import Direction, Horizon
from investsim.providers.market_data import MarketSnapshot

# Un movimiento del ±3% satura la confianza de la señal de dp.
_DP_SATURATION = 3.0
_MIN_CONFIDENCE = 0.05
_MAX_CONFIDENCE = 0.95


def _range_label(range_position: float) -> str:
    if range_position >= 0.66:
        return "cerca de máximos del rango diario"
    if range_position <= 0.33:
        return "cerca de mínimos del rango diario"
    return "en la zona media del rango diario"


class RuleBasedEngine:
    """Motor determinista sobre señales intradía: dp + posición en el rango del día."""

    def __init__(self, base_amount: float = 20.0) -> None:
        self.base_amount = base_amount

    def propose(self, snapshot: MarketSnapshot) -> Recommendation:
        dp = snapshot.day_change_pct
        direction = Direction.UP if dp >= 0 else Direction.DOWN
        base_confidence = min(abs(dp) / _DP_SATURATION, 1.0)

        span = snapshot.day_high - snapshot.day_low
        if span == 0:
            range_position = 0.5
        else:
            range_position = (snapshot.price - snapshot.day_low) / span

        confirmation = (
            range_position if direction is Direction.UP else 1 - range_position
        )
        confidence = base_confidence * (0.5 + confirmation / 2)
        confidence = max(_MIN_CONFIDENCE, min(confidence, _MAX_CONFIDENCE))

        verb = "sube" if direction is Direction.UP else "baja"
        rationale = (
            f"{snapshot.symbol} {verb} {abs(dp):.2f}% hoy y cotiza "
            f"{_range_label(range_position)}."
        )

        return Recommendation(
            symbol=snapshot.symbol,
            direction=direction,
            confidence=confidence,
            suggested_amount=self.base_amount * confidence,
            horizon=Horizon.ONE_DAY,
            rationale=rationale,
        )
