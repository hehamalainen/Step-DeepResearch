import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { FileText, Clock, CheckCircle, XCircle, Loader2 } from 'lucide-react'
import clsx from 'clsx'
import * as api from '../api'
import { RunStatus } from '../types'

const statusConfig: Record<RunStatus, { icon: typeof Clock; color: string; label: string }> = {
  pending: { icon: Clock, color: 'text-gray-400', label: 'Pending' },
  running: { icon: Loader2, color: 'text-blue-400', label: 'Running' },
  succeeded: { icon: CheckCircle, color: 'text-green-400', label: 'Succeeded' },
  failed: { icon: XCircle, color: 'text-red-400', label: 'Failed' },
  cancelled: { icon: XCircle, color: 'text-yellow-400', label: 'Cancelled' },
}

export default function RunsPage() {
  const { data: runs = [], isLoading, error } = useQuery({
    queryKey: ['runs'],
    queryFn: () => api.listRuns(),
    refetchInterval: 5000,
  })

  return (
    <div className="flex-1 overflow-auto">
      <div className="max-w-6xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-white">Research Runs</h1>
          <Link
            to="/research"
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
          >
            New Research
          </Link>
        </div>

        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 text-blue-400 animate-spin" />
          </div>
        )}

        {error && (
          <div className="p-4 bg-red-900/50 border border-red-700 rounded-lg text-red-300">
            Error loading runs: {(error as Error).message}
          </div>
        )}

        {!isLoading && runs.length === 0 && (
          <div className="text-center py-12">
            <FileText className="h-12 w-12 text-gray-600 mx-auto mb-4" />
            <p className="text-gray-400">No research runs yet</p>
            <Link to="/research" className="text-blue-400 hover:underline text-sm mt-2 inline-block">
              Start your first research
            </Link>
          </div>
        )}

        <div className="space-y-3">
          {runs.map((run) => {
            const status = statusConfig[run.status]
            const StatusIcon = status.icon
            return (
              <Link
                key={run.run_id}
                to={`/runs/${run.run_id}`}
                className="block p-4 bg-slate-800 border border-slate-700 rounded-lg hover:bg-slate-750 hover:border-slate-600 transition-colors"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <p className="text-white font-medium truncate">{run.query}</p>
                    <div className="flex items-center gap-4 mt-2 text-sm text-gray-400">
                      <span>{run.engine}</span>
                      <span>{run.tool_calls} tool calls</span>
                      <span>{new Date(run.created_at).toLocaleString()}</span>
                    </div>
                  </div>
                  <div className={clsx('flex items-center gap-2', status.color)}>
                    <StatusIcon className={clsx('h-4 w-4', run.status === 'running' && 'animate-spin')} />
                    <span className="text-sm">{status.label}</span>
                  </div>
                </div>
              </Link>
            )
          })}
        </div>
      </div>
    </div>
  )
}
