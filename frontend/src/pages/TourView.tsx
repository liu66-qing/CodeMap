import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Route, ArrowDown, CornerDownRight, AlertCircle, Sparkles, Cpu, Crosshair } from 'lucide-react'
import { api, type CodeTour, type TourStep, type RepoSummary } from '../services/api'

const KIND_COLORS: Record<string, string> = {
  module: '#6366f1',
  class: '#10b981',
  function: '#f59e0b',
  method: '#06b6d4',
}

function shortName(qname: string): string {
  const parts = qname.split('.')
  return parts.length <= 2 ? qname : parts.slice(-2).join('.')
}

export default function TourView() {
  const navigate = useNavigate()
  const [repos, setRepos] = useState<string[]>([])
  const [repoId, setRepoId] = useState('')
  const [tour, setTour] = useState<CodeTour | null>(null)
  const [entryInput, setEntryInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [isSample, setIsSample] = useState(false)
  const [activeStep, setActiveStep] = useState(0)

  useEffect(() => {
    api
      .listRepos()
      .then((res) => {
        const ids = (res.repositories || []).map((r: RepoSummary) => r.repo_id)
        if (ids.length) {
          setRepos(ids)
          setRepoId(ids[0])
        } else {
          setTour(SAMPLE_TOUR)
          setIsSample(true)
        }
      })
      .catch(() => {
        setTour(SAMPLE_TOUR)
        setIsSample(true)
      })
  }, [])

  function loadTour(entry?: string) {
    if (!repoId) return
    setLoading(true)
    api
      .getTour(repoId, entry)
      .then((res) => {
        if (res.tour && res.tour.steps.length) {
          setTour(res.tour)
          setIsSample(false)
          setActiveStep(0)
        } else {
          setTour(SAMPLE_TOUR)
          setIsSample(true)
        }
      })
      .catch(() => {
        setTour(SAMPLE_TOUR)
        setIsSample(true)
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (repoId) loadTour()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repoId])

  function jumpToGraph(symbol: string) {
    navigate(`/?focus=${encodeURIComponent(symbol)}`)
  }

  return (
    <div className="h-full flex flex-col">
      <header className="p-4 border-b bg-white flex items-center gap-4 flex-wrap">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Route className="w-5 h-5 text-indigo-500" />
          代码导览
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
        <div className="flex items-center gap-2">
          <input
            value={entryInput}
            onChange={(e) => setEntryInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && loadTour(entryInput || undefined)}
            placeholder="入口符号(如 main / create_app),留空自动检测"
            className="border rounded-lg px-3 py-1.5 text-sm w-72"
          />
          <button
            onClick={() => loadTour(entryInput || undefined)}
            className="text-sm bg-indigo-600 text-white px-3 py-1.5 rounded-lg hover:bg-indigo-700"
          >
            生成导览
          </button>
        </div>
        {tour && (
          <span className="flex items-center gap-1 text-xs text-gray-500">
            {tour.generated_by === 'llm' ? (
              <>
                <Sparkles className="w-3 h-3 text-amber-500" /> LLM 讲解
              </>
            ) : (
              <>
                <Cpu className="w-3 h-3 text-gray-400" /> 结构化讲解
              </>
            )}
          </span>
        )}
        {isSample && (
          <span className="flex items-center gap-1 text-xs text-amber-700 bg-amber-50 border border-amber-200 px-2 py-1 rounded">
            <AlertCircle className="w-3 h-3" />
            示例数据
          </span>
        )}
      </header>

      {tour?.entry_point && (
        <div className="px-6 py-3 bg-indigo-50 border-b text-sm">
          入口:<span className="font-mono font-medium">{tour.entry_point}</span>
          {tour.auto_detected && <span className="ml-2 text-xs text-gray-500">(自动检测)</span>}
        </div>
      )}

      <div className="flex-1 overflow-auto p-6 bg-gray-50">
        {loading && <p className="text-sm text-gray-400">生成中…</p>}
        {tour && (
          <div className="max-w-3xl mx-auto">
            {tour.steps.map((step, i) => (
              <TourStepCard
                key={i}
                step={step}
                active={i === activeStep}
                isLast={i === tour.steps.length - 1}
                onSelect={() => setActiveStep(i)}
                onJump={() => jumpToGraph(step.symbol)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function TourStepCard({
  step,
  active,
  isLast,
  onSelect,
  onJump,
}: {
  step: TourStep
  active: boolean
  isLast: boolean
  onSelect: () => void
  onJump: () => void
}) {
  return (
    <div className="relative">
      <div
        onClick={onSelect}
        className={`bg-white border rounded-xl p-4 shadow-sm cursor-pointer transition-all ${
          active ? 'border-indigo-400 ring-2 ring-indigo-100' : 'hover:border-gray-300'
        }`}
        style={{ marginLeft: `${Math.min(step.depth, 4) * 20}px` }}
      >
        <div className="flex items-center gap-2">
          <span
            className="w-6 h-6 rounded-full text-white text-xs flex items-center justify-center font-medium"
            style={{ backgroundColor: KIND_COLORS[step.kind] || '#6b7280' }}
          >
            {step.order}
          </span>
          <span className="font-mono text-sm font-medium break-all" title={step.symbol}>
            {shortName(step.symbol)}
          </span>
          <button
            onClick={(e) => {
              e.stopPropagation()
              onJump()
            }}
            title="在图谱中定位"
            className="ml-auto text-gray-400 hover:text-indigo-600"
          >
            <Crosshair className="w-4 h-4" />
          </button>
        </div>
        {step.signature && (
          <pre className="mt-2 text-xs bg-gray-50 border rounded p-2 font-mono whitespace-pre-wrap break-all">
            {step.signature}
          </pre>
        )}
        <p className="mt-2 text-sm text-gray-700 leading-relaxed">{step.explanation}</p>
        {step.calls.length > 0 && (
          <div className="mt-2 flex flex-wrap items-center gap-1 text-xs text-gray-400">
            <CornerDownRight className="w-3 h-3" />
            {step.calls.map((c) => (
              <span key={c} className="font-mono">
                {shortName(c)}
              </span>
            ))}
          </div>
        )}
        {step.file_path && (
          <p className="mt-1 text-xs text-gray-300 break-all">{step.file_path}</p>
        )}
      </div>
      {!isLast && (
        <div className="flex justify-center py-1" style={{ marginLeft: `${Math.min(step.depth, 4) * 20}px` }}>
          <ArrowDown className="w-4 h-4 text-gray-300" />
        </div>
      )}
    </div>
  )
}

// Sample tour: a request flowing through GitGraph's own pipeline.
const SAMPLE_TOUR: CodeTour = {
  entry_point: 'evolution.CodeRepoPipeline.process_repository',
  auto_detected: true,
  generated_by: 'structural',
  steps: [
    {
      order: 1,
      symbol: 'evolution.CodeRepoPipeline.process_repository',
      kind: 'method',
      signature: 'process_repository(repo_id, repo_path, max_commits=None)',
      file_path: 'src/evograph/evolution/code_repo_pipeline.py',
      depth: 0,
      calls: ['git_loader.iter_history', 'detector.scan_history'],
      explanation: '编排入口:遍历 git 历史、构建图谱、检测破坏性变更、运行理解 Agent。',
    },
    {
      order: 2,
      symbol: 'ingestion.git_loader.iter_history',
      kind: 'function',
      signature: 'iter_history(repo_path, max_commits=None)',
      file_path: 'src/evograph/ingestion/git_loader.py',
      depth: 1,
      calls: ['git_loader.load_commit_snapshot'],
      explanation: '按时间顺序逐个产出提交快照,供后续逐版本对比。',
    },
    {
      order: 3,
      symbol: 'evolution.breaking_change_detector.scan_history',
      kind: 'function',
      signature: 'scan_history(snapshots)',
      file_path: 'src/evograph/evolution/breaking_change_detector.py',
      depth: 1,
      calls: ['detector.diff_snapshots'],
      explanation: '对相邻快照做签名 diff,定位每个破坏性变更的引入提交。',
    },
  ],
}
