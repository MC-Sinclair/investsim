import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useMetrics } from './useMetrics'
import * as client from '../api/client'
import { createQueryWrapper, createTestQueryClient } from '../test/queryWrapper'

describe('useMetrics', () => {
  it('fetches the metrics via getMetrics', async () => {
    vi.spyOn(client, 'getMetrics').mockResolvedValue({
      total_predictions: 1,
      settled: 1,
      hits: 1,
      hit_rate_pct: 100,
      total_invested: 10,
      total_final_value: 13.4,
      total_return_pct: 34,
    })
    const queryClient = createTestQueryClient()

    const { result } = renderHook(() => useMetrics(), {
      wrapper: createQueryWrapper(queryClient),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.hit_rate_pct).toBe(100)
  })
})
