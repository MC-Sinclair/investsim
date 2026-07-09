from __future__ import annotations

from datetime import datetime
from typing import Callable

from investsim.db.repositories import PortfolioRepository, PredictionRepository
from investsim.db.tables import PredictionRow
from investsim.domain.enums import Direction
from investsim.providers.market_data import MarketDataProvider
from investsim.services.portfolio_service import _utcnow


class SettlementService:
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

    def settle_due(self) -> list[PredictionRow]:
        now = self.clock()
        due = self.prediction_repo.list_open_due(now)
        if not due:
            return []

        portfolio = self.portfolio_repo.get()
        settled: list[PredictionRow] = []
        for pred in due:
            quote = self.market_data.get_quote(pred.symbol)
            pred.exit_price = quote.price
            pred.final_value = pred.shares * quote.price
            pred.pnl_pct = (
                (quote.price - pred.entry_price) / pred.entry_price * 100
            )
            actual = Direction.UP if quote.price >= pred.entry_price else Direction.DOWN
            pred.hit = pred.expected_direction == actual.value
            pred.status = "settled"
            portfolio.cash_balance += pred.final_value
            self.prediction_repo.save(pred)
            settled.append(pred)

        self.portfolio_repo.save(portfolio)
        return settled

    def mark_to_market(self, prediction: PredictionRow) -> float:
        quote = self.market_data.get_quote(prediction.symbol)
        return prediction.shares * quote.price
