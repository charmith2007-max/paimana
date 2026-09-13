'use client'

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { RISK_COLORS } from '@/lib/risk'
import type { RiskDistribution } from '@/lib/types'

export function RiskDonut({ data }: { data: RiskDistribution }) {
  const slices = [
    { name: 'High Risk', level: 'High' as const, value: data.high },
    { name: 'Medium Risk', level: 'Medium' as const, value: data.medium },
    { name: 'Low Risk', level: 'Low' as const, value: data.low },
  ]

  return (
    <div className="flex flex-col items-center gap-6 sm:flex-row sm:justify-between">
      <div className="relative h-44 w-44 shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={slices}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              innerRadius={58}
              outerRadius={82}
              paddingAngle={2}
              stroke="var(--card)"
              strokeWidth={2}
              startAngle={90}
              endAngle={-270}
            >
              {slices.map((s) => (
                <Cell key={s.level} fill={RISK_COLORS[s.level]} />
              ))}
            </Pie>
            <Tooltip
              cursor={false}
              contentStyle={{
                background: 'var(--popover)',
                border: '1px solid var(--border)',
                borderRadius: 8,
                fontSize: 12,
                color: 'var(--popover-foreground)',
              }}
              itemStyle={{ color: 'var(--popover-foreground)' }}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-semibold tabular-nums text-foreground">
            {data.total}
          </span>
          <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
            Projects
          </span>
        </div>
      </div>

      <ul className="flex w-full flex-col gap-2.5 sm:max-w-[210px]">
        {slices.map((s) => {
          const pct = data.total ? Math.round((s.value / data.total) * 100) : 0
          return (
            <li
              key={s.level}
              className="flex items-center justify-between rounded-md border border-border bg-background/40 px-3 py-2"
            >
              <span className="flex items-center gap-2 text-sm text-muted-foreground">
                <span
                  aria-hidden
                  className="size-2.5 rounded-sm"
                  style={{ background: RISK_COLORS[s.level] }}
                />
                {s.name}
              </span>
              <span className="text-sm font-semibold tabular-nums text-foreground">
                {s.value}
                <span className="ml-1 text-xs font-normal text-muted-foreground">
                  {pct}%
                </span>
              </span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
