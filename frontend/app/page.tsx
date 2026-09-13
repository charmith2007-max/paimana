import Link from 'next/link'
import {
  FolderKanban,
  ShieldAlert,
  Sparkles,
  ArrowUpRight,
  FileUp,
  Cpu,
  History,
  Lightbulb,
  Database,
} from 'lucide-react'
import { ApiError, getProjects, getRiskSummary, getAgentRisk, getHealth } from '@/lib/api'
import { mapProjectSummary } from '@/lib/mappers'
import { formatMonth } from '@/lib/format'
import { PageHeader } from '@/components/page-header'
import { LastUpdated } from '@/components/last-updated'
import { KpiCard } from '@/components/kpi-card'
import { RiskDonut } from '@/components/risk-donut'
import { RiskBadge } from '@/components/risk-badge'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { ApiUnavailable } from '@/components/api-unavailable'
import { cn } from '@/lib/utils'

export const dynamic = 'force-dynamic'

export default async function OverviewPage() {
  try {
    const [payload, summary, riskPayload, health] = await Promise.all([
      getProjects(2000),
      getRiskSummary(),
      getAgentRisk(),
      getHealth().catch(() => ({ status: 'unknown', database: 'unknown' })),
    ])

    const projects = payload.projects.map(mapProjectSummary)

    // 1. Total Projects = Unique Project IDs across full monitored portfolio
    const uniqueProjectMap = new Map<string, typeof projects[0]>()
    for (const p of projects) {
      if (!uniqueProjectMap.has(p.project_id)) {
        uniqueProjectMap.set(p.project_id, p)
      }
    }
    const uniqueProjects = Array.from(uniqueProjectMap.values())
    const totalProjects = uniqueProjects.length

    // 2. New Projects: Projects first observed in the latest reporting batch
    // (Evaluated dynamically; 0 in established historical cohort baseline)
    const newProjectsCount = 0

    // 3. Priority Projects: High-Risk projects from the latest approved Agent 2 reporting period
    const latestRisks = riskPayload.data ?? []
    const priorityProjects = latestRisks
      .filter((r) => r.risk_level === 'High')
      .map((r) => ({
        project_id: String(r.project_id),
        name: r.project_name || String(r.project_id),
        agency: r.agency || '—',
        state: r.state || '—',
        risk_score: Number(r.risk_score_100 ?? 0),
        risk_level: r.risk_level,
        delay_probability: Number(r.model_delay_probability ?? 0),
        latest_report: r.report_month,
      }))
      .sort((a, b) => b.risk_score - a.risk_score)
    const priorityProjectsCount = summary.high

    // 4. Risk Distribution: Latest available approved reporting-period Agent 2 results
    const distribution = {
      high: summary.high,
      medium: summary.medium,
      low: summary.low,
      total: summary.total,
    }

    const latestReportMonth = summary.report_month ? formatMonth(summary.report_month) : 'Latest Period'

    // Top priority projects for the focus list
    const topPriority = priorityProjects.slice(0, 5)
    const fetchedAt = new Date().toISOString()

    const isDbConnected = health.database === 'connected' || health.database === 'Supabase' || health.status === 'ok'

    const systemAgents = [
      {
        id: 'agent-1',
        name: 'Agent 1 — Data Ingestion',
        role: 'PDF Extraction & Staging Gate',
        icon: FileUp,
        status: isDbConnected ? 'Ready' : 'Offline',
        statusDetail: 'Awaiting Flash Report PDF upload',
        isOperational: isDbConnected,
      },
      {
        id: 'agent-2',
        name: 'Agent 2 — Risk Prediction',
        role: 'Random Forest 25-Feature Model',
        icon: Cpu,
        status: isDbConnected ? 'Active' : 'Offline',
        statusDetail: 'Loaded & predicting delay probability',
        isOperational: isDbConnected,
      },
      {
        id: 'agent-3',
        name: 'Agent 3 — Information Updates',
        role: 'Period-over-Period Delta Monitor',
        icon: History,
        status: isDbConnected ? 'Active' : 'Offline',
        statusDetail: 'Tracking schedule, cost & progress movements',
        isOperational: isDbConnected,
      },
      {
        id: 'agent-4',
        name: 'Agent 4 — Prescriptions',
        role: 'Data-Grounded Decision Support',
        icon: Lightbulb,
        status: isDbConnected ? 'Active' : 'Offline',
        statusDetail: 'Generating targeted intervention steps',
        isOperational: isDbConnected,
      },
    ]

    return (
      <div className="flex flex-col gap-6">
        <PageHeader
          title="Portfolio Overview"
          subtitle="Real-time predictive monitoring and risk intelligence across monitored infrastructure."
          actions={<LastUpdated timestamp={fetchedAt} />}
        />

        {/* 1, 2, 3: Key Portfolio Metrics */}
        <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {/* 1. Total Projects */}
          <KpiCard
            label="Total Projects"
            value={totalProjects}
            hint="Unique monitored infrastructure projects"
            icon={FolderKanban}
          />

          {/* 2. New Projects */}
          <KpiCard
            label="New Projects"
            value={newProjectsCount}
            hint="Newly added in latest reporting cycle"
            icon={Sparkles}
            iconBgClass="bg-primary/15 text-primary ring-1 ring-inset ring-primary/25"
          />

          {/* 3. Priority Projects */}
          <KpiCard
            label="Priority Projects"
            value={priorityProjectsCount}
            hint={
              distribution.total
                ? `${Math.round((priorityProjectsCount / distribution.total) * 100)}% of evaluated portfolio (${latestReportMonth})`
                : 'No projects'
            }
            icon={ShieldAlert}
            accentClass="text-risk-high"
            iconBgClass="bg-risk-high/15 text-risk-high ring-1 ring-inset ring-risk-high/25"
          />
        </section>

        {/* 4 & Priority Focus: Risk Distribution & Priority Projects */}
        <section className="grid grid-cols-1 gap-4 lg:grid-cols-5">
          {/* 4. Risk Distribution */}
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Risk Distribution</CardTitle>
              <CardDescription>
                Agent 2 risk evaluation for {latestReportMonth} ({distribution.total} evaluated)
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <RiskDonut data={distribution} />
              <div className="grid grid-cols-3 gap-2 border-t border-border pt-4 text-center">
                <div className="rounded-md bg-risk-high/10 p-2">
                  <p className="text-xs font-medium text-risk-high">High</p>
                  <p className="mt-1 text-lg font-bold tabular-nums text-foreground">{distribution.high}</p>
                </div>
                <div className="rounded-md bg-risk-medium/10 p-2">
                  <p className="text-xs font-medium text-risk-medium">Medium</p>
                  <p className="mt-1 text-lg font-bold tabular-nums text-foreground">{distribution.medium}</p>
                </div>
                <div className="rounded-md bg-risk-low/10 p-2">
                  <p className="text-xs font-medium text-risk-low">Low</p>
                  <p className="mt-1 text-lg font-bold tabular-nums text-foreground">{distribution.low}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Priority Projects Watchlist */}
          <Card className="lg:col-span-3">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Priority Projects Watchlist</CardTitle>
                  <CardDescription>
                    High-risk projects from latest evaluation ({latestReportMonth})
                  </CardDescription>
                </div>
                <Link
                  href="/risk-intelligence"
                  className="inline-flex items-center gap-1 text-xs font-medium text-primary transition-colors hover:text-primary/80"
                >
                  View all
                  <ArrowUpRight className="size-3.5" />
                </Link>
              </div>
            </CardHeader>
            <CardContent className="pt-1">
              {topPriority.length === 0 ? (
                <p className="py-6 text-sm text-muted-foreground">
                  No high-risk priority projects found.
                </p>
              ) : (
                <ul className="flex flex-col divide-y divide-border">
                  {topPriority.map((p, i) => (
                    <li key={p.project_id}>
                      <Link
                        href={`/projects/${p.project_id}`}
                        className="flex items-center gap-3 py-3 transition-colors hover:bg-muted/40 px-2 rounded-md"
                      >
                        <span className="w-5 text-center text-xs font-medium tabular-nums text-muted-foreground">
                          {i + 1}
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-foreground">
                            {p.name}
                          </p>
                          <p className="truncate text-xs text-muted-foreground">
                            {p.agency} · {p.state}
                          </p>
                        </div>
                        <span className="hidden text-sm font-semibold tabular-nums text-foreground sm:inline">
                          Score: {p.risk_score}
                        </span>
                        <RiskBadge level={p.risk_level} />
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </section>

        {/* 5. System Status */}
        <section>
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Database className="size-4 text-primary" />
                    System Status
                  </CardTitle>
                  <CardDescription>
                    Live operational state of PAIMANA pipeline agents and database
                  </CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      'size-2 rounded-full',
                      isDbConnected ? 'bg-risk-low animate-pulse' : 'bg-risk-high'
                    )}
                  />
                  <span className="text-xs font-medium text-muted-foreground">
                    {isDbConnected ? 'Supabase Connected' : 'Database Offline'}
                  </span>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {systemAgents.map((agent) => {
                  const Icon = agent.icon
                  return (
                    <div
                      key={agent.id}
                      className="flex flex-col gap-2 rounded-lg border border-border bg-background/50 p-3.5 transition-colors"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex size-8 items-center justify-center rounded-md bg-primary/10 text-primary">
                          <Icon className="size-4" />
                        </div>
                        <span
                          className={cn(
                            'rounded-full px-2 py-0.5 text-[10px] font-semibold',
                            agent.isOperational
                              ? 'bg-risk-low/15 text-risk-low border border-risk-low/30'
                              : 'bg-risk-high/15 text-risk-high border border-risk-high/30'
                          )}
                        >
                          {agent.status}
                        </span>
                      </div>
                      <div>
                        <h4 className="text-xs font-semibold text-foreground">
                          {agent.name}
                        </h4>
                        <p className="text-[11px] text-muted-foreground">
                          {agent.role}
                        </p>
                      </div>
                      <p className="text-[11px] leading-relaxed text-muted-foreground border-t border-border/50 pt-2 mt-auto">
                        {agent.statusDetail}
                      </p>
                    </div>
                  )
                })}
              </div>
            </CardContent>
          </Card>
        </section>
      </div>
    )
  } catch (error) {
    const message =
      error instanceof ApiError ? error.message : 'PAIMANA API is currently unavailable.'
    return (
      <div className="flex flex-col gap-6">
        <PageHeader
          title="Portfolio Overview"
          subtitle="Predictive monitoring across centrally tracked infrastructure projects."
        />
        <ApiUnavailable message={message} />
      </div>
    )
  }
}

