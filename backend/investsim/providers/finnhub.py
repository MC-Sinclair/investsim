from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable

import httpx

from investsim.config import FinnhubConfig
from investsim.providers.market_data import (
    Quote,
    UnknownSymbol,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FinnhubMarketDataProvider:
    def __init__(
        self,
        config: FinnhubConfig,
        client: httpx.Client | None = None,
        clock: Callable[[], datetime] = _utcnow,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self.client = client or httpx.Client(
            base_url=config.base_url, timeout=config.timeout
        )
        self.clock = clock
        self.sleep = sleep

    def get_quote(self, symbol: str) -> Quote:
        response = self.client.get(
            "/quote", params={"symbol": symbol, "token": self.config.api_key}
        )
        data = response.json()
        price = data.get("c", 0)
        if price == 0:
            raise UnknownSymbol(symbol)
        as_of = datetime.fromtimestamp(data["t"], tz=timezone.utc)
        return Quote(symbol=symbol, price=float(price), as_of=as_of)
