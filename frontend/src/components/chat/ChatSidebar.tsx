import { useState, useRef, useEffect } from 'react'
import { MessageSquareCode, Send, X, Loader2, Code2 } from 'lucide-react'
import { api, type AskCodebaseResponse } from '../../services/api'

interface Message {
  role: 'user' | 'assistant'
  content: string
  sources?: { symbol: string; file_path: string; line_start: number; relevance?: string }[]
  loading?: boolean
}

export default function ChatSidebar({ repoId }: { repoId: string }) {
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function send() {
    if (!input.trim() || loading || !repoId) return
    const q = input.trim()
    setInput('')
    setMessages((m) => [...m, { role: 'user', content: q }])
    setLoading(true)
    try {
      const res = await api.askCodebase(repoId, q)
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          content: res.answer || '无法回答',
          sources: res.sources?.map((s) => ({
            symbol: s.symbol,
            file_path: s.file_path,
            line_start: s.line_start,
            relevance: s.relevance,
          })),
        },
      ])
    } catch {
      setMessages((m) => [...m, { role: 'assistant', content: '请求失败,请检查后端是否运行。' }])
    } finally {
      setLoading(false)
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-50 w-12 h-12 bg-indigo-600 text-white rounded-full shadow-lg flex items-center justify-center hover:bg-indigo-700 transition-colors"
        title="问代码库"
      >
        <MessageSquareCode className="w-5 h-5" />
      </button>
    )
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 w-96 h-[520px] bg-white border rounded-2xl shadow-2xl flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b bg-indigo-50">
        <div className="flex items-center gap-2">
          <MessageSquareCode className="w-4 h-4 text-indigo-600" />
          <span className="text-sm font-medium text-gray-700">问代码库</span>
          {repoId && <span className="text-[10px] text-gray-400 truncate max-w-[140px]">{repoId.split(':').pop()}</span>}
        </div>
        <button onClick={() => setOpen(false)} className="text-gray-400 hover:text-gray-600">
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-auto px-4 py-3 space-y-3">
        {messages.length === 0 && (
          <div className="text-center text-xs text-gray-400 mt-8">
            <p>基于源码的智能问答</p>
            <p className="mt-1">试试:"agent 怎么协作" / "数据怎么流动"</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[85%] rounded-xl px-3 py-2 text-sm ${
                msg.role === 'user'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-gray-100 text-gray-800'
              }`}
            >
              <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-2 border-t border-gray-200 pt-1.5 space-y-1">
                  {msg.sources.slice(0, 4).map((s, j) => (
                    <div key={j} className="flex items-center gap-1 text-[10px] text-gray-500">
                      <Code2 className="w-3 h-3" />
                      <span className="font-mono">{s.symbol.split('.').pop()}</span>
                      {s.file_path && <span className="text-gray-400">:{s.line_start}</span>}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-xl px-3 py-2">
              <Loader2 className="w-4 h-4 animate-spin text-gray-400" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t px-3 py-2">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && send()}
            placeholder="输入问题…"
            disabled={loading}
            className="flex-1 px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-gray-50"
          />
          <button
            onClick={send}
            disabled={loading || !input.trim()}
            className="px-3 py-2 bg-indigo-600 text-white rounded-lg disabled:opacity-50"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
