import { useEffect, useMemo, useRef, useState } from 'react'
import { Loader2, Sparkles } from 'lucide-react'
import { api, type ModuleMap, type ModuleCard, type ModuleEdge, type ModuleCardSymbol, type MechanismAnalysis } from '../services/api'
import SourceViewer from '../components/common/SourceViewer'

// Layer order + accent (matches the symbol graph's layers; light theme, not UA's dark).
const LAYER_DEFS: { key: string; label: string; accent: string; chip: string }[] = [
  { key: 'interface', label: '接口层 Interface', accent: '#6366f1', chip: 'bg-indigo-50 text-indigo-700 border-indigo-200' },
  { key: 'service', label: '业务层 Service', accent: '#10b981', chip: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  { key: 'data', label: '数据层 Data', accent: '#f59e0b', chip: 'bg-amber-50 text-amber-700 border-amber-200' },
  { key: 'infrastructure', label: '基础设施 Infra', accent: '#06b6d4', chip: 'bg-cyan-50 text-cyan-700 border-cyan-200' },
  { key: 'background', label: '后台 Background', accent: '#a855f7', chip: 'bg-purple-50 text-purple-700 border-purple-200' },
  { key: 'shared', label: '公共 Shared', accent: '#64748b', chip: 'bg-slate-50 text-slate-700 border-slate-200' },
  { key: 'other', label: '其他 Other', accent: '#94a3b8', chip: 'bg-gray-50 text-gray-600 border-gray-200' },
]
const LAYER_BY_KEY = Object.fromEntries(LAYER_DEFS.map((l) => [l.key, l]))

const COMPLEXITY_CHIP: Record<string, string> = {
  simple: 'text-emerald-600',
  moderate: 'text-amber-600',
  complex: 'text-red-600',
}

// Card box geometry for the SVG connector layer.
const CARD_W = 230
const CARD_H = 150
const COL_GAP = 40
const ROW_GAP = 80
const ROW_PAD_TOP = 44 // room for the layer label above each row

interface Placed {
  card: ModuleCard
  x: number
  y: number
}

// Lay cards out in layer rows (top→bottom by LAYER_DEFS order), centered per row.
function layout(cards: ModuleCard[], width: number): { placed: Placed[]; rows: { key: string; y: number; h: number }[]; height: number } {
  const byLayer = new Map<string, ModuleCard[]>()
  for (const c of cards) {
    const k = LAYER_BY_KEY[c.layer] ? c.layer : 'other'
    if (!byLayer.has(k)) byLayer.set(k, [])
    byLayer.get(k)!.push(c)
  }
  const placed: Placed[] = []
  const rows: { key: string; y: number; h: number }[] = []
  let y = 16
  for (const def of LAYER_DEFS) {
    const group = byLayer.get(def.key)
    if (!group || group.length === 0) continue
    const rowW = group.length * CARD_W + (group.length - 1) * COL_GAP
    const startX = Math.max(24, (width - rowW) / 2)
    const rowTop = y + ROW_PAD_TOP
    group.forEach((card, i) => {
      placed.push({ card, x: startX + i * (CARD_W + COL_GAP), y: rowTop })
    })
    rows.push({ key: def.key, y, h: ROW_PAD_TOP + CARD_H })
    y = rowTop + CARD_H + ROW_GAP
  }
  return { placed, rows, height: y }
}

// Cubic vertical connector between two card boxes.
function connectorPath(a: Placed, b: Placed): string {
  const x1 = a.x + CARD_W / 2
  const y1 = a.y + CARD_H
  const x2 = b.x + CARD_W / 2
  const y2 = b.y
  const my = (y1 + y2) / 2
  return `M${x1},${y1} C${x1},${my} ${x2},${my} ${x2},${y2}`
}

export default function ModuleCardCanvas({
  map,
  repoId,
  onSelectSymbol,
  selectedSymbol,
}: {
  map: ModuleMap
  repoId: string
  onSelectSymbol: (symbolName: string) => void
  selectedSymbol: string | null
}) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(900)
  const [selectedCard, setSelectedCard] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)

  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const ro = new ResizeObserver((entries) => setWidth(entries[0].contentRect.width))
    ro.observe(el)
    setWidth(el.clientWidth)
    return () => ro.disconnect()
  }, [])

  const { placed, rows, height } = useMemo(() => layout(map.cards, width), [map.cards, width])
  const posById = useMemo(() => new Map(placed.map((p) => [p.card.id, p])), [placed])

  // Highlight edges touching the selected card.
  const activeEdges = (e: ModuleEdge) => selectedCard && (e.source === selectedCard || e.target === selectedCard)

  return (
    <div className="flex-1 flex min-h-0">
      <div ref={wrapRef} className="flex-1 relative overflow-auto bg-gray-50">
        <div className="relative" style={{ height, minWidth: '100%' }}>
          {/* Layer row labels */}
          {rows.map((r) => {
            const def = LAYER_BY_KEY[r.key]
            return (
              <div key={r.key} className="absolute left-0 right-0" style={{ top: r.y }}>
                <div className="px-6 text-xs font-semibold tracking-wide" style={{ color: def.accent }}>
                  {def.label}
                </div>
              </div>
            )
          })}

          {/* SVG connector layer (behind cards) */}
          <svg className="absolute inset-0 pointer-events-none" width="100%" height={height}>
            <defs>
              <marker id="card-arrow" viewBox="0 -5 10 10" refX="8" refY="0" markerWidth="6" markerHeight="6" orient="auto">
                <path d="M0,-5L10,0L0,5" fill="#cbd5e1" />
              </marker>
            </defs>
            {map.edges.map((e, i) => {
              const a = posById.get(e.source)
              const b = posById.get(e.target)
              if (!a || !b) return null
              const active = activeEdges(e)
              const mx = (a.x + b.x) / 2 + CARD_W / 2
              const my = (a.y + CARD_H + b.y) / 2
              return (
                <g key={i}>
                  <path
                    d={connectorPath(a, b)}
                    fill="none"
                    stroke={active ? '#6366f1' : '#cbd5e1'}
                    strokeWidth={active ? 2 : Math.min(1 + Math.log2(e.weight + 1), 4)}
                    strokeOpacity={selectedCard && !active ? 0.25 : 0.7}
                    markerEnd="url(#card-arrow)"
                  />
                  <text x={mx} y={my} fontSize="10" fill="#94a3b8" textAnchor="middle" className="select-none">
                    {e.weight}
                  </text>
                </g>
              )
            })}
          </svg>

          {/* Cards */}
          {placed.map(({ card, x, y }) => (
            <CardBox
              key={card.id}
              card={card}
              x={x}
              y={y}
              selected={selectedCard === card.id}
              onClick={() => {
                setSelectedCard(card.id)
                setExpanded((cur) => (cur === card.id ? cur : null))
              }}
              onToggleExpand={() => setExpanded((cur) => (cur === card.id ? null : card.id))}
              expanded={expanded === card.id}
              onSelectSymbol={onSelectSymbol}
              selectedSymbol={selectedSymbol}
            />
          ))}
        </div>
      </div>

      <ProjectInfoPanel map={map} repoId={repoId} selectedCard={selectedCard ? posById.get(selectedCard)?.card ?? null : null} />
    </div>
  )
}

