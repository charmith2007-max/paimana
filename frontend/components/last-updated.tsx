import { Activity } from 'lucide-react'

function formatTimestamp(iso: string): string {
  return new Date(iso).toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function LastUpdated({ timestamp }: { timestamp: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-md border border-border bg-card/60 px-2.5 py-1 text-xs text-muted-foreground">
      <Activity className="size-3.5 text-risk-low" />
      <span className="hidden sm:inline">Last updated</span>
      <span className="font-medium text-foreground">{formatTimestamp(timestamp)}</span>
    </span>
  )
}
