import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useOpenPrediction } from './useOpenPrediction'
import * as client from '../api/client'
import { createQueryWrapper, createTestQueryClient } from '../test/queryWrapper'

describe('useOpenPrediction', () => {
  it('invalidates portfolio, predictions and metrics queries on success', async () => {
    vi.spyOn(client, 'postPrediction').mockResolvedValue({
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
    })
    const queryClient = createTestQueryClient()
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useOpenPrediction(), {
      wrapper: createQueryWrapper(queryClient),
    })

    act(() => {
      result.current.mutate({
        symbol: 'AAPL',
        amount: 10,
        direction: 'up',
        confidence: 0.5,
        horizon: '1D',
        rationale: '',
      })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['portfolio'] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['predictions'] })
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['metrics'] })
  })
})
