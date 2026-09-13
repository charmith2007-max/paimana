'use client'

import {
  Bar,
  BarChart,
  Cell,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { RISK_COLORS } from '@/lib/risk'
import { riskLevelFromScore } from '@/lib/risk'

const AXIS = {
  stroke: 'var(--muted-foreground)',
  fontSize: 11,
  tickLine: false,
  axisLine: false,
}

const TOOLTIP_STYLE = {
  background: 'var(--popover)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  fontSize: 12,
  color: 'var(--popover-foreground)',
}

export function ProjectRiskBar({
  data,
}: {
  data: { name: string; score: number }[]
}) {
  return (
    <ResponsiveContainer width="100%" height={Math.max(220, data.length * 34)}>
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 4, right: 16, left: 8, bottom: 4 }}
        barCategoryGap={10}
      >
        <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" horizontal={false} />
        <XAxis type="number" domain={[0, 100]} {...AXIS} />
        <YAxis
          type="category"
          dataKey="name"
          width={150}
          {...AXIS}
          tickFormatter={(v: string) => (v.length > 22 ? `${v.slice(0, 21)}…` : v)}
        />
        <Tooltip
          cursor={{ fill: 'var(--muted)', opacity: 0.4 }}
          contentStyle={TOOLTIP_STYLE}
          formatter={(value) => [`${value}`, 'Risk Score']}
        />
        <Bar dataKey="score" radius={[0, 4, 4, 0]}>
          {data.map((d) => (
            <Cell key={d.name} fill={RISK_COLORS[riskLevelFromScore(d.score)]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

export function SectorRiskBar({
  data,
}: {
  data: { sector: string; avg: number }[]
}) {
  const chartData = data.slice(0, 12)

  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart
        data={chartData}
        margin={{ top: 8, right: 16, left: 0, bottom: 45 }}
        barCategoryGap={18}
      >
        <CartesianGrid
          stroke="var(--border)"
          strokeDasharray="3 3"
          vertical={false}
        />

        <XAxis
          dataKey="sector"
          {...AXIS}
          interval={0}
          angle={-35}
          textAnchor="end"
          height={70}
          tickFormatter={(v: string) =>
            v.length > 15 ? `${v.slice(0, 14)}…` : v
          }
        />

        <YAxis domain={[0, 100]} width={36} {...AXIS} />

        <Tooltip
          cursor={{ fill: 'var(--muted)', opacity: 0.4 }}
          contentStyle={TOOLTIP_STYLE}
          formatter={(value) => [`${value}`, 'Avg Risk Score']}
        />

        <Bar dataKey="avg" radius={[4, 4, 0, 0]}>
          {chartData.map((d) => (
            <Cell
              key={d.sector}
              fill={RISK_COLORS[riskLevelFromScore(d.avg)]}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}