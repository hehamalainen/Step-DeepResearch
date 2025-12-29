import { Settings } from 'lucide-react'

export default function SettingsPage() {
  return (
    <div className="flex-1 overflow-auto">
      <div className="max-w-2xl mx-auto px-6 py-8">
        <div className="flex items-center gap-3 mb-6">
          <Settings className="h-6 w-6 text-blue-400" />
          <h1 className="text-2xl font-bold text-white">Settings</h1>
        </div>

        <div className="space-y-6">
          <div className="p-4 bg-slate-800 rounded-lg border border-slate-700">
            <h3 className="text-white font-medium mb-3">Model Configuration</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-sm text-gray-400 mb-1">API Base URL</label>
                <input
                  type="text"
                  defaultValue="https://api.openai.com/v1"
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded text-white text-sm"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Model</label>
                <input
                  type="text"
                  defaultValue="gpt-4o-mini"
                  className="w-full px-3 py-2 bg-slate-700 border border-slate-600 rounded text-white text-sm"
                />
              </div>
            </div>
          </div>

          <div className="p-4 bg-slate-800 rounded-lg border border-slate-700">
            <h3 className="text-white font-medium mb-3">Default Ablations</h3>
            <p className="text-gray-400 text-sm">
              Configure default capability toggles for new research runs.
              These can be overridden per-run in the Research page.
            </p>
          </div>

          <div className="p-4 bg-slate-800 rounded-lg border border-slate-700">
            <h3 className="text-white font-medium mb-3">About</h3>
            <p className="text-gray-400 text-sm">
              Copilot Deep Research Showcase - Based on Step-DeepResearch paper.
              Demonstrates ReAct-based research agents with reflection, authority ranking, and structured outputs.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
