import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import * as d3 from 'd3'
import { Search, GitBranch, AlertCircle, Layers, Share2, Sparkles, Cpu, LayoutGrid } from 'lucide-react'
import {
  api,
  type CodeGraphNode,
  type SymbolDetail,
  type ArchitectureSummary,
  type Persona,
  type SymbolExplanation,
  type ModuleMap,
} from '../services/api'
import ModuleCardCanvas from './ModuleCardCanvas'

type ViewMode = 'cards' | 'layered' | 'force'

// Persona options for the role-adaptive summary (matches backend keys).
const PERSONAS: { key: Persona; label: string }[] = [
  { key: 'junior', label: '初级开发' },
  { key: 'pm', label: '产品经理' },
  { key: 'senior', label: '高级开发' },
]

// A code symbol in the graph. `layer` is assigned from the architecture summary.
interface GraphNode {
  id: string
  name: string
  kind: string // module | class | function | method
  signature?: string
  file_path?: string
  layer?: string // canonical layer key (see LAYER_DEFS)
  fanIn?: number // incoming CALLS — drives node size (importance)
  x?: number
  y?: number
  fx?: number | null
  fy?: number | null
}

interface GraphLink {
  source: string | GraphNode
  target: string | GraphNode
  type: string // CALLS | IMPORTS | INHERITS | DEFINES
}

// Canonical layers, ordered top→bottom to mirror call-flow (interface drives
// service drives data…). Each has a label and a distinct band color.
const LAYER_DEFS: { key: string; label: string; color: string; band: string }[] = [
  { key: 'interface', label: '接口层 Interface', color: '#6366f1', band: '#eef2ff' },
  { key: 'service', label: '业务层 Service', color: '#10b981', band: '#ecfdf5' },
  { key: 'data', label: '数据层 Data', color: '#f59e0b', band: '#fffbeb' },
  { key: 'infrastructure', label: '基础设施 Infra', color: '#06b6d4', band: '#ecfeff' },
  { key: 'background', label: '后台 Background', color: '#a855f7', band: '#faf5ff' },
  { key: 'shared', label: '公共 Shared', color: '#64748b', band: '#f8fafc' },
  { key: 'other', label: '其他 Other', color: '#94a3b8', band: '#f1f5f9' },
]
const LAYER_BY_KEY = Object.fromEntries(LAYER_DEFS.map((l) => [l.key, l]))

// Map a free-text layer name (LLM may emit Chinese or English) to a canonical key.
function canonicalLayer(name: string): string {
  const n = name.toLowerCase()
  if (/接口|interface|controller|api|route|handler|endpoint|web|http/.test(n)) return 'interface'
  if (/业务|service|use-?case|application|orchestrat|agent|manager|logic/.test(n)) return 'service'
  if (/数据|data|repository|repo|model|schema|persistence|entity|dao|store/.test(n)) return 'data'
  if (/基础设施|infra|client|adapter|gateway|connector|provider|integration/.test(n)) return 'infrastructure'
  if (/后台|background|worker|task|job|queue|celery|schedul/.test(n)) return 'background'
  if (/公共|shared|util|common|core|lib|helper|config/.test(n)) return 'shared'
  return 'other'
}

const KIND_COLORS: Record<string, string> = {
  module: '#6366f1',
  class: '#10b981',
  function: '#f59e0b',
  method: '#06b6d4',
}

const EDGE_COLORS: Record<string, string> = {
  CALLS: '#f59e0b',
  IMPORTS: '#6366f1',
  INHERITS: '#10b981',
  DEFINES: '#cbd5e1',
}

const KIND_LABELS: Record<string, string> = {
  module: '模块 module',
  class: '类 class',
  function: '函数 function',
  method: '方法 method',
}

// Short name for display: keep the last 2 dotted segments (Class.method / module.fn).
function shortName(qname: string): string {
  const parts = qname.split('.')
  return parts.length <= 2 ? qname : parts.slice(-2).join('.')
}

function toNode(n: CodeGraphNode): GraphNode {
  return {
    id: n.id || n.name,
    name: n.name,
    kind: n.kind || 'function',
    signature: n.signature || undefined,
    file_path: n.file_path || undefined,
  }
}

