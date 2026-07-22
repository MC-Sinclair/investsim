import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { usePortfolio } from './hooks/usePortfolio'
import { usePredictions } from './hooks/usePredictions'
import { useMetrics } from './hooks/useMetrics'
import { useRecommendation } from './hooks/useRecommendation'
import { useOpenPrediction } from './hooks/useOpenPrediction'
import { LEGAL_DISCLAIMER } from './components/LegalBanner'

vi.mock('./hooks/usePortfolio')
vi.mock('./hooks/usePredictions')
vi.mock('./hooks/useMetrics')
vi.mock('./hooks/useRecommendation')
vi.mock('./hooks/useOpenPrediction')

function query(overrides: Record<string, unknown> = {}) {
  return {
    data: undefined,
    isPending: false,
    isError: false,
    refetch: vi.fn(),
    ...overrides,
  }
}

function mutation(overrides: Record<string, unknown> = {}) {
  return {
    data: undefined,
    error: null,
    isPending: false,
    isError: false,
    mutate: vi.fn(),
    reset: vi.fn(),
    ...overrides,
  } as unknown as ReturnType<typeof useRecommendation>
}

beforeEach(() => {
  vi.mocked(usePortfolio).mockReturnValue(
    query({
      data: { cash_balance: 990, initial_capital: 500, open_predictions_value: 15, total_value: 505 },
    }) as unknown as ReturnType<typeof usePortfolio>
  )
  vi.mocked(usePredictions).mockReturnValue(
    query({ data: [] }) as unknown as ReturnType<typeof usePredictions>
  )
  vi.mocked(useMetrics).mockReturnValue(
    query({
      data: {
        total_predictions: 0,
        settled: 0,
        hits: 0,
        hit_rate_pct: 0,
        total_invested: 0,
        total_final_value: 0,
        total_return_pct: 0,
      },
    }) as unknown as ReturnType<typeof useMetrics>
  )
  vi.mocked(useRecommendation).mockReturnValue(mutation())
  vi.mocked(useOpenPrediction).mockReturnValue(
    mutation() as unknown as ReturnType<typeof useOpenPrediction>
  )
})

describe('App', () => {
  it('renders the legal banner and every dashboard panel', () => {
    render(<App />)

    expect(screen.getAllByText(LEGAL_DISCLAIMER)[0]).toBeInTheDocument()
    expect(screen.getByText('Portfolio')).toBeInTheDocument()
    expect(screen.getByText('Métricas')).toBeInTheDocument()
    expect(screen.getByText(/todavía no hay predicciones/i)).toBeInTheDocument()
    expect(screen.getByText('505,00 €')).toBeInTheDocument()
  })
})
