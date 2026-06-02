import type { ReactNode } from 'react'

/**
 * Cognition goal card — uniform header for each of the 4 stations.
 * Tells user "what this page covers" + "what you should take away".
 * Spec ref: product-design-spec.md §四 "认知目标卡片".
 */
export default function CognitionGoalCard({
  icon,
  station,
  title,
  helps,
  takeaway,
  accentColor = '#6366f1',
}: {
  icon: ReactNode
  station: string         // e.g. "全貌 · 建立第一印象"
  title?: string
  helps: string[]         // bullet points: "这页帮你了解"
  takeaway: string        // "读完你应该能"
  accentColor?: string
}) {
  return (
    <div
      className="bg-white border-2 rounded-xl p-5 mb-6 shadow-sm"
      style={{ borderColor: accentColor + '33' }}
    >
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xl" style={{ color: accentColor }}>{icon}</span>
        <h2 className="text-base font-semibold" style={{ color: accentColor }}>
          {station}
        </h2>
      </div>
      {title && <p className="text-sm font-medium text-gray-700 mb-2">{title}</p>}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
            这页帮你了解
          </p>
          <ul className="space-y-1">
            {helps.map((h, i) => (
              <li key={i} className="text-sm text-gray-600 flex gap-2">
                <span className="text-gray-300 shrink-0">•</span>
                <span>{h}</span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1.5">
            读完你应该能
          </p>
          <p className="text-sm text-gray-600 leading-relaxed">{takeaway}</p>
        </div>
      </div>
    </div>
  )
}
