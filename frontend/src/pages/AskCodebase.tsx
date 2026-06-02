import { useEffect, useState } from 'react'
import { MessageSquareCode, Send, Loader2, Code2, AlertCircle } from 'lucide-react'
import { api, type AskCodebaseResponse, type AskSource, type RepoSummary } from '../services/api'
import SourceViewer from '../components/common/SourceViewer'

export default function AskCodebase() {
  const [repos, setRepos] = useState<string[]>([])
  const [repoId, setRepoId] = useState('')
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<AskCodebaseResponse | null>(null)
  const [history, setHistory] = useState<{ q: string; a: AskCodebaseResponse }[]>([])

  useEffect(() => {
    api
      .listRepos()
      .then((res) => {
        const ids = (res.repositories || []).map((r: RepoSummary) => r.repo_id)
        if (ids.length) {
          setRepos(ids)
          setRepoId(ids[0])
        }
      })
      .catch(() => {})
  }, [])

  async function ask() {
    if (!question.trim() || !repoId) return
    setLoading(true)
    setResult(null)
    try {
      const res = await api.askCodebase(repoId, question.trim())
      setResult(res)
      setHistory((h) => [{ q: question.trim(), a: res }, ...h].slice(0, 10))
    } catch (e) {
      setResult({
        repo_id: repoId,
        question: question.trim(),
        answer: e instanceof Error ? e.message : '请求失败',
        sources: [],
        generated_by: 'error',
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="h-full flex flex-col">
      <header className="p-4 border-b bg-white">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <MessageSquareCode className="w-5 h-5 text-indigo-500" />
          问代码库
        </h2>
        <p className="text-sm text-gray-500">
          用自然语言提问,系统检索相关源码并综合回答,附带可追溯的代码来源。
        </p>
      </header>

      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-3xl mx-auto space-y-5">
          {/* Input */}
          <div className="bg-white border rounded-xl p-4 shadow-sm">
            <div className="flex items-center gap-3 mb-3">
              {repos.length > 0 && (
                <select
                  value={repoId}
                  onChange={(e) => setRepoId(e.target.value)}
                  className="border rounded-lg px-2 py-1.5 text-sm"
                >
                  {repos.map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
              )}
            </div>
            <div className="flex gap-2">
              <input
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !loading && ask()}
                placeholder="例如:agent 之间怎么协作? / 上下文怎么传递? / 记忆存在哪?"
                disabled={loading}
                className="flex-1 px-4 py-2.5 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-gray-50"
              />
              <button
                onClick={ask}
                disabled={loading || !question.trim()}
                className="px-4 py-2.5 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-1.5"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                提问
              </button>
            </div>
          </div>

          {/* Result */}
          {result && (
            <div className="bg-white border rounded-xl p-5 shadow-sm space-y-4">
              <div>
                <p className="text-xs text-gray-400 mb-1">
                  {result.generated_by === 'llm' ? '基于源码的 LLM 回答' : '检索结果'}
                </p>
                <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
                  {result.answer}
                </p>
              </div>

              {result.sources.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-500 mb-2 flex items-center gap-1">
                    <Code2 className="w-3.5 h-3.5" />
                    代码来源 ({result.sources.length})
                  </p>
                  <div className="space-y-2">
                    {result.sources.map((s, i) => (
                      <SourceCard key={i} source={s} repoId={repoId} />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Suggestions */}
          {!result && !loading && (
            <div className="text-center py-8">
              <MessageSquareCode className="w-10 h-10 mx-auto text-gray-300 mb-3" />
              <p className="text-sm text-gray-400 mb-4">试试这些问题:</p>
              <div className="flex flex-wrap justify-center gap-2">
                {['agent 之间怎么协作', '数据模型长什么样', '入口在哪里', '错误怎么处理'].map((q) => (
                  <button
                    key={q}
                    onClick={() => { setQuestion(q); }}
                    className="text-xs px-3 py-1.5 border rounded-full text-gray-600 hover:bg-indigo-50 hover:border-indigo-200"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* History */}
          {history.length > 1 && (
            <div className="border-t pt-4">
              <p className="text-xs text-gray-400 mb-2">历史提问</p>
              {history.slice(1).map((h, i) => (
                <button
                  key={i}
                  onClick={() => { setQuestion(h.q); setResult(h.a); }}
                  className="block w-full text-left text-xs text-gray-600 hover:text-indigo-600 py-1 truncate"
                >
                  {h.q}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function SourceCard({ source, repoId }: { source: AskSource; repoId: string }) {
  const simple = source.symbol.split('.').pop()
  return (
    <div className="border rounded-lg p-3 bg-gray-50">
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs text-gray-700">{simple}</span>
        {source.file_path && (
          <span className="text-[10px] text-gray-400">
            {source.file_path.split('/').pop()}:{source.line_start}
          </span>
        )}
      </div>
      {source.relevance && (
        <p className="text-[11px] text-gray-500 mt-1">{source.relevance}</p>
      )}
      {source.symbol && repoId && (
        <SourceViewer repoId={repoId} symbol={source.symbol} />
      )}
    </div>
  )
}
