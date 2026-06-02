import { useEffect, useState } from 'react'
import { Layers, Boxes, Workflow, AlertCircle, Sparkles, Cpu } from 'lucide-react'
import { api, type ArchitectureSummary, type RepoSummary } from '../services/api'

// Color a layer card by its inferred architectural role (matched loosely on the
// layer name, which may be Chinese or English depending on LLM vs heuristic).
function layerAccent(name: string): string {
  const n = name.toLowerCase()
  if (/接口|interface|controller|api/.test(n)) return 'border-indigo-300 bg-indigo-50'
  if (/业务|service|use-case|application/.test(n)) return 'border-emerald-300 bg-emerald-50'
  if (/数据|data|repository|model|persistence/.test(n)) return 'border-amber-300 bg-amber-50'
  if (/基础设施|infrastructure|client|adapter/.test(n)) return 'border-cyan-300 bg-cyan-50'
  if (/后台|background|worker|task/.test(n)) return 'border-purple-300 bg-purple-50'
  if (/公共|shared|util|common/.test(n)) return 'border-gray-300 bg-gray-50'
  return 'border-slate-300 bg-slate-50'
}

function shortName(qname: string): string {
  const parts = qname.split('.')
  return parts.length <= 2 ? qname : parts.slice(-2).join('.')
}

export default function ArchitectureView() {
  const [repos, setRepos] = useState<string[]>([])
  const [repoId, setRepoId] = useState('')
  const [arch, setArch] = useState<ArchitectureSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [isSample, setIsSample] = useState(false)

  useEffect(() => {
    api
      .listRepos()
      .then((res) => {
        const ids = (res.repositories || []).map((r: RepoSummary) => r.repo_id)
        if (ids.length) {
          setRepos(ids)
          setRepoId(ids[0])
        } else {
          setArch(SAMPLE_ARCH)
          setIsSample(true)
        }
      })
      .catch(() => {
        setArch(SAMPLE_ARCH)
        setIsSample(true)
      })
  }, [])

  useEffect(() => {
    if (!repoId) return
    setLoading(true)
    api
      .getArchitecture(repoId)
      .then((res) => {
        if (res.architecture && res.architecture.layers.length) {
          setArch(res.architecture)
          setIsSample(false)
        } else {
          setArch(SAMPLE_ARCH)
          setIsSample(true)
        }
      })
      .catch(() => {
        setArch(SAMPLE_ARCH)
        setIsSample(true)
      })
      .finally(() => setLoading(false))
  }, [repoId])

  return (
    <div className="h-full flex flex-col">
      <header className="p-4 border-b bg-white flex items-center gap-4 flex-wrap">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Layers className="w-5 h-5 text-indigo-500" />
          架构分层概览
        </h2>
        {repos.length > 1 && (
          <select
            value={repoId}
            onChange={(e) => setRepoId(e.target.value)}
            className="border rounded-lg px-2 py-1.5 text-sm"
          >
            {repos.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        )}
        {arch && (
          <span className="flex items-center gap-1 text-xs text-gray-500">
            {arch.generated_by === 'llm' ? (
              <>
                <Sparkles className="w-3 h-3 text-amber-500" /> LLM 分析
              </>
            ) : (
              <>
                <Cpu className="w-3 h-3 text-gray-400" /> 启发式推断
              </>
            )}
            {arch.module_count != null && ` · ${arch.module_count} 模块`}
          </span>
        )}
        {isSample && (
          <span className="flex items-center gap-1 text-xs text-amber-700 bg-amber-50 border border-amber-200 px-2 py-1 rounded">
            <AlertCircle className="w-3 h-3" />
            示例数据
          </span>
        )}
      </header>

      <div className="flex-1 overflow-auto p-6 bg-gray-50">
        {loading && <p className="text-sm text-gray-400">分析中…</p>}
        {arch && <ArchitectureBody arch={arch} />}
      </div>
    </div>
  )
}

function ArchitectureBody({ arch }: { arch: ArchitectureSummary }) {
  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {arch.summary && (
        <div className="bg-white border rounded-xl p-4 shadow-sm">
          <p className="text-sm text-gray-700 leading-relaxed">{arch.summary}</p>
        </div>
      )}

      <section>
        <h3 className="text-sm font-semibold text-gray-600 mb-3 flex items-center gap-2">
          <Layers className="w-4 h-4" /> 分层 ({arch.layers.length})
        </h3>
        <div className="space-y-3">
          {arch.layers.map((layer, i) => (
            <div key={i} className={`border rounded-xl p-4 ${layerAccent(layer.name)}`}>
              <div className="flex items-center justify-between">
                <h4 className="font-medium text-sm">{layer.name}</h4>
                <span className="text-xs text-gray-500">{layer.modules.length} 模块</span>
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {layer.modules.map((m) => (
                  <span
                    key={m}
                    title={m}
                    className="text-xs font-mono bg-white/70 border border-white px-2 py-0.5 rounded"
                  >
                    {shortName(m)}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h3 className="text-sm font-semibold text-gray-600 mb-3 flex items-center gap-2">
          <Workflow className="w-4 h-4" /> 设计模式 ({arch.patterns.length})
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {arch.patterns.length === 0 && (
            <p className="text-xs text-gray-400">未识别到明显的设计模式。</p>
          )}
          {arch.patterns.map((p, i) => (
            <div key={i} className="bg-white border rounded-xl p-4 shadow-sm">
              <h4 className="font-medium text-sm">{p.name}</h4>
              <p className="text-xs text-gray-500 mt-1">{p.evidence}</p>
              {p.modules.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {p.modules.map((m) => (
                    <span key={m} className="text-xs font-mono text-gray-600">
                      {shortName(m)}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      <section>
        <h3 className="text-sm font-semibold text-gray-600 mb-3 flex items-center gap-2">
          <Boxes className="w-4 h-4" /> 关键模块边界 ({arch.boundaries.length})
        </h3>
        <div className="bg-white border rounded-xl overflow-hidden shadow-sm">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500 text-xs">
              <tr>
                <th className="text-left px-4 py-2">模块</th>
                <th className="text-left px-4 py-2">角色</th>
                <th className="text-right px-4 py-2">被依赖</th>
                <th className="text-right px-4 py-2">依赖出</th>
              </tr>
            </thead>
            <tbody>
              {arch.boundaries.map((b, i) => (
                <tr key={i} className="border-t">
                  <td className="px-4 py-2 font-mono text-xs" title={b.module}>
                    {shortName(b.module)}
                  </td>
                  <td className="px-4 py-2 text-xs text-gray-500">{b.role || b.reason || '-'}</td>
                  <td className="px-4 py-2 text-right text-xs">{b.fan_in ?? '-'}</td>
                  <td className="px-4 py-2 text-right text-xs">{b.fan_out ?? '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

// Sample: GitGraph's own layered shape, shown when the backend has no data.
const SAMPLE_ARCH: ArchitectureSummary = {
  generated_by: 'heuristic',
  module_count: 6,
  summary:
    '该仓库是一个代码演化分析引擎,按职责粗分为接口层(FastAPI 路由)、业务层(演化/分析管线)、数据层(图谱存储)三层,并辅以解析与 Agent 工具模块。',
  layers: [
    { name: '接口层 / Interface', description: 'API 路由', modules: ['api.v1.repositories', 'api.v1.graph'] },
    { name: '业务层 / Service', description: '管线与检测', modules: ['evolution.code_repo_pipeline', 'evolution.breaking_change_detector'] },
    { name: '数据层 / Data', description: '图谱与解析', modules: ['graph.neo4j_client', 'ingestion.code_parser'] },
  ],
  patterns: [
    { name: '分层架构 / Layered', evidence: '接口层 → 业务层 → 数据层 单向调用。', modules: [] },
    { name: '适配器 / Adapter', evidence: 'code_graph_adapter 把解析结果适配到统一的图谱模型。', modules: ['ingestion.code_graph_adapter'] },
  ],
  boundaries: [
    { module: 'graph.neo4j_client', role: 'data', fan_in: 12, fan_out: 0, files: [] },
    { module: 'evolution.code_repo_pipeline', role: 'service', fan_in: 1, fan_out: 8, files: [] },
  ],
}
