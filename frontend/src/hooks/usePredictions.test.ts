import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { usePredictions } from './usePredictions'
import * as client from '../api/client'
import { createQueryWrapper, createTestQueryClient } from '../test/queryWrapper'
import type { PredictionOut } from '../api/types'

function prediction(overrides: Partial<PredictionOut>): PredictionOut {
  return {
    id: 1,
    symbol: 'AAPL',
    created_at: '2026-07-22T00:00:00Z',
    entry_price: 100,
    amount: 10,
    shares: 0.1,
    horizon: '1D',
    evaluate_at: '2026-07-23T00:00:00Z',
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

describe('usePredictions', () => {
  it('sorts predictions by id descending, most recent first', async () => {
    vi.spyOn(client, 'getPredictions').mockResolvedValue([
      prediction({ id: 1 }),
      prediction({ id: 3 }),
      prediction({ id: 2 }),
    ])
    const queryClient = createTestQueryClient()

    const { result } = renderHook(() => usePredictions(), {
      wrapper: createQueryWrapper(queryClient),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.map((p) => p.id)).toEqual([3, 2, 1])
  })
})
