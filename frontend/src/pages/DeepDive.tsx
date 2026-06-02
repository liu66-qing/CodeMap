import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Code2, Loader2 } from 'lucide-react'
import { api, type RepoSummary, type ModuleCard, type MechanismAnalysis, type SourceSnippet } from '../services/api'

export default function DeepDive() {
  const [searchParams] = useSearchParams()
  const [repos, setRepos] = useState<string[]>([])
  const [repoId, setRepoId] = useState('')
  const [modules, setModules] = useState<ModuleCard[]>([])
  const [selectedModule, setSelectedModule] = useState('')
  const [mechanism, setMechanism] = useState<MechanismAnalysis | null>(null)
  const [sourceMap, setSourceMap] = useState<Record<string, SourceSnippet>>({})
  const [loading, setLoading] = useState(false)
  const [mechLoading, setMechLoading] = useState(false)
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
    setModules([])
    setSelectedModule('')
    setMechanism(null)
    api.getModules(repoId)
      .then((d) => setModules(d.module_map?.cards || []))
      .catch(() => setError('加载失败'))
      .finally(() => setLoading(false))
  }, [repoId])

  useEffect(() => {
    if (!repoId || !selectedModule) return
    setMechLoading(true)
    setMechanism(null)
    setSourceMap({})
    api.getModuleMechanism(repoId, selectedModule)
      .then((d) => setMechanism(d.mechanism || null))
      .catch(() => {})
      .finally(() => setMechLoading(false))
  }, [repoId, selectedModule])

  const fetchSource = (symbol: string) => {
    if (sourceMap[symbol]) return
    api.getSymbolSource(repoId, symbol)
      .then((d) => { if (d.source) setSourceMap((m) => ({ ...m, [symbol]: d.source! })) })
      .catch(() => {})
  }

  return (
    <div className="h-full flex">
      {/* Left sidebar: module list */}
      <aside className="w-64 border-r bg-gray-50 overflow-y-auto shrink-0">
        <div className="p-4">
          <header className="flex items-center gap-2 mb-4">
            <Code2 className="w-5 h-5 text-indigo-500" />
            <h1 className="text-sm font-bold text-gray-800">深钻</h1>
            {repos.length > 1 && (
              <select value={repoId} onChange={(e) => setRepoId(e.target.value)}
                className="ml-auto border rounded px-1 py-0.5 text-xs w-24 truncate">
                {repos.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            )}
          </header>
          {loading && <div className="flex items-center gap-2 text-gray-400 text-xs"><Loader2 className="w-3 h-3 animate-spin" /> 加载中…</div>}
          {error && <p className="text-red-500 text-xs">{error}</p>}
          <ul className="space-y-1">
            {modules.map((m) => (
              <li key={m.id}>
                <button onClick={() => setSelectedModule(m.id)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm transition ${selectedModule === m.id ? 'bg-indigo-100 text-indigo-800 font-medium' : 'hover:bg-gray-100 text-gray-700'}`}>
                  <p className="truncate">{m.title}</p>
                  <p className="text-[10px] text-gray-400 truncate">{m.layer} · {m.symbol_count} 符号</p>
                </button>
              </li>
            ))}
          </ul>
        </div>
      </aside>

      {/* Right: mechanism detail */}
      <main className="flex-1 overflow-y-auto p-6">
        {!selectedModule && (
          <div className="flex items-center justify-center h-full text-gray-400 text-sm">
            <Code2 className="w-5 h-5 mr-2" /> 选择左侧模块查看实现机制
          </div>
        )}
        {mechLoading && <div className="flex items-center gap-2 text-gray-400"><Loader2 className="w-4 h-4 animate-spin" /> 分析中…</div>}
        {mechanism && !mechLoading && (
          <div className="max-w-3xl space-y-5">
            <h2 className="text-lg font-bold text-gray-800">{mechanism.module}</h2>
            <Section title="概述" content={mechanism.overview} />
            {mechanism.parts.length > 0 && (
              <section>
                <h3 className="text-sm font-semibold text-gray-700 mb-2">组成部分</h3>
                <ul className="space-y-2">
                  {mechanism.parts.map((p) => (
                    <li key={p.symbol} className="flex items-start gap-2 text-sm">
                      <code className="font-mono text-indigo-600 shrink-0">{p.symbol}</code>
                      <span className="text-gray-600">{p.role}</span>
                      <button onClick={() => fetchSource(p.symbol)}
                        className="ml-auto text-[10px] text-indigo-500 hover:underline shrink-0">查看源码</button>
                    </li>
                  ))}
                </ul>
              </section>
            )}
            <Section title="连接关系" content={mechanism.connections} />
            <Section title="数据流" content={mechanism.data_flow} />
            {mechanism.state_memory && <Section title="状态/记忆" content={mechanism.state_memory} />}

            {/* Source code blocks */}
            {Object.entries(sourceMap).map(([sym, src]) => (
              <div key={sym} className="mt-4">
                <p className="text-xs text-gray-500 mb-1 font-mono">{sym} — {src.file_path}:{src.line_start}-{src.line_end}</p>
                <pre className="bg-gray-900 text-gray-100 rounded-lg p-4 text-xs overflow-x-auto leading-5">
                  {src.code.split('\n').map((line, i) => (
                    <div key={i}><span className="text-gray-500 select-none mr-3">{src.line_start + i}</span>{line}</div>
                  ))}
                </pre>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}

function Section({ title, content }: { title: string; content: string }) {
  if (!content) return null
  return (
    <section>
      <h3 className="text-sm font-semibold text-gray-700 mb-1">{title}</h3>
      <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">{content}</p>
    </section>
  )
}
