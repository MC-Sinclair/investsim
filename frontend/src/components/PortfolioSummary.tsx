import type { PortfolioOut } from '../api/types'
import { formatEUR } from '../format'
import styles from './PortfolioSummary.module.css'

interface PortfolioSummaryProps {
  portfolio: PortfolioOut | undefined
  isLoading: boolean
  isError: boolean
  onRetry: () => void
}

export function PortfolioSummary({ portfolio, isLoading, isError, onRetry }: PortfolioSummaryProps) {
  if (isLoading) {
    return <section className={styles.panel}>Cargando portfolio...</section>
  }

  if (isError || !portfolio) {
    return (
      <section className={styles.panel}>
        <p>No se pudo conectar con la API.</p>
        <button type="button" onClick={onRetry}>
          Reintentar
        </button>
      </section>
    )
  }

  return (
    <section className={styles.panel}>
      <h2>Portfolio</h2>
      <dl className={styles.grid}>
        <dt>Caja</dt>
        <dd className="tabular-nums">{formatEUR(portfolio.cash_balance)}</dd>
        <dt>Capital inicial</dt>
        <dd className="tabular-nums">{formatEUR(portfolio.initial_capital)}</dd>
        <dt>Valor abierto</dt>
        <dd className="tabular-nums">{formatEUR(portfolio.open_predictions_value)}</dd>
        <dt>Valor total</dt>
        <dd className="tabular-nums">{formatEUR(portfolio.total_value)}</dd>
      </dl>
    </section>
  )
}
