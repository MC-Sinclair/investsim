from __future__ import annotations

from dataclasses import dataclass

from investsim.db.tables import PredictionRow


@dataclass(frozen=True)
class Metrics:
    total_predictions: int
    settled: int
    hits: int
    hit_rate_pct: float
    total_invested: float
    total_final_value: float
    total_return_pct: float


def compute_metrics(predictions: list[PredictionRow]) -> Metrics:
    settled = [p for p in predictions if p.status == "settled"]
    hits = sum(1 for p in settled if p.hit)
    hit_rate = (hits / len(settled) * 100) if settled else 0.0
    invested = sum(p.amount for p in settled)
    final_value = sum((p.final_value or 0.0) for p in settled)
    total_return = (
        (final_value - invested) / invested * 100 if invested else 0.0
    )
    return Metrics(
        total_predictions=len(predictions),
        settled=len(settled),
        hits=hits,
        hit_rate_pct=hit_rate,
        total_invested=invested,
        total_final_value=final_value,
        total_return_pct=total_return,
    )
