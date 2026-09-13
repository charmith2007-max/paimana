import Link from 'next/link'
import { ArrowUpRight } from 'lucide-react'
import type { ProjectSummary } from '@/lib/types'
import { formatMonth } from '@/lib/format'
import { formatPercent } from '@/lib/risk'
import { RiskBadge } from '@/components/risk-badge'
import { RiskScore } from '@/components/risk-score'

export function ProjectsTable({
  projects,
  showLatestReport = false,
  emptyMessage = 'No projects match the current filters.',
}: {
  projects: ProjectSummary[]
  showLatestReport?: boolean
  emptyMessage?: string
}) {
  return (
    <div className="w-full overflow-x-auto">
      <table className="w-full min-w-[860px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
            <th className="whitespace-nowrap px-4 py-3 font-medium">Project</th>
            <th className="whitespace-nowrap px-4 py-3 font-medium">Project ID</th>
            <th className="whitespace-nowrap px-4 py-3 font-medium">Agency</th>
            <th className="whitespace-nowrap px-4 py-3 font-medium">State</th>
            {showLatestReport ? (
              <th className="whitespace-nowrap px-4 py-3 font-medium">Latest Report</th>
            ) : null}
            <th className="whitespace-nowrap px-4 py-3 font-medium">Risk Score</th>
            <th className="whitespace-nowrap px-4 py-3 font-medium">Risk Level</th>
            <th className="whitespace-nowrap px-4 py-3 font-medium">Delay Prob.</th>
            <th className="whitespace-nowrap px-4 py-3 text-right font-medium">Action</th>
          </tr>
        </thead>
        <tbody>
          {projects.length === 0 ? (
            <tr>
              <td
                colSpan={showLatestReport ? 9 : 8}
                className="px-4 py-10 text-center text-muted-foreground"
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            projects.map((p) => (
              <tr
                key={p.project_id}
                className="border-b border-border/60 transition-colors last:border-0 hover:bg-muted/40"
              >
                <td className="px-4 py-3">
                  <div className="max-w-[280px]">
                    <p className="truncate font-medium text-foreground">{p.name}</p>
                    {p.sector ? (
                      <p className="truncate text-xs text-muted-foreground">{p.sector}</p>
                    ) : null}
                  </div>
                </td>
                <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                  {p.project_id}
                </td>
                <td className="px-4 py-3 text-muted-foreground">{p.agency}</td>
                <td className="px-4 py-3 text-muted-foreground">{p.state}</td>
                {showLatestReport ? (
                  <td className="px-4 py-3 text-muted-foreground">
                    {formatMonth(p.latest_report)}
                  </td>
                ) : null}
                <td className="px-4 py-3">
                  <RiskScore score={p.risk_score} level={p.risk_level} />
                </td>
                <td className="px-4 py-3">
                  <RiskBadge level={p.risk_level} />
                </td>
                <td className="px-4 py-3 font-medium tabular-nums text-foreground">
                  {formatPercent(p.delay_probability)}
                </td>
                <td className="px-4 py-3 text-right">
                  <Link
                    href={`/projects/${p.project_id}`}
                    className="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-xs font-medium text-foreground transition-colors hover:border-primary/40 hover:bg-primary/10 hover:text-primary"
                  >
                    View
                    <ArrowUpRight className="size-3.5" />
                  </Link>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}
