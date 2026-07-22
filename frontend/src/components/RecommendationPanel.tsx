import { useState, type FormEvent } from 'react'
import { useRecommendation } from '../hooks/useRecommendation'
import { useOpenPrediction } from '../hooks/useOpenPrediction'
import { LEGAL_DISCLAIMER } from './LegalBanner'
import { formatEUR, formatPercent } from '../format'
import styles from './RecommendationPanel.module.css'

export function RecommendationPanel() {
  const [symbol, setSymbol] = useState('')
  const recommendation = useRecommendation()
  const openPrediction = useOpenPrediction()

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmed = symbol.trim()
    if (!trimmed) return
    openPrediction.reset()
    recommendation.mutate(trimmed.toUpperCase())
  }

  function handleAccept() {
    const data = recommendation.data
    if (!data) return
    openPrediction.mutate(
      {
        symbol: data.symbol,
        amount: data.suggested_amount,
        direction: data.direction,
        confidence: data.confidence,
        horizon: data.horizon,
        rationale: data.rationale,
      },
      {
        onSuccess: () => {
          recommendation.reset()
          setSymbol('')
        },
      }
    )
  }

  return (
    <section className={styles.panel}>
      <h2>Nueva recomendación</h2>
      <form onSubmit={handleSubmit} className={styles.form}>
        <label htmlFor="symbol">Símbolo</label>
        <input
          id="symbol"
          value={symbol}
          onChange={(event) => setSymbol(event.target.value)}
          placeholder="AAPL"
        />
        <button type="submit" disabled={recommendation.isPending || !symbol.trim()}>
          {recommendation.isPending ? 'Pidiendo...' : 'Pedir recomendación'}
        </button>
      </form>

      {recommendation.isError && (
        <p role="alert" className={styles.error}>
          {recommendation.error.message}
        </p>
      )}

      {recommendation.data && (
        <div className={styles.card}>
          <p className={recommendation.data.direction === 'up' ? styles.up : styles.down}>
            {recommendation.data.symbol} {recommendation.data.direction === 'up' ? '↑' : '↓'} (
            {formatPercent(recommendation.data.confidence * 100)} confianza)
          </p>
          <p>Importe sugerido: {formatEUR(recommendation.data.suggested_amount)}</p>
          <p>Horizonte: {recommendation.data.horizon}</p>
          <p className={styles.rationale}>{recommendation.data.rationale}</p>
          <p className={styles.disclaimer}>{LEGAL_DISCLAIMER}</p>

          {openPrediction.isError && (
            <p role="alert" className={styles.error}>
              {openPrediction.error.message}
            </p>
          )}

          <button type="button" onClick={handleAccept} disabled={openPrediction.isPending}>
            {openPrediction.isPending ? 'Aceptando...' : 'Aceptar predicción'}
          </button>
        </div>
      )}
    </section>
  )
}
