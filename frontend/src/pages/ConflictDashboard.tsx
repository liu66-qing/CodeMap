import { useState } from 'react'
import { AlertTriangle, CheckCircle, Eye } from 'lucide-react'
import { clsx } from 'clsx'

interface Conflict {
  id: string
  type: 'temporal_overlap' | 'logical_contradiction' | 'source_disagreement'
  status: 'open' | 'resolved' | 'dismissed'
  description: string
  fact_a: string
  fact_b: string
  detected_at: string
}

const DEMO_CONFLICTS: Conflict[] = [
  {
    id: '1',
    type: 'temporal_overlap',
    status: 'open',
    description: 'CEO_OF relationship overlap for OpenAI',
    fact_a: 'Sam Altman --[CEO_OF]--> OpenAI (2019-present)',
    fact_b: 'Mira Murati --[CEO_OF]--> OpenAI (2023-11 to 2023-11)',
    detected_at: '2024-01-15',
  },
  {
    id: '2',
    type: 'source_disagreement',
    status: 'open',
    description: 'Conflicting acquisition dates for DeepMind',
    fact_a: 'Google acquired DeepMind in January 2014 (Source: TechCrunch)',
    fact_b: 'Google acquired DeepMind in February 2014 (Source: Reuters)',
    detected_at: '2024-01-10',
  },
]

export default function ConflictDashboard() {
  const [conflicts] = useState<Conflict[]>(DEMO_CONFLICTS)
  const [selectedConflict, setSelectedConflict] = useState<Conflict | null>(null)

  const openCount = conflicts.filter((c) => c.status === 'open').length

  return (
    <div className="h-full flex flex-col">
      <header className="p-4 border-b bg-white">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-amber-500" />
          Knowledge Conflicts
        </h2>
        <p className="text-sm text-gray-500">
          {openCount} open conflict{openCount !== 1 ? 's' : ''} detected in the knowledge graph
        </p>
      </header>

      <div className="flex-1 flex">
        <div className="w-1/2 border-r overflow-auto p-4 space-y-2">
          {conflicts.map((conflict) => (
            <div
              key={conflict.id}
              onClick={() => setSelectedConflict(conflict)}
              className={clsx(
                'p-3 rounded-lg border cursor-pointer transition-colors',
                selectedConflict?.id === conflict.id ? 'border-blue-500 bg-blue-50' : 'hover:bg-gray-50'
              )}
            >
              <div className="flex items-center gap-2">
                <TypeBadge type={conflict.type} />
                <span className={clsx(
                  'text-xs px-1.5 py-0.5 rounded',
                  conflict.status === 'open' ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
                )}>
                  {conflict.status}
                </span>
              </div>
              <p className="text-sm mt-2">{conflict.description}</p>
              <p className="text-xs text-gray-400 mt-1">Detected: {conflict.detected_at}</p>
            </div>
          ))}
        </div>

        <div className="w-1/2 p-4">
          {selectedConflict ? (
            <div>
              <h3 className="font-semibold mb-4">Conflict Evidence</h3>
              <div className="space-y-4">
                <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                  <p className="text-xs font-medium text-blue-700 mb-1">Fact A</p>
                  <p className="text-sm">{selectedConflict.fact_a}</p>
                </div>
                <div className="text-center text-gray-400 text-sm">vs</div>
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg">
                  <p className="text-xs font-medium text-amber-700 mb-1">Fact B</p>
                  <p className="text-sm">{selectedConflict.fact_b}</p>
                </div>
              </div>
              <div className="mt-6 flex gap-2">
                <button className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded hover:bg-blue-700">Accept Fact A</button>
                <button className="px-3 py-1.5 bg-amber-600 text-white text-sm rounded hover:bg-amber-700">Accept Fact B</button>
                <button className="px-3 py-1.5 border text-sm rounded hover:bg-gray-50">Dismiss</button>
              </div>
            </div>
          ) : (
            <div className="text-center text-gray-400 mt-20">
              <Eye className="w-8 h-8 mx-auto mb-2 opacity-50" />
              <p>Select a conflict to view details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function TypeBadge({ type }: { type: string }) {
  const labels: Record<string, string> = {
    temporal_overlap: 'Temporal',
    logical_contradiction: 'Logical',
    source_disagreement: 'Source',
  }
  const colors: Record<string, string> = {
    temporal_overlap: 'bg-purple-100 text-purple-700',
    logical_contradiction: 'bg-red-100 text-red-700',
    source_disagreement: 'bg-amber-100 text-amber-700',
  }
  return (
    <span className={clsx('text-xs px-1.5 py-0.5 rounded', colors[type] || 'bg-gray-100')}>
      {labels[type] || type}
    </span>
  )
}
