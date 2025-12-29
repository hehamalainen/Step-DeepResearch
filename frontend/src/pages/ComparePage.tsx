import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { GitCompare, ArrowRight } from 'lucide-react'
import * as api from '../api'

export default function ComparePage() {
  const [runAId, setRunAId] = useState('')
  const [runBId, setRunBId] = useState('')

  const { data: runs = [] } = useQuery({
    queryKey: ['runs'],
    queryFn: () => api.listRuns(),
  })

  const compareMutation = useMutation({
    mutationFn: () => api.compareRuns(runAId, runBId),
  })

  const handleCompare = () => {
    if (runAId && runBId) {
      compareMutation.mutate()
    }
  }

  return (
    <div className="flex-1 overflow-auto">
      <div className="max-w-4xl mx-auto px-6 py-8">
        <h1 className="text-2xl font-bold text-white mb-6">Compare Runs</h1>

        <div className="flex items-center gap-4 mb-8">
          <select
            value={runAId}
            onChange={(e) => setRunAId(e.target.value)}
            className="flex-1 px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white"
          >
            <option value="">Select Run A</option>
            {runs.map((r) => (
              <option key={r.run_id} value={r.run_id}>{r.query.slice(0, 50)}...</option>
            ))}
          </select>
          
          <ArrowRight className="h-5 w-5 text-gray-500" />
          
          <select
            value={runBId}
            onChange={(e) => setRunBId(e.target.value)}
            className="flex-1 px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white"
          >
            <option value="">Select Run B</option>
            {runs.map((r) => (
              <option key={r.run_id} value={r.run_id}>{r.query.slice(0, 50)}...</option>
            ))}
          </select>
          
          <button
            onClick={handleCompare}
            disabled={!runAId || !runBId || compareMutation.isPending}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:text-gray-500 text-white rounded-lg font-medium"
          >
            <GitCompare className="h-4 w-4" />
          </button>
        </div>

        {compareMutation.data && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 bg-slate-800 rounded-lg border border-slate-700">
                <h3 className="text-sm font-medium text-gray-400 mb-2">Run A Metrics</h3>
                <div className="space-y-1 text-sm text-white">
                  <p>Tool Calls: {compareMutation.data.run_a.metrics?.total_tool_calls ?? 'N/A'}</p>
                  <p>Tokens: {compareMutation.data.run_a.metrics?.total_tokens ?? 'N/A'}</p>
                  <p>Citations: {compareMutation.data.run_a.metrics?.citation_count ?? 'N/A'}</p>
                </div>
              </div>
              <div className="p-4 bg-slate-800 rounded-lg border border-slate-700">
                <h3 className="text-sm font-medium text-gray-400 mb-2">Run B Metrics</h3>
                <div className="space-y-1 text-sm text-white">
                  <p>Tool Calls: {compareMutation.data.run_b.metrics?.total_tool_calls ?? 'N/A'}</p>
                  <p>Tokens: {compareMutation.data.run_b.metrics?.total_tokens ?? 'N/A'}</p>
                  <p>Citations: {compareMutation.data.run_b.metrics?.citation_count ?? 'N/A'}</p>
                </div>
              </div>
            </div>

            <div className="p-4 bg-slate-800 rounded-lg border border-slate-700">
              <h3 className="text-sm font-medium text-gray-400 mb-3">Claim Differences</h3>
              {compareMutation.data.claim_diffs.length === 0 ? (
                <p className="text-gray-500 text-sm">No claim differences found</p>
              ) : (
                <div className="space-y-2">
                  {compareMutation.data.claim_diffs.map((diff, idx) => (
                    <div key={idx} className="p-3 bg-slate-700 rounded text-sm">
                      <p className="text-white">{diff.claim_text}</p>
                      <div className="flex gap-4 mt-1 text-xs">
                        <span className="text-gray-400">A: {diff.status_a ?? 'missing'}</span>
                        <span className="text-gray-400">B: {diff.status_b ?? 'missing'}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
