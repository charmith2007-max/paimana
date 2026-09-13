import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Card } from '@/components/ui/card'

export function KpiCard({
  label,
  value,
  hint,
  icon: Icon,
  accentClass,
  iconBgClass,
}: {
  label: string
  value: string | number
  hint?: string
  icon: LucideIcon
  accentClass?: string
  iconBgClass?: string
}) {
  return (
    <Card className="p-4 transition-colors hover:border-border/80 hover:bg-card/80">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {label}
          </p>
          <p className={cn('mt-2 text-3xl font-semibold tracking-tight tabular-nums', accentClass)}>
            {value}
          </p>
          {hint ? <p className="mt-1 text-xs text-muted-foreground">{hint}</p> : null}
        </div>
        <div
          className={cn(
            'flex size-9 shrink-0 items-center justify-center rounded-md',
            iconBgClass ?? 'bg-primary/15 text-primary ring-1 ring-inset ring-primary/25',
          )}
        >
          <Icon className="size-4.5" />
        </div>
      </div>
    </Card>
  )
}
