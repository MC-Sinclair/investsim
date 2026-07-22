import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useRecommendation } from './useRecommendation'
import * as client from '../api/client'
import { createQueryWrapper, createTestQueryClient } from '../test/queryWrapper'

describe('useRecommendation', () => {
  it('calls postRecommendation with the given symbol', async () => {
    vi.spyOn(client, 'postRecommendation').mockResolvedValue({
      symbol: 'AAPL',
      direction: 'up',
      confidence: 0.5,
      suggested_amount: 10,
      horizon: '1D',
      rationale: 'motivo',
    })
    const queryClient = createTestQueryClient()

    const { result } = renderHook(() => useRecommendation(), {
      wrapper: createQueryWrapper(queryClient),
    })

    act(() => {
      result.current.mutate('AAPL')
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(client.postRecommendation).toHaveBeenCalledWith('AAPL')
    expect(result.current.data?.symbol).toBe('AAPL')
  })
})
