import { useMutation } from '@tanstack/react-query'
import { postRecommendation } from '../api/client'

export function useRecommendation() {
  return useMutation({
    mutationFn: (symbol: string) => postRecommendation(symbol),
  })
}
