import { displayText } from './format'
import type {
  HealthResponse,
  HealthStatus,
  ModelInfo,
  ModelInfoApi,
  MonthlyReport,
  PredictionResponse,
  ProjectDetail,
  ProjectHistoryResponse,
  ProjectSummary,
  ProjectSummaryApi,
  RiskDistribution,
  RiskLevel,
  WarningIndicator,
} from './types'

export function asRiskLevel(value: string | null | undefined): RiskLevel {
  if (value === 'High' || value === 'Medium' || value === 'Low') return value
  return 'Low'
}

function asNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null
  const n = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(n) ? n : null
}

export function mapProjectSummary(project: ProjectSummaryApi): ProjectSummary {
  const name = displayText(project.project_name, '')
  return {
    project_id: String(project.project_id),
    name: name || String(project.project_id),
    agency: displayText(project.agency),
    state: displayText(project.state),
    sector: '',
    latest_report: project.report_month ?? '',
    risk_score: project.risk_score_100,
    risk_level: asRiskLevel(project.risk_level),
    delay_probability: project.delay_probability,
    top_risk_drivers: project.top_risk_drivers ?? [],
    interpretation: project.interpretation ?? '',
  }
}

export function mapMonthlyReport(row: ProjectSummaryApi): MonthlyReport {
  return {
    report_month: row.report_month ?? '',
    original_cost: asNumber(row.original_cost),
    revised_cost: asNumber(row.revised_cost),
    anticipated_cost: asNumber(row.anticipated_cost),
    expenditure: asNumber(row.expenditure),
    original_completion: row.original_completion ?? null,
    revised_completion: row.revised_completion ?? null,
    anticipated_completion: row.anticipated_completion ?? null,
    physical_progress: asNumber(row.physical_progress),
    time_overrun: asNumber(row.time_overrun),
    cost_overrun: asNumber(row.cost_overrun),
    delay_probability: asNumber(row.delay_probability),
    risk_score: asNumber(row.risk_score_100),
    risk_level: row.risk_level ? asRiskLevel(row.risk_level) : null,
  }
}

export function mapWarnings(
  drivers: string[],
  fallbackLevel: RiskLevel,
  interpretation?: string,
): WarningIndicator[] {
  const warnings = drivers.map((title, index) => ({
    id: `driver-${index}`,
    title,
    detail: interpretation || 'Rule-based warning flag associated with this prediction.',
    severity: fallbackLevel,
  }))

  if (warnings.length === 0) {
    return [
      {
        id: 'none',
        title: 'No strong rule-based warning flag',
        detail: interpretation || 'The model did not surface a dominant driver for this observation.',
        severity: 'Low',
      },
    ]
  }

  return warnings
}

export function mapProjectDetail(payload: ProjectHistoryResponse): ProjectDetail {
  const latest = payload.latest ?? payload.history[payload.history.length - 1]
  const summary = mapProjectSummary(latest)

  return {
    ...summary,
    project_id: String(payload.project_id),
    observation_count: payload.observation_count,
    history: payload.history.map(mapMonthlyReport),
    warnings: mapWarnings(
      latest.top_risk_drivers ?? [],
      asRiskLevel(latest.risk_level),
      latest.interpretation,
    ),
  }
}

export function mapPrediction(payload: PredictionResponse): ProjectSummary {
  return mapProjectSummary(payload)
}

export function getRiskDistribution(projects: ProjectSummary[]): RiskDistribution {
  const high = projects.filter((p) => p.risk_level === 'High').length
  const medium = projects.filter((p) => p.risk_level === 'Medium').length
  const low = projects.filter((p) => p.risk_level === 'Low').length
  return { high, medium, low, total: projects.length }
}

function metricValue(value: number | undefined): string | null {
  if (value === undefined || Number.isNaN(value)) return null
  return value.toFixed(3)
}

export function mapModelInfo(meta: ModelInfoApi): ModelInfo {
  const algorithm = meta.model?.trim() || 'RandomForestClassifier'
  const modelName = algorithm.split('(')[0] || algorithm

  const metrics: { label: string; value: string }[] = []
  const validationAuc = metricValue(meta.metrics?.validation?.roc_auc)
  const validationPr = metricValue(meta.metrics?.validation?.pr_auc)
  const testAuc = metricValue(meta.metrics?.test?.roc_auc)
  const testPr = metricValue(meta.metrics?.test?.pr_auc)

  if (validationAuc) metrics.push({ label: 'Validation ROC-AUC', value: validationAuc })
  if (validationPr) metrics.push({ label: 'Validation PR-AUC', value: validationPr })
  if (testAuc) metrics.push({ label: 'Test ROC-AUC', value: testAuc })
  if (testPr) metrics.push({ label: 'Test PR-AUC', value: testPr })

  const records =
    (meta.metrics?.validation?.n ?? 0) + (meta.metrics?.test?.n ?? 0) || null

  return {
    model_name: modelName,
    version: meta.sklearn_version ? `sklearn ${meta.sklearn_version}` : '—',
    algorithm,
    training_scope: meta.training_scope?.trim() || '—',
    records_trained: records,
    features: (meta.features ?? []).map((name) => ({
      name,
      description: 'Input feature used by the trained model.',
    })),
    target:
      'The model estimates the probability of next-month additional delay' +
      (meta.target ? ` (training target: ${meta.target}).` : '.'),
    metrics,
    validation_scope: meta.validation_scope?.trim() || '—',
    test_scope: meta.test_scope?.trim() || '—',
  }
}

export function mapHealth(payload: HealthResponse): HealthStatus {
  const database = payload.database ?? ''
  const ok = payload.status === 'ok' && !database.startsWith('error')

  return {
    status: ok ? 'ok' : 'degraded',
    database: database || 'unknown',
    model: payload.model ?? '—',
    training_scope: payload.training_scope ?? '—',
  }
}

export function uniqueSorted(values: string[]): string[] {
  return Array.from(new Set(values.filter((v) => v && v !== '—'))).sort((a, b) =>
    a.localeCompare(b),
  )
}
