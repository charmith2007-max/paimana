'use client'

import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { MonthlyReport } from '@/lib/types'
import { formatMonth } from '@/lib/format'

const AXIS = {
  stroke: 'var(--muted-foreground)',
  fontSize: 11,
  tickLine: false,
  axisLine: false,
}

const GRID_STROKE = 'var(--border)'

const TOOLTIP_STYLE = {
  background: 'var(--popover)',
  border: '1px solid var(--border)',
  borderRadius: 8,
  fontSize: 12,
  color: 'var(--popover-foreground)',
}

type ChartRow = MonthlyReport & { label: string }

function useRows(history: MonthlyReport[]): ChartRow[] {
  return history.map((h) => ({ ...h, label: formatMonth(h.report_month) }))
}

export function CostTrendChart({ history }: { history: MonthlyReport[] }) {
  const rows = useRows(history)
  return (
    <ResponsiveContainer width="100%" height={240}>
      <AreaChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="antCost" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--chart-4)" stopOpacity={0.35} />
            <stop offset="100%" stopColor="var(--chart-4)" stopOpacity={0.02} />
          </linearGradient>
          <linearGradient id="expend" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--chart-3)" stopOpacity={0.3} />
            <stop offset="100%" stopColor="var(--chart-3)" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={GRID_STROKE} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="label" {...AXIS} minTickGap={16} />
        <YAxis {...AXIS} width={56} tickFormatter={(v) => `Rs ${(v / 1000).toFixed(0)}k`} />
        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          formatter={(value, name) => [
            value === null || value === undefined ? '—' : `Rs ${Number(value).toLocaleString('en-IN')} cr`,
            name,
          ]}
        />
        <Area
          type="monotone"
          dataKey="anticipated_cost"
          name="Anticipated Cost"
          stroke="var(--chart-4)"
          strokeWidth={2}
          fill="url(#antCost)"
        />
        <Area
          type="monotone"
          dataKey="expenditure"
          name="Expenditure"
          stroke="var(--chart-3)"
          strokeWidth={2}
          fill="url(#expend)"
        />
        <Line
          type="monotone"
          dataKey="original_cost"
          name="Sanctioned Cost"
          stroke="var(--muted-foreground)"
          strokeWidth={1.5}
          strokeDasharray="4 4"
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}

export function ProgressChart({ history }: { history: MonthlyReport[] }) {
  const rows = useRows(history)
  return (
    <ResponsiveContainer width="100%" height={240}>
      <AreaChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="progress" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--chart-4)" stopOpacity={0.35} />
            <stop offset="100%" stopColor="var(--chart-4)" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={GRID_STROKE} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="label" {...AXIS} minTickGap={16} />
        <YAxis {...AXIS} width={40} domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          formatter={(value) => [
            value === null || value === undefined ? '—' : `${value}%`,
            'Physical Progress',
          ]}
        />
        <Area
          type="monotone"
          dataKey="physical_progress"
          name="Physical Progress"
          stroke="var(--chart-4)"
          strokeWidth={2}
          fill="url(#progress)"
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}

export function OverrunChart({ history }: { history: MonthlyReport[] }) {
  const rows = useRows(history)
  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={GRID_STROKE} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="label" {...AXIS} minTickGap={16} />
        <YAxis
          yAxisId="left"
          {...AXIS}
          width={44}
          tickFormatter={(v) => `${v}%`}
        />
        <YAxis
          yAxisId="right"
          orientation="right"
          {...AXIS}
          width={36}
          tickFormatter={(v) => `${v}m`}
        />
        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          formatter={(value, name) => {
            if (value === null || value === undefined) return ['—', String(name)]
            return name === 'Cost Overrun' ? [`${value}%`, name] : [`${value} months`, name]
          }}
        />
        <Line
          yAxisId="left"
          type="monotone"
          dataKey="cost_overrun"
          name="Cost Overrun"
          stroke="var(--chart-1)"
          strokeWidth={2}
          dot={false}
        />
        <Line
          yAxisId="right"
          type="monotone"
          dataKey="time_overrun"
          name="Time Overrun"
          stroke="var(--chart-2)"
          strokeWidth={2}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
