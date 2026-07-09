from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from investsim.db.tables import PortfolioRow, PredictionRow


class PortfolioRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, initial_capital: float, created_at: datetime) -> PortfolioRow:
        row = PortfolioRow(
            cash_balance=initial_capital,
            initial_capital=initial_capital,
            created_at=created_at,
        )
        self.session.add(row)
        self.session.commit()
        return row

    def get(self) -> PortfolioRow | None:
        return self.session.scalars(select(PortfolioRow).limit(1)).first()

    def save(self, row: PortfolioRow) -> None:
        self.session.add(row)
        self.session.commit()


class PredictionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, row: PredictionRow) -> PredictionRow:
        self.session.add(row)
        self.session.commit()
        return row

    def get(self, prediction_id: int) -> PredictionRow | None:
        return self.session.get(PredictionRow, prediction_id)

    def list_all(self) -> list[PredictionRow]:
        return list(self.session.scalars(select(PredictionRow)))

    def list_open_due(self, now: datetime) -> list[PredictionRow]:
        stmt = select(PredictionRow).where(
            PredictionRow.status == "open",
            PredictionRow.evaluate_at <= now,
        )
        return list(self.session.scalars(stmt))

    def save(self, row: PredictionRow) -> None:
        self.session.add(row)
        self.session.commit()
