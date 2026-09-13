/**
 * Shared presentational helpers. Live project data is loaded from FastAPI
 * via lib/api.ts — this file must not contain mock projects.
 */

export { formatMonth } from './format'
export { riskLevelFromScore } from './risk'
export { getRiskDistribution } from './mappers'
export type { RiskDistribution } from './types'
