import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { usePortfolio } from './usePortfolio'
import * as client from '../api/client'
import { createQueryWrapper, createTestQueryClient } from '../test/queryWrapper'

describe('usePortfolio', () => {
  it('fetches the portfolio via getPortfolio', async () => {
    vi.spyOn(client, 'getPortfolio').mockResolvedValue({
      cash_balance: 990,
      initial_capital: 500,
      open_predictions_value: 15,
      total_value: 505,
    })
    const queryClient = createTestQueryClient()

    const { result } = renderHook(() => usePortfolio(), {
      wrapper: createQueryWrapper(queryClient),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.total_value).toBe(505)
  })
})
