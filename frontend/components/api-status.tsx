'use client'

import { useCallback, useEffect, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { getHealth } from '@/lib/api'
import { cn } from '@/lib/utils'

type Status = 'checking' | 'connected' | 'offline'

export function ApiStatus() {
  const [status, setStatus] = useState<Status>('checking')

  const check = useCallback(async () => {
    setStatus('checking')
    try {
      const health = await getHealth()
      setStatus(health.status === 'ok' ? 'connected' : 'offline')
    } catch {
      setStatus('offline')
    }
  }, [])

  useEffect(() => {
    void check()
    const id = window.setInterval(() => {
      void check()
    }, 30000)
    return () => window.clearInterval(id)
  }, [check])

  const connected = status === 'connected'

  return (
    <div className="rounded-md border border-sidebar-border bg-sidebar-accent/40 px-3 py-2.5">
      <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
        System Status
      </p>
      <div className="mt-1.5 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="relative flex size-2">
            {connected ? (
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-risk-low opacity-60" />
            ) : null}
            <span
              className={cn(
                'relative inline-flex size-2 rounded-full',
                status === 'checking'
                  ? 'bg-risk-medium'
                  : connected
                    ? 'bg-risk-low'
                    : 'bg-risk-high',
              )}
            />
          </span>
          <span className="text-xs font-medium text-sidebar-foreground">
            {status === 'checking'
              ? 'Checking API…'
              : connected
                ? 'API Connected'
                : 'API Offline'}
          </span>
        </div>
        <button
          type="button"
          onClick={() => void check()}
          aria-label="Retry API health check"
          className="rounded p-0.5 text-muted-foreground transition-colors hover:text-sidebar-foreground"
        >
          <RefreshCw className={cn('size-3', status === 'checking' && 'animate-spin')} />
        </button>
      </div>
    </div>
  )
}
