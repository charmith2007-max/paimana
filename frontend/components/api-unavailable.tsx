'use client'

import { useCallback, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { TriangleAlert, RefreshCw } from 'lucide-react'
import { API_UNAVAILABLE_MESSAGE, getHealth } from '@/lib/api'
import { cn } from '@/lib/utils'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

export function ApiUnavailable({
  message = API_UNAVAILABLE_MESSAGE,
}: {
  message?: string
}) {
  const router = useRouter()
  const [retrying, setRetrying] = useState(false)

  const handleRetry = useCallback(() => {
    setRetrying(true)
    router.refresh()
    setTimeout(() => {
      setRetrying(false)
    }, 1500)
  }, [router])

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const health = await getHealth()
        if (health.status === 'ok') {
          router.refresh()
        }
      } catch {
        // API still unavailable, continue polling
      }
    }

    const id = window.setInterval(() => {
      void checkHealth()
    }, 3000)

    return () => window.clearInterval(id)
  }, [router])

  return (
    <Card>
      <CardContent className="flex flex-col items-start gap-3 p-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-md bg-risk-high/15 text-risk-high">
            <TriangleAlert className="size-4" />
          </div>
          <div>
            <p className="text-sm font-medium text-foreground">{message}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Check that the FastAPI service is running, then retry.
            </p>
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleRetry}
          disabled={retrying}
        >
          <RefreshCw className={cn('size-3.5', retrying && 'animate-spin')} />
          {retrying ? 'Retrying…' : 'Retry'}
        </Button>
      </CardContent>
    </Card>
  )
}

