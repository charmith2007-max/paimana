import { ApiError, getRiskSummary, getAgentRisk } from '@/lib/api'
import type { ProjectSummary } from '@/lib/types'
import { PageHeader } from '@/components/page-header'
import { LastUpdated } from '@/components/last-updated'
import { RiskDonut } from '@/components/risk-donut'
import { ProjectRiskBar, SectorRiskBar } from '@/components/risk-charts'
import { ProjectsTable } from '@/components/projects-table'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { ApiUnavailable } from '@/components/api-unavailable'

export const dynamic = 'force-dynamic'

export default async function RiskIntelligencePage() {
  try {
    const [summary, riskPayload] = await Promise.all([
      getRiskSummary(),
      getAgentRisk(),
    ])

    const risks = riskPayload.data ?? []

    // Convert Agent 2 response into dashboard format
    const projects: ProjectSummary[] = risks.map((r) => ({
      project_id: String(r.project_id),
      name: r.project_name || String(r.project_id),
      agency: r.agency || '—',
      state: r.state || '—',
      sector: '',
      latest_report: r.report_month,
      risk_score: Number(r.risk_score_100 ?? 0),
      risk_level: r.risk_level,
      delay_probability: Number(r.model_delay_probability ?? 0),
      top_risk_drivers: Array.isArray(r.top_risk_drivers)
        ? r.top_risk_drivers
        : typeof r.top_risk_drivers === 'string' && r.top_risk_drivers
        ? [r.top_risk_drivers]
        : [],
      interpretation: r.risk_interpretation || '',
    }))

    const distribution = {
      high: summary.high,
      medium: summary.medium,
      low: summary.low,
      total: summary.total,
    }

    const byRisk = [...projects].sort(
      (a, b) => b.risk_score - a.risk_score
    )

    const projectBars = byRisk.slice(0, 25).map((p) => ({
      name: p.name,
      score: p.risk_score,
    }))

    const stateMap = new Map<string, number[]>()

    for (const p of projects) {
      const key = p.state && p.state !== '—' ? p.state : 'Unknown'
      const arr = stateMap.get(key) ?? []
      arr.push(p.risk_score)
      stateMap.set(key, arr)
    }

    const sectorData = Array.from(stateMap.entries())
      .map(([sector, scores]) => ({
        sector,
        avg: Math.round(
          scores.reduce((a, b) => a + b, 0) / scores.length
        ),
      }))
      .sort((a, b) => b.avg - a.avg)

    const highRisk = byRisk.filter(
      (p) => p.risk_level === 'High'
    )

    return (
      <div className="flex flex-col gap-6">
        <PageHeader
          title="Risk Intelligence"
          subtitle="Portfolio-wide analysis of predicted delay and cost risk."
          actions={
            <LastUpdated timestamp={new Date().toISOString()} />
          }
        />

        {/* Risk Distribution */}
        <section className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle>Risk Distribution</CardTitle>
              <CardDescription>
                {new Date(summary.report_month).toLocaleDateString('en-IN', {
                  month: 'long',
                  year: 'numeric',
                })}{' '}
                predicted risk levels
              </CardDescription>
            </CardHeader>

            <CardContent>
              <RiskDonut data={distribution} />
            </CardContent>
          </Card>

          {/* Summary */}
          <Card>
            <CardHeader>
              <CardTitle>Total Projects</CardTitle>
              <CardDescription>
                Agent 2 predictions
              </CardDescription>
            </CardHeader>

            <CardContent>
              <div className="text-4xl font-bold">
                {summary.total}
              </div>

              <p className="mt-2 text-sm text-muted-foreground">
                Reporting month:{' '}
                {new Date(summary.report_month).toLocaleDateString(
                  'en-IN',
                  {
                    month: 'long',
                    year: 'numeric',
                  }
                )}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>High Risk</CardTitle>
              <CardDescription>
                Projects requiring priority intervention
              </CardDescription>
            </CardHeader>

            <CardContent>
              <div className="text-4xl font-bold">
                {summary.high}
              </div>

              <p className="mt-2 text-sm text-muted-foreground">
                {summary.medium} medium · {summary.low} low
              </p>
            </CardContent>
          </Card>
        </section>

        {/* Risk Ranking */}
        <section>
          <Card>
            <CardHeader>
              <CardTitle>Risk Score Ranking</CardTitle>
              <CardDescription>
                Highest-risk projects by Agent 2 risk score
              </CardDescription>
            </CardHeader>

            <CardContent>
              {projectBars.length === 0 ? (
                <p className="py-6 text-sm text-muted-foreground">
                  No risk predictions available.
                </p>
              ) : (
                <ProjectRiskBar data={projectBars} />
              )}
            </CardContent>
          </Card>
        </section>

        {/* High Risk Watchlist */}
        <section>
          <Card>
            <CardHeader>
              <CardTitle>High-Risk Watchlist</CardTitle>

              <CardDescription>
                {highRisk.length} project
                {highRisk.length === 1 ? '' : 's'} requiring priority
                intervention
              </CardDescription>
            </CardHeader>

            <CardContent className="px-0 pb-0">
              <ProjectsTable
                projects={highRisk}
                showLatestReport
                emptyMessage="No high-risk projects."
              />
            </CardContent>
          </Card>
        </section>
      </div>
    )
  } catch (error) {
    const message =
      error instanceof ApiError
        ? error.message
        : 'PAIMANA API is currently unavailable.'

    return (
      <div className="flex flex-col gap-6">
        <PageHeader
          title="Risk Intelligence"
          subtitle="Portfolio-wide analysis of predicted delay and cost risk."
        />

        <ApiUnavailable message={message} />
      </div>
    )
  }
}
