'use client'

import { useMemo, useState } from 'react'
import { Search, X } from 'lucide-react'
import type { ProjectSummary, RiskLevel } from '@/lib/types'
import { deduplicateProjectsByLatestReport } from '@/lib/mappers'
import { cn } from '@/lib/utils'
import { ProjectsTable } from '@/components/projects-table'
import { Card } from '@/components/ui/card'

const RISK_OPTIONS: (RiskLevel | 'All')[] = ['All', 'High', 'Medium', 'Low']

function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  options: string[]
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-9 rounded-md border border-input bg-background px-3 text-sm text-foreground outline-none transition-colors focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
      >
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
    </label>
  )
}

export function ProjectsExplorer({
  projects,
  states,
  agencies,
}: {
  projects: ProjectSummary[]
  states: string[]
  agencies: string[]
}) {
  const [query, setQuery] = useState('')
  const [state, setState] = useState('All')
  const [agency, setAgency] = useState('All')
  const [risk, setRisk] = useState('All')

  const uniqueProjects = useMemo(() => {
    return deduplicateProjectsByLatestReport(projects)
  }, [projects])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return uniqueProjects.filter((p) => {
      if (state !== 'All' && p.state !== state) return false
      if (agency !== 'All' && p.agency !== agency) return false
      if (risk !== 'All' && p.risk_level !== risk) return false
      if (q) {
        const haystack = `${p.name} ${p.project_id} ${p.agency}`.toLowerCase()
        if (!haystack.includes(q)) return false
      }
      return true
    })
  }, [uniqueProjects, query, state, agency, risk])

  const hasFilters = query || state !== 'All' || agency !== 'All' || risk !== 'All'

  function reset() {
    setQuery('')
    setState('All')
    setAgency('All')
    setRisk('All')
  }

  return (
    <div className="flex flex-col gap-4">
      <Card className="p-4">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-4">
          <label className="flex flex-col gap-1.5 md:col-span-2 lg:col-span-1">
            <span className="text-xs font-medium text-muted-foreground">Search</span>
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Name, ID, agency…"
                className="h-9 w-full rounded-md border border-input bg-background pl-8 pr-3 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40"
              />
            </div>
          </label>
          <Select label="State" value={state} onChange={setState} options={['All', ...states]} />
          <Select
            label="Agency"
            value={agency}
            onChange={setAgency}
            options={['All', ...agencies]}
          />
          <Select label="Risk Level" value={risk} onChange={setRisk} options={RISK_OPTIONS} />
        </div>

        <div className="mt-3 flex items-center justify-between border-t border-border pt-3">
          <p className="text-xs text-muted-foreground">
            Showing{' '}
            <span className="font-semibold text-foreground">{filtered.length}</span> of{' '}
            {uniqueProjects.length} projects
          </p>
          <button
            type="button"
            onClick={reset}
            disabled={!hasFilters}
            className={cn(
              'inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
              hasFilters
                ? 'text-foreground hover:bg-muted'
                : 'cursor-not-allowed text-muted-foreground/50',
            )}
          >
            <X className="size-3.5" />
            Clear filters
          </button>
        </div>
      </Card>

      <Card className="overflow-hidden">
        <ProjectsTable projects={filtered} showLatestReport />
      </Card>
    </div>
  )
}
