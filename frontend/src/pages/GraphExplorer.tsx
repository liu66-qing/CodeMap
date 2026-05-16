import { useEffect, useRef, useState } from 'react'
import * as d3 from 'd3'
import { Search, ZoomIn, ZoomOut, Maximize2 } from 'lucide-react'

interface GraphNode {
  id: string
  name: string
  type: string
  x?: number
  y?: number
}

interface GraphLink {
  source: string | GraphNode
  target: string | GraphNode
  type: string
  confidence: number
}

const TYPE_COLORS: Record<string, string> = {
  person: '#3b82f6',
  organization: '#10b981',
  product: '#f59e0b',
  event: '#ef4444',
  location: '#8b5cf6',
  technology: '#06b6d4',
  concept: '#6b7280',
}

export default function GraphExplorer() {
  const svgRef = useRef<SVGSVGElement>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [nodes, setNodes] = useState<GraphNode[]>(DEMO_NODES)
  const [links, setLinks] = useState<GraphLink[]>(DEMO_LINKS)

  useEffect(() => {
    if (!svgRef.current) return
    renderGraph(svgRef.current, nodes, links, setSelectedNode)
  }, [nodes, links])

  return (
    <div className="h-full flex flex-col">
      <header className="p-4 border-b bg-white flex items-center gap-4">
        <h2 className="text-lg font-semibold">Knowledge Graph Explorer</h2>
        <div className="flex-1 max-w-md relative">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search entities..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div className="flex gap-1">
          <button className="p-2 hover:bg-gray-100 rounded"><ZoomIn className="w-4 h-4" /></button>
          <button className="p-2 hover:bg-gray-100 rounded"><ZoomOut className="w-4 h-4" /></button>
          <button className="p-2 hover:bg-gray-100 rounded"><Maximize2 className="w-4 h-4" /></button>
        </div>
      </header>

      <div className="flex-1 flex">
        <div className="flex-1 relative bg-gray-50">
          <svg ref={svgRef} className="w-full h-full" />
          <div className="absolute bottom-4 left-4 bg-white rounded-lg shadow p-3 text-xs">
            <p className="font-medium mb-2">Entity Types</p>
            {Object.entries(TYPE_COLORS).map(([type, color]) => (
              <div key={type} className="flex items-center gap-2 mb-1">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
                <span className="capitalize">{type}</span>
              </div>
            ))}
          </div>
        </div>

        {selectedNode && (
          <aside className="w-80 border-l bg-white p-4 overflow-auto">
            <h3 className="font-semibold text-lg">{selectedNode.name}</h3>
            <span
              className="inline-block px-2 py-0.5 rounded text-xs text-white mt-1 capitalize"
              style={{ backgroundColor: TYPE_COLORS[selectedNode.type] || '#6b7280' }}
            >
              {selectedNode.type}
            </span>
            <div className="mt-4 text-sm text-gray-600">
              <p className="font-medium text-gray-800 mb-2">Relationships</p>
              {links
                .filter(
                  (l) =>
                    (typeof l.source === 'string' ? l.source : l.source.id) === selectedNode.id ||
                    (typeof l.target === 'string' ? l.target : l.target.id) === selectedNode.id
                )
                .map((l, i) => (
                  <div key={i} className="py-1 border-b border-gray-100">
                    <span className="text-blue-600">{l.type}</span>
                    <span className="text-gray-400 ml-2">({(l.confidence * 100).toFixed(0)}%)</span>
                  </div>
                ))}
            </div>
          </aside>
        )}
      </div>
    </div>
  )
}

function renderGraph(
  svg: SVGSVGElement,
  nodes: GraphNode[],
  links: GraphLink[],
  onNodeClick: (node: GraphNode) => void
) {
  const width = svg.clientWidth || 800
  const height = svg.clientHeight || 600

  d3.select(svg).selectAll('*').remove()

  const g = d3.select(svg).append('g')

  const zoom = d3.zoom<SVGSVGElement, unknown>()
    .scaleExtent([0.1, 4])
    .on('zoom', (event) => g.attr('transform', event.transform))
  d3.select(svg).call(zoom)

  const simulation = d3.forceSimulation(nodes as d3.SimulationNodeDatum[])
    .force('link', d3.forceLink(links).id((d: any) => d.id).distance(120))
    .force('charge', d3.forceManyBody().strength(-300))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collision', d3.forceCollide().radius(30))

  const link = g.append('g')
    .selectAll('line')
    .data(links)
    .join('line')
    .attr('class', 'graph-link')
    .attr('stroke-width', (d) => Math.max(1, d.confidence * 3))

  const node = g.append('g')
    .selectAll('g')
    .data(nodes)
    .join('g')
    .attr('cursor', 'pointer')
    .on('click', (_event, d) => onNodeClick(d as GraphNode))
    .call(d3.drag<any, any>()
      .on('start', (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart()
        d.fx = d.x; d.fy = d.y
      })
      .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y })
      .on('end', (event, d) => {
        if (!event.active) simulation.alphaTarget(0)
        d.fx = null; d.fy = null
      })
    )

  node.append('circle')
    .attr('r', 12)
    .attr('fill', (d) => TYPE_COLORS[d.type] || '#6b7280')
    .attr('stroke', '#fff')
    .attr('stroke-width', 2)

  node.append('text')
    .text((d) => d.name)
    .attr('x', 16)
    .attr('y', 4)
    .attr('font-size', '11px')
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

// Demo data for initial render
const DEMO_NODES: GraphNode[] = [
  { id: '1', name: 'OpenAI', type: 'organization' },
  { id: '2', name: 'Sam Altman', type: 'person' },
  { id: '3', name: 'GPT-4', type: 'product' },
  { id: '4', name: 'Microsoft', type: 'organization' },
  { id: '5', name: 'Satya Nadella', type: 'person' },
  { id: '6', name: 'AI Safety', type: 'concept' },
  { id: '7', name: 'San Francisco', type: 'location' },
  { id: '8', name: 'Transformer', type: 'technology' },
]

const DEMO_LINKS: GraphLink[] = [
  { source: '2', target: '1', type: 'CEO_OF', confidence: 0.95 },
  { source: '1', target: '3', type: 'PRODUCES', confidence: 0.99 },
  { source: '4', target: '1', type: 'INVESTED_IN', confidence: 0.9 },
  { source: '5', target: '4', type: 'CEO_OF', confidence: 0.95 },
  { source: '1', target: '7', type: 'LOCATED_IN', confidence: 0.85 },
  { source: '3', target: '8', type: 'USES', confidence: 0.9 },
  { source: '1', target: '6', type: 'RESEARCHES', confidence: 0.8 },
]
