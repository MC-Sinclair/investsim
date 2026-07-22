import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { PredictionsTable } from './PredictionsTable'
import type { PredictionOut } from '../api/types'

function prediction(overrides: Partial<PredictionOut>): PredictionOut {
  return {
    id: 1,
    symbol: 'AAPL',
    created_at: '2026-07-22T10:00:00Z',
    entry_price: 100,
    amount: 10,
    shares: 0.1,
    horizon: '1D',
    evaluate_at: '2026-07-23T10:00:00Z',
    expected_direction: 'up',
    confidence: 0.5,
    rationale: '',
    status: 'open',
    exit_price: null,
    final_value: null,
    pnl_pct: null,
    hit: null,
    current_value: null,
    ...overrides,
  }
}

describe('PredictionsTable', () => {
  it('shows a loading state', () => {
    render(<PredictionsTable predictions={undefined} isLoading isError={false} onRetry={vi.fn()} />)
    expect(screen.getByText(/cargando predicciones/i)).toBeInTheDocument()
  })

  it('shows an empty state when there are no predictions', () => {
    render(<PredictionsTable predictions={[]} isLoading={false} isError={false} onRetry={vi.fn()} />)
    expect(screen.getByText(/todavía no hay predicciones/i)).toBeInTheDocument()
  })

  it('shows an error with a retry button that calls onRetry', async () => {
    const onRetry = vi.fn()
    render(<PredictionsTable predictions={undefined} isLoading={false} isError onRetry={onRetry} />)

    await userEvent.click(screen.getByRole('button', { name: /reintentar/i }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('shows current_value for an open prediction', () => {
    render(
      <PredictionsTable
        predictions={[prediction({ status: 'open', current_value: 12 })]}
        isLoading={false}
        isError={false}
        onRetry={vi.fn()}
      />
    )
    expect(screen.getByText('Abierta')).toBeInTheDocument()
    expect(screen.getByText('12,00 €')).toBeInTheDocument()
  })

  it('shows final_value for a settled prediction', () => {
    render(
      <PredictionsTable
        predictions={[
          prediction({ status: 'settled', current_value: null, final_value: 9, pnl_pct: -10, hit: false }),
        ]}
        isLoading={false}
        isError={false}
        onRetry={vi.fn()}
      />
    )
    expect(screen.getByText('Liquidada')).toBeInTheDocument()
    expect(screen.getByText('9,00 €')).toBeInTheDocument()
  })
})
