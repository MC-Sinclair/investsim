import type { MetricsOut } from '../api/types'
import { formatPercent } from '../format'
import styles from './MetricsPanel.module.css'

interface MetricsPanelProps {
  metrics: MetricsOut | undefined
  isLoading: boolean
  isError: boolean
  onRetry: () => void
}

export function MetricsPanel({ metrics, isLoading, isError, onRetry }: MetricsPanelProps) {
  if (isLoading) {
    return <section className={styles.panel}>Cargando métricas...</section>
  }

  if (isError || !metrics) {
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
      <h2>Métricas</h2>
      <dl className={styles.grid}>
        <dt>Predicciones totales</dt>
        <dd className="tabular-nums">{metrics.total_predictions}</dd>
        <dt>Liquidadas</dt>
        <dd className="tabular-nums">{metrics.settled}</dd>
        <dt>Aciertos</dt>
        <dd className="tabular-nums">{metrics.hits}</dd>
        <dt>Tasa de acierto</dt>
        <dd className="tabular-nums">{formatPercent(metrics.hit_rate_pct)}</dd>
        <dt>Retorno total</dt>
        <dd className={`tabular-nums ${metrics.total_return_pct >= 0 ? styles.up : styles.down}`}>
          {formatPercent(metrics.total_return_pct)}
        </dd>
      </dl>
    </section>
  )
}
