'use client'

import { useEffect, useState } from 'react'
import {
  CheckCircle2,
  FileUp,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Trash2,
  AlertCircle,
  ArrowRight,
} from 'lucide-react'
import {
  approveIngestion,
  deleteIngestionRecord,
  getIngestionRun,
  getIngestionRuns,
  uploadFlashReport,
  type IngestionRecord,
  type IngestionRun,
} from '@/lib/api'
import { Card } from '@/components/ui/card'

export default function DataIngestionPage() {
  const [file, setFile] = useState<File | null>(null)
  const [reportMonth, setReportMonth] = useState('')
  const [runs, setRuns] = useState<IngestionRun[]>([])
  const [selectedRun, setSelectedRun] = useState<IngestionRun | null>(null)
  const [records, setRecords] = useState<IngestionRecord[]>([])

  const [loading, setLoading] = useState(false)
  const [loadingRuns, setLoadingRuns] = useState(true)
  const [approving, setApproving] = useState(false)
  const [deleting, setDeleting] = useState<number | null>(null)

  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function loadRuns() {
    try {
      setLoadingRuns(true)
      const response = await getIngestionRuns()
      setRuns(response.runs || [])
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to load ingestion runs.',
      )
    } finally {
      setLoadingRuns(false)
    }
  }

  useEffect(() => {
    loadRuns()
  }, [])

  async function handleUpload() {
    if (!file) {
      setError('Please select a PDF Flash Report first.')
      return
    }

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Only PDF Flash Reports are supported.')
      return
    }

    try {
      setLoading(true)
      setError('')
      setMessage('')
      setSelectedRun(null)
      setRecords([])

      const response = await uploadFlashReport(file, reportMonth || undefined)

      setMessage(
        `Agent 1 extracted ${response.extracted_projects} project records. The dataset is now in DRAFT for officer review.`,
      )

      setFile(null)
      setReportMonth('')
      await loadRuns()

      // Automatically open the newly created draft.
      await openRun(response.ingestion_run_id)
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Flash Report processing failed.',
      )
    } finally {
      setLoading(false)
    }
  }

  async function openRun(runId: number) {
    try {
      setError('')

      const response = await getIngestionRun(runId, 100, 0)

      setSelectedRun(response.run)
      setRecords(response.records || [])
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to load the ingestion draft.',
      )
    }
  }

  async function handleDeleteRecord(recordId: number) {
    if (!selectedRun) return

    const confirmed = window.confirm(
      'Delete this extracted record from the draft?',
    )

    if (!confirmed) return

    try {
      setDeleting(recordId)
      setError('')
      setMessage('')

      await deleteIngestionRecord(
        selectedRun.id,
        recordId,
      )

      await openRun(selectedRun.id)
      await loadRuns()

      setMessage('Record removed from the draft.')
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to delete the record.',
      )
    } finally {
      setDeleting(null)
    }
  }

  async function handleApprove() {
    if (!selectedRun) return

    const confirmed = window.confirm(
      `Approve ${records.length} extracted records for ML prediction?\n\nAgent 2 will run automatically after approval.`,
    )

    if (!confirmed) return

    try {
      setApproving(true)
      setError('')
      setMessage('')

      const response = await approveIngestion(selectedRun.id)

      setMessage(
        response.message ||
          'Dataset approved successfully. Agent 2 prediction has completed.',
      )

      await loadRuns()

      const refreshed = await getIngestionRun(
        selectedRun.id,
        100,
        0,
      )

      setSelectedRun(refreshed.run)
      setRecords(refreshed.records || [])
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Dataset approval failed.',
      )
    } finally {
      setApproving(false)
    }
  }

  function formatDate(value?: string) {
    if (!value) return '—'

    return new Date(value).toLocaleString('en-IN', {
      dateStyle: 'medium',
      timeStyle: 'short',
    })
  }

  return (
    <div className="flex flex-col gap-6">

      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <FileUp className="size-5 text-primary" />
          <h1 className="text-2xl font-semibold tracking-tight">
            Data Ingestion
          </h1>
        </div>

        <p className="mt-1 text-sm text-muted-foreground">
          Agent 1 — Flash Report extraction, validation and officer approval
        </p>
      </div>

      {/* Upload section */}
      <Card className="p-6">
        <div className="flex flex-col gap-5">

          <div>
            <h2 className="text-base font-semibold">
              Upload Flash Report
            </h2>

            <p className="mt-1 text-sm text-muted-foreground">
              Upload an official PAIMANA Flash Report PDF. Agent 1 will
              extract project records and prepare them as a DRAFT dataset.
            </p>
          </div>

          <div className="rounded-lg border border-dashed border-border bg-muted/20 p-8">
            <div className="flex flex-col items-center justify-center text-center">

              <div className="flex size-12 items-center justify-center rounded-full bg-primary/10">
                <FileUp className="size-6 text-primary" />
              </div>

              <p className="mt-3 text-sm font-medium">
                Select a Flash Report PDF
              </p>

              <p className="mt-1 text-xs text-muted-foreground">
                PDF files only
              </p>

              <label className="mt-4 cursor-pointer">
                <span className="inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90">
                  Choose PDF
                </span>

                <input
                  type="file"
                  accept=".pdf,application/pdf"
                  className="hidden"
                  onChange={(e) => {
                    setFile(e.target.files?.[0] || null)
                    setError('')
                    setMessage('')
                  }}
                />
              </label>

              {file && (
                <div className="mt-4 rounded-md border border-border bg-background px-4 py-2 text-sm">
                  {file.name}
                </div>
              )}
            </div>
          </div>

          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2 w-full sm:w-auto">
              <label className="text-xs font-medium text-muted-foreground whitespace-nowrap">
                Report Period (Optional Override):
              </label>
              <input
                type="text"
                placeholder="Auto-detect or YYYY-MM"
                value={reportMonth}
                onChange={(e) => setReportMonth(e.target.value)}
                className="h-9 w-48 rounded-md border border-border bg-background px-3 text-xs focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>

            <button
              onClick={handleUpload}
              disabled={!file || loading}
              className="inline-flex h-10 w-full sm:w-auto items-center justify-center gap-2 rounded-md bg-primary px-5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Agent 1 Processing...
                </>
              ) : (
                <>
                  <FileUp className="size-4" />
                  Process Flash Report
                </>
              )}
            </button>
          </div>

        </div>
      </Card>

      {/* Messages */}
      {message && (
        <div className="flex items-start gap-3 rounded-md border border-risk-low/30 bg-risk-low/10 p-4 text-sm">
          <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-risk-low" />
          <span>{message}</span>
        </div>
      )}

      {error && (
        <div className="flex items-start gap-3 rounded-md border border-risk-high/30 bg-risk-high/10 p-4 text-sm">
          <AlertCircle className="mt-0.5 size-4 shrink-0 text-risk-high" />
          <span>{error}</span>
        </div>
      )}

      {/* Previous runs */}
      <Card>
        <div className="flex items-center justify-between border-b border-border p-5">
          <div>
            <h2 className="text-base font-semibold">
              Ingestion Runs
            </h2>

            <p className="mt-1 text-xs text-muted-foreground">
              Uploaded Flash Reports and their validation status
            </p>
          </div>

          <button
            onClick={loadRuns}
            disabled={loadingRuns}
            className="inline-flex size-8 items-center justify-center rounded-md border border-border hover:bg-muted disabled:opacity-50"
            title="Refresh"
          >
            <RefreshCw
              className={`size-4 ${
                loadingRuns ? 'animate-spin' : ''
              }`}
            />
          </button>
        </div>

        {loadingRuns ? (
          <div className="flex items-center justify-center p-10">
            <Loader2 className="size-5 animate-spin text-muted-foreground" />
          </div>
        ) : runs.length === 0 ? (
          <div className="p-10 text-center text-sm text-muted-foreground">
            No Flash Reports have been uploaded yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="whitespace-nowrap px-5 py-3 font-medium">
                    Report
                  </th>
                  <th className="whitespace-nowrap px-5 py-3 font-medium">
                    Month
                  </th>
                  <th className="whitespace-nowrap px-5 py-3 font-medium">
                    Records
                  </th>
                  <th className="whitespace-nowrap px-5 py-3 font-medium">
                    Status
                  </th>
                  <th className="whitespace-nowrap px-5 py-3 font-medium">
                    Uploaded
                  </th>
                  <th className="whitespace-nowrap px-5 py-3 font-medium">
                    Action
                  </th>
                </tr>
              </thead>

              <tbody>
                {runs.map((run) => (
                  <tr
                    key={run.id}
                    className="border-b border-border last:border-0 hover:bg-muted/30"
                  >
                    <td className="max-w-[280px] truncate px-5 py-3 font-medium">
                      {run.filename}
                    </td>

                    <td className="px-5 py-3">
                      {run.report_month}
                    </td>

                    <td className="px-5 py-3 tabular-nums">
                      {run.row_count ?? run.accepted_rows ?? 0}
                    </td>

                    <td className="px-5 py-3">
                      <StatusBadge status={run.status} />
                    </td>

                    <td className="whitespace-nowrap px-5 py-3 text-muted-foreground">
                      {formatDate(run.uploaded_at)}
                    </td>

                    <td className="px-5 py-3">
                      <button
                        onClick={() => openRun(run.id)}
                        className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                      >
                        Review
                        <ArrowRight className="size-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Review */}
      {selectedRun && (
        <Card>
          <div className="border-b border-border p-5">

            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">

              <div>
                <div className="flex items-center gap-2">
                  <ShieldCheck className="size-5 text-primary" />

                  <h2 className="text-base font-semibold">
                    Officer Review
                  </h2>

                  <StatusBadge status={selectedRun.status} />
                </div>

                <p className="mt-1 text-xs text-muted-foreground">
                  {selectedRun.filename}
                  {' · '}
                  Report month: {selectedRun.report_month}
                </p>
              </div>

              {selectedRun.status === 'DRAFT' && (
                <button
                  onClick={handleApprove}
                  disabled={approving || records.length === 0}
                  className="inline-flex h-9 items-center justify-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {approving ? (
                    <>
                      <Loader2 className="size-4 animate-spin" />
                      Running Agent 2...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="size-4" />
                      Approve & Run ML
                    </>
                  )}
                </button>
              )}
            </div>

            {selectedRun.notes && (
              <p className="mt-4 rounded-md bg-muted/50 p-3 text-xs text-muted-foreground">
                {selectedRun.notes}
              </p>
            )}
          </div>

          {/* Review summary */}
          <div className="grid grid-cols-2 gap-3 border-b border-border p-5 md:grid-cols-4">

            <SummaryItem
              label="Extracted Records"
              value={records.length}
            />

            <SummaryItem
              label="Report Month"
              value={selectedRun.report_month}
            />

            <SummaryItem
              label="Status"
              value={selectedRun.status}
            />

            <SummaryItem
              label="ML Ready"
              value={
                selectedRun.status === 'APPROVED'
                  ? 'Yes'
                  : 'No'
              }
            />

          </div>

          {/* Records */}
          <div className="overflow-x-auto">
            <table className="w-full min-w-[700px] text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/20 text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="whitespace-nowrap px-4 py-3 font-medium">
                    Project ID
                  </th>
                  <th className="whitespace-nowrap px-4 py-3 font-medium">
                    Project
                  </th>
                  <th className="whitespace-nowrap px-4 py-3 font-medium">
                    Agency
                  </th>
                  <th className="whitespace-nowrap px-4 py-3 font-medium">
                    State
                  </th>
                  <th className="whitespace-nowrap px-4 py-3 font-medium">
                    Progress
                  </th>
                  <th className="whitespace-nowrap px-4 py-3 font-medium">
                    Delay
                  </th>
                  {selectedRun.status === 'DRAFT' && (
                    <th className="whitespace-nowrap px-4 py-3 font-medium">
                      Action
                    </th>
                  )}
                </tr>
              </thead>

              <tbody>
                {records.map((record) => (
                  <tr
                    key={record.id}
                    className="border-b border-border last:border-0 hover:bg-muted/20"
                  >

                    <td className="px-4 py-3 font-mono text-xs">
                      {record.project_id || '—'}
                    </td>

                    <td className="max-w-[280px] truncate px-4 py-3 font-medium">
                      {record.project_name || '—'}
                    </td>

                    <td className="max-w-[180px] truncate px-4 py-3">
                      {record.agency || '—'}
                    </td>

                    <td className="max-w-[150px] truncate px-4 py-3">
                      {record.state || '—'}
                    </td>

                    <td className="px-4 py-3 tabular-nums">
                      {formatNumber(record.physical_progress)}
                    </td>

                    <td className="px-4 py-3 tabular-nums">
                      {formatNumber(record.time_overrun)}
                    </td>

                    {selectedRun.status === 'DRAFT' && (
                      <td className="px-4 py-3">
                        <button
                          onClick={() =>
                            handleDeleteRecord(record.id)
                          }
                          disabled={deleting === record.id}
                          className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-risk-high hover:bg-risk-high/10 disabled:opacity-50"
                        >
                          {deleting === record.id ? (
                            <Loader2 className="size-3.5 animate-spin" />
                          ) : (
                            <Trash2 className="size-3.5" />
                          )}
                          Delete
                        </button>
                      </td>
                    )}

                  </tr>
                ))}
              </tbody>
            </table>

            {records.length === 0 && (
              <div className="p-8 text-center text-sm text-muted-foreground">
                No records available in this ingestion run.
              </div>
            )}

          </div>

          {records.length >= 100 && (
            <div className="border-t border-border p-4 text-center text-xs text-muted-foreground">
              Showing the first 100 records. Backend pagination is available
              for larger datasets.
            </div>
          )}
        </Card>
      )}

    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const normalized = status.toUpperCase()

  let className =
    'border-border bg-muted text-muted-foreground'

  if (normalized === 'DRAFT') {
    className =
      'border-risk-medium/30 bg-risk-medium/10 text-risk-medium'
  }

  if (normalized === 'APPROVED') {
    className =
      'border-risk-low/30 bg-risk-low/10 text-risk-low'
  }

  if (
    normalized === 'FAILED' ||
    normalized === 'REJECTED'
  ) {
    className =
      'border-risk-high/30 bg-risk-high/10 text-risk-high'
  }

  return (
    <span
      className={`inline-flex rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${className}`}
    >
      {status}
    </span>
  )
}

function SummaryItem({
  label,
  value,
}: {
  label: string
  value: string | number
}) {
  return (
    <div className="rounded-md border border-border bg-muted/20 p-3">
      <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </p>

      <p className="mt-1 text-sm font-semibold">
        {value}
      </p>
    </div>
  )
}

function formatNumber(value: unknown) {
  if (value === null || value === undefined || value === '') {
    return '—'
  }

  const number = Number(value)

  if (Number.isNaN(number)) {
    return String(value)
  }

  return number.toLocaleString('en-IN', {
    maximumFractionDigits: 2,
  })
}