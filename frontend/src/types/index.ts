// API Types matching backend models

export type RunStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled'

export type AgentPhase = 
  | 'planning' 
  | 'information_seeking' 
  | 'reflection' 
  | 'cross_validation' 
  | 'report_generation' 
  | 'completed'

export type ToolType = 
  | 'web_search' 
  | 'web_browse' 
  | 'file_read' 
  | 'file_write' 
  | 'file_edit' 
  | 'todo' 
  | 'shell'

export type ClaimStatus = 'verified' | 'supported' | 'refuted' | 'uncertain' | 'unverified'

export type AuthorityTier = 'official' | 'academic' | 'industry' | 'media' | 'general' | 'other'

export type OutputFormat = 'report' | 'adr' | 'brief' | 'memo'

export type EngineType = 'deep_research' | 'baseline'

export interface AblationConfig {
  enable_reflection: boolean
  enable_authority_ranking: boolean
  enable_todo_state: boolean
  enable_patch_editing: boolean
}

export interface RunConfig {
  engine: EngineType
  model_name?: string
  model_base_url?: string
  output_format: OutputFormat
  max_steps: number
  verification_strictness: number
  time_horizon?: string
  geography?: string
  required_sources?: string[]
  ablations: AblationConfig
}

export interface CreateRunRequest {
  query: string
  config: RunConfig
}

export interface RunMetrics {
  total_tool_calls: number
  tool_calls_by_type: Record<string, number>
  total_tokens: number
  prompt_tokens: number
  completion_tokens: number
  cost_estimate_usd: number
  latency_ms: number
  reflection_steps: number
  cross_validation_events: number
  citation_count: number
  citation_authority_mix: Record<string, number>
  unsupported_claims: number
  context_spill_to_disk_events: number
  patch_edit_savings_percent?: number
}

export interface Run {
  run_id: string
  query: string
  config: RunConfig
  status: RunStatus
  current_phase: AgentPhase
  created_at: string
  started_at?: string
  completed_at?: string
  metrics: RunMetrics
  error_message?: string
  report_artifact_path?: string
  trace_path?: string
}

export interface RunSummary {
  run_id: string
  query: string
  status: RunStatus
  engine: EngineType
  current_phase: AgentPhase
  created_at: string
  completed_at?: string
  citation_count: number
  tool_calls: number
}

export interface ToolEvent {
  event_id: string
  run_id: string
  tool: ToolType
  tool_name: string
  args: Record<string, unknown>
  result?: unknown
  result_file_path?: string
  started_at: string
  ended_at?: string
  duration_ms?: number
  error?: string
}

export interface Evidence {
  evidence_id: string
  run_id: string
  source_url: string
  source_title?: string
  snippet: string
  authority_tier: AuthorityTier
  retrieved_at: string
  tool_event_id?: string
  cross_validated: boolean
  validation_sources: string[]
}

export interface Claim {
  claim_id: string
  run_id: string
  text: string
  status: ClaimStatus
  evidence_ids: string[]
  section?: string
  confidence?: number
}

export interface ReportSection {
  id: string
  title: string
  content: string
  claims: string[]
  order: number
}

export interface Report {
  run_id: string
  title: string
  executive_summary: string
  sections: ReportSection[]
  markdown: string
  created_at: string
  updated_at: string
  version: number
}

export interface TodoItem {
  id: string
  title: string
  description?: string
  status: string
  created_at: string
  completed_at?: string
  parent_id?: string
}

export interface TodoState {
  items: TodoItem[]
  completed_count: number
  pending_count: number
}

// Comparison types
export interface ClaimDiff {
  claim_text: string
  status_a?: ClaimStatus
  status_b?: ClaimStatus
  evidence_count_a: number
  evidence_count_b: number
  in_both: boolean
}

export interface RunComparison {
  run_a: Run
  run_b: Run
  report_diff_summary: string
  claim_diffs: ClaimDiff[]
  metric_deltas: Record<string, number>
  citation_comparison: Record<string, Record<string, number>>
}

// Evaluation types
export interface EvaluationTask {
  task_id: string
  query: string
  description?: string
  output_format: OutputFormat
  expected_criteria?: string[]
  run_a_id?: string
  run_b_id?: string
}

export interface TaskSet {
  task_set_id: string
  name: string
  description?: string
  tasks: EvaluationTask[]
  created_at: string
}

export interface PairwiseResult {
  result_id: string
  run_a_id: string
  run_b_id: string
  winner: string
  scores: Record<string, Record<string, number>>
  notes?: string
  evaluated_at: string
  evaluator_id?: string
}

export interface EvaluationSummary {
  total_comparisons: number
  wins_by_engine: Record<string, number>
  average_scores: Record<string, Record<string, number>>
  elo_ratings?: Record<string, number>
}

// WebSocket event types
export type WSEventType =
  | 'connected'
  | 'disconnected'
  | 'error'
  | 'run_started'
  | 'run_completed'
  | 'run_failed'
  | 'phase_changed'
  | 'tool_call_started'
  | 'tool_call_completed'
  | 'tool_call_failed'
  | 'evidence_found'
  | 'claim_extracted'
  | 'claim_verified'
  | 'todo_updated'
  | 'report_draft_updated'
  | 'report_section_added'
  | 'report_finalized'
  | 'metrics_updated'
  | 'context_spill'
  | 'reflection_started'
  | 'cross_validation'

export interface WSEvent {
  event_type: WSEventType
  run_id: string
  timestamp: string
  data: Record<string, unknown>
}

// Demo scenario type
export interface DemoScenario {
  id: string
  name: string
  category: string
  query: string
  description: string
}
