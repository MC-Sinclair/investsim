import { toApiError } from './errors'
import type {
  MetricsOut,
  OpenPredictionIn,
  PortfolioOut,
  PredictionOut,
  RecommendationOut,
} from './types'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  })

  if (!response.ok) {
    throw await toApiError(response)
  }

  return (await response.json()) as T
}

export function postRecommendation(symbol: string): Promise<RecommendationOut> {
  return request<RecommendationOut>('/recommendations', {
    method: 'POST',
    body: JSON.stringify({ symbol }),
  })
}

export function postPrediction(body: OpenPredictionIn): Promise<PredictionOut> {
  return request<PredictionOut>('/predictions', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function getPortfolio(): Promise<PortfolioOut> {
  return request<PortfolioOut>('/portfolio')
}

export function getPredictions(): Promise<PredictionOut[]> {
  return request<PredictionOut[]>('/predictions')
}

export function getMetrics(): Promise<MetricsOut> {
  return request<MetricsOut>('/metrics')
}
