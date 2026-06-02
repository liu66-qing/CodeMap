import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Eye, Loader2, ArrowRight } from 'lucide-react'
import { api, type RepoSummary } from '../services/api'
import CognitionGoalCard from '../components/common/CognitionGoalCard'

interface Capability { name: string; description: string }
interface FlowStage { name: string; description: string; modules: string[] }
interface Abstraction { name: string; purpose: string; relationships: string[] }
interface PanoramaData {
  capabilities: Capability[]
  data_flow: FlowStage[]
  collaboration: string
  abstractions: Abstraction[]
}

export default function Panorama() {
  const [searchParams] = useSearchParams()
  const [repos, setRepos] = useState<string[]>([])
  const [repoId, setRepoId] = useState('')
  const [data, setData] = useState<PanoramaData | null>(null)
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
    fetch('/api/v1/repositories/' + encodeURIComponent(repoId) + '/panorama')
      .then((res) => { if (!res.ok) throw new Error('failed'); return res.json() })
      .then((d) => setData(d))
      .catch(() => setError('加载失败'))
      .finally(() => setLoading(false))
  }, [repoId])

  return (
    <div className="h-full overflow-auto">
      <div className="max-w-5xl mx-auto px-6 py-8">
        <header className="flex items-center gap-3 mb-4">
          <Eye className="w-6 h-6 text-indigo-500" />
          <div>
            <h1 className="text-xl font-bold text-gray-800">全景 · 运转逻辑</h1>
            <p className="text-sm text-gray-500">功能清单、数据流、协作关系、关键抽象</p>
          </div>
          {repos.length > 1 && (
            <select value={repoId} onChange={(e) => setRepoId(e.target.value)}
              className="ml-auto border rounded-lg px-2 py-1.5 text-sm">
              {repos.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          )}
        </header>

        <CognitionGoalCard
          icon={<Eye className="w-5 h-5" />}
          station="🗺️ 全景 · 理解运转逻辑"
          helps={[
            '这个项目对外提供了哪些能力',
            '一个典型请求从进入到返回经历了什么',
            '系统的核心数据模型长什么样',
            '模块之间怎么通信、状态怎么维持',
          ]}
          takeaway={'闭上眼在脑子里模拟一遍"一个请求进来后发生了什么",并说出几个核心概念及其关系。'}
          accentColor="#10b981"
        />

        {loading && <div className="flex items-center gap-2 text-gray-400"><Loader2 className="w-4 h-4 animate-spin" /> 加载中…</div>}
        {error && <p className="text-red-500 text-sm">{error}</p>}

        {!loading && !error && data && (
          <div className="space-y-6">
            {/* 功能清单 */}
            {data.capabilities?.length > 0 && (
              <section className="bg-white border rounded-xl p-5">
                <h2 className="text-sm font-semibold text-gray-700 mb-3">功能清单</h2>
                <ul className="space-y-2">
                  {data.capabilities.map((c, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="mt-1 w-1.5 h-1.5 rounded-full bg-indigo-400 shrink-0" />
                      <div>
                        <span className="text-sm font-medium text-gray-800">{c.name}</span>
                        <span className="text-sm text-gray-500 ml-2">{c.description}</span>
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {/* 数据流旅程 */}
            {data.data_flow?.length > 0 && (
              <section className="bg-white border rounded-xl p-5">
                <h2 className="text-sm font-semibold text-gray-700 mb-3">数据流旅程</h2>
                <div className="flex items-start gap-2 overflow-x-auto pb-2">
                  {data.data_flow.map((stage, i) => (
                    <div key={i} className="flex items-center gap-2 shrink-0">
                      <div className="border rounded-lg p-3 w-48">
                        <p className="text-sm font-medium text-gray-800">{stage.name}</p>
                        <p className="text-xs text-gray-500 mt-1">{stage.description}</p>
                        {stage.modules?.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-2">
                            {stage.modules.map((m) => (
                              <span key={m} className="text-[10px] px-1.5 py-0.5 bg-indigo-50 text-indigo-600 rounded">{m}</span>
                            ))}
                          </div>
                        )}
                      </div>
                      {i < data.data_flow.length - 1 && <ArrowRight className="w-4 h-4 text-gray-300 shrink-0" />}
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* 协作关系 */}
            {data.collaboration && (
              <section className="bg-white border rounded-xl p-5">
                <h2 className="text-sm font-semibold text-gray-700 mb-2">协作关系</h2>
                <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">{data.collaboration}</p>
              </section>
            )}

            {/* 关键抽象 */}
            {data.abstractions?.length > 0 && (
              <section className="bg-white border rounded-xl p-5">
                <h2 className="text-sm font-semibold text-gray-700 mb-3">关键抽象</h2>
                <div className="space-y-3">
                  {data.abstractions.map((a, i) => (
                    <div key={i} className="border rounded-lg p-3">
                      <p className="text-sm font-medium text-gray-800">{a.name}</p>
                      <p className="text-xs text-gray-500 mt-1">{a.purpose}</p>
                      {a.relationships?.length > 0 && (
                        <p className="text-[10px] text-gray-400 mt-1">关联: {a.relationships.join(', ')}</p>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>
        )}

        {!loading && !error && !data && repoId && (
          <p className="text-sm text-gray-400">暂无全景数据</p>
        )}
      </div>
    </div>
  )
}
