import type { CSSProperties, ReactNode } from 'react'
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  Code2,
  Flag,
  Lightbulb,
  Map,
  Star,
} from 'lucide-react'
import { stageAssets, stageBackgrounds, type StageAssetKey, type StageBackgroundKey } from '../../assets/pixel/stage-library'

type Tone = 'blue' | 'green' | 'amber' | 'purple' | 'red' | 'neutral'

const toneClass: Record<Tone, string> = {
  blue: 'cg-tone-blue',
  green: 'cg-tone-green',
  amber: 'cg-tone-amber',
  purple: 'cg-tone-purple',
  red: 'cg-tone-red',
  neutral: 'cg-tone-neutral',
}

export const nonCodeAssetComponents = [
  { id: 'mentor-sprites', label: '角色状态图', reason: '跑步、挖矿、举杯等像素姿态需要稳定角色造型，不能靠 CSS 可靠生成。' },
  { id: 'scene-backgrounds', label: '阶段场景背景', reason: '学习地图、主线草地、矿洞、营火小屋是完整场景美术，需要图片资产。' },
  { id: 'semantic-props', label: '语义道具', reason: '矿石、宝箱、木牌、路径箭头、徽章承担识别记忆点，需要透明 PNG。' },
] as const

export const codeComponentPrimitives = [
  'StageShell',
  'StageHero',
  'ProgressPill',
  'PixelAsset',
  'SpeechBubble',
  'ParchmentPanel',
  'ConceptCard',
  'FlowChain',
  'TaskChecklist',
  'RewardStrip',
  'CodeFoldPanel',
  'NextStageCard',
] as const

export function PixelAsset({
  asset,
  alt,
  className = '',
  style,
}: {
  asset: StageAssetKey
  alt: string
  className?: string
  style?: CSSProperties
}) {
  return <img src={stageAssets[asset]} alt={alt} className={`cg-pixel-asset ${className}`} style={style} />
}

export function StageShell({
  background,
  children,
  className = '',
}: {
  background?: StageBackgroundKey
  children: ReactNode
  className?: string
}) {
  const style = background ? ({ '--stage-bg': `url(${stageBackgrounds[background]})` } as CSSProperties) : undefined
  return (
    <section className={`cg-stage-shell ${background ? 'has-bg' : ''} ${className}`} style={style}>
      {children}
    </section>
  )
}

export function StageHero({
  stage,
  title,
  subtitle,
  background,
  mentor = 'mentorRunner',
  speech,
  progress,
  children,
}: {
  stage: string
  title: string
  subtitle: string
  background: StageBackgroundKey
  mentor?: StageAssetKey
  speech?: string
  progress?: number
  children?: ReactNode
}) {
  return (
    <StageShell background={background} className="cg-stage-hero">
      <div className="cg-stage-topbar">
        <button type="button" className="cg-back-button">
          <Map size={18} />
          返回学习地图
        </button>
        {typeof progress === 'number' && <ProgressPill label="当前进度" value={progress} />}
      </div>
      <div className="cg-stage-title">
        <h1>{stage} · {title}</h1>
        <p>{subtitle}</p>
      </div>
      <div className="cg-stage-mentor-row">
        {speech && <SpeechBubble>{speech}</SpeechBubble>}
        <PixelAsset asset={mentor} alt="阶段导师" className="cg-stage-mentor" />
        {children}
      </div>
    </StageShell>
  )
}

export function ProgressPill({ label, value }: { label: string; value: number }) {
  const clamped = Math.max(0, Math.min(100, value))
  return (
    <div className="cg-progress-pill">
      <PixelAsset asset="mentorRunner" alt="" className="cg-progress-avatar" />
      <div>
        <strong>{label}</strong>
        <span><i style={{ width: `${clamped}%` }} /></span>
      </div>
      <b>{clamped}%</b>
    </div>
  )
}

export function SpeechBubble({ children }: { children: ReactNode }) {
  return <div className="cg-speech-bubble">{children}</div>
}

export function ParchmentPanel({
  title,
  icon,
  tone = 'neutral',
  children,
}: {
  title: string
  icon?: ReactNode
  tone?: Tone
  children: ReactNode
}) {
  return (
    <section className={`cg-parchment ${toneClass[tone]}`}>
      <header>
        {icon}
        <h2>{title}</h2>
      </header>
      {children}
    </section>
  )
}

export function ConceptCard({
  title,
  body,
  asset,
  tone = 'blue',
}: {
  title: string
  body: string
  asset: StageAssetKey
  tone?: Tone
}) {
  return (
    <article className={`cg-concept-card ${toneClass[tone]}`}>
      <PixelAsset asset={asset} alt="" />
      <div>
        <h3>{title}</h3>
        <p>{body}</p>
      </div>
    </article>
  )
}

export function FlowChain({ steps, activeIndex = 0 }: { steps: Array<{ title: string; note: string; icon?: ReactNode }>; activeIndex?: number }) {
  return (
    <div className="cg-flow-chain">
      {steps.map((step, index) => (
        <div key={step.title} className={index === activeIndex ? 'is-active' : ''}>
          <em>{index + 1}</em>
          <span>{step.icon || <BookOpen size={32} />}</span>
          <strong>{step.title}</strong>
          <small>{step.note}</small>
          {index < steps.length - 1 && <ArrowRight className="cg-flow-arrow" size={30} />}
        </div>
      ))}
    </div>
  )
}

export function TaskChecklist({ title, tasks }: { title: string; tasks: string[] }) {
  return (
    <ParchmentPanel title={title} icon={<ClipboardList size={22} />} tone="amber">
      <ul className="cg-task-list">
        {tasks.map((task) => (
          <li key={task}>
            <CheckCircle2 size={20} />
            <span>{task}</span>
          </li>
        ))}
      </ul>
    </ParchmentPanel>
  )
}

export function RewardStrip({ items }: { items: Array<{ label: string; detail: string; icon?: ReactNode }> }) {
  return (
    <div className="cg-reward-strip">
      <strong><Star size={20} /> 你已经收获</strong>
      <div>
        {items.map((item) => (
          <span key={item.label}>
            {item.icon || <Lightbulb size={20} />}
            <b>{item.label}</b>
            <small>{item.detail}</small>
          </span>
        ))}
      </div>
    </div>
  )
}

export function CodeFoldPanel({ sections }: { sections: Array<{ title: string; lines: string[]; open?: boolean }> }) {
  return (
    <ParchmentPanel title="代码证据折叠面板" icon={<Code2 size={22} />} tone="blue">
      <div className="cg-code-folds">
        {sections.map((section) => (
          <details key={section.title} open={section.open}>
            <summary>
              {section.title}
              <ChevronRight size={18} />
            </summary>
            <pre>{section.lines.join('\n')}</pre>
          </details>
        ))}
      </div>
    </ParchmentPanel>
  )
}

export function NextStageCard({
  title,
  body,
  asset = 'mineEntrance',
}: {
  title: string
  body: string
  asset?: StageAssetKey
}) {
  return (
    <aside className="cg-next-stage-card">
      <header>
        <Flag size={22} />
        <strong>{title}</strong>
      </header>
      <p>{body}</p>
      <PixelAsset asset={asset} alt="" />
      <button type="button">
        进入下一步
        <ArrowRight size={20} />
      </button>
    </aside>
  )
}
