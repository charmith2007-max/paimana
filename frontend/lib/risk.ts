import type { RiskLevel } from './types'

/** Matches FastAPI risk_level(): <30 Low, <=60 Medium, else High. */
export function riskLevelFromScore(score: number): RiskLevel {
  if (score < 30) return 'Low'
  if (score <= 60) return 'Medium'
  return 'High'
}

export const RISK_COLORS: Record<RiskLevel, string> = {
  High: 'var(--risk-high)',
  Medium: 'var(--risk-medium)',
  Low: 'var(--risk-low)',
}

/** Tailwind classes for a filled risk badge. */
export const RISK_BADGE_CLASS: Record<RiskLevel, string> = {
  High: 'bg-risk-high/15 text-risk-high ring-1 ring-inset ring-risk-high/30',
  Medium: 'bg-risk-medium/15 text-risk-medium ring-1 ring-inset ring-risk-medium/30',
  Low: 'bg-risk-low/15 text-risk-low ring-1 ring-inset ring-risk-low/30',
}

/** Text-only accent for scores. */
export const RISK_TEXT_CLASS: Record<RiskLevel, string> = {
  High: 'text-risk-high',
  Medium: 'text-risk-medium',
  Low: 'text-risk-low',
}

export function formatPercent(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${(value * 100).toFixed(digits)}%`
}

export function formatCrore(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `Rs ${value.toLocaleString('en-IN')} cr`
}
