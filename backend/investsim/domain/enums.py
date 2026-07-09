from __future__ import annotations

from datetime import timedelta
from enum import Enum


class Horizon(str, Enum):
    ONE_DAY = "1D"
    ONE_WEEK = "1W"
    ONE_MONTH = "1M"

    def to_timedelta(self) -> timedelta:
        return {
            Horizon.ONE_DAY: timedelta(days=1),
            Horizon.ONE_WEEK: timedelta(weeks=1),
            Horizon.ONE_MONTH: timedelta(days=30),
        }[self]


class Direction(str, Enum):
    UP = "up"
    DOWN = "down"


class Status(str, Enum):
    OPEN = "open"
    SETTLED = "settled"
