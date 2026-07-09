"""Smoke test manual del bucle central de InvestSim (Fase 1).

Recorre el bucle completo SIN red ni coste, usando FakeMarketDataProvider:
abrir operacion simulada -> avanzar el reloj -> liquidar -> metricas.

Ejecutar desde la raiz del repo:
    python backend/examples/smoke_loop.py
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from investsim.db.base import Base, make_engine, make_session_factory
from investsim.db.repositories import PortfolioRepository, PredictionRepository
from investsim.domain.enums import Direction, Horizon
from investsim.metrics import compute_metrics
from investsim.providers.market_data import FakeMarketDataProvider
from investsim.services.portfolio_service import PortfolioService
from investsim.services.settlement_service import SettlementService


def main() -> None:
    # --- Montaje: BD en memoria + proveedor de datos falso ---
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = make_session_factory(engine)()

    portfolio_repo = PortfolioRepository(session)
    prediction_repo = PredictionRepository(session)

    t0 = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)
    now = t0  # reloj mutable que iremos avanzando a mano

    portfolio_repo.create(initial_capital=100.0, created_at=t0)
    market = FakeMarketDataProvider({"AAPL": 100.0}, as_of=t0)

    portfolio_service = PortfolioService(
        portfolio_repo, prediction_repo, market, clock=lambda: now
    )
    settlement_service = SettlementService(
        portfolio_repo, prediction_repo, market, clock=lambda: now
    )

    print("=== InvestSim - smoke test del bucle central (datos ficticios) ===\n")
    print(f"Caja inicial: {portfolio_repo.get().cash_balance:.2f} EUR")

    # --- A) Abrir operacion simulada: invertir 10 EUR en AAPL a 100 EUR, prediciendo subida ---
    pred = portfolio_service.open_prediction(
        symbol="AAPL",
        amount=10.0,
        direction=Direction.UP,
        confidence=0.9,
        horizon=Horizon.ONE_WEEK,
        rationale="Momentum alcista (ficticio).",
    )
    print(
        f"\n[Abrir] {pred.symbol}: invierto {pred.amount:.2f} EUR "
        f"a {pred.entry_price:.2f} EUR/accion => {pred.shares:.4f} acciones. "
        f"Prediccion: {pred.expected_direction} (conf {pred.confidence:.0%}). "
        f"Vence el {pred.evaluate_at:%Y-%m-%d}."
    )
    print(f"Caja tras abrir: {portfolio_repo.get().cash_balance:.2f} EUR")

    # --- B) Pasa una semana y el precio sube a 134 EUR (+34%) ---
    now = t0 + timedelta(weeks=1, minutes=1)
    market.set_price("AAPL", 134.0)
    print(f"\n[Tiempo] Avanzamos a {now:%Y-%m-%d}. AAPL ahora cotiza a 134.00 EUR.")

    # --- C) Liquidacion perezosa de las vencidas ---
    settled = settlement_service.settle_due()
    for p in settled:
        signo = "acierto" if p.hit else "fallo"
        print(
            f"\n[Liquidar] {p.symbol}: salida a {p.exit_price:.2f} EUR. "
            f"Resultado {p.pnl_pct:+.2f}% -> valor final {p.final_value:.2f} EUR ({signo})."
        )
        print(
            f"  >> Si hubieras invertido {p.amount:.0f} EUR, "
            f"ahora tendrias {p.final_value:.2f} EUR ({p.pnl_pct:+.0f}%)."
        )

    print(f"\nCaja tras liquidar: {portfolio_repo.get().cash_balance:.2f} EUR")

    # --- D) Metricas acumuladas (calculadas desde las predicciones) ---
    m = compute_metrics(prediction_repo.list_all())
    print("\n=== Metricas del agente ===")
    print(f"Predicciones: {m.total_predictions} (liquidadas: {m.settled})")
    print(f"Tasa de acierto: {m.hit_rate_pct:.0f}%")
    print(
        f"Invertido: {m.total_invested:.2f} EUR -> valor final: "
        f"{m.total_final_value:.2f} EUR ({m.total_return_pct:+.1f}%)"
    )
    print("\n(Simulacion educativa, no es asesoramiento financiero. Capital ficticio.)")


if __name__ == "__main__":
    main()
