from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: float
    as_of: datetime


class UnknownSymbol(Exception):
    pass


class MarketDataProvider(Protocol):
    def get_quote(self, symbol: str) -> Quote: ...


class FakeMarketDataProvider:
    def __init__(
        self, prices: dict[str, float], as_of: datetime | None = None
    ) -> None:
        self._prices = dict(prices)
        self._as_of = as_of or datetime.now(timezone.utc)

    def set_price(self, symbol: str, price: float) -> None:
        self._prices[symbol] = price

    def get_quote(self, symbol: str) -> Quote:
        if symbol not in self._prices:
            raise UnknownSymbol(symbol)
        return Quote(symbol=symbol, price=self._prices[symbol], as_of=self._as_of)
