import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, FileText, Shield, Link2, Activity, FolderOpen, Download } from 'lucide-react'
import clsx from 'clsx'
import * as api from '../api'
import { useWebSocket } from '../hooks/useWebSocket'
import { useRunStore } from '../store/runStore'

type TabId = 'report' | 'claims' | 'sources' | 'trace' | 'artifacts'

const tabs: { id: TabId; label: string; icon: typeof FileText }[] = [
  { id: 'report', label: 'Report', icon: FileText },
  { id: 'claims', label: 'Claims', icon: Shield },
  { id: 'sources', label: 'Sources', icon: Link2 },
  { id: 'trace', label: 'Trace', icon: Activity },
  { id: 'artifacts', label: 'Artifacts', icon: FolderOpen },
]

export default function RunDetailPage() {
  const { runId } = useParams<{ runId: string }>()
  const [activeTab, setActiveTab] = useState<TabId>('report')
  
  const { setCurrentRun, handleWSEvent, currentEvidence, currentClaims, currentToolEvents } = useRunStore()

  const { data: run, isLoading } = useQuery({
    queryKey: ['run', runId],
    queryFn: () => api.getRun(runId!),
    enabled: !!runId,
    refetchInterval: (query) => query.state.data?.status === 'running' ? 2000 : false,
  })

  const { data: reportData } = useQuery({
    queryKey: ['report', runId],
    queryFn: () => api.getRunReport(runId!),
    enabled: !!runId && run?.status === 'succeeded',
  })

  useWebSocket({
    runId: runId ?? undefined,
    onEvent: (event) => {
      handleWSEvent(event)
    },
  })

  useEffect(() => {
    if (run) setCurrentRun(run)
  }, [run, setCurrentRun])

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="animate-pulse text-gray-400">Loading...</div>
      </div>
    )
  }

  if (!run) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-gray-400">Run not found</p>
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <header className="px-6 py-4 border-b border-slate-700 bg-slate-800">
        <div className="flex items-center gap-4">
          <Link to="/runs" className="text-gray-400 hover:text-white">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div className="flex-1 min-w-0">
            <h1 className="text-lg font-semibold text-white truncate">{run.query}</h1>
            <div className="flex items-center gap-3 mt-1 text-sm text-gray-400">
              <span className={clsx(
                'px-2 py-0.5 rounded-full text-xs',
                run.status === 'running' && 'bg-blue-900 text-blue-300',
                run.status === 'succeeded' && 'bg-green-900 text-green-300',
                run.status === 'failed' && 'bg-red-900 text-red-300',
              )}>
                {run.status}
              </span>
              <span>{run.config.engine}</span>
              {run.current_phase && <span>Phase: {run.current_phase}</span>}
            </div>
          </div>
          {reportData && (
            <a
              href={`data:text/markdown;charset=utf-8,${encodeURIComponent(reportData.markdown)}`}
              download={`report-${runId}.md`}
              className="flex items-center gap-2 px-3 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm text-white"
            >
              <Download className="h-4 w-4" />
              Export
            </a>
          )}
        </div>
      </header>

      {/* Tabs */}
      <div className="flex border-b border-slate-700 px-6">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={clsx(
              'flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors',
              activeTab === tab.id
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-gray-400 hover:text-white'
            )}
          >
            <tab.icon className="h-4 w-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-auto p-6">
        {activeTab === 'report' && (
          <div className="prose prose-invert max-w-none">
            {reportData?.markdown ? (
              <pre className="whitespace-pre-wrap text-gray-300 text-sm">{reportData.markdown}</pre>
            ) : run.status === 'running' ? (
              <p className="text-gray-400">Report will appear here when research completes...</p>
            ) : (
              <p className="text-gray-400">No report available</p>
            )}
          </div>
        )}

        {activeTab === 'claims' && (
          <div className="space-y-3">
            {currentClaims.length === 0 && <p className="text-gray-400">No claims extracted yet</p>}
            {currentClaims.map((claim) => (
              <div key={claim.claim_id} className="p-4 bg-slate-800 rounded-lg border border-slate-700">
                <p className="text-white">{claim.text}</p>
                <div className="flex items-center gap-2 mt-2">
                  <span className={clsx(
                    'px-2 py-0.5 rounded text-xs',
                    claim.status === 'verified' && 'bg-green-900 text-green-300',
                    claim.status === 'refuted' && 'bg-red-900 text-red-300',
                    claim.status === 'unverified' && 'bg-gray-700 text-gray-400',
                  )}>
                    {claim.status}
                  </span>
                  <span className="text-xs text-gray-500">{claim.evidence_ids.length} sources</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'sources' && (
          <div className="space-y-3">
            {currentEvidence.length === 0 && <p className="text-gray-400">No sources collected yet</p>}
            {currentEvidence.map((ev) => (
              <div key={ev.evidence_id} className="p-4 bg-slate-800 rounded-lg border border-slate-700">
                <a href={ev.source_url} target="_blank" rel="noopener" className="text-blue-400 hover:underline font-medium">
                  {ev.source_title}
                </a>
                <p className="text-gray-400 text-sm mt-1">{ev.snippet}</p>
                <div className="flex items-center gap-2 mt-2">
                  <span className={clsx(
                    'px-2 py-0.5 rounded text-xs',
                    ev.authority_tier === 'official' && 'bg-purple-900 text-purple-300',
                    ev.authority_tier === 'academic' && 'bg-blue-900 text-blue-300',
                    ev.authority_tier === 'industry' && 'bg-green-900 text-green-300',
                    ev.authority_tier === 'general' && 'bg-gray-700 text-gray-400',
                  )}>
                    {ev.authority_tier}
                  </span>
                  {ev.cross_validated && <span className="text-xs text-green-400">✓ Cross-validated</span>}
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'trace' && (
          <div className="space-y-2">
            {currentToolEvents.length === 0 && <p className="text-gray-400">No tool events yet</p>}
            {currentToolEvents.map((event, idx) => (
              <div key={event.event_id || idx} className="flex items-center gap-3 p-3 bg-slate-800 rounded-lg border border-slate-700">
                <div className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center text-xs text-gray-400">
                  {idx + 1}
                </div>
                <div className="flex-1">
                  <p className="text-white text-sm font-medium">{event.tool_name}</p>
                  <p className="text-gray-500 text-xs">{event.duration_ms}ms</p>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeTab === 'artifacts' && (
          <div className="text-gray-400">
            <p>Artifacts will appear here when the agent creates files.</p>
          </div>
        )}
      </div>
    </div>
  )
}
