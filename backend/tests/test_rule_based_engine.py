from datetime import datetime, timezone

import pytest

from investsim.agent.rules import RuleBasedEngine
from investsim.domain.enums import Direction, Horizon
from investsim.providers.market_data import MarketSnapshot

AS_OF = datetime(2026, 7, 19, 15, 0, tzinfo=timezone.utc)


def _snapshot(
    dp: float,
    price: float,
    high: float,
    low: float,
    symbol: str = "AAPL",
) -> MarketSnapshot:
    return MarketSnapshot(
        symbol=symbol,
        price=price,
        day_change_pct=dp,
        day_high=high,
        day_low=low,
        day_open=low,
        prev_close=low,
        as_of=AS_OF,
    )


def test_positive_change_gives_direction_up():
    rec = RuleBasedEngine().propose(_snapshot(dp=1.5, price=102, high=104, low=100))
    assert rec.direction is Direction.UP
    assert rec.symbol == "AAPL"


def test_negative_change_gives_direction_down():
    rec = RuleBasedEngine().propose(_snapshot(dp=-2.0, price=100.5, high=105, low=100))
    assert rec.direction is Direction.DOWN


def test_horizon_is_always_one_day():
    rec = RuleBasedEngine().propose(_snapshot(dp=-2.0, price=100.5, high=105, low=100))
    assert rec.horizon is Horizon.ONE_DAY


def test_confidence_mid_range():
    """dp=1.5 => base 0.5; precio en mitad del rango => factor 0.75."""
    rec = RuleBasedEngine().propose(_snapshot(dp=1.5, price=102, high=104, low=100))
    assert rec.confidence == pytest.approx(0.375)


def test_range_position_confirms_direction_up():
    """Mismo dp, pero cotizando en máximos: confianza reforzada."""
    rec = RuleBasedEngine().propose(_snapshot(dp=1.5, price=104, high=104, low=100))
    assert rec.confidence == pytest.approx(0.5)


def test_range_position_contradicts_direction_up():
    """Mismo dp, pero cotizando en mínimos: confianza atenuada."""
    rec = RuleBasedEngine().propose(_snapshot(dp=1.5, price=100, high=104, low=100))
    assert rec.confidence == pytest.approx(0.25)


def test_range_position_confirms_direction_down():
    """dp=-2.0 => base 2/3; precio cerca del mínimo (rp=0.1) => factor 0.95."""
    rec = RuleBasedEngine().propose(_snapshot(dp=-2.0, price=100.5, high=105, low=100))
    assert rec.confidence == pytest.approx(0.6333333, abs=1e-6)


def test_zero_change_is_up_with_minimum_confidence():
    rec = RuleBasedEngine().propose(_snapshot(dp=0.0, price=100, high=104, low=100))
    assert rec.direction is Direction.UP
    assert rec.confidence == pytest.approx(0.05)


def test_flat_range_uses_neutral_position():
    """day_high == day_low: rp=0.5 neutral, sin división por cero."""
    rec = RuleBasedEngine().propose(_snapshot(dp=3.0, price=110, high=110, low=110))
    assert rec.confidence == pytest.approx(0.75)


def test_confidence_is_clamped_at_upper_bound():
    """dp enorme y precio en máximos saturarían a 1.0; el clamp lo deja en 0.95."""
    rec = RuleBasedEngine().propose(_snapshot(dp=10.0, price=110, high=110, low=105))
    assert rec.confidence == pytest.approx(0.95)


def test_suggested_amount_scales_with_confidence():
    rec = RuleBasedEngine().propose(_snapshot(dp=1.5, price=102, high=104, low=100))
    assert rec.suggested_amount == pytest.approx(20.0 * 0.375)


def test_base_amount_is_configurable():
    engine = RuleBasedEngine(base_amount=50.0)
    rec = engine.propose(_snapshot(dp=1.5, price=102, high=104, low=100))
    assert rec.suggested_amount == pytest.approx(50.0 * 0.375)


def test_rationale_mentions_symbol_change_and_range_high():
    rec = RuleBasedEngine().propose(_snapshot(dp=1.24, price=104, high=104, low=100))
    assert rec.rationale == (
        "AAPL sube 1.24% hoy y cotiza cerca de máximos del rango diario."
    )


def test_rationale_for_down_near_lows():
    rec = RuleBasedEngine().propose(_snapshot(dp=-2.0, price=100.5, high=105, low=100))
    assert rec.rationale == (
        "AAPL baja 2.00% hoy y cotiza cerca de mínimos del rango diario."
    )


def test_rationale_for_mid_range():
    rec = RuleBasedEngine().propose(_snapshot(dp=1.5, price=102, high=104, low=100))
    assert rec.rationale == (
        "AAPL sube 1.50% hoy y cotiza en la zona media del rango diario."
    )
