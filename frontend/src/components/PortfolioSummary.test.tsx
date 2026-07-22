import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { PortfolioSummary } from './PortfolioSummary'

const portfolio = {
  cash_balance: 990,
  initial_capital: 500,
  open_predictions_value: 15,
  total_value: 505,
}

describe('PortfolioSummary', () => {
  it('shows a loading state', () => {
    render(<PortfolioSummary portfolio={undefined} isLoading isError={false} onRetry={vi.fn()} />)
    expect(screen.getByText(/cargando portfolio/i)).toBeInTheDocument()
  })

  it('shows the portfolio values once loaded', () => {
    render(<PortfolioSummary portfolio={portfolio} isLoading={false} isError={false} onRetry={vi.fn()} />)
    expect(screen.getByText('990,00 €')).toBeInTheDocument()
    expect(screen.getByText('505,00 €')).toBeInTheDocument()
  })

  it('shows an error with a retry button that calls onRetry', async () => {
    const onRetry = vi.fn()
    render(<PortfolioSummary portfolio={undefined} isLoading={false} isError onRetry={onRetry} />)

    expect(screen.getByText(/no se pudo conectar/i)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /reintentar/i }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })
})
