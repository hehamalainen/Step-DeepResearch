import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { BarChart3, ThumbsUp, Minus } from 'lucide-react'
import clsx from 'clsx'
import * as api from '../api'
import { EvaluationTask } from '../types'

export default function EvaluationPage() {
  const queryClient = useQueryClient()

  const { data: tasksData } = useQuery({
    queryKey: ['evalTasks'],
    queryFn: api.getEvaluationTasks,
  })

  const judgmentMutation = useMutation({
    mutationFn: (params: { taskId: string; runA: string; runB: string; winner: 'a' | 'b' | 'tie' }) =>
      api.submitPairwiseJudgment({
        run_a_id: params.runA,
        run_b_id: params.runB,
        winner: params.winner,
        completeness_a: 3,
        completeness_b: 3,
        depth_a: 3,
        depth_b: 3,
        readability_a: 3,
        readability_b: 3,
        requirement_fit_a: 3,
        requirement_fit_b: 3,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['evalTasks'] })
    },
  })

  const tasks: EvaluationTask[] = tasksData?.tasks ?? []

  return (
    <div className="flex-1 overflow-auto">
      <div className="max-w-4xl mx-auto px-6 py-8">
        <div className="flex items-center gap-3 mb-6">
          <BarChart3 className="h-6 w-6 text-blue-400" />
          <h1 className="text-2xl font-bold text-white">Evaluation Framework</h1>
        </div>

        <p className="text-gray-400 mb-8">
          Compare research outputs using pairwise human evaluation. Judge which run produces better results.
        </p>

        {tasks.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-500">No evaluation tasks available.</p>
            <p className="text-gray-600 text-sm mt-2">Run research with different configurations to create comparison tasks.</p>
          </div>
        ) : (
          <div className="space-y-6">
            {tasks.map((task) => (
              <div key={task.task_id} className="p-6 bg-slate-800 rounded-lg border border-slate-700">
                <h3 className="text-white font-medium mb-2">{task.query}</h3>
                <p className="text-gray-400 text-sm mb-4">{task.description}</p>

                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div className="p-3 bg-slate-700 rounded">
                    <p className="text-xs text-gray-500 mb-1">Run A</p>
                    <p className="text-sm text-white">{task.run_a_id?.slice(0, 8) ?? 'Pending'}</p>
                  </div>
                  <div className="p-3 bg-slate-700 rounded">
                    <p className="text-xs text-gray-500 mb-1">Run B</p>
                    <p className="text-sm text-white">{task.run_b_id?.slice(0, 8) ?? 'Pending'}</p>
                  </div>
                </div>

                {task.run_a_id && task.run_b_id && (
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-gray-400 mr-2">Winner:</span>
                    <button
                      onClick={() => judgmentMutation.mutate({
                        taskId: task.task_id,
                        runA: task.run_a_id!,
                        runB: task.run_b_id!,
                        winner: 'a',
                      })}
                      className={clsx(
                        'flex items-center gap-1 px-3 py-1.5 rounded text-sm transition-colors',
                        'bg-slate-700 hover:bg-green-900 text-gray-300 hover:text-green-300'
                      )}
                    >
                      <ThumbsUp className="h-4 w-4" /> A
                    </button>
                    <button
                      onClick={() => judgmentMutation.mutate({
                        taskId: task.task_id,
                        runA: task.run_a_id!,
                        runB: task.run_b_id!,
                        winner: 'tie',
                      })}
                      className="flex items-center gap-1 px-3 py-1.5 rounded text-sm bg-slate-700 hover:bg-yellow-900 text-gray-300 hover:text-yellow-300"
                    >
                      <Minus className="h-4 w-4" /> Tie
                    </button>
                    <button
                      onClick={() => judgmentMutation.mutate({
                        taskId: task.task_id,
                        runA: task.run_a_id!,
                        runB: task.run_b_id!,
                        winner: 'b',
                      })}
                      className="flex items-center gap-1 px-3 py-1.5 rounded text-sm bg-slate-700 hover:bg-green-900 text-gray-300 hover:text-green-300"
                    >
                      <ThumbsUp className="h-4 w-4" /> B
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
