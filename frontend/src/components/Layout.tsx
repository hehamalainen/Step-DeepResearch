import { NavLink } from 'react-router-dom'
import { 
  Search, 
  FileText, 
  GitCompare, 
  BarChart3, 
  Settings,
  Sparkles 
} from 'lucide-react'
import clsx from 'clsx'

interface LayoutProps {
  children: React.ReactNode
}

const navItems = [
  { path: '/research', label: 'Research', icon: Search },
  { path: '/runs', label: 'Runs', icon: FileText },
  { path: '/compare', label: 'Compare', icon: GitCompare },
  { path: '/evaluation', label: 'Evaluation', icon: BarChart3 },
  { path: '/settings', label: 'Settings', icon: Settings },
]

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="min-h-screen bg-slate-900 flex">
      {/* Sidebar */}
      <aside className="w-64 bg-slate-800 border-r border-slate-700 flex flex-col">
        {/* Logo */}
        <div className="h-16 flex items-center px-4 border-b border-slate-700">
          <Sparkles className="h-6 w-6 text-blue-400 mr-2" />
          <span className="text-lg font-semibold text-white">
            Deep Research
          </span>
        </div>
        
        {/* Navigation */}
        <nav className="flex-1 py-4">
          <ul className="space-y-1 px-2">
            {navItems.map((item) => (
              <li key={item.path}>
                <NavLink
                  to={item.path}
                  className={({ isActive }) =>
                    clsx(
                      'flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                      isActive
                        ? 'bg-blue-600 text-white'
                        : 'text-gray-300 hover:bg-slate-700 hover:text-white'
                    )
                  }
                >
                  <item.icon className="h-5 w-5 mr-3" />
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        
        {/* Footer */}
        <div className="p-4 border-t border-slate-700">
          <p className="text-xs text-gray-500">
            Based on Step-DeepResearch
          </p>
          <p className="text-xs text-gray-600 mt-1">
            Copilot Deep Research Showcase
          </p>
        </div>
      </aside>
      
      {/* Main content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {children}
      </main>
    </div>
  )
}
