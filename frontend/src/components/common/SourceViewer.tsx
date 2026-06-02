import { useEffect, useState } from 'react'
import { Code2, ExternalLink, Loader2 } from 'lucide-react'
import { api, type SourceSnippet } from '../../services/api'

/**
 * Inline source code viewer: fetches and displays a symbol's real code body
 * with line numbers and language hint. Reusable across detail panels.
 */
export default function SourceViewer({
  repoId,
  symbol,
  githubBase,
}: {
  repoId: string
  symbol: string
  githubBase?: string // e.g. "https://github.com/owner/repo/blob/main"
}) {
  const [source, setSource] = useState<SourceSnippet | null>(null)
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    setSource(null)
    setExpanded(false)
  }, [symbol])

  function loadSource() {
    if (source) {
      setExpanded(!expanded)
      return
    }
    setLoading(true)
    api
      .getSymbolSource(repoId, symbol, 2)
      .then((res) => {
        if (res.source) setSource(res.source)
        setExpanded(true)
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  const githubUrl =
    githubBase && source
      ? `${githubBase}/${source.file_path}#L${source.line_start}-L${source.line_end}`
      : null

  return (
    <div className="mt-2">
      <button
        onClick={loadSource}
        className="flex items-center gap-1.5 text-xs text-indigo-600 hover:text-indigo-800"
      >
        {loading ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        ) : (
          <Code2 className="w-3.5 h-3.5" />
        )}
        {expanded ? '收起源码' : '查看源码'}
      </button>
      {expanded && source && (
        <div className="mt-2 rounded-lg border bg-gray-900 text-gray-100 text-[11px] font-mono overflow-auto max-h-72">
          <div className="flex items-center justify-between px-3 py-1.5 bg-gray-800 text-gray-400 text-[10px]">
            <span>
              {source.file_path} · L{source.line_start}–{source.line_end} · {source.language}
            </span>
            {githubUrl && (
              <a
                href={githubUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-gray-400 hover:text-white"
              >
                GitHub <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>
          <pre className="p-3 whitespace-pre-wrap break-all leading-relaxed">
            {source.code.split('\n').map((line, i) => (
              <div key={i} className="flex">
                <span className="w-8 text-right text-gray-600 select-none pr-3 shrink-0">
                  {source.line_start + i}
                </span>
                <span>{line}</span>
              </div>
            ))}
          </pre>
          {source.truncated && (
            <p className="px-3 py-1 text-[10px] text-gray-500 border-t border-gray-700">
              (已截断,完整文件请在 IDE 中查看)
            </p>
          )}
        </div>
      )}
    </div>
  )
}
