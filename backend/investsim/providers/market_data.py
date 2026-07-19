from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: float
    as_of: datetime


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    price: float
    day_change_pct: float
    day_high: float
    day_low: float
    day_open: float
    prev_close: float
    as_of: datetime


class MarketDataError(Exception):
    pass


class UnknownSymbol(MarketDataError):
    pass


class ProviderUnavailable(MarketDataError):
    pass


class MarketDataProvider(Protocol):
    def get_quote(self, symbol: str) -> Quote: ...

    def get_snapshot(self, symbol: str) -> MarketSnapshot: ...


class FakeMarketDataProvider:
    def __init__(
        self,
        prices: dict[str, float],
        as_of: datetime | None = None,
        snapshots: dict[str, MarketSnapshot] | None = None,
    ) -> None:
        self._prices = dict(prices)
        self._as_of = as_of or datetime.now(timezone.utc)
        self._snapshots = dict(snapshots or {})

    def set_price(self, symbol: str, price: float) -> None:
        self._prices[symbol] = price

    def set_snapshot(self, snapshot: MarketSnapshot) -> None:
        self._snapshots[snapshot.symbol] = snapshot

    def get_quote(self, symbol: str) -> Quote:
        if symbol not in self._prices:
            raise UnknownSymbol(symbol)
        return Quote(symbol=symbol, price=self._prices[symbol], as_of=self._as_of)

    def get_snapshot(self, symbol: str) -> MarketSnapshot:
        snapshot = self._snapshots.get(symbol)
        if snapshot is not None:
            return snapshot
        if symbol not in self._prices:
            raise UnknownSymbol(symbol)
        price = self._prices[symbol]
        return MarketSnapshot(
            symbol=symbol,
            price=price,
            day_change_pct=0.0,
            day_high=price,
            day_low=price,
            day_open=price,
            prev_close=price,
            as_of=self._as_of,
        )
