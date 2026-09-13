'use client'

import { useState } from 'react'
import { Loader2, Sparkles } from 'lucide-react'
import { predictProject, ApiError, API_UNAVAILABLE_MESSAGE } from '@/lib/api'
import { mapPrediction } from '@/lib/mappers'
import { formatPercent } from '@/lib/risk'
import type { ProjectSummary } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { RiskBadge } from '@/components/risk-badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export function RunPrediction({
  projectId,
  initial,
}: {
  projectId: string
  initial: ProjectSummary
}) {
  const [result, setResult] = useState<ProjectSummary>(initial)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function run() {
    setLoading(true)
    setError(null)
    try {
      const payload = await predictProject(projectId)
      setResult(mapPrediction(payload))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : API_UNAVAILABLE_MESSAGE)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle>Risk Prediction</CardTitle>
            <CardDescription>
              Live Random Forest estimate of next-month additional delay
            </CardDescription>
          </div>
          <Button onClick={() => void run()} disabled={loading} size="sm">
            {loading ? <Loader2 className="size-3.5 animate-spin" /> : <Sparkles className="size-3.5" />}
            {loading ? 'Running…' : 'Run Risk Prediction'}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {error ? (
          <p className="text-sm text-risk-high">{error}</p>
        ) : null}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="rounded-md border border-border bg-background/40 p-3">
            <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
              Delay Probability
            </p>
            <p className="mt-1 text-xl font-semibold tabular-nums text-foreground">
              {formatPercent(result.delay_probability, 1)}
            </p>
          </div>
          <div className="rounded-md border border-border bg-background/40 p-3">
            <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
              Risk Score
            </p>
            <p className="mt-1 text-xl font-semibold tabular-nums text-foreground">
              {result.risk_score}
            </p>
          </div>
          <div className="rounded-md border border-border bg-background/40 p-3">
            <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
              Risk Level
            </p>
            <div className="mt-2">
              <RiskBadge level={result.risk_level} />
            </div>
          </div>
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
            Top Risk Drivers
          </p>
          <ul className="mt-2 flex flex-col gap-1.5">
            {result.top_risk_drivers.map((driver) => (
              <li key={driver} className="text-sm text-foreground">
                {driver}
              </li>
            ))}
          </ul>
        </div>
        {result.interpretation ? (
          <p className="text-xs leading-relaxed text-muted-foreground">
            {result.interpretation}
          </p>
        ) : null}
      </CardContent>
    </Card>
  )
}
