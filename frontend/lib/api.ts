import type {
  HealthResponse,
  ModelInfoApi,
  PredictionResponse,
  ProjectChangesResponse,
  ProjectHistoryResponse,
  ProjectRecommendationsResponse,
  ProjectsListResponse,
} from './types'

export const API_UNAVAILABLE_MESSAGE = 'PAIMANA API is currently unavailable.'

export class ApiError extends Error {
  status?: number

  constructor(message: string, status?: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}
export type RiskSummaryResponse = {
  report_month: string
  total: number
  high: number
  medium: number
  low: number
  total_projects?: number
  new_projects?: number
}

export type AgentRiskRecord = {
  project_id: string
  project_name?: string | null
  agency?: string | null
  state?: string | null
  report_month: string
  model_delay_probability: number
  risk_score_100: number
  risk_level: 'High' | 'Medium' | 'Low'
  top_risk_drivers?: string[] | string | null
  risk_interpretation?: string | null
  prediction_source?: string | null
}

export type AgentRiskResponse = {
  report_month: string
  total: number
  data: AgentRiskRecord[]
}

function getApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '')

  if (!configured) {
    if (typeof window !== 'undefined') {
      return 'http://127.0.0.1:8000'
    }
    throw new ApiError(
      'NEXT_PUBLIC_API_URL is not set. Add it to .env.local.',
    )
  }

  return configured
}

async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const url = `${getApiBaseUrl()}${path}`

  let response: Response

  try {
    const isFormData =
      typeof FormData !== 'undefined' &&
      init?.body instanceof FormData

    response = await fetch(url, {
      cache: 'no-store',
      ...init,
      headers: {
        Accept: 'application/json',

        // Only set JSON Content-Type for non-FormData requests.
        // The browser must set multipart/form-data + boundary itself.
        ...(init?.body && !isFormData
          ? { 'Content-Type': 'application/json' }
          : {}),

        ...init?.headers,
      },
    })
  } catch (err) {
    throw new ApiError(
      err instanceof Error && err.message ? err.message : API_UNAVAILABLE_MESSAGE,
    )
  }

  if (!response.ok) {
    let errorDetail = API_UNAVAILABLE_MESSAGE
    try {
      const errorJson = await response.json()
      if (typeof errorJson?.detail === 'string') {
        errorDetail = errorJson.detail
      } else if (typeof errorJson?.detail?.message === 'string') {
        errorDetail = errorJson.detail.message
      } else if (typeof errorJson?.message === 'string') {
        errorDetail = errorJson.message
      }
    } catch {
      // fallback
    }

    if (response.status === 404 && errorDetail === API_UNAVAILABLE_MESSAGE) {
      throw new ApiError('Project not found.', 404)
    }

    throw new ApiError(errorDetail, response.status)
  }

  try {
    return (await response.json()) as T
  } catch {
    throw new ApiError(API_UNAVAILABLE_MESSAGE, response.status)
  }
}
export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health')
}

export function getModelInfo(): Promise<ModelInfoApi> {
  return request<ModelInfoApi>('/model-info')
}

export function getProjects(limit = 2000): Promise<ProjectsListResponse> {
  const safeLimit = Math.max(1, Math.min(limit, 2000))
  return request<ProjectsListResponse>(`/projects?limit=${safeLimit}`)
}

export function getProjectById(projectId: string): Promise<ProjectHistoryResponse> {
  return request<ProjectHistoryResponse>(
    `/projects/${encodeURIComponent(projectId)}`,
  )
}

export function predictProject(projectId: string): Promise<PredictionResponse> {
  return request<PredictionResponse>('/predict', {
    method: 'POST',
    body: JSON.stringify({ project_id: projectId }),
  })
}

export function getProjectChanges(projectId: string): Promise<ProjectChangesResponse> {
  return request<ProjectChangesResponse>(`/agent/changes/${encodeURIComponent(projectId)}`)
}

