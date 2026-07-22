import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MetricsPanel } from './MetricsPanel'

const metrics = {
  total_predictions: 5,
  settled: 3,
  hits: 2,
  hit_rate_pct: 66.7,
  total_invested: 30,
  total_final_value: 40,
  total_return_pct: 33.3,
}

describe('MetricsPanel', () => {
  it('shows a loading state', () => {
    render(<MetricsPanel metrics={undefined} isLoading isError={false} onRetry={vi.fn()} />)
    expect(screen.getByText(/cargando métricas/i)).toBeInTheDocument()
  })

  it('shows the metrics once loaded', () => {
    render(<MetricsPanel metrics={metrics} isLoading={false} isError={false} onRetry={vi.fn()} />)
    expect(screen.getByText('66,7%')).toBeInTheDocument()
    expect(screen.getByText('33,3%')).toBeInTheDocument()
    expect(screen.getByText('5')).toBeInTheDocument()
  })

  it('shows an error with a retry button that calls onRetry', async () => {
    const onRetry = vi.fn()
    render(<MetricsPanel metrics={undefined} isLoading={false} isError onRetry={onRetry} />)

    await userEvent.click(screen.getByRole('button', { name: /reintentar/i }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })
})
