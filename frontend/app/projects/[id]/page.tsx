import Link from 'next/link'
import { notFound } from 'next/navigation'
import {
  ArrowLeft,
  Building2,
  MapPin,
  Hash,
  Calendar,
  Gauge,
  ShieldAlert,
  TrendingUp,
  Clock,
  Activity,
  TriangleAlert,
  History,
  Lightbulb,
  CheckCircle2,
} from 'lucide-react'
import { ApiError, getProjectById, getProjectChanges, getProjectRecommendations } from '@/lib/api'
import { mapProjectDetail } from '@/lib/mappers'
import { formatMonth } from '@/lib/format'
import { formatOptionalNumber } from '@/lib/format'
import { formatPercent, formatCrore, RISK_BADGE_CLASS } from '@/lib/risk'
import { cn } from '@/lib/utils'
import { PageHeader } from '@/components/page-header'
import { RiskBadge } from '@/components/risk-badge'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { ChartLegend } from '@/components/chart-legend'
import { CostTrendChart, ProgressChart, OverrunChart } from '@/components/project-charts'
import { RunPrediction } from '@/components/run-prediction'
import { ApiUnavailable } from '@/components/api-unavailable'

export const dynamic = 'force-dynamic'
export const dynamicParams = true

const SEVERITY_ICON_CLASS = {
  High: 'bg-risk-high/15 text-risk-high',
  Medium: 'bg-risk-medium/15 text-risk-medium',
  Low: 'bg-risk-low/15 text-risk-low',
} as const

const PRIORITY_BADGE_CLASS = {
  Urgent: 'bg-risk-high/15 text-risk-high border-risk-high/30',
  High: 'bg-risk-high/10 text-risk-high border-risk-high/20',
  Medium: 'bg-risk-medium/15 text-risk-medium border-risk-medium/30',
  Low: 'bg-risk-low/15 text-risk-low border-risk-low/30',
} as const

