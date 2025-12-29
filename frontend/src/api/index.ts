import { 
  Run, 
  RunSummary, 
  Report, 
  Evidence, 
  Claim, 
  ToolEvent,
  RunComparison,
  TaskSet,
  PairwiseResult,
  EvaluationSummary,
  EvaluationTask,
  CreateRunRequest,
  DemoScenario,
} from '../types'

const API_BASE = '/api'

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${url}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  })
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(error.detail || 'API request failed')
  }
  
  return response.json()
}

// Runs API
export async function createRun(request: CreateRunRequest): Promise<Run> {
  return fetchJSON<Run>('/runs', {
    method: 'POST',
    body: JSON.stringify(request),
  })
}

export async function listRuns(params?: {
  status?: string
  limit?: number
  offset?: number
}): Promise<RunSummary[]> {
  const searchParams = new URLSearchParams()
  if (params?.status) searchParams.set('status', params.status)
  if (params?.limit) searchParams.set('limit', String(params.limit))
  if (params?.offset) searchParams.set('offset', String(params.offset))
  
  const query = searchParams.toString()
  return fetchJSON<RunSummary[]>(`/runs${query ? `?${query}` : ''}`)
}

export async function getRun(runId: string): Promise<Run> {
  return fetchJSON<Run>(`/runs/${runId}`)
}

export async function getRunReport(runId: string): Promise<Report> {
  return fetchJSON<Report>(`/runs/${runId}/report`)
}

export async function getRunEvidence(runId: string): Promise<Evidence[]> {
  return fetchJSON<Evidence[]>(`/runs/${runId}/evidence`)
}

export async function getRunClaims(runId: string): Promise<Claim[]> {
  return fetchJSON<Claim[]>(`/runs/${runId}/claims`)
}

export async function getRunToolEvents(runId: string): Promise<ToolEvent[]> {
  return fetchJSON<ToolEvent[]>(`/runs/${runId}/tool-events`)
}

export async function exportRun(runId: string, format: string = 'markdown'): Promise<{
  format: string
  content: string
  evidence_count: number
  claim_count: number
}> {
  return fetchJSON(`/runs/${runId}/export?format=${format}`)
}

export async function deleteRun(runId: string): Promise<{ status: string; run_id: string }> {
  return fetchJSON(`/runs/${runId}`, { method: 'DELETE' })
}

// Comparison API
export async function compareRuns(runAId: string, runBId: string): Promise<RunComparison> {
  return fetchJSON<RunComparison>(`/runs/${runAId}/compare/${runBId}`)
}

// Evaluation API
export async function createTaskSet(data: {
  name: string
  description?: string
  tasks: { query: string; format?: string; criteria?: string[] }[]
}): Promise<TaskSet> {
  return fetchJSON<TaskSet>('/eval/tasks', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function listTaskSets(): Promise<TaskSet[]> {
  return fetchJSON<TaskSet[]>('/eval/tasks')
}

export async function getEvaluationTasks(): Promise<{ tasks: EvaluationTask[] }> {
  return fetchJSON<{ tasks: EvaluationTask[] }>('/eval/tasks')
}

export async function runEvaluationBatch(
  taskSetId: string,
  engines: string[] = ['deep_research']
): Promise<{ task_set_id: string; runs_created: number; run_ids: string[] }> {
  const params = new URLSearchParams()
  params.set('task_set_id', taskSetId)
  engines.forEach(e => params.append('engines', e))
  
  return fetchJSON(`/eval/runs?${params.toString()}`, { method: 'POST' })
}

export async function submitPairwiseJudgment(data: {
  run_a_id: string
  run_b_id: string
  winner: string
  completeness_a: number
  completeness_b: number
  depth_a: number
  depth_b: number
  readability_a: number
  readability_b: number
  requirement_fit_a: number
  requirement_fit_b: number
  notes?: string
}): Promise<PairwiseResult> {
  return fetchJSON<PairwiseResult>('/eval/pairwise', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function getEvaluationResults(runId?: string): Promise<PairwiseResult[]> {
  const query = runId ? `?run_id=${runId}` : ''
  return fetchJSON<PairwiseResult[]>(`/eval/results${query}`)
}

export async function getEvaluationSummary(): Promise<EvaluationSummary> {
  return fetchJSON<EvaluationSummary>('/eval/summary')
}

// Settings API
export async function getModelProviders(): Promise<{
  id: string
  name: string
  base_url: string
  default_model?: string
  configured: boolean
}[]> {
  return fetchJSON('/settings/providers')
}

export async function getAblationOptions(): Promise<{
  toggles: {
    id: string
    name: string
    description: string
    default: boolean
  }[]
}> {
  return fetchJSON('/settings/ablations')
}

// Demo Scenarios API
export async function getDemoScenarios(): Promise<{ scenarios: DemoScenario[] }> {
  return fetchJSON('/scenarios')
}

// Health check
export async function healthCheck(): Promise<{ status: string; timestamp: string }> {
  return fetchJSON('/health'.replace('/api', ''))
}