export default function GraphExplorer() {
  const svgRef = useRef<SVGSVGElement>(null)
  const [searchParams, setSearchParams] = useSearchParams()
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [nodes, setNodes] = useState<GraphNode[]>([])
  const [links, setLinks] = useState<GraphLink[]>([])
  const [repoId, setRepoId] = useState<string>('')
  const [repos, setRepos] = useState<string[]>([])
  const [isSample, setIsSample] = useState(false)
  const [viewMode, setViewMode] = useState<ViewMode>('cards') // cards | layered | force
  const [moduleLayer, setModuleLayer] = useState<Map<string, string>>(new Map())
  const [persona, setPersona] = useState<Persona>('junior')
  const [moduleMap, setModuleMap] = useState<ModuleMap | null>(null)
  const layered = viewMode === 'layered' // symbol-graph layout flag

  // Load the list of analyzed repos; honor ?repo=<id> if present, else first, else sample.
  useEffect(() => {
    let cancelled = false
    api
      .listRepos()
      .then((res) => {
        if (cancelled) return
        const ids = (res.repositories || []).map((r) => r.repo_id)
        if (ids.length > 0) {
          setRepos(ids)
          const wanted = searchParams.get('repo')
          setRepoId(wanted && ids.includes(wanted) ? wanted : ids[0])
        } else {
          loadSample()
        }
      })
      .catch(() => loadSample())
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Fetch graph + architecture together, then tag each node with a layer.
  useEffect(() => {
    if (!repoId) return
    let cancelled = false
    Promise.all([api.getRepoGraph(repoId), api.getArchitecture(repoId).catch(() => null)])
      .then(([graph, archRes]) => {
        if (cancelled) return
        if (!graph.nodes || graph.nodes.length === 0) {
          loadSample()
          return
        }
        const arch = archRes?.architecture || null
        const modLayer = buildModuleLayerMap(arch)
        setModuleLayer(modLayer)
        setIsSample(false)
        const rawNodes = graph.nodes.map(toNode)
        const rawLinks = (graph.edges || []).map((e) => ({
          source: e.source,
          target: e.target,
          type: e.type,
        }))
        assignLayersAndFanIn(rawNodes, rawLinks, modLayer)
        setNodes(rawNodes)
        setLinks(rawLinks)
      })
      .catch(() => loadSample())
    return () => {
      cancelled = true
    }
  }, [repoId])

  // Fetch the module-card map (powers the default card view).
  useEffect(() => {
    if (!repoId) {
      setModuleMap(SAMPLE_MODULE_MAP)
      return
    }
    let cancelled = false
    api
      .getModules(repoId)
      .then((res) => {
        if (cancelled) return
        setModuleMap(res.module_map && res.module_map.cards.length ? res.module_map : SAMPLE_MODULE_MAP)
      })
      .catch(() => !cancelled && setModuleMap(SAMPLE_MODULE_MAP))
    return () => {
      cancelled = true
    }
  }, [repoId])

  function loadSample() {
    setIsSample(true)
    const modLayer = buildModuleLayerMap(SAMPLE_ARCH)
    setModuleLayer(modLayer)
    const n = SAMPLE_NODES.map((x) => ({ ...x }))
    const l = SAMPLE_LINKS.map((x) => ({ ...x }))
    assignLayersAndFanIn(n, l, modLayer)
    setNodes(n)
    setLinks(l)
  }

  // Filter by symbol name; empty query shows everything.
  const visibleNodes = searchQuery
    ? nodes.filter((n) => n.name.toLowerCase().includes(searchQuery.toLowerCase()))
    : nodes
  const visibleIds = new Set(visibleNodes.map((n) => n.id))
  const nameToId = new Map(nodes.map((n) => [n.name, n.id]))
  const visibleLinks = links.filter((l) => {
    const s = typeof l.source === 'string' ? l.source : l.source.id
    const t = typeof l.target === 'string' ? l.target : l.target.id
    const sid = visibleIds.has(s) ? s : nameToId.get(s)
    const tid = visibleIds.has(t) ? t : nameToId.get(t)
    return sid && tid && visibleIds.has(sid) && visibleIds.has(tid)
  })

  // Which layers are actually present (drives the band rendering + legend).
  const presentLayers = LAYER_DEFS.filter((ld) => visibleNodes.some((n) => n.layer === ld.key))

  useEffect(() => {
    if (viewMode === 'cards') return // card canvas renders itself; no svg graph
    if (!svgRef.current) return
    renderGraph(svgRef.current, visibleNodes, visibleLinks, setSelectedNode, layered, presentLayers)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, links, searchQuery, viewMode])

  // Select a symbol by qualified name (used by the card canvas drill-down and the
  // /?focus= deep-link). Resolves against the loaded node list and switches to the
  // symbol graph so the rich detail panel (with persona summary) is visible.
  function selectSymbolByName(name: string) {
    const match =
      nodes.find((n) => n.name === name) ||
      nodes.find((n) => n.name.endsWith('.' + name)) ||
      nodes.find((n) => n.name.toLowerCase().includes(name.toLowerCase()))
    if (match) {
      setSelectedNode(match)
      setViewMode('layered')
      setSearchQuery('')
    }
  }

  // Deep-link: /?focus=<symbol> (from the code tour) selects + filters to a node.
  useEffect(() => {
    const focus = searchParams.get('focus')
    if (!focus || nodes.length === 0) return
    const match =
      nodes.find((n) => n.name === focus) ||
      nodes.find((n) => n.name.endsWith('.' + focus)) ||
      nodes.find((n) => n.name.toLowerCase().includes(focus.toLowerCase()))
    if (match) {
      setSelectedNode(match)
      setViewMode('layered') // focus targets a symbol → show the symbol graph
      setSearchQuery(shortName(match.name).split('.').pop() || '')
    }
    searchParams.delete('focus')
    setSearchParams(searchParams, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes])

  return (
    <div className="h-full flex flex-col">
      <header className="p-4 border-b bg-white flex items-center gap-4 flex-wrap">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <GitBranch className="w-5 h-5 text-indigo-500" />
          代码图谱浏览器
        </h2>
        {repos.length > 1 && (
          <select
            value={repoId}
            onChange={(e) => setRepoId(e.target.value)}
            className="border rounded-lg px-2 py-1.5 text-sm max-w-xs"
          >
            {repos.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        )}
        <div className="flex-1 max-w-md relative">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="按符号名搜索(函数/类/方法)…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
        </div>
        {/* View toggle: card map (default) / layered symbol graph / free force. */}
        <div className="flex rounded-lg border overflow-hidden text-sm">
          <button
            onClick={() => setViewMode('cards')}
            className={`flex items-center gap-1 px-3 py-1.5 ${viewMode === 'cards' ? 'bg-indigo-600 text-white' : 'bg-white text-gray-600'}`}
          >
            <LayoutGrid className="w-4 h-4" /> 卡片地图
          </button>
          <button
            onClick={() => setViewMode('layered')}
            className={`flex items-center gap-1 px-3 py-1.5 border-l ${viewMode === 'layered' ? 'bg-indigo-600 text-white' : 'bg-white text-gray-600'}`}
          >
            <Layers className="w-4 h-4" /> 分层符号
          </button>
          <button
            onClick={() => setViewMode('force')}
            className={`flex items-center gap-1 px-3 py-1.5 border-l ${viewMode === 'force' ? 'bg-indigo-600 text-white' : 'bg-white text-gray-600'}`}
          >
            <Share2 className="w-4 h-4" /> 力导向
          </button>
        </div>
        {/* Persona selector: tunes the LLM node summary's depth & wording. */}
        <select
          value={persona}
          onChange={(e) => setPersona(e.target.value as Persona)}
          title="讲解视角"
          className="border rounded-lg px-2 py-1.5 text-sm"
        >
          {PERSONAS.map((p) => (
            <option key={p.key} value={p.key}>
              视角:{p.label}
            </option>
          ))}
        </select>
        {isSample && <SampleBadge />}
      </header>

      {viewMode === 'cards' ? (
        moduleMap ? (
          <ModuleCardCanvas
            map={moduleMap}
            repoId={repoId}
            selectedSymbol={selectedNode?.name ?? null}
            onSelectSymbol={selectSymbolByName}
          />
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">加载模块地图中…</div>
        )
      ) : (
        <div className="flex-1 flex min-h-0">
          <div className="flex-1 relative bg-gray-50">
            <svg ref={svgRef} className="w-full h-full" />
            <GraphLegend layered={layered} presentLayers={presentLayers} />
          </div>

          {selectedNode && (
            <NodeDetail
              node={selectedNode}
              links={links}
              nameToId={nameToId}
              nodes={nodes}
              repoId={isSample ? '' : repoId}
              moduleLayer={moduleLayer}
              persona={persona}
            />
          )}
        </div>
      )}
    </div>
  )
}

// === Layer assignment ===================================================

// Build module-qualified-name -> layer-key from the architecture summary.
function buildModuleLayerMap(arch: ArchitectureSummary | null): Map<string, string> {
  const m = new Map<string, string>()
  if (!arch) return m
  for (const layer of arch.layers || []) {
    const key = canonicalLayer(layer.name)
    for (const mod of layer.modules || []) m.set(mod, key)
  }
  return m
}

// Tag each node with a layer (via its enclosing module) and compute fan-in.
function assignLayersAndFanIn(
  nodes: GraphNode[],
  links: GraphLink[],
  moduleLayer: Map<string, string>
) {
  // Longest module-name prefix wins, so a.b.c.fn inherits a.b.c's layer.
  const modules = [...moduleLayer.keys()].sort((a, b) => b.length - a.length)
  for (const n of nodes) {
    let layer = moduleLayer.get(n.name)
    if (!layer) {
      const owner = modules.find((mod) => n.name === mod || n.name.startsWith(mod + '.'))
      layer = owner ? moduleLayer.get(owner) : undefined
    }
    n.layer = layer || canonicalLayer(n.name)
  }
  const fanIn = new Map<string, number>()
  for (const l of links) {
    if (l.type !== 'CALLS') continue
    const t = typeof l.target === 'string' ? l.target : l.target.id
    fanIn.set(t, (fanIn.get(t) || 0) + 1)
  }
  for (const n of nodes) n.fanIn = fanIn.get(n.name) || 0
}

function SampleBadge() {
  return (
    <span className="flex items-center gap-1 text-xs text-amber-700 bg-amber-50 border border-amber-200 px-2 py-1 rounded">
      <AlertCircle className="w-3 h-3" />
      示例数据(后端未连接,展示工具分析自身的结构)
    </span>
  )
}

function GraphLegend({
  layered,
  presentLayers,
}: {
  layered: boolean
  presentLayers: { key: string; label: string; color: string }[]
}) {
  return (
    <div className="absolute bottom-4 left-4 bg-white/95 rounded-lg shadow p-3 text-xs max-w-[220px]">
      {layered ? (
        <>
          <p className="font-medium mb-2">架构分层(从上到下:调用流向)</p>
          {presentLayers.map((l) => (
            <div key={l.key} className="flex items-center gap-2 mb-1">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: l.color }} />
              <span>{l.label}</span>
            </div>
          ))}
          <p className="text-gray-400 mt-2">圆点越大 = 被调用越多(越核心)</p>
        </>
      ) : (
        <>
          <p className="font-medium mb-2">符号类型</p>
          {Object.entries(KIND_COLORS).map(([kind, color]) => (
            <div key={kind} className="flex items-center gap-2 mb-1">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
              <span>{KIND_LABELS[kind] || kind}</span>
            </div>
          ))}
        </>
      )}
      <p className="font-medium mt-3 mb-2">关系</p>
      {Object.entries(EDGE_COLORS).map(([type, color]) => (
        <div key={type} className="flex items-center gap-2 mb-1">
          <div className="w-4 h-0.5" style={{ backgroundColor: color }} />
          <span>{type}</span>
        </div>
      ))}
    </div>
  )
}

// === Node detail panel ==================================================

function NodeDetail({
  node,
  links,
  nameToId,
  nodes,
  repoId,
  moduleLayer,
  persona,
}: {
  node: GraphNode
  links: GraphLink[]
  nameToId: Map<string, string>
  nodes: GraphNode[]
  repoId: string
  moduleLayer: Map<string, string>
  persona: Persona
}) {
  const [detail, setDetail] = useState<SymbolDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [explanation, setExplanation] = useState<SymbolExplanation | null>(null)
  const [loadingExplain, setLoadingExplain] = useState(false)

  useEffect(() => {
    setDetail(null)
    if (!repoId) return
    let cancelled = false
    setLoadingDetail(true)
    api
      .getSymbolDetail(repoId, node.name)
      .then((d) => {
        if (!cancelled && d.node) setDetail(d)
      })
      .catch(() => {})
      .finally(() => !cancelled && setLoadingDetail(false))
    return () => {
      cancelled = true
    }
  }, [repoId, node.name])

  // Fetch the persona-tuned summary; re-fetch when the node OR persona changes.
  useEffect(() => {
    setExplanation(null)
    if (!repoId) return
    let cancelled = false
    setLoadingExplain(true)
    api
      .explainSymbol(repoId, node.name, persona)
      .then((res) => {
        if (!cancelled && res.explanation) setExplanation(res.explanation)
      })
      .catch(() => {})
      .finally(() => !cancelled && setLoadingExplain(false))
    return () => {
      cancelled = true
    }
  }, [repoId, node.name, persona])

  const idToName = new Map(nodes.map((n) => [n.id, n.name]))
  const resolve = (ref: string | GraphNode) => (typeof ref === 'string' ? ref : ref.id)
  const outgoing = links.filter((l) => {
    const s = resolve(l.source)
    return s === node.name || nameToId.get(s) === node.id || s === node.id
  })
  const incoming = links.filter((l) => {
    const t = resolve(l.target)
    return t === node.name || nameToId.get(t) === node.id || t === node.id
  })
  const label = (ref: string | GraphNode) => shortName(idToName.get(resolve(ref)) || resolve(ref))

  const layerDef = node.layer ? LAYER_BY_KEY[node.layer] : undefined

  return (
    <aside className="w-80 border-l bg-white p-4 overflow-auto">
      <h3 className="font-semibold text-sm break-all">{node.name}</h3>
      <div className="flex items-center gap-1.5 mt-1 flex-wrap">
        <span
          className="inline-block px-2 py-0.5 rounded text-xs text-white"
          style={{ backgroundColor: KIND_COLORS[node.kind] || '#6b7280' }}
        >
          {KIND_LABELS[node.kind] || node.kind}
        </span>
        {layerDef && (
          <span
            className="inline-block px-2 py-0.5 rounded text-xs text-white"
            style={{ backgroundColor: layerDef.color }}
          >
            {layerDef.label}
          </span>
        )}
        {(node.fanIn ?? 0) > 0 && (
          <span className="inline-block px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-600">
            被调用 {node.fanIn}
          </span>
        )}
      </div>
      {node.signature && (
        <pre className="mt-3 text-xs bg-gray-50 border rounded p-2 whitespace-pre-wrap break-all font-mono">
          {node.signature}
        </pre>
      )}

      {/* Persona-tuned plain-language summary. */}
      {repoId && (
        <div className="mt-3 rounded-lg border border-indigo-100 bg-indigo-50/60 p-3">
          <div className="flex items-center gap-1.5 text-xs font-medium text-indigo-700 mb-1">
            {explanation?.generated_by === 'llm' ? (
              <Sparkles className="w-3.5 h-3.5" />
            ) : (
              <Cpu className="w-3.5 h-3.5" />
            )}
            通俗讲解 · {PERSONAS.find((p) => p.key === persona)?.label}
          </div>
          {loadingExplain && <p className="text-xs text-gray-400">生成中…</p>}
          {!loadingExplain && explanation && (
            <p className="text-sm text-gray-700 leading-relaxed">{explanation.summary}</p>
          )}
          {!loadingExplain && !explanation && (
            <p className="text-xs text-gray-400">暂无讲解</p>
          )}
        </div>
      )}
      {(detail?.module || node.file_path) && (
        <p className="mt-2 text-xs text-gray-400 break-all">
          {detail?.module && <span className="text-gray-500">所属模块: {detail.module}</span>}
          {detail?.module && node.file_path && <br />}
          {node.file_path}
        </p>
      )}

      {repoId && detail ? (
        <>
          <DetailList
            title={`调用方 / 被依赖 (${detail.callers.length})`}
            items={detail.callers.map((c) => shortName(c.caller))}
          />
          <DetailList
            title={`依赖 / 调用出 (${detail.callees.length})`}
            items={detail.callees.map((c) => shortName(c.callee))}
          />
          {detail.history.length > 0 && (
            <div className="mt-4 text-sm">
              <p className="font-medium text-gray-800 mb-2">演化历史 ({detail.history.length})</p>
              {detail.history.map((h, i) => (
                <div key={i} className="py-2 border-b border-gray-100 text-xs">
                  <span className="font-mono text-amber-600">{h.commit}</span> · {h.subject}
                  <p className="text-gray-500 mt-0.5 break-all">{h.change}</p>
                </div>
              ))}
            </div>
          )}
        </>
      ) : (
        <>
          {loadingDetail && <p className="mt-3 text-xs text-gray-400">加载详情中…</p>}
          <div className="mt-4 text-sm">
            <p className="font-medium text-gray-800 mb-2">依赖 / 调用出向 ({outgoing.length})</p>
            {outgoing.length === 0 && <p className="text-xs text-gray-400">无</p>}
            {outgoing.map((l, i) => (
              <div key={i} className="py-1 border-b border-gray-100 flex justify-between text-xs">
                <span className="text-gray-700 break-all">{label(l.target)}</span>
                <span style={{ color: EDGE_COLORS[l.type] }}>{l.type}</span>
              </div>
            ))}
          </div>
          <div className="mt-4 text-sm">
            <p className="font-medium text-gray-800 mb-2">被调用 / 入向 ({incoming.length})</p>
            {incoming.length === 0 && <p className="text-xs text-gray-400">无</p>}
            {incoming.map((l, i) => (
              <div key={i} className="py-1 border-b border-gray-100 flex justify-between text-xs">
                <span className="text-gray-700 break-all">{label(l.source)}</span>
                <span style={{ color: EDGE_COLORS[l.type] }}>{l.type}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </aside>
  )
}

function DetailList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="mt-4 text-sm">
      <p className="font-medium text-gray-800 mb-2">{title}</p>
      {items.length === 0 && <p className="text-xs text-gray-400">无</p>}
      {items.map((it, i) => (
        <div key={i} className="py-1 border-b border-gray-100 flex justify-between text-xs">
          <span className="text-gray-700 break-all">{it}</span>
          <span style={{ color: EDGE_COLORS.CALLS }}>CALLS</span>
        </div>
      ))}
    </div>
  )
}

// === Rendering ==========================================================

type LayerDef = { key: string; label: string; color: string; band: string }

function renderGraph(
  svg: SVGSVGElement,
  nodes: GraphNode[],
  links: GraphLink[],
  onNodeClick: (node: GraphNode) => void,
  layered: boolean,
  presentLayers: LayerDef[]
) {
  const width = svg.clientWidth || 800
  const height = svg.clientHeight || 600
  d3.select(svg).selectAll('*').remove()
  if (nodes.length === 0) return

  const byKey = new Map<string, GraphNode>()
  nodes.forEach((n) => {
    byKey.set(n.id, n)
    byKey.set(n.name, n)
  })
  const resolvedLinks = links
    .map((l) => {
      const s = byKey.get(typeof l.source === 'string' ? l.source : l.source.id)
      const t = byKey.get(typeof l.target === 'string' ? l.target : l.target.id)
      return s && t ? { source: s.id, target: t.id, type: l.type } : null
    })
    .filter(Boolean) as { source: string; target: string; type: string }[]

  const g = d3.select(svg).append('g')
  const zoom = d3
    .zoom<SVGSVGElement, unknown>()
    .scaleExtent([0.1, 4])
    .on('zoom', (event) => g.attr('transform', event.transform))
  d3.select(svg).call(zoom)

  // Node radius scales with fan-in (importance), so core symbols pop.
  const maxFan = Math.max(1, d3.max(nodes, (n) => n.fanIn || 0) || 1)
  const radius = (n: GraphNode) => {
    const base = n.kind === 'module' ? 8 : n.kind === 'class' ? 7 : 5
    return base + 8 * Math.sqrt((n.fanIn || 0) / maxFan)
  }
  const colorOf = (n: GraphNode) =>
    layered ? LAYER_BY_KEY[n.layer || 'other']?.color || '#94a3b8' : KIND_COLORS[n.kind] || '#6b7280'

  let simulation: d3.Simulation<GraphNode, undefined>

  if (layered) {
    // --- Layered bands: pin each node to its layer's horizontal row. ---
    const bandH = height / Math.max(1, presentLayers.length)
    const layerY = new Map<string, number>()
    presentLayers.forEach((l, i) => layerY.set(l.key, bandH * (i + 0.5)))

    // Draw bands + labels behind everything.
    const bands = g.append('g')
    presentLayers.forEach((l, i) => {
      bands
        .append('rect')
        .attr('x', 0)
        .attr('y', bandH * i)
        .attr('width', width)
        .attr('height', bandH)
        .attr('fill', l.band)
        .attr('opacity', 0.7)
      bands
        .append('line')
        .attr('x1', 0)
        .attr('x2', width)
        .attr('y1', bandH * (i + 1))
        .attr('y2', bandH * (i + 1))
        .attr('stroke', '#e2e8f0')
      bands
        .append('text')
        .text(l.label)
        .attr('x', 12)
        .attr('y', bandH * i + 18)
        .attr('font-size', '12px')
        .attr('font-weight', 600)
        .attr('fill', l.color)
    })

    simulation = d3
      .forceSimulation(nodes)
      .force(
        'link',
        d3
          .forceLink(resolvedLinks)
          .id((d: any) => d.id)
          .distance(60)
          .strength(0.2)
      )
      .force('charge', d3.forceManyBody().strength(-180))
      .force('x', d3.forceX(width / 2).strength(0.04))
      .force(
        'y',
        d3
          .forceY((d: any) => layerY.get(d.layer || 'other') ?? height / 2)
          .strength(1.0)
      )
      .force('collision', d3.forceCollide().radius((d: any) => radius(d) + 3))
  } else {
    // --- Free force-directed (the raw graph). ---
    simulation = d3
      .forceSimulation(nodes)
      .force('link', d3.forceLink(resolvedLinks).id((d: any) => d.id).distance(90))
      .force('charge', d3.forceManyBody().strength(-260))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius((d: any) => radius(d) + 4))
  }

  // Arrow markers so CALLS direction is visible.
  const defs = d3.select(svg).append('defs')
  Object.entries(EDGE_COLORS).forEach(([type, color]) => {
    defs
      .append('marker')
      .attr('id', `arrow-${type}`)
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 18)
      .attr('refY', 0)
      .attr('markerWidth', 5)
      .attr('markerHeight', 5)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', color)
  })

  const link = g
    .append('g')
    .selectAll('line')
    .data(resolvedLinks)
    .join('line')
    .attr('stroke', (d) => EDGE_COLORS[d.type] || '#cbd5e1')
    .attr('stroke-width', 1.4)
    .attr('stroke-opacity', 0.6)
    .attr('marker-end', (d) => (d.type === 'CALLS' ? `url(#arrow-${d.type})` : null))

  const node = g
    .append('g')
    .selectAll('g')
    .data(nodes)
    .join('g')
    .attr('cursor', 'pointer')
    .on('click', (_event, d) => onNodeClick(d as GraphNode))
    .call(
      d3
        .drag<any, any>()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart()
          d.fx = d.x
          d.fy = d.y
        })
        .on('drag', (event, d) => {
          d.fx = event.x
          d.fy = event.y
        })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0)
          d.fx = null
          d.fy = null
        })
    )

  // Modules as rounded squares, others as circles; size by fan-in; color by mode.
  node
    .filter((d) => d.kind === 'module')
    .append('rect')
    .attr('x', (d) => -radius(d))
    .attr('y', (d) => -radius(d))
    .attr('width', (d) => radius(d) * 2)
    .attr('height', (d) => radius(d) * 2)
    .attr('rx', 3)
    .attr('fill', colorOf)
    .attr('stroke', '#fff')
    .attr('stroke-width', 1.5)
  node
    .filter((d) => d.kind !== 'module')
    .append('circle')
    .attr('r', radius)
    .attr('fill', colorOf)
    .attr('stroke', '#fff')
    .attr('stroke-width', 1.5)

  node
    .append('text')
    .text((d) => shortName(d.name))
    .attr('x', (d) => radius(d) + 4)
    .attr('y', 3)
    .attr('font-size', '9px')
    .attr('fill', '#374151')

  simulation.on('tick', () => {
    link
      .attr('x1', (d: any) => d.source.x)
      .attr('y1', (d: any) => d.source.y)
      .attr('x2', (d: any) => d.target.x)
      .attr('y2', (d: any) => d.target.y)
    node.attr('transform', (d: any) => `translate(${d.x},${d.y})`)
  })
}

