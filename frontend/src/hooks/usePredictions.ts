import { useQuery } from '@tanstack/react-query'
import { getPredictions } from '../api/client'
import type { PredictionOut } from '../api/types'

export function usePredictions() {
  return useQuery({
    queryKey: ['predictions'],
    queryFn: getPredictions,
    select: (predictions: PredictionOut[]) => [...predictions].sort((a, b) => b.id - a.id),
  })
}