function CardBox({
  card, x, y, selected, expanded, onClick, onToggleExpand, onSelectSymbol, selectedSymbol,
}: {
  card: ModuleCard
  x: number
  y: number
  selected: boolean
  expanded: boolean
  onClick: () => void
  onToggleExpand: () => void
  onSelectSymbol: (s: string) => void
  selectedSymbol: string | null
}) {
  const def = LAYER_BY_KEY[card.layer] || LAYER_BY_KEY.other
  return (
    <div
      className={`absolute rounded-xl bg-white border shadow-sm transition-shadow cursor-pointer ${
        selected ? 'ring-2 ring-indigo-400 shadow-md' : 'hover:shadow-md'
      }`}
      style={{ left: x, top: y, width: CARD_W }}
      onClick={onClick}
    >
      <div className="absolute left-0 top-0 bottom-0 w-1 rounded-l-xl" style={{ backgroundColor: def.accent }} />
      <div className="pl-4 pr-3 py-2.5">
        <div className="flex items-center justify-between">
          <span className={`text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded border ${def.chip}`}>
            {def.label.split(' ')[0]}
          </span>
          <span className={`text-[10px] font-mono ${COMPLEXITY_CHIP[card.complexity] || 'text-gray-400'}`}>
            {card.complexity}
          </span>
        </div>
        <div className="mt-1.5 font-semibold text-sm text-gray-800 truncate" title={card.module}>
          {card.title}
        </div>
        <p className="mt-1 text-[11px] text-gray-500 leading-snug line-clamp-2">{card.summary}</p>
        {card.entities.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1">
            {card.entities.slice(0, 4).map((e) => (
              <span key={e} className="text-[9px] font-mono bg-gray-100 text-gray-600 px-1 py-0.5 rounded">{e}</span>
            ))}
          </div>
        )}
        <div className="mt-2 flex items-center justify-between text-[10px] text-gray-400">
          <span>{card.file_count} 文件 · {card.symbol_count} 符号</span>
          <button
            onClick={(ev) => { ev.stopPropagation(); onToggleExpand() }}
            className="text-indigo-500 hover:text-indigo-700"
          >
            {expanded ? '收起' : '展开符号'}
          </button>
        </div>
        {expanded && (
          <div className="mt-2 border-t pt-2 max-h-44 overflow-auto">
            {card.symbols.length === 0 && <p className="text-[10px] text-gray-400">无可展开的符号</p>}
            {card.symbols.map((s) => (
              <SymbolRow key={s.name} sym={s} active={selectedSymbol === s.name} onSelect={() => onSelectSymbol(s.name)} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function SymbolRow({ sym, active, onSelect }: { sym: ModuleCardSymbol; active: boolean; onSelect: () => void }) {
  const simple = sym.name.split('.').pop()
  const kindColor: Record<string, string> = {
    class: 'text-emerald-600', function: 'text-amber-600', method: 'text-cyan-600', module: 'text-indigo-600',
  }
  return (
    <button
      onClick={(e) => { e.stopPropagation(); onSelect() }}
      className={`w-full text-left flex items-center gap-1.5 py-0.5 text-[11px] rounded px-1 ${
        active ? 'bg-indigo-50' : 'hover:bg-gray-50'
      }`}
    >
      <span className={`font-mono ${kindColor[sym.kind] || 'text-gray-500'} text-[9px]`}>{sym.kind[0]}</span>
      <span className="font-mono text-gray-700 truncate">{simple}</span>
    </button>
  )
}

function ProjectInfoPanel({ map, repoId, selectedCard }: { map: ModuleMap; repoId: string; selectedCard: ModuleCard | null }) {
  const meta = map.meta
  const [mechanism, setMechanism] = useState<MechanismAnalysis | null>(null)
  const [mechLoading, setMechLoading] = useState(false)

  // Fetch mechanism when a card is selected.
  useEffect(() => {
    setMechanism(null)
    if (!selectedCard || !repoId) return
    let cancelled = false
    setMechLoading(true)
    api
      .getModuleMechanism(repoId, selectedCard.id)
      .then((res) => {
        if (!cancelled && res.mechanism) setMechanism(res.mechanism)
      })
      .catch(() => {})
      .finally(() => !cancelled && setMechLoading(false))
    return () => { cancelled = true }
  }, [selectedCard?.id, repoId])

  if (selectedCard) {
    const def = LAYER_BY_KEY[selectedCard.layer] || LAYER_BY_KEY.other
    return (
      <aside className="w-80 border-l bg-white p-4 overflow-auto shrink-0">
        <span className="text-xs font-semibold px-2 py-0.5 rounded border" style={{ borderColor: def.accent, color: def.accent }}>
          {def.label}
        </span>
        <h3 className="mt-2 font-semibold text-sm break-all">{selectedCard.module}</h3>
        <p className="mt-2 text-sm text-gray-600 leading-relaxed">{selectedCard.summary}</p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <Stat label="文件" value={selectedCard.file_count} />
          <Stat label="符号" value={selectedCard.symbol_count} />
        </div>
        {selectedCard.entities.length > 0 && (
          <div className="mt-3">
            <p className="text-xs font-medium text-gray-500 mb-1">主要实体</p>
            <div className="flex flex-wrap gap-1">
              {selectedCard.entities.map((e) => (
                <span key={e} className="text-[10px] font-mono bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">{e}</span>
              ))}
            </div>
          </div>
        )}

        {/* Mechanism analysis: the design narrative */}
        <div className="mt-4 border-t pt-3">
          <p className="text-xs font-medium text-gray-700 mb-2 flex items-center gap-1">
            <Sparkles className="w-3.5 h-3.5 text-amber-500" />
            机制剖析
          </p>
          {mechLoading && (
            <div className="flex items-center gap-2 text-xs text-gray-400">
              <Loader2 className="w-3.5 h-3.5 animate-spin" /> 正在读取源码并分析…
            </div>
          )}
          {mechanism && (
            <div className="space-y-2 text-xs text-gray-700">
              <p className="leading-relaxed">{mechanism.overview}</p>
              {mechanism.parts.length > 0 && (
                <div>
                  <p className="font-medium text-gray-500 mt-2 mb-1">分工</p>
                  {mechanism.parts.slice(0, 6).map((p, i) => (
                    <div key={i} className="py-1 border-b border-gray-100">
                      <span className="font-mono text-indigo-600">{p.symbol.split('.').pop()}</span>
                      <span className="text-gray-500 ml-1">— {p.role}</span>
                      <SourceViewer repoId={repoId} symbol={p.symbol} />
                    </div>
                  ))}
                </div>
              )}
              {mechanism.connections && (
                <div>
                  <p className="font-medium text-gray-500 mt-2 mb-1">连接与协作</p>
                  <p className="leading-relaxed">{mechanism.connections}</p>
                </div>
              )}
              {mechanism.data_flow && (
                <div>
                  <p className="font-medium text-gray-500 mt-2 mb-1">数据流动</p>
                  <p className="leading-relaxed">{mechanism.data_flow}</p>
                </div>
              )}
              {mechanism.state_memory && (
                <div>
                  <p className="font-medium text-gray-500 mt-2 mb-1">状态/记忆管理</p>
                  <p className="leading-relaxed">{mechanism.state_memory}</p>
                </div>
              )}
              <p className="text-[10px] text-gray-400 mt-2">
                基于 {mechanism.grounded_in.length} 个符号的真实源码 · {mechanism.generated_by === 'llm' ? 'LLM 综合' : '结构化推断'}
              </p>
            </div>
          )}
          {!mechLoading && !mechanism && (
            <p className="text-[10px] text-gray-400">点击卡片后自动加载机制分析。</p>
          )}
        </div>
      </aside>
    )
  }
  return (
    <aside className="w-80 border-l bg-white p-4 overflow-auto shrink-0">
      <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">项目总览</p>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <Stat label="符号节点" value={meta.nodes} />
        <Stat label="关系" value={meta.edges} />
        <Stat label="模块卡片" value={meta.cards} />
        <Stat label="分层" value={meta.layers} />
      </div>
      <div className="mt-4">
        <p className="text-xs font-medium text-gray-500 mb-1.5">符号类型</p>
        {Object.entries(meta.kinds).map(([k, v]) => (
          <Bar key={k} label={k} value={v} max={meta.nodes} />
        ))}
      </div>
      <div className="mt-4">
        <p className="text-xs font-medium text-gray-500 mb-1.5">分层卡片数</p>
        {Object.entries(meta.layer_counts).map(([k, v]) => (
          <div key={k} className="flex justify-between text-xs py-0.5">
            <span style={{ color: (LAYER_BY_KEY[k] || LAYER_BY_KEY.other).accent }}>
              {(LAYER_BY_KEY[k] || LAYER_BY_KEY.other).label}
            </span>
            <span className="text-gray-500">{v}</span>
          </div>
        ))}
      </div>
      <p className="mt-4 text-[10px] text-gray-400">点击卡片查看模块详情与机制剖析。</p>
    </aside>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="border rounded-lg p-2">
      <div className="text-xl font-bold text-gray-800">{value}</div>
      <div className="text-[10px] text-gray-400">{label}</div>
    </div>
  )
}

function Bar({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = max ? Math.round((value / max) * 100) : 0
  return (
    <div className="flex items-center gap-2 text-xs py-0.5">
      <span className="w-16 text-gray-600">{label}</span>
      <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div className="h-full bg-indigo-400" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-gray-400 w-6 text-right">{value}</span>
    </div>
  )
}
