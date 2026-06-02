import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Compass, Terminal, Layers, LayoutGrid, Loader2 } from 'lucide-react'
import { api, type ArchitectureSummary, type QuickstartInfo, type ModuleMap, type RepoSummary } from '../services/api'
import CognitionGoalCard from '../components/common/CognitionGoalCard'

export default function Orient() {
  const [searchParams] = useSearchParams()
  const [repos, setRepos] = useState<string[]>([])
  const [repoId, setRepoId] = useState('')
  const [quickstart, setQuickstart] = useState<QuickstartInfo | null>(null)
  const [arch, setArch] = useState<ArchitectureSummary | null>(null)
  const [moduleMap, setModuleMap] = useState<ModuleMap | null>(null)
  const [loading, setLoading] = useState(false)

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
    Promise.all([
      api.getQuickstart(repoId).catch(() => null),
      api.getArchitecture(repoId).catch(() => null),
      api.getModules(repoId).catch(() => null),
    ]).then(([qs, ar, mm]) => {
      setQuickstart(qs?.quickstart || null)
      setArch(ar?.architecture || null)
      setModuleMap(mm?.module_map || null)
    }).finally(() => setLoading(false))
  }, [repoId])

  return (
    <div className="h-full overflow-auto">
      <div className="max-w-4xl mx-auto px-6 py-8">
        <header className="flex items-center gap-3 mb-4">
          <Compass className="w-6 h-6 text-indigo-500" />
          <div>
            <h1 className="text-xl font-bold text-gray-800">全貌 · 建立第一印象</h1>
            <p className="text-sm text-gray-500">这是什么、由什么组成、从哪里开始跑</p>
          </div>
          {repos.length > 1 && (
            <select value={repoId} onChange={(e) => setRepoId(e.target.value)}
              className="ml-auto border rounded-lg px-2 py-1.5 text-sm">
              {repos.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          )}
        </header>

        <CognitionGoalCard
          icon={<Compass className="w-5 h-5" />}
          station="🧭 全貌 · 建立第一印象"
          helps={[
            '这个项目解决什么问题、给谁用',
            '它由哪些核心模块组成、模块间是什么关系',
            '程序从哪里开始运行',
          ]}
          takeaway="用一句话向别人解释这个项目是什么,并画出它的模块组成草图。"
          accentColor="#6366f1"
        />

        {loading && <div className="flex items-center gap-2 text-gray-400"><Loader2 className="w-4 h-4 animate-spin" /> 加载中…</div>}

        {!loading && (
          <div className="space-y-6">
            {/* Architecture summary = one-line positioning */}
            {arch && (
              <section className="bg-white border rounded-xl p-5">
                <h2 className="text-sm font-semibold text-gray-700 mb-2">项目定位</h2>
                <p className="text-sm text-gray-700 leading-relaxed">{arch.summary}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {quickstart?.stack?.map((fw) => (
                    <span key={fw} className="text-xs px-2 py-0.5 bg-indigo-50 text-indigo-700 rounded border border-indigo-200">{fw}</span>
                  ))}
                </div>
                {arch.generated_by && (
                  <p className="text-[10px] text-gray-400 mt-2">架构风格: {arch.patterns?.[0]?.name || '分层架构'} · {arch.module_count} 模块 · {arch.layers.length} 层</p>
                )}
              </section>
            )}

            {/* Quickstart: how to run */}
            {quickstart?.available && (
              <section className="bg-white border rounded-xl p-5">
                <h2 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                  <Terminal className="w-4 h-4 text-gray-400" /> 快速上手
                </h2>
                <div className="space-y-2">
                  {quickstart.install && (
                    <CmdBlock label="安装" cmd={quickstart.install} />
                  )}
                  {quickstart.run && (
                    <CmdBlock label="启动" cmd={quickstart.run} />
                  )}
                  {quickstart.entrypoints && quickstart.entrypoints.length > 0 && (
                    <div className="text-xs text-gray-500">
                      入口文件: <span className="font-mono">{quickstart.entrypoints.join(', ')}</span>
                    </div>
                  )}
                </div>
              </section>
            )}

            {/* Module map (cards) */}
            {moduleMap && moduleMap.cards.length > 0 && (
              <section className="bg-white border rounded-xl p-5">
                <h2 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                  <LayoutGrid className="w-4 h-4 text-gray-400" /> 模块地图
                </h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {moduleMap.cards.map((c) => (
                    <div key={c.id} className="border rounded-lg p-3">
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-sm text-gray-800">{c.title}</span>
                        <span className="text-[10px] text-gray-400">{c.layer}</span>
                      </div>
                      <p className="text-xs text-gray-500 mt-1 line-clamp-2">{c.summary}</p>
                      <p className="text-[10px] text-gray-400 mt-1">{c.file_count} 文件 · {c.symbol_count} 符号</p>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Architecture layers */}
            {arch && arch.layers.length > 0 && (
              <section className="bg-white border rounded-xl p-5">
                <h2 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                  <Layers className="w-4 h-4 text-gray-400" /> 架构分层
                </h2>
                <div className="space-y-2">
                  {arch.layers.map((l, i) => (
                    <div key={i} className="flex items-start gap-3 py-2 border-b border-gray-100 last:border-0">
                      <span className="text-xs font-mono text-gray-400 w-5 shrink-0">L{i + 1}</span>
                      <div>
                        <p className="text-sm font-medium text-gray-700">{l.name}</p>
                        <p className="text-xs text-gray-400">{l.modules.slice(0, 5).join(', ')}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function CmdBlock({ label, cmd }: { label: string; cmd: string }) {
  return (
    <div className="flex items-center gap-3 bg-gray-900 text-gray-100 rounded-lg px-4 py-2.5">
      <span className="text-[10px] text-gray-400 uppercase w-8 shrink-0">{label}</span>
      <code className="text-sm font-mono flex-1">{cmd}</code>
    </div>
  )
}
