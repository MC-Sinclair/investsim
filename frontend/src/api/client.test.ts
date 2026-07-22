import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  getMetrics,
  getPortfolio,
  getPredictions,
  postPrediction,
  postRecommendation,
} from './client'

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('postRecommendation', () => {
  it('POSTs the symbol and returns the parsed recommendation', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(200, {
        symbol: 'AAPL',
        direction: 'up',
        confidence: 0.5,
        suggested_amount: 10,
        horizon: '1D',
        rationale: 'motivo',
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await postRecommendation('AAPL')

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/recommendations'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ symbol: 'AAPL' }),
      })
    )
    expect(result.symbol).toBe('AAPL')
    expect(result.direction).toBe('up')
  })

  it('throws an ApiError with the domain message on 404', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse(404, { detail: 'Simbolo desconocido: NOPE' }))
    )

    await expect(postRecommendation('NOPE')).rejects.toMatchObject({
      status: 404,
      message: 'Simbolo desconocido: NOPE',
    })
  })
})

describe('postPrediction', () => {
  it('POSTs the prediction body and returns the parsed prediction', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(200, {
        id: 1,
        symbol: 'AAPL',
        created_at: '2026-07-22T19:53:03.555030Z',
        entry_price: 100,
        amount: 10,
        shares: 0.1,
        horizon: '1D',
        evaluate_at: '2026-07-23T19:53:03.555030Z',
        expected_direction: 'up',
        confidence: 0.5,
        rationale: '',
        status: 'open',
        exit_price: null,
        final_value: null,
        pnl_pct: null,
        hit: null,
        current_value: null,
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await postPrediction({
      symbol: 'AAPL',
      amount: 10,
      direction: 'up',
      confidence: 0.5,
      horizon: '1D',
      rationale: '',
    })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/predictions'),
      expect.objectContaining({ method: 'POST' })
    )
    expect(result.id).toBe(1)
    expect(result.status).toBe('open')
  })

  it('throws an ApiError with the domain message on 400', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse(400, { detail: 'amount 10000.0 > cash 990.0' }))
    )

    await expect(
      postPrediction({
        symbol: 'AAPL',
        amount: 10000,
        direction: 'up',
        confidence: 0.5,
        horizon: '1D',
        rationale: '',
      })
    ).rejects.toMatchObject({ status: 400, message: 'amount 10000.0 > cash 990.0' })
  })
})

describe('getPortfolio', () => {
  it('GETs the portfolio', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(200, {
        cash_balance: 990,
        initial_capital: 1000,
        open_predictions_value: 15,
        total_value: 1005,
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await getPortfolio()

    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/portfolio'), expect.anything())
    expect(result.total_value).toBe(1005)
  })
})

describe('getPredictions', () => {
  it('GETs the predictions list', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(200, [])))

    const result = await getPredictions()

    expect(result).toEqual([])
  })
})

describe('getMetrics', () => {
  it('GETs the metrics', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(200, {
        total_predictions: 1,
        settled: 1,
        hits: 1,
        hit_rate_pct: 100,
        total_invested: 10,
        total_final_value: 13.4,
        total_return_pct: 34,
      })
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await getMetrics()

    expect(result.hit_rate_pct).toBe(100)
  })
})