// === Sample data (shown when no backend repo is analyzed) ===============

const SAMPLE_ARCH: ArchitectureSummary = {
  generated_by: 'heuristic',
  module_count: 4,
  summary: 'GitGraph 自身的分层:接口层(API)→业务层(管线)→数据层(图谱/解析)。',
  layers: [
    { name: '接口层 Interface', description: '', modules: ['api.repositories', 'api.graph'] },
    { name: '业务层 Service', description: '', modules: ['evolution.pipeline', 'evolution.detector'] },
    { name: '数据层 Data', description: '', modules: ['graph.neo4j', 'ingestion.parser'] },
  ],
  patterns: [],
  boundaries: [],
}

const SAMPLE_NODES: GraphNode[] = [
  { id: 'api_repos', name: 'api.repositories', kind: 'module' },
  { id: 'analyze', name: 'api.repositories.analyze_repository', kind: 'function', signature: 'analyze_repository(req)' },
  { id: 'api_graph', name: 'api.graph', kind: 'module' },
  { id: 'pipeline', name: 'evolution.pipeline', kind: 'module' },
  { id: 'process', name: 'evolution.pipeline.process_repository', kind: 'method', signature: 'process_repository(repo_id, repo_path)' },
  { id: 'detector', name: 'evolution.detector', kind: 'module' },
  { id: 'scan', name: 'evolution.detector.scan_history', kind: 'function', signature: 'scan_history(snapshots)' },
  { id: 'neo4j', name: 'graph.neo4j', kind: 'module' },
  { id: 'merge', name: 'graph.neo4j.merge_extraction', kind: 'function', signature: 'merge_extraction(extraction, mapping)' },
  { id: 'parser', name: 'ingestion.parser', kind: 'module' },
  { id: 'parse', name: 'ingestion.parser.parse_python_source', kind: 'function', signature: 'parse_python_source(source, module)' },
]

