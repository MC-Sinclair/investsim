import type { PredictionOut } from '../api/types'
import { parseApiDate } from '../api/dates'
import { formatEUR } from '../format'
import styles from './PredictionsTable.module.css'

interface PredictionsTableProps {
  predictions: PredictionOut[] | undefined
  isLoading: boolean
  isError: boolean
  onRetry: () => void
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat('es-ES', { dateStyle: 'short', timeStyle: 'short' }).format(
    parseApiDate(value)
  )
}

export function PredictionsTable({ predictions, isLoading, isError, onRetry }: PredictionsTableProps) {
  if (isLoading) {
    return <section className={styles.panel}>Cargando predicciones...</section>
  }

  if (isError || !predictions) {
    return (
      <section className={styles.panel}>
        <p>No se pudo conectar con la API.</p>
        <button type="button" onClick={onRetry}>
          Reintentar
        </button>
      </section>
    )
  }

  if (predictions.length === 0) {
    return (
      <section className={styles.panel}>
        <h2>Predicciones</h2>
        <p>Todavía no hay predicciones abiertas.</p>
      </section>
    )
  }

  return (
    <section className={styles.panel}>
      <h2>Predicciones</h2>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Símbolo</th>
            <th>Fecha</th>
            <th>Importe</th>
            <th>Estado</th>
            <th>Valor</th>
          </tr>
        </thead>
        <tbody>
          {predictions.map((prediction) => {
            const value =
              prediction.status === 'open' ? prediction.current_value : prediction.final_value
            return (
              <tr key={prediction.id}>
                <td>{prediction.symbol}</td>
                <td>{formatDate(prediction.created_at)}</td>
                <td className="tabular-nums">{formatEUR(prediction.amount)}</td>
                <td className={prediction.status === 'open' ? styles.open : styles.settled}>
                  {prediction.status === 'open' ? 'Abierta' : 'Liquidada'}
                </td>
                <td className="tabular-nums">{value !== null ? formatEUR(value) : '—'}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </section>
  )
}
