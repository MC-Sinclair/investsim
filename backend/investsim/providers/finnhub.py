from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable

import httpx

from investsim.config import FinnhubConfig
from investsim.providers.market_data import (
    MarketSnapshot,
    ProviderUnavailable,
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
        self._cache: dict[str, tuple[dict, datetime]] = {}

    def _quote_data(self, symbol: str) -> dict:
        now = self.clock()
        cached = self._cache.get(symbol)
        if cached is not None:
            data, fetched_at = cached
            if now - fetched_at < self.config.ttl:
                return data

        data = self._fetch_quote_data(symbol)
        if data.get("c", 0) == 0:
            raise UnknownSymbol(symbol)
        self._cache[symbol] = (data, now)
        return data

    def get_quote(self, symbol: str) -> Quote:
        data = self._quote_data(symbol)
        return Quote(
            symbol=symbol,
            price=float(data["c"]),
            as_of=datetime.fromtimestamp(data["t"], tz=timezone.utc),
        )

    def get_snapshot(self, symbol: str) -> MarketSnapshot:
        data = self._quote_data(symbol)
        price = float(data["c"])
        return MarketSnapshot(
            symbol=symbol,
            price=price,
            day_change_pct=float(data.get("dp") or 0.0),
            day_high=float(data.get("h") or price),
            day_low=float(data.get("l") or price),
            day_open=float(data.get("o") or price),
            prev_close=float(data.get("pc") or price),
            as_of=datetime.fromtimestamp(data["t"], tz=timezone.utc),
        )

    def _fetch_quote_data(self, symbol: str) -> dict:
        last_error: Exception | None = None
        for attempt in range(self.config.max_retries):
            try:
                response = self.client.get(
                    "/quote",
                    params={"symbol": symbol, "token": self.config.api_key},
                )
            except httpx.HTTPError as exc:  # red / timeout
                last_error = exc
            else:
                if response.status_code == 200:
                    return response.json()
                if response.status_code == 429 or response.status_code >= 500:
                    last_error = ProviderUnavailable(
                        f"Finnhub HTTP {response.status_code}"
                    )
                else:  # 4xx que no es 429 (p. ej. 401): no reintentar
                    raise ProviderUnavailable(
                        f"Finnhub HTTP {response.status_code} para {symbol}"
                    )

            if attempt < self.config.max_retries - 1:
                self.sleep(0.5 * 2**attempt)

        raise ProviderUnavailable(
            f"Finnhub no disponible tras {self.config.max_retries} intentos"
        ) from last_error
