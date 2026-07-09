from datetime import timedelta

from investsim.domain.enums import Direction, Horizon, Status


def test_horizon_values():
    assert Horizon.ONE_DAY.value == "1D"
    assert Horizon.ONE_WEEK.value == "1W"
    assert Horizon.ONE_MONTH.value == "1M"


def test_horizon_to_timedelta():
    assert Horizon.ONE_DAY.to_timedelta() == timedelta(days=1)
    assert Horizon.ONE_WEEK.to_timedelta() == timedelta(weeks=1)
    assert Horizon.ONE_MONTH.to_timedelta() == timedelta(days=30)


def test_direction_and_status_values():
    assert Direction.UP.value == "up"
    assert Direction.DOWN.value == "down"
    assert Status.OPEN.value == "open"
    assert Status.SETTLED.value == "settled"
