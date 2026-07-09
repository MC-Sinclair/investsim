from datetime import datetime, timezone

from investsim.db.tables import PredictionRow
from investsim.metrics import Metrics, compute_metrics

NOW = datetime(2026, 7, 7, tzinfo=timezone.utc)


def _settled(pnl_pct, hit, amount=10.0):
    final = amount * (1 + pnl_pct / 100)
    return PredictionRow(
        symbol="AAPL", created_at=NOW, entry_price=100.0, amount=amount,
        shares=amount / 100.0, horizon="1W", evaluate_at=NOW,
        expected_direction="up", confidence=0.7, rationale="", status="settled",
        exit_price=100.0 * (1 + pnl_pct / 100), final_value=final,
        pnl_pct=pnl_pct, hit=hit,
    )


def _open():
    return PredictionRow(
        symbol="AAPL", created_at=NOW, entry_price=100.0, amount=10.0,
        shares=0.1, horizon="1W", evaluate_at=NOW, expected_direction="up",
        confidence=0.7, rationale="", status="open",
    )


def test_empty_metrics():
    m = compute_metrics([])
    assert m == Metrics(0, 0, 0, 0.0, 0.0, 0.0, 0.0)


def test_metrics_ignores_open_and_computes_hit_rate_and_return():
    preds = [
        _settled(pnl_pct=34.0, hit=True),    # 10 -> 13.40
        _settled(pnl_pct=-10.0, hit=False),  # 10 -> 9.00
        _open(),                             # se ignora
    ]
    m = compute_metrics(preds)
    assert m.total_predictions == 3
    assert m.settled == 2
    assert m.hits == 1
    assert m.hit_rate_pct == 50.0
    assert round(m.total_invested, 2) == 20.0
    assert round(m.total_final_value, 2) == 22.40
    assert round(m.total_return_pct, 2) == 12.0
