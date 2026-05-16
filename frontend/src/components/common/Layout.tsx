import { NavLink } from 'react-router-dom'
import { Network, MessageSquare, FileUp, AlertTriangle, Clock } from 'lucide-react'
import { clsx } from 'clsx'

const navItems = [
  { path: '/', label: 'Graph Explorer', icon: Network },
  { path: '/query', label: 'Query Console', icon: MessageSquare },
  { path: '/documents', label: 'Documents', icon: FileUp },
  { path: '/conflicts', label: 'Conflicts', icon: AlertTriangle },
  { path: '/timeline', label: 'Timeline', icon: Clock },
]

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen">
      <aside className="w-64 bg-gray-900 text-white flex flex-col">
        <div className="p-4 border-b border-gray-700">
          <h1 className="text-xl font-bold flex items-center gap-2">
            <Network className="w-6 h-6 text-blue-400" />
            EvoGraph
          </h1>
          <p className="text-xs text-gray-400 mt-1">Knowledge Graph Evolution Agent</p>
        </div>
        <nav className="flex-1 p-2">
          {navItems.map(({ path, label, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors',
                  isActive
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                )
              }
            >
              <Icon className="w-4 h-4" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-gray-700 text-xs text-gray-500">
          Agentic RAG with KG Evolution
        </div>
      </aside>
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  )
}
