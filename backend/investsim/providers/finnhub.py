from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable

import httpx

from investsim.config import FinnhubConfig
from investsim.providers.market_data import (
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
        self._cache: dict[str, tuple[Quote, datetime]] = {}

    def get_quote(self, symbol: str) -> Quote:
        now = self.clock()
        cached = self._cache.get(symbol)
        if cached is not None:
            quote, fetched_at = cached
            if now - fetched_at < self.config.ttl:
                return quote

        data = self._fetch_quote_data(symbol)
        price = data.get("c", 0)
        if price == 0:
            raise UnknownSymbol(symbol)
        as_of = datetime.fromtimestamp(data["t"], tz=timezone.utc)
        quote = Quote(symbol=symbol, price=float(price), as_of=as_of)
        self._cache[symbol] = (quote, now)
        return quote

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
