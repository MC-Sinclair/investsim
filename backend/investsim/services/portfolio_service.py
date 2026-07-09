from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from investsim.db.repositories import PortfolioRepository, PredictionRepository
from investsim.db.tables import PredictionRow
from investsim.domain.enums import Direction, Horizon
from investsim.providers.market_data import MarketDataProvider


class InsufficientFunds(Exception):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PortfolioService:
    def __init__(
        self,
        portfolio_repo: PortfolioRepository,
        prediction_repo: PredictionRepository,
        market_data: MarketDataProvider,
        clock: Callable[[], datetime] = _utcnow,
    ) -> None:
        self.portfolio_repo = portfolio_repo
        self.prediction_repo = prediction_repo
        self.market_data = market_data
        self.clock = clock

    def open_prediction(
        self,
        symbol: str,
        amount: float,
        direction: Direction,
        confidence: float,
        horizon: Horizon,
        rationale: str = "",
    ) -> PredictionRow:
        portfolio = self.portfolio_repo.get()
        if portfolio is None:
            raise InsufficientFunds("no portfolio")
        if amount > portfolio.cash_balance:
            raise InsufficientFunds(
                f"amount {amount} > cash {portfolio.cash_balance}"
            )

        quote = self.market_data.get_quote(symbol)
        now = self.clock()
        row = PredictionRow(
            symbol=symbol,
            created_at=now,
            entry_price=quote.price,
            amount=amount,
            shares=amount / quote.price,
            horizon=horizon.value,
            evaluate_at=now + horizon.to_timedelta(),
            expected_direction=direction.value,
            confidence=confidence,
            rationale=rationale,
            status="open",
        )
        portfolio.cash_balance -= amount
        self.portfolio_repo.save(portfolio)
        return self.prediction_repo.add(row)
