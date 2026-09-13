/**
 * Domain types for the PAIMANA platform.
 *
 * API (snake_case) types match FastAPI. UI types keep existing component
 * property names via the mapping layer in lib/mappers.ts.
 */

export type RiskLevel = 'High' | 'Medium' | 'Low'

export interface ProjectSummaryApi {
  project_id: string
  project_name: string | null
  agency: string | null
  state: string | null
  report_month: string | null
  delay_probability: number
  risk_score_100: number
  risk_level: RiskLevel
  top_risk_drivers: string[]
  interpretation: string
  original_cost?: number | null
  revised_cost?: number | null
  anticipated_cost?: number | null
  expenditure?: number | null
  physical_progress?: number | null
  time_overrun?: number | null
  cost_overrun?: number | null
  original_completion?: string | null
  revised_completion?: string | null
  anticipated_completion?: string | null
}

export interface ProjectsListResponse {
  count: number
  projects: ProjectSummaryApi[]
}

export interface PredictionResponse extends ProjectSummaryApi {
  prediction_source?: string
  missing_features_supplied?: string[]
}

export interface ProjectHistoryResponse {
  project_id: string
  observation_count: number
  history: ProjectSummaryApi[]
  latest: ProjectSummaryApi
}

export interface HealthResponse {
  status: string
  database?: string
  model?: string
  training_scope?: string
}

export interface ModelMetricBlock {
  n?: number
  roc_auc?: number
  pr_auc?: number
}

export interface ModelInfoApi {
  features?: string[]
  categorical_features?: string[]
  numeric_features?: string[]
  target?: string
  model?: string
  sklearn_version?: string
  metrics?: {
    validation?: ModelMetricBlock
    test?: ModelMetricBlock
  }
  risk_thresholds?: {
    low_lt?: number
    medium_lte?: number
    high_gt?: number
  }
  training_scope?: string
  validation_scope?: string
  test_scope?: string
}

export interface ProjectSummary {
  project_id: string
  name: string
  agency: string
  state: string
  sector: string
  latest_report: string
  risk_score: number
  risk_level: RiskLevel
  delay_probability: number
  top_risk_drivers: string[]
  interpretation: string
}

export interface MonthlyReport {
  report_month: string
  original_cost: number | null
  revised_cost: number | null
  anticipated_cost: number | null
  expenditure: number | null
  original_completion: string | null
  revised_completion: string | null
  anticipated_completion: string | null
  physical_progress: number | null
  time_overrun: number | null
  cost_overrun: number | null
  delay_probability: number | null
  risk_score: number | null
  risk_level: RiskLevel | null
}

export interface WarningIndicator {
  id: string
  title: string
  detail: string
  severity: RiskLevel
}

export interface ProjectDetail extends ProjectSummary {
  warnings: WarningIndicator[]
  history: MonthlyReport[]
  observation_count: number
}

export interface ModelInfo {
  model_name: string
  version: string
  algorithm: string
  training_scope: string
  records_trained: number | null
  features: { name: string; description: string }[]
  target: string
  metrics: { label: string; value: string }[]
  validation_scope: string
  test_scope: string
}

export interface HealthStatus {
  status: 'ok' | 'degraded' | 'down'
  database: string
  model: string
  training_scope: string
}

export interface RiskDistribution {
  high: number
  medium: number
  low: number
  total: number
}

// Agent 3 Types
export interface ProjectChangeItem {
  category: 'Schedule' | 'Cost' | 'Financial' | 'Progress' | 'Risk Intelligence' | string
  metric: string
  previous: string
  current: string
  delta: string
  direction: 'worsened' | 'improved' | 'neutral'
  severity: RiskLevel
}

export interface ProjectChangesResponse {
  project_id: string
  has_previous_period: boolean
  current_month: string | null
  previous_month: string | null
  changes: ProjectChangeItem[]
  summary: string
  risk_movement: 'increased' | 'decreased' | 'unchanged' | 'baseline'
}

// Agent 4 Types
export interface PrescriptionItem {
  id: string
  priority: 'Urgent' | 'High' | 'Medium' | 'Low'
  category: 'Governance' | 'Schedule' | 'Cost' | 'Site Execution' | 'Contractual' | string
  action_title: string
  rationale: string
  recommended_steps: string[]
}

export interface ProjectRecommendationsResponse {
  project_id: string
  risk_level: RiskLevel
  risk_score: number
  prescriptions_count: number
  prescriptions: PrescriptionItem[]
  generated_at: string
}

export type { ProjectHistoryResponse as ProjectHistory }

export type { ModelInfoApi as ModelInfoRaw }