const SAMPLE_LINKS: GraphLink[] = [
  { source: 'api.repositories.analyze_repository', target: 'evolution.pipeline.process_repository', type: 'CALLS' },
  { source: 'evolution.pipeline.process_repository', target: 'evolution.detector.scan_history', type: 'CALLS' },
  { source: 'evolution.pipeline.process_repository', target: 'graph.neo4j.merge_extraction', type: 'CALLS' },
  { source: 'evolution.pipeline.process_repository', target: 'ingestion.parser.parse_python_source', type: 'CALLS' },
  { source: 'evolution.detector.scan_history', target: 'ingestion.parser.parse_python_source', type: 'CALLS' },
  { source: 'api.repositories', target: 'api.repositories.analyze_repository', type: 'DEFINES' },
  { source: 'evolution.pipeline', target: 'evolution.pipeline.process_repository', type: 'DEFINES' },
  { source: 'evolution.detector', target: 'evolution.detector.scan_history', type: 'DEFINES' },
  { source: 'graph.neo4j', target: 'graph.neo4j.merge_extraction', type: 'DEFINES' },
  { source: 'ingestion.parser', target: 'ingestion.parser.parse_python_source', type: 'DEFINES' },
]

// Sample module-card map (GitGraph's own layered shape), shown when no backend repo.
const SAMPLE_MODULE_MAP: ModuleMap = {
  generated_by: 'structural',
  meta: {
    nodes: 11, edges: 5, cards: 4, layers: 3,
    kinds: { module: 4, function: 6, method: 1 },
    file_types: { py: 4 },
    layer_counts: { interface: 1, service: 2, data: 2 },
  },
  cards: [
    {
      id: 'api.repositories', title: 'repositories', module: 'api.repositories', layer: 'interface',
      complexity: 'simple', symbol_count: 1, file_count: 1, kinds: { function: 1 },
      files: ['api/repositories.py'], entities: ['analyze_repository'],
      symbols: [{ name: 'api.repositories.analyze_repository', kind: 'function', signature: 'analyze_repository(req)', file_path: 'api/repositories.py' }],
      summary: '对外 API 入口,接收分析请求并派发任务。',
    },
    {
      id: 'evolution.pipeline', title: 'pipeline', module: 'evolution.pipeline', layer: 'service',
      complexity: 'moderate', symbol_count: 1, file_count: 1, kinds: { method: 1 },
      files: ['evolution/pipeline.py'], entities: ['process_repository'],
      symbols: [{ name: 'evolution.pipeline.process_repository', kind: 'method', signature: 'process_repository(repo_id, repo_path)', file_path: 'evolution/pipeline.py' }],
      summary: '核心编排:遍历历史、建图、检测破坏性变更、运行理解 Agent。',
    },
    {
      id: 'evolution.detector', title: 'detector', module: 'evolution.detector', layer: 'service',
      complexity: 'simple', symbol_count: 1, file_count: 1, kinds: { function: 1 },
      files: ['evolution/detector.py'], entities: ['scan_history'],
      symbols: [{ name: 'evolution.detector.scan_history', kind: 'function', signature: 'scan_history(snapshots)', file_path: 'evolution/detector.py' }],
      summary: '对相邻提交做签名 diff,定位破坏性变更。',
    },
    {
      id: 'ingestion.parser', title: 'parser', module: 'ingestion.parser', layer: 'data',
      complexity: 'simple', symbol_count: 1, file_count: 1, kinds: { function: 1 },
      files: ['ingestion/parser.py'], entities: ['parse_python_source'],
      symbols: [{ name: 'ingestion.parser.parse_python_source', kind: 'function', signature: 'parse_python_source(source, module)', file_path: 'ingestion/parser.py' }],
      summary: '用 AST 确定性地把 Python 源码解析成代码图谱。',
    },
  ],
  edges: [
    { source: 'api.repositories', target: 'evolution.pipeline', type: 'CALLS', weight: 1 },
    { source: 'evolution.pipeline', target: 'evolution.detector', type: 'CALLS', weight: 2 },
    { source: 'evolution.pipeline', target: 'ingestion.parser', type: 'CALLS', weight: 1 },
    { source: 'evolution.detector', target: 'ingestion.parser', type: 'CALLS', weight: 1 },
  ],
}
