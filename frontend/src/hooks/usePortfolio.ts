import { useQuery } from '@tanstack/react-query'
import { getPortfolio } from '../api/client'

export function usePortfolio() {
  return useQuery({
    queryKey: ['portfolio'],
    queryFn: getPortfolio,
  })
}
