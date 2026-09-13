'use client'

import { useRouter } from 'next/navigation'
import { TriangleAlert, RefreshCw } from 'lucide-react'
import { API_UNAVAILABLE_MESSAGE } from '@/lib/api'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

export function ApiUnavailable({
  message = API_UNAVAILABLE_MESSAGE,
}: {
  message?: string
}) {
  const router = useRouter()

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
        <Button variant="outline" size="sm" onClick={() => router.refresh()}>
          <RefreshCw className="size-3.5" />
          Retry
        </Button>
      </CardContent>
    </Card>
  )
}
