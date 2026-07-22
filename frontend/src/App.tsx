import { LegalBanner } from './components/LegalBanner'
import { RecommendationPanel } from './components/RecommendationPanel'
import { PortfolioSummary } from './components/PortfolioSummary'
import { PredictionsTable } from './components/PredictionsTable'
import { MetricsPanel } from './components/MetricsPanel'
import { usePortfolio } from './hooks/usePortfolio'
import { usePredictions } from './hooks/usePredictions'
import { useMetrics } from './hooks/useMetrics'
import styles from './App.module.css'

function App() {
  const portfolio = usePortfolio()
  const predictions = usePredictions()
  const metrics = useMetrics()

  return (
    <div className={styles.app}>
      <LegalBanner />
      <main className={styles.main}>
        <h1>InvestSim</h1>
        <RecommendationPanel />
        <PortfolioSummary
          portfolio={portfolio.data}
          isLoading={portfolio.isPending}
          isError={portfolio.isError}
          onRetry={() => portfolio.refetch()}
        />
        <MetricsPanel
          metrics={metrics.data}
          isLoading={metrics.isPending}
          isError={metrics.isError}
          onRetry={() => metrics.refetch()}
        />
        <PredictionsTable
          predictions={predictions.data}
          isLoading={predictions.isPending}
          isError={predictions.isError}
          onRetry={() => predictions.refetch()}
        />
      </main>
    </div>
  )
}

export default App
