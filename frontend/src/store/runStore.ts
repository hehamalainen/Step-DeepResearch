import { create } from 'zustand'
import { 
  Run, 
  RunSummary, 
  Evidence, 
  Claim, 
  ToolEvent, 
  TodoState,
  WSEvent,
  AgentPhase,
  RunMetrics,
} from '../types'

interface RunState {
  // Current run being viewed/executed
  currentRun: Run | null
  currentEvidence: Evidence[]
  currentClaims: Claim[]
  currentToolEvents: ToolEvent[]
  currentTodoState: TodoState | null
  currentReportMarkdown: string
  
  // Run list
  runs: RunSummary[]
  
  // Comparison
  compareRunA: RunSummary | null
  compareRunB: RunSummary | null
  
  // Actions
  setCurrentRun: (run: Run | null) => void
  updateRunStatus: (status: Run['status']) => void
  updateRunPhase: (phase: AgentPhase) => void
  updateRunMetrics: (metrics: Partial<RunMetrics>) => void
  
  setEvidence: (evidence: Evidence[]) => void
  addEvidence: (evidence: Evidence) => void
  
  setClaims: (claims: Claim[]) => void
  addClaim: (claim: Claim) => void
  updateClaimStatus: (claimId: string, status: Claim['status']) => void
  
  setToolEvents: (events: ToolEvent[]) => void
  addToolEvent: (event: ToolEvent) => void
  
  setTodoState: (state: TodoState) => void
  
  setReportMarkdown: (markdown: string) => void
  
  setRuns: (runs: RunSummary[]) => void
  
  setCompareRuns: (runA: RunSummary | null, runB: RunSummary | null) => void
  
  // WebSocket event handler
  handleWSEvent: (event: WSEvent) => void
  
  // Reset
  reset: () => void
}

const initialState = {
  currentRun: null,
  currentEvidence: [],
  currentClaims: [],
  currentToolEvents: [],
  currentTodoState: null,
  currentReportMarkdown: '',
  runs: [],
  compareRunA: null,
  compareRunB: null,
}

export const useRunStore = create<RunState>((set, get) => ({
  ...initialState,
  
  setCurrentRun: (run) => set({ currentRun: run }),
  
  updateRunStatus: (status) => set((state) => ({
    currentRun: state.currentRun 
      ? { ...state.currentRun, status } 
      : null,
  })),
  
  updateRunPhase: (phase) => set((state) => ({
    currentRun: state.currentRun 
      ? { ...state.currentRun, current_phase: phase } 
      : null,
  })),
  
  updateRunMetrics: (metrics) => set((state) => ({
    currentRun: state.currentRun 
      ? { 
          ...state.currentRun, 
          metrics: { ...state.currentRun.metrics, ...metrics } 
        } 
      : null,
  })),
  
  setEvidence: (evidence) => set({ currentEvidence: evidence }),
  
  addEvidence: (evidence) => set((state) => ({
    currentEvidence: [...state.currentEvidence, evidence],
  })),
  
  setClaims: (claims) => set({ currentClaims: claims }),
  
  addClaim: (claim) => set((state) => ({
    currentClaims: [...state.currentClaims, claim],
  })),
  
  updateClaimStatus: (claimId, status) => set((state) => ({
    currentClaims: state.currentClaims.map((c) =>
      c.claim_id === claimId ? { ...c, status } : c
    ),
  })),
  
  setToolEvents: (events) => set({ currentToolEvents: events }),
  
  addToolEvent: (event) => set((state) => ({
    currentToolEvents: [...state.currentToolEvents, event],
  })),
  
  setTodoState: (state) => set({ currentTodoState: state }),
  
  setReportMarkdown: (markdown) => set({ currentReportMarkdown: markdown }),
  
  setRuns: (runs) => set({ runs }),
  
  setCompareRuns: (runA, runB) => set({ 
    compareRunA: runA, 
    compareRunB: runB,
  }),
  
  handleWSEvent: (event) => {
    const { event_type, data } = event
    
    switch (event_type) {
      case 'run_started':
        get().updateRunStatus('running')
        break
        
      case 'run_completed':
        get().updateRunStatus('succeeded')
        break
        
      case 'run_failed':
        get().updateRunStatus('failed')
        break
        
      case 'phase_changed':
        if (data.phase) {
          get().updateRunPhase(data.phase as AgentPhase)
        }
        break
        
      case 'tool_call_completed':
        get().addToolEvent({
          event_id: data.event_id as string,
          run_id: event.run_id,
          tool: 'web_search',
          tool_name: data.tool_name as string,
          args: {},
          started_at: event.timestamp,
          ended_at: event.timestamp,
          duration_ms: data.duration_ms as number,
        })
        break
        
      case 'evidence_found':
        get().addEvidence({
          evidence_id: data.evidence_id as string,
          run_id: event.run_id,
          source_url: data.source_url as string,
          source_title: data.source_title as string,
          snippet: data.snippet as string,
          authority_tier: data.authority_tier as Evidence['authority_tier'],
          retrieved_at: event.timestamp,
          cross_validated: false,
          validation_sources: [],
        })
        break
        
      case 'claim_extracted':
        get().addClaim({
          claim_id: data.claim_id as string,
          run_id: event.run_id,
          text: data.text as string,
          status: 'unverified',
          evidence_ids: [],
          section: data.section as string | undefined,
        })
        break
        
      case 'claim_verified':
        get().updateClaimStatus(
          data.claim_id as string,
          data.status as Claim['status']
        )
        break
        
      case 'todo_updated':
        get().setTodoState({
          items: data.items as TodoState['items'],
          completed_count: data.completed_count as number,
          pending_count: data.pending_count as number,
        })
        break
        
      case 'report_draft_updated':
      case 'report_finalized':
        if (data.markdown) {
          get().setReportMarkdown(data.markdown as string)
        } else if (data.markdown_preview) {
          get().setReportMarkdown(data.markdown_preview as string)
        }
        break
        
      case 'metrics_updated':
        get().updateRunMetrics(data as Partial<RunMetrics>)
        break
    }
  },
  
  reset: () => set(initialState),
}))
