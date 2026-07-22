import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RecommendationPanel } from './RecommendationPanel'
import { useRecommendation } from '../hooks/useRecommendation'
import { useOpenPrediction } from '../hooks/useOpenPrediction'
import { ApiError } from '../api/errors'

vi.mock('../hooks/useRecommendation')
vi.mock('../hooks/useOpenPrediction')

const mockedUseRecommendation = vi.mocked(useRecommendation)
const mockedUseOpenPrediction = vi.mocked(useOpenPrediction)

function recommendationMutation(overrides: Record<string, unknown> = {}) {
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

function openPredictionMutation(overrides: Record<string, unknown> = {}) {
  return {
    data: undefined,
    error: null,
    isPending: false,
    isError: false,
    mutate: vi.fn(),
    reset: vi.fn(),
    ...overrides,
  } as unknown as ReturnType<typeof useOpenPrediction>
}

beforeEach(() => {
  mockedUseRecommendation.mockReturnValue(recommendationMutation())
  mockedUseOpenPrediction.mockReturnValue(openPredictionMutation())
})

describe('RecommendationPanel', () => {
  it('requests a recommendation for the typed symbol, uppercased', async () => {
    const mutate = vi.fn()
    mockedUseRecommendation.mockReturnValue(recommendationMutation({ mutate }))

    render(<RecommendationPanel />)
    await userEvent.type(screen.getByLabelText(/símbolo/i), 'aapl')
    await userEvent.click(screen.getByRole('button', { name: /pedir recomendación/i }))

    expect(mutate).toHaveBeenCalledWith('AAPL')
  })

  it('shows an error message when the recommendation request fails', () => {
    mockedUseRecommendation.mockReturnValue(
      recommendationMutation({ isError: true, error: new ApiError(404, 'Simbolo desconocido: NOPE') })
    )

    render(<RecommendationPanel />)

    expect(screen.getByRole('alert')).toHaveTextContent('Simbolo desconocido: NOPE')
  })

  it('shows the recommendation card with the legal disclaimer and an accept button once it resolves', () => {
    mockedUseRecommendation.mockReturnValue(
      recommendationMutation({
        data: {
          symbol: 'AAPL',
          direction: 'up',
          confidence: 0.5,
          suggested_amount: 10,
          horizon: '1D',
          rationale: 'motivo de prueba',
        },
      })
    )

    render(<RecommendationPanel />)

    expect(screen.getByText(/motivo de prueba/)).toBeInTheDocument()
    expect(
      screen.getByText('Simulación educativa, no es asesoramiento financiero. Capital ficticio.')
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /aceptar predicción/i })).toBeInTheDocument()
  })

  it('accepts the recommendation as-is when clicking Aceptar', async () => {
    const mutate = vi.fn()
    mockedUseRecommendation.mockReturnValue(
      recommendationMutation({
        data: {
          symbol: 'AAPL',
          direction: 'up',
          confidence: 0.5,
          suggested_amount: 10,
          horizon: '1D',
          rationale: 'motivo',
        },
      })
    )
    mockedUseOpenPrediction.mockReturnValue(openPredictionMutation({ mutate }))

    render(<RecommendationPanel />)
    await userEvent.click(screen.getByRole('button', { name: /aceptar predicción/i }))

    expect(mutate).toHaveBeenCalledWith(
      {
        symbol: 'AAPL',
        amount: 10,
        direction: 'up',
        confidence: 0.5,
        horizon: '1D',
        rationale: 'motivo',
      },
      expect.anything()
    )
  })

  it('shows an insufficient funds error without discarding the recommendation card', () => {
    mockedUseRecommendation.mockReturnValue(
      recommendationMutation({
        data: {
          symbol: 'AAPL',
          direction: 'up',
          confidence: 0.5,
          suggested_amount: 10,
          horizon: '1D',
          rationale: 'motivo',
        },
      })
    )
    mockedUseOpenPrediction.mockReturnValue(
      openPredictionMutation({ isError: true, error: new ApiError(400, 'amount 10000.0 > cash 990.0') })
    )

    render(<RecommendationPanel />)

    expect(screen.getByRole('alert')).toHaveTextContent('amount 10000.0 > cash 990.0')
    expect(screen.getByRole('button', { name: /aceptar predicción/i })).toBeInTheDocument()
  })
})
