import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Sparkles, Loader2 } from 'lucide-react'
import { api, type RepoSummary } from '../services/api'

interface Highlight {
  category: string
  title: string
  problem: string
  solution: string
  tradeoff: string
  modules: string[]
  symbols: string[]
}

const categoryColors: Record<string, string> = {
  context_management: 'bg-cyan-50 text-cyan-700 border-cyan-200',
  fault_tolerance: 'bg-amber-50 text-amber-700 border-amber-200',
  abstraction: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  performance: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  extensibility: 'bg-purple-50 text-purple-700 border-purple-200',
}

export default function Highlights() {
  const [searchParams] = useSearchParams()
  const [repos, setRepos] = useState<string[]>([])
  const [repoId, setRepoId] = useState('')
  const [highlights, setHighlights] = useState<Highlight[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.listRepos().then((r) => {
      const ids = (r.repositories || []).map((x: RepoSummary) => x.repo_id)
      setRepos(ids)
      const wanted = searchParams.get('repo')
      setRepoId(wanted && ids.includes(wanted) ? wanted : ids[0] || '')
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!repoId) return
    setLoading(true)
    setError('')
    fetch('/api/v1/repositories/' + encodeURIComponent(repoId) + '/highlights')
      .then((res) => { if (!res.ok) throw new Error('failed'); return res.json() })
      .then((d) => setHighlights(d.highlights || []))
      .catch(() => setError('加载失败'))
      .finally(() => setLoading(false))
  }, [repoId])

  const badgeClass = (cat: string) => categoryColors[cat] || 'bg-gray-50 text-gray-700 border-gray-200'

  return (
    <div className="h-full overflow-auto">
      <div className="max-w-4xl mx-auto px-6 py-8">
        <header className="flex items-center gap-3 mb-6">
          <Sparkles className="w-6 h-6 text-indigo-500" />
          <div>
            <h1 className="text-xl font-bold text-gray-800">亮点:这个项目牛在哪</h1>
            <p className="text-sm text-gray-500">值得学习的设计决策与工程亮点</p>
          </div>
          {repos.length > 1 && (
            <select value={repoId} onChange={(e) => setRepoId(e.target.value)}
              className="ml-auto border rounded-lg px-2 py-1.5 text-sm">
              {repos.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          )}
        </header>

        {loading && <div className="flex items-center gap-2 text-gray-400"><Loader2 className="w-4 h-4 animate-spin" /> 加载中…</div>}
        {error && <p className="text-red-500 text-sm">{error}</p>}

        {!loading && !error && highlights.length > 0 && (
          <div className="space-y-4">
            {highlights.map((h, i) => (
              <div key={i} className="bg-white border rounded-xl p-5">
                <div className="flex items-center gap-2 mb-2">
                  <span className={`text-[10px] px-2 py-0.5 rounded border ${badgeClass(h.category)}`}>
                    {h.category.replace(/_/g, ' ')}
                  </span>
                  <span className="text-sm font-bold text-gray-800">{h.title}</span>
                </div>
                <div className="space-y-2 text-sm">
                  <div><span className="font-medium text-gray-600">问题: </span><span className="text-gray-700">{h.problem}</span></div>
                  <div><span className="font-medium text-gray-600">方案: </span><span className="text-gray-700">{h.solution}</span></div>
                  {h.tradeoff && (
                    <div className="bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
                      <span className="font-medium text-amber-700 text-xs">Tradeoff: </span>
                      <span className="text-amber-800 text-xs">{h.tradeoff}</span>
                    </div>
                  )}
                </div>
                {(h.modules?.length > 0 || h.symbols?.length > 0) && (
                  <div className="flex flex-wrap gap-1 mt-3">
                    {h.modules?.map((m) => (
                      <span key={m} className="text-[10px] px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded">{m}</span>
                    ))}
                    {h.symbols?.map((s) => (
                      <span key={s} className="text-[10px] px-1.5 py-0.5 bg-indigo-50 text-indigo-600 rounded font-mono">{s}</span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {!loading && !error && highlights.length === 0 && repoId && (
          <p className="text-sm text-gray-400">暂无亮点数据</p>
        )}
      </div>
    </div>
  )
}