export default async function ProjectDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params

  try {
    const [payload, changesData, recsData] = await Promise.all([
      getProjectById(id),
      getProjectChanges(id).catch(() => null),
      getProjectRecommendations(id).catch(() => null),
    ])

    const project = mapProjectDetail(payload)
    const latest = project.history[project.history.length - 1]

    const meta = [
      { icon: Building2, label: 'Agency', value: project.agency },
      { icon: MapPin, label: 'State', value: project.state },
      { icon: Hash, label: 'Project ID', value: project.project_id },
      {
        icon: Calendar,
        label: 'Latest Report',
        value: formatMonth(project.latest_report),
      },
    ]

    const kpis = [
      {
        label: 'Risk Score',
        value: String(project.risk_score),
        icon: ShieldAlert,
        accent: 'text-foreground',
      },
      {
        label: 'Delay Probability',
        value: formatPercent(project.delay_probability, 1),
        icon: Gauge,
        accent: 'text-risk-high',
      },
      {
        label: 'Cost Overrun',
        value: formatOptionalNumber(latest?.cost_overrun, '%'),
        icon: TrendingUp,
        accent: 'text-risk-medium',
      },
      {
        label: 'Time Overrun',
        value: latest?.time_overrun === null || latest?.time_overrun === undefined
          ? '—'
          : `${latest.time_overrun} mo`,
        icon: Clock,
        accent: 'text-risk-medium',
      },
      {
        label: 'Physical Progress',
        value: formatOptionalNumber(latest?.physical_progress, '%'),
        icon: Activity,
        accent: 'text-risk-low',
      },
    ]

    return (
      <div className="flex flex-col gap-6">
        <Link
          href="/projects"
          className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          Back to projects
        </Link>

        <PageHeader
          title={project.name}
          subtitle={`Project ID ${project.project_id}`}
          actions={<RiskBadge level={project.risk_level} className="px-3 py-1 text-sm" />}
        />

        <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {meta.map((m) => {
            const Icon = m.icon
            return (
              <Card key={m.label} className="flex items-center gap-3 p-3.5">
                <div className="flex size-9 items-center justify-center rounded-md bg-muted text-muted-foreground">
                  <Icon className="size-4" />
                </div>
                <div className="min-w-0">
                  <p className="text-[11px] uppercase tracking-wide text-muted-foreground">
                    {m.label}
                  </p>
                  <p className="truncate text-sm font-medium text-foreground">{m.value}</p>
                </div>
              </Card>
            )
          })}
        </section>

        <section className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {kpis.map((k) => {
            const Icon = k.icon
            return (
              <Card key={k.label} className="p-4">
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Icon className="size-4" />
                  <span className="text-xs font-medium uppercase tracking-wide">{k.label}</span>
                </div>
                <p className={cn('mt-2 text-2xl font-semibold tabular-nums', k.accent)}>
                  {k.value}
                </p>
              </Card>
            )
          })}
        </section>

        <RunPrediction projectId={project.project_id} initial={project} />

        {/* Agent 3: Reporting Period Movements & Changes */}
        {changesData && (
          <section>
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <History className="size-4 text-primary" />
                      Reporting Period Movements (Agent 3)
                    </CardTitle>
                    <CardDescription>
                      {changesData.has_previous_period && changesData.previous_month
                        ? `Comparing ${changesData.previous_month} → ${changesData.current_month}`
                        : `Current reporting month: ${changesData.current_month || 'Latest'}`}
                    </CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <p className="text-xs leading-relaxed text-muted-foreground rounded-md bg-muted/40 p-3">
                  {changesData.summary}
                </p>

                {changesData.changes && changesData.changes.length > 0 ? (
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {changesData.changes.map((ch, idx) => (
                      <div
                        key={idx}
                        className="flex flex-col gap-1.5 rounded-md border border-border bg-background/50 p-3"
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                            {ch.category}
                          </span>
                          <span
                            className={cn(
                              'rounded px-1.5 py-0.5 text-[10px] font-semibold',
                              RISK_BADGE_CLASS[ch.severity as keyof typeof RISK_BADGE_CLASS] ||
                                'bg-muted text-foreground'
                            )}
                          >
                            {ch.delta}
                          </span>
                        </div>
                        <p className="text-sm font-medium text-foreground">{ch.metric}</p>
                        <p className="text-xs text-muted-foreground">
                          {ch.previous} → <span className="font-semibold text-foreground">{ch.current}</span>
                        </p>
                      </div>
                    ))}
                  </div>
                ) : null}
              </CardContent>
            </Card>
          </section>
        )}

        {/* Agent 4: Prescriptions & Recommendations */}
        {recsData && recsData.prescriptions && recsData.prescriptions.length > 0 && (
          <section>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Lightbulb className="size-4 text-primary" />
                  Prescriptions & Actionable Recommendations (Agent 4)
                </CardTitle>
                <CardDescription>
                  Data-grounded intervention strategies for {project.agency}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                {recsData.prescriptions.map((rx) => (
                  <div
                    key={rx.id}
                    className="flex flex-col gap-2 rounded-lg border border-border bg-background/50 p-4 transition-colors hover:bg-muted/20"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span
                          className={cn(
                            'rounded-md border px-2 py-0.5 text-xs font-semibold',
                            PRIORITY_BADGE_CLASS[rx.priority as keyof typeof PRIORITY_BADGE_CLASS] ||
                              'bg-muted text-muted-foreground'
                          )}
                        >
                          {rx.priority} Priority
                        </span>
                        <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                          {rx.category}
                        </span>
                      </div>
                    </div>

                    <h4 className="text-sm font-semibold text-foreground">{rx.action_title}</h4>
                    <p className="text-xs leading-relaxed text-muted-foreground">{rx.rationale}</p>

                    {rx.recommended_steps && rx.recommended_steps.length > 0 && (
                      <div className="mt-1 flex flex-col gap-1 border-t border-border/50 pt-2">
                        <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                          Action Steps:
                        </p>
                        <ul className="flex flex-col gap-1 pl-1">
                          {rx.recommended_steps.map((step, sIdx) => (
                            <li key={sIdx} className="flex items-start gap-2 text-xs text-foreground/90">
                              <CheckCircle2 className="size-3.5 shrink-0 text-primary mt-0.5" />
                              <span>{step}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>
          </section>
        )}

        <section>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TriangleAlert className="size-4 text-risk-medium" />
                Early-Warning Indicators
              </CardTitle>
              <CardDescription>
                Signals contributing to the predicted delay risk
              </CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {project.warnings.map((w) => (
                <div
                  key={w.id}
                  className="flex gap-3 rounded-md border border-border bg-background/40 p-3.5"
                >
                  <div
                    className={cn(
                      'flex size-8 shrink-0 items-center justify-center rounded-md',
                      SEVERITY_ICON_CLASS[w.severity],
                    )}
                  >
                    <TriangleAlert className="size-4" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-foreground">{w.title}</p>
                      <span
                        className={cn(
                          'rounded px-1.5 py-0.5 text-[10px] font-medium',
                          RISK_BADGE_CLASS[w.severity],
                        )}
                      >
                        {w.severity}
                      </span>
                    </div>
                    <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                      {w.detail}
                    </p>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </section>

        <section className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Cost Trajectory</CardTitle>
              <CardDescription>Sanctioned vs. anticipated cost and expenditure</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <CostTrendChart history={project.history} />
              <ChartLegend
                items={[
                  { label: 'Anticipated Cost', color: 'var(--chart-4)' },
                  { label: 'Expenditure', color: 'var(--chart-3)' },
                  { label: 'Sanctioned Cost', color: 'var(--muted-foreground)', dashed: true },
                ]}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Physical Progress</CardTitle>
              <CardDescription>Reported completion across available observations</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <ProgressChart history={project.history} />
              <ChartLegend items={[{ label: 'Physical Progress %', color: 'var(--chart-4)' }]} />
            </CardContent>
          </Card>

          <Card className="xl:col-span-2">
            <CardHeader>
              <CardTitle>Overrun Trend</CardTitle>
              <CardDescription>Cost overrun (%) and time overrun (months)</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <OverrunChart history={project.history} />
              <ChartLegend
                items={[
                  { label: 'Cost Overrun (%)', color: 'var(--chart-1)' },
                  { label: 'Time Overrun (months)', color: 'var(--chart-2)' },
                ]}
              />
            </CardContent>
          </Card>
        </section>

        <section>
          <Card>
            <CardHeader>
              <CardTitle>Monthly Report History</CardTitle>
              <CardDescription>
                {project.observation_count} observation
                {project.observation_count === 1 ? '' : 's'} returned by the API
              </CardDescription>
            </CardHeader>
            <CardContent className="px-0 pb-0">
              <div className="w-full overflow-x-auto">
                <table className="w-full min-w-[720px] border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                      <th className="px-4 py-3 font-medium">Report Month</th>
                      <th className="px-4 py-3 font-medium">Anticipated Cost</th>
                      <th className="px-4 py-3 font-medium">Expenditure</th>
                      <th className="px-4 py-3 font-medium">Progress</th>
                      <th className="px-4 py-3 font-medium">Cost Overrun</th>
                      <th className="px-4 py-3 font-medium">Time Overrun</th>
                      <th className="px-4 py-3 font-medium">Anticipated Completion</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...project.history].reverse().map((h, index) => (
                      <tr
                        key={`${h.report_month}-${index}`}
                        className="border-b border-border/60 last:border-0 hover:bg-muted/40"
                      >
                        <td className="px-4 py-3 font-medium text-foreground">
                          {formatMonth(h.report_month)}
                        </td>
                        <td className="px-4 py-3 tabular-nums text-muted-foreground">
                          {formatCrore(h.anticipated_cost)}
                        </td>
                        <td className="px-4 py-3 tabular-nums text-muted-foreground">
                          {formatCrore(h.expenditure)}
                        </td>
                        <td className="px-4 py-3 tabular-nums text-muted-foreground">
                          {formatOptionalNumber(h.physical_progress, '%')}
                        </td>
                        <td className="px-4 py-3 tabular-nums text-muted-foreground">
                          {formatOptionalNumber(h.cost_overrun, '%')}
                        </td>
                        <td className="px-4 py-3 tabular-nums text-muted-foreground">
                          {h.time_overrun === null || h.time_overrun === undefined
                            ? '—'
                            : `${h.time_overrun} mo`}
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">
                          {formatMonth(h.anticipated_completion)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </section>
      </div>
    )
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      notFound()
    }

    const message =
      error instanceof ApiError ? error.message : 'PAIMANA API is currently unavailable.'

    return (
      <div className="flex flex-col gap-6">
        <Link
          href="/projects"
          className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          Back to projects
        </Link>
        <PageHeader title="Project details" subtitle={`Project ID ${id}`} />
        <ApiUnavailable message={message} />
      </div>
    )
  }
}
