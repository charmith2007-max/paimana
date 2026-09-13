import { cn } from '@/lib/utils'
import { RISK_COLORS, RISK_TEXT_CLASS } from '@/lib/risk'
import type { RiskLevel } from '@/lib/types'

export function RiskScore({
  score,
  level,
  className,
}: {
  score: number
  level: RiskLevel
  className?: string
}) {
  return (
    <div className={cn('flex items-center gap-2.5', className)}>
      <span className={cn('w-8 text-sm font-semibold tabular-nums', RISK_TEXT_CLASS[level])}>
        {Number(score).toFixed(1)}
      </span>
      <div
        className="h-1.5 w-16 overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-valuenow={score}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className="h-full rounded-full"
          style={{ width: `${score}%`, background: RISK_COLORS[level] }}
        />
      </div>
    </div>
  )
}
