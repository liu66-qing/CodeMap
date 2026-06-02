import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { GitCommit, Loader2, AlertTriangle } from 'lucide-react'
import { api, type RepoSummary, type RepoCommit, type BreakingChange } from '../services/api'

export default function Evolution() {
  const [searchParams] = useSearchParams()
  const [repos, setRepos] = useState<string[]>([])
  const [repoId, setRepoId] = useState('')
  const [tab, setTab] = useState<'commits' | 'breaking'>('commits')
  const [commits, setCommits] = useState<RepoCommit[]>([])
  const [breaking, setBreaking] = useState<BreakingChange[]>([])
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
    Promise.all([
      api.getRepoCommits(repoId).catch(() => null),
      api.getBreakingChanges(repoId).catch(() => null),
    ]).then(([c, b]) => {
      setCommits(c?.commits || [])
      setBreaking(b?.breaking_changes || [])
    }).catch(() => setError('加载失败'))
      .finally(() => setLoading(false))
  }, [repoId])

  return (
    <div className="h-full overflow-auto">
      <div className="max-w-4xl mx-auto px-6 py-8">
        <header className="flex items-center gap-3 mb-6">
          <GitCommit className="w-6 h-6 text-indigo-500" />
          <div>
            <h1 className="text-xl font-bold text-gray-800">演化:Git 历史与破坏性变更</h1>
            <p className="text-sm text-gray-500">提交时间线与 API 兼容性变化</p>
          </div>
          {repos.length > 1 && (
            <select value={repoId} onChange={(e) => setRepoId(e.target.value)}
              className="ml-auto border rounded-lg px-2 py-1.5 text-sm">
              {repos.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          )}
        </header>

        {/* Tabs */}
        <div className="flex gap-1 mb-5 border-b">
          <TabBtn active={tab === 'commits'} onClick={() => setTab('commits')}>提交时间线</TabBtn>
          <TabBtn active={tab === 'breaking'} onClick={() => setTab('breaking')}>
            破坏性变更 {breaking.length > 0 && <span className="ml-1 text-[10px] bg-red-100 text-red-600 px-1.5 rounded-full">{breaking.length}</span>}
          </TabBtn>
        </div>

        {loading && <div className="flex items-center gap-2 text-gray-400"><Loader2 className="w-4 h-4 animate-spin" /> 加载中…</div>}
        {error && <p className="text-red-500 text-sm">{error}</p>}

        {!loading && !error && tab === 'commits' && (
          <div className="relative pl-6 border-l-2 border-gray-200 space-y-4">
            {commits.length === 0 && <p className="text-sm text-gray-400">暂无提交数据</p>}
            {commits.map((c) => (
              <div key={c.sha} className="relative">
                <span className="absolute -left-[25px] top-1.5 w-3 h-3 rounded-full bg-indigo-400 border-2 border-white" />
                <div className="bg-white border rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <code className="text-[10px] px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded font-mono">{c.short_sha}</code>
                    <span className="text-sm text-gray-800 font-medium truncate flex-1">{c.subject}</span>
                    {c.breaking_changes > 0 && <AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0" />}
                  </div>
                  <div className="flex items-center gap-3 text-[10px] text-gray-400">
                    {c.author && <span>{c.author}</span>}
                    {c.timestamp && <span>{new Date(c.timestamp).toLocaleDateString()}</span>}
                    {c.callables != null && <span>{c.callables} 函数</span>}
                    {c.files != null && <span>{c.files} 文件</span>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {!loading && !error && tab === 'breaking' && (
          <div className="space-y-3">
            {breaking.length === 0 && <p className="text-sm text-gray-400">未检测到破坏性变更</p>}
            {breaking.map((b, i) => (
              <div key={i} className="bg-white border border-amber-200 rounded-xl p-4">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="w-4 h-4 text-amber-500" />
                  <code className="text-sm font-mono font-medium text-gray-800">{b.symbol}</code>
                </div>
                <p className="text-sm text-gray-600 mb-2">{b.description}</p>
                {(b.old_signature || b.new_signature) && (
                  <div className="bg-gray-900 rounded-lg p-3 text-xs font-mono space-y-1">
                    {b.old_signature && <div className="text-red-400">- {b.old_signature}</div>}
                    {b.new_signature && <div className="text-green-400">+ {b.new_signature}</div>}
                  </div>
                )}
                {b.affected_callers && b.affected_callers.length > 0 && (
                  <p className="text-[10px] text-gray-400 mt-2">影响 {b.affected_callers.length} 个调用方</p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function TabBtn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button onClick={onClick}
      className={`px-4 py-2 text-sm font-medium border-b-2 transition -mb-px ${active ? 'border-indigo-500 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>
      {children}
    </button>
  )
}
