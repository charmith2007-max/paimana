import { cn } from '@/lib/utils'
import { RISK_BADGE_CLASS } from '@/lib/risk'
import type { RiskLevel } from '@/lib/types'

export function RiskBadge({
  level,
  className,
}: {
  level: RiskLevel
  className?: string
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium',
        RISK_BADGE_CLASS[level],
        className,
      )}
    >
      <span
        aria-hidden
        className="size-1.5 rounded-full bg-current"
      />
      {level}
    </span>
  )
}