export function getProjectRecommendations(projectId: string): Promise<ProjectRecommendationsResponse> {
  return request<ProjectRecommendationsResponse>(`/agent/recommend/${encodeURIComponent(projectId)}`)
}

export function getRiskSummary(): Promise<RiskSummaryResponse> {
  return request<RiskSummaryResponse>('/agent/risk/summary')
}

export function getAgentRisk(): Promise<AgentRiskResponse> {
  return request<AgentRiskResponse>('/agent/risk')
}
// ===============================
// Agent 1 — Data Ingestion
// ===============================

export type IngestionRun = {
  id: number
  filename: string
  report_month: string
  status: string
  row_count?: number
  accepted_rows?: number
  uploaded_at?: string
  notes?: string
}

export type IngestionRecord = {
  id: number
  ingestion_run_id: number

  project_id?: string
  project_name?: string
  agency?: string
  state?: string

  original_cost?: number | string
  revised_cost?: number | string
  anticipated_cost?: number | string
  expenditure?: number | string

  original_completion?: string
  revised_completion?: string
  anticipated_completion?: string

  physical_progress?: number | string
  time_overrun?: number | string
  cost_overrun?: number | string

  delay_reason?: string
  is_delayed?: number | boolean
  additional_delay_flag?: number | boolean
  additional_delay_months?: number | string
  delay_reason_category?: string

  [key: string]: unknown
}

export type IngestionListResponse = {
  runs: IngestionRun[]
}

export type IngestionDetailResponse = {
  run: IngestionRun
  records: IngestionRecord[]
  limit: number
  offset: number
}

export type IngestionUploadResponse = {
  agent: string
  status: string
  ingestion_run_id: number
  filename: string
  report_month: string
  extracted_projects: number
  message: string
}

export type IngestionUpdateResponse = {
  status: string
  ingestion_run_id: number
  record_id: number
  record: IngestionRecord
  message: string
}

export type IngestionDeleteRecordResponse = {
  status: string
  ingestion_run_id: number
  record_id: number
  remaining_records: number
  message: string
}

export type IngestionApproveResponse = {
  status: string
  ingestion_run_id: number
  message: string
  [key: string]: unknown
}

export async function uploadFlashReport(
  file: File,
  reportMonth?: string,
): Promise<IngestionUploadResponse> {
  const formData = new FormData()
  formData.append('file', file)
  if (reportMonth && reportMonth.trim()) {
    formData.append('report_month', reportMonth.trim())
  }

  return request<IngestionUploadResponse>(
    '/agent/ingest',
    {
      method: 'POST',
      body: formData,
    },
  )
}

export function getIngestionRuns(): Promise<IngestionListResponse> {
  return request<IngestionListResponse>('/agent/ingest')
}

export function getIngestionRun(
  ingestionRunId: number,
  limit = 100,
  offset = 0,
): Promise<IngestionDetailResponse> {
  return request<IngestionDetailResponse>(
    `/agent/ingest/${ingestionRunId}?limit=${limit}&offset=${offset}`,
  )
}

export function updateIngestionRecord(
  ingestionRunId: number,
  recordId: number,
  updates: Partial<IngestionRecord>,
): Promise<IngestionUpdateResponse> {
  return request<IngestionUpdateResponse>(
    `/agent/ingest/${ingestionRunId}/records/${recordId}`,
    {
      method: 'PUT',
      body: JSON.stringify(updates),
    },
  )
}

export function deleteIngestionRecord(
  ingestionRunId: number,
  recordId: number,
): Promise<IngestionDeleteRecordResponse> {
  return request<IngestionDeleteRecordResponse>(
    `/agent/ingest/${ingestionRunId}/records/${recordId}`,
    {
      method: 'DELETE',
    },
  )
}

export function approveIngestion(
  ingestionRunId: number,
): Promise<IngestionApproveResponse> {
  return request<IngestionApproveResponse>(
    `/agent/ingest/${ingestionRunId}/approve`,
    {
      method: 'POST',
    },
  )
}
