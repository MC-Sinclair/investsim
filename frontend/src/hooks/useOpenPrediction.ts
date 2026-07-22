import { useMutation, useQueryClient } from '@tanstack/react-query'
import { postPrediction } from '../api/client'
import type { OpenPredictionIn } from '../api/types'

export function useOpenPrediction() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (body: OpenPredictionIn) => postPrediction(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['portfolio'] })
      queryClient.invalidateQueries({ queryKey: ['predictions'] })
      queryClient.invalidateQueries({ queryKey: ['metrics'] })
    },
  })
}
