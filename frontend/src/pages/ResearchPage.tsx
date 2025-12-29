import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { 
  Play, 
  Settings as SettingsIcon, 
  ChevronDown,
  Sparkles,
  Lightbulb,
} from 'lucide-react'
import clsx from 'clsx'
import * as api from '../api'
import { 
  AblationConfig, 
  CreateRunRequest, 
  DemoScenario, 
  EngineType, 
  OutputFormat 
} from '../types'

const outputFormats: { value: OutputFormat; label: string; description: string }[] = [
  { value: 'report', label: 'Research Report', description: 'Comprehensive research report with citations' },
  { value: 'adr', label: 'ADR', description: 'Architecture Decision Record' },
  { value: 'brief', label: 'Brief', description: 'Executive brief with key findings' },
  { value: 'memo', label: 'Policy Memo', description: 'Policy-oriented memo format' },
]

const defaultAblations: AblationConfig = {
  enable_reflection: true,
  enable_authority_ranking: true,
  enable_todo_state: true,
  enable_patch_editing: true,
}

export default function ResearchPage() {
  const navigate = useNavigate()
  
  const [query, setQuery] = useState('')
  const [engine, setEngine] = useState<EngineType>('deep_research')
  const [outputFormat, setOutputFormat] = useState<OutputFormat>('report')
  const [maxSteps, setMaxSteps] = useState(50)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [ablations, setAblations] = useState<AblationConfig>(defaultAblations)
  
  // Fetch demo scenarios
  const { data: scenariosData } = useQuery({
    queryKey: ['scenarios'],
    queryFn: api.getDemoScenarios,
  })
  
  const scenarios = scenariosData?.scenarios ?? []
  
  // Create run mutation
  const createRunMutation = useMutation({
    mutationFn: (request: CreateRunRequest) => api.createRun(request),
    onSuccess: (run) => {
      navigate(`/runs/${run.run_id}`)
    },
  })
  
  const handleSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault()
    
    if (!query.trim()) return
    
    createRunMutation.mutate({
      query: query.trim(),
      config: {
        engine,
        output_format: outputFormat,
        max_steps: maxSteps,
        verification_strictness: 2,
        ablations,
      },
    })
  }, [query, engine, outputFormat, maxSteps, ablations, createRunMutation])
  
  const handleScenarioClick = (scenario: DemoScenario) => {
    setQuery(scenario.query)
  }
  
  return (
    <div className="flex-1 overflow-auto">
      <div className="max-w-4xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">
            Deep Research
          </h1>
          <p className="text-gray-400">
            Conduct thorough research with ReAct-based agents that reason, act, and reflect.
          </p>
        </div>
        
        {/* Query Form */}
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Query Input */}
          <div>
            <label 
              htmlFor="query" 
              className="block text-sm font-medium text-gray-300 mb-2"
            >
              Research Question
            </label>
            <textarea
              id="query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Enter your research question or task..."
              rows={4}
              className="w-full px-4 py-3 bg-slate-800 border border-slate-600 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
            />
          </div>
          
          {/* Quick Config */}
          <div className="grid grid-cols-2 gap-4">
            {/* Engine */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Engine
              </label>
              <select
                value={engine}
                onChange={(e) => setEngine(e.target.value as EngineType)}
                className="w-full px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="deep_research">Deep Research (Full)</option>
                <option value="baseline">Baseline Model</option>
              </select>
            </div>
            
            {/* Output Format */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Output Format
              </label>
              <select
                value={outputFormat}
                onChange={(e) => setOutputFormat(e.target.value as OutputFormat)}
                className="w-full px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {outputFormats.map((fmt) => (
                  <option key={fmt.value} value={fmt.value}>
                    {fmt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          
          {/* Advanced Settings Toggle */}
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center text-sm text-gray-400 hover:text-white transition-colors"
          >
            <SettingsIcon className="h-4 w-4 mr-2" />
            Advanced Settings
            <ChevronDown 
              className={clsx(
                'h-4 w-4 ml-1 transition-transform',
                showAdvanced && 'rotate-180'
              )} 
            />
          </button>
          
          {/* Advanced Settings Panel */}
          {showAdvanced && (
            <div className="p-4 bg-slate-800/50 rounded-lg border border-slate-700 space-y-4">
              {/* Max Steps */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Max Steps: {maxSteps}
                </label>
                <input
                  type="range"
                  min={10}
                  max={100}
                  value={maxSteps}
                  onChange={(e) => setMaxSteps(parseInt(e.target.value))}
                  className="w-full"
                />
              </div>
              
              {/* Ablation Toggles */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-3">
                  Capability Toggles (Ablations)
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <label className="flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={ablations.enable_reflection}
                      onChange={(e) => setAblations({
                        ...ablations,
                        enable_reflection: e.target.checked,
                      })}
                      className="h-4 w-4 rounded border-slate-600 text-blue-500 focus:ring-blue-500 bg-slate-700"
                    />
                    <span className="ml-2 text-sm text-gray-300">
                      Reflection & Cross-Validation
                    </span>
                  </label>
                  
                  <label className="flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={ablations.enable_authority_ranking}
                      onChange={(e) => setAblations({
                        ...ablations,
                        enable_authority_ranking: e.target.checked,
                      })}
                      className="h-4 w-4 rounded border-slate-600 text-blue-500 focus:ring-blue-500 bg-slate-700"
                    />
                    <span className="ml-2 text-sm text-gray-300">
                      Authority-Aware Ranking
                    </span>
                  </label>
                  
                  <label className="flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={ablations.enable_todo_state}
                      onChange={(e) => setAblations({
                        ...ablations,
                        enable_todo_state: e.target.checked,
                      })}
                      className="h-4 w-4 rounded border-slate-600 text-blue-500 focus:ring-blue-500 bg-slate-700"
                    />
                    <span className="ml-2 text-sm text-gray-300">
                      Todo State Tracking
                    </span>
                  </label>
                  
                  <label className="flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={ablations.enable_patch_editing}
                      onChange={(e) => setAblations({
                        ...ablations,
                        enable_patch_editing: e.target.checked,
                      })}
                      className="h-4 w-4 rounded border-slate-600 text-blue-500 focus:ring-blue-500 bg-slate-700"
                    />
                    <span className="ml-2 text-sm text-gray-300">
                      Patch-Based Editing
                    </span>
                  </label>
                </div>
              </div>
            </div>
          )}
          
          {/* Submit Button */}
          <button
            type="submit"
            disabled={!query.trim() || createRunMutation.isPending}
            className={clsx(
              'w-full flex items-center justify-center px-6 py-3 rounded-lg font-medium transition-colors',
              query.trim() && !createRunMutation.isPending
                ? 'bg-blue-600 hover:bg-blue-700 text-white'
                : 'bg-slate-700 text-gray-500 cursor-not-allowed'
            )}
          >
            {createRunMutation.isPending ? (
              <>
                <Sparkles className="h-5 w-5 mr-2 animate-spin" />
                Starting Research...
              </>
            ) : (
              <>
                <Play className="h-5 w-5 mr-2" />
                Start Research
              </>
            )}
          </button>
          
          {createRunMutation.isError && (
            <p className="text-red-400 text-sm">
              Error: {createRunMutation.error.message}
            </p>
          )}
        </form>
        
        {/* Demo Scenarios */}
        <div className="mt-12">
          <div className="flex items-center mb-4">
            <Lightbulb className="h-5 w-5 text-yellow-400 mr-2" />
            <h2 className="text-lg font-semibold text-white">
              Demo Scenarios
            </h2>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {scenarios.map((scenario) => (
              <button
                key={scenario.id}
                onClick={() => handleScenarioClick(scenario)}
                className="p-4 bg-slate-800 border border-slate-700 rounded-lg text-left hover:bg-slate-700 hover:border-slate-600 transition-colors group"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-medium text-white group-hover:text-blue-400 transition-colors">
                      {scenario.name}
                    </h3>
                    <p className="text-sm text-gray-400 mt-1">
                      {scenario.description}
                    </p>
                  </div>
                  <span className={clsx(
                    'px-2 py-0.5 text-xs rounded-full',
                    scenario.category === 'planning' && 'bg-purple-900 text-purple-300',
                    scenario.category === 'information_seeking' && 'bg-blue-900 text-blue-300',
                    scenario.category === 'verification' && 'bg-yellow-900 text-yellow-300',
                    scenario.category === 'reporting' && 'bg-green-900 text-green-300',
                    scenario.category === 'authority' && 'bg-orange-900 text-orange-300',
                  )}>
                    {scenario.category.replace('_', ' ')}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
