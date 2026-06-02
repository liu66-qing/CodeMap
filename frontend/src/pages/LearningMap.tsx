import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Map,
  Star,
  Clock,
  BookOpen,
  Trophy,
  ChevronRight,
  Zap,
} from 'lucide-react'
import {
  StageShell,
  ProgressPill,
  PixelAsset,
  SpeechBubble,
  ParchmentPanel,
  FlowChain,
} from '../components/common/PixelStageKit'
import { useProgress } from '../hooks/useProgress'
import type { LearningBadge, LearningPathStep } from '../services/api'

const STAGE_ROUTES: Record<string, string> = {
  overview: '/overview',
  mainflow: '/mainflow',
  showcase: '/showcase',
  takeaway: '/takeaway',
}

const STAGE_LABELS: Record<string, string> = {
  overview: '先看门道',
  mainflow: '跑通主线',
  showcase: '拆它绝活',
  takeaway: '抄走一招',
}

const STAGE_NUMBERS = ['1', '2', '3', '4']

export default function LearningMap() {
  const navigate = useNavigate()
  const { stats, loading, refresh } = useProgress()
  const [pathLevel, setPathLevel] = useState<'quick' | 'standard' | 'deep'>('standard')

  const progress = stats?.progress
  const badges = stats?.badges ?? []
  const path = stats?.path

  return (
    <StageShell background="learningMap" className="cg-learning-map">
      {/* Top bar */}
      <div className="cg-map-topbar">
        <div className="cg-map-title">
          <Map size={24} />
          <h1>学习地图</h1>
          <span>探索学习路径，循序渐进掌握项目精髓</span>
        </div>
        <div className="cg-map-topbar-right">
          {progress && (
            <ProgressPill label="总体进度" value={progress.overall_percent} />
          )}
        </div>
      </div>

      {/* Stage map (flow chain) */}
      <section className="cg-map-stages">
        <FlowChain
          steps={Object.entries(STAGE_LABELS).map(([key, label], i) => ({
            title: `Stage ${STAGE_NUMBERS[i]}`,
            note: label,
            icon: (
              <span
                className={`cg-map-stage-dot ${
                  progress?.stages?.[key]?.complete ? 'is-done' : ''
                } ${progress?.stages?.[key]?.visited ? 'is-visited' : ''}`}
                onClick={() => navigate(STAGE_ROUTES[key])}
              >
                {STAGE_NUMBERS[i]}
              </span>
            ),
          }))}
          activeIndex={_activeIndex(progress?.stages)}
        />
      </section>

      {/* Main grid: 3 panels */}
      <div className="cg-map-grid">
        {/* Left: Progress overview */}
        <ParchmentPanel title="学习进度总览" icon={<BookOpen size={20} />} tone="blue">
          <div className="cg-map-progress-stats">
            <_StatItem icon={<Star size={18} />} label="总进度" value={`${progress?.overall_percent ?? 0}%`} />
            <_StatItem icon={<BookOpen size={18} />} label="已学阶段" value={`${_completedCount(progress?.stages)} / 4`} />
            <_StatItem icon={<Clock size={18} />} label="学习时长" value={_formatMinutes(progress?.total_time_seconds ?? 0)} />
            <_StatItem icon={<Zap size={18} />} label="活跃天数" value={`${progress?.days_active ?? 0} 天`} />
          </div>
          {/* Per-stage bars */}
          <div className="cg-map-stage-bars">
            {Object.entries(STAGE_LABELS).map(([key, label]) => {
              const s = progress?.stages?.[key]
              return (
                <div key={key} className="cg-map-bar-row">
                  <span>{label}</span>
                  <div className="cg-map-bar">
                    <i style={{ width: `${_stagePercent(s)}%` }} />
                  </div>
                  <small>{s?.complete ? '✓' : `${Math.round(_stagePercent(s))}%`}</small>
                </div>
              )
            })}
          </div>
        </ParchmentPanel>

        {/* Center: Recommended path */}
        <ParchmentPanel title="推荐学习路径" icon={<Map size={20} />} tone="green">
          <div className="cg-map-path-tabs">
            {(['quick', 'standard', 'deep'] as const).map((lv) => (
              <button
                key={lv}
                className={pathLevel === lv ? 'active' : ''}
                onClick={() => setPathLevel(lv)}
              >
                {lv === 'quick' ? '快速' : lv === 'standard' ? '默认路径' : '深度'}
              </button>
            ))}
          </div>
          <div className="cg-map-path-list">
            {path?.steps.map((step: LearningPathStep, i: number) => (
              <div
                key={step.stage + i}
                className={`cg-map-path-item ${step.status === 'done' ? 'is-done' : ''}`}
                onClick={() => navigate(STAGE_ROUTES[step.stage] || '/')}
              >
                <em>{step.action === 'learn' ? '学' : step.action === 'skim' ? '览' : '复'}</em>
                <div>
                  <strong>{step.title}</strong>
                  <small>{step.description}</small>
                </div>
                <span>≈{step.estimated_minutes}min</span>
                <ChevronRight size={16} />
              </div>
            ))}
          </div>
          {path && (
            <div className="cg-map-path-total">
              预计总时长: <b>{path.total_minutes} 分钟</b>
            </div>
          )}
        </ParchmentPanel>

        {/* Right: Achievements + Hint */}
        <div className="cg-map-right-col">
          <ParchmentPanel title="成就徽章" icon={<Trophy size={20} />} tone="amber">
            <div className="cg-map-badges">
              {badges.map((badge: LearningBadge) => (
                <div
                  key={badge.id}
                  className={`cg-map-badge ${badge.unlocked ? 'is-unlocked' : ''}`}
                  title={badge.description}
                >
                  <PixelAsset
                    asset={badge.icon as any}
                    alt={badge.title}
                    className="cg-map-badge-icon"
                  />
                  <small>{badge.title}</small>
                </div>
              ))}
            </div>
          </ParchmentPanel>

          {/* Mentor hint */}
          <div className="cg-map-hint">
            <PixelAsset asset="mentorRunner" alt="导师" className="cg-map-hint-mentor" />
            <SpeechBubble>
              {path?.mentor_hint || '开始你的代码探索之旅！'}
            </SpeechBubble>
          </div>
        </div>
      </div>
    </StageShell>
  )
}

// --- Helpers ---

function _StatItem({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="cg-map-stat">
      {icon}
      <span>{value}</span>
      <small>{label}</small>
    </div>
  )
}

function _completedCount(stages: Record<string, any> | undefined): number {
  if (!stages) return 0
  return Object.values(stages).filter((s: any) => s?.complete).length
}

function _activeIndex(stages: Record<string, any> | undefined): number {
  if (!stages) return 0
  const order = ['overview', 'mainflow', 'showcase', 'takeaway']
  for (let i = 0; i < order.length; i++) {
    if (!stages[order[i]]?.complete) return i
  }
  return order.length - 1
}

function _stagePercent(s: any): number {
  if (!s) return 0
  if (s.complete) return 100
  if (!s.visited) return 0
  // Partial: based on time ratio
  const thresholds: Record<string, number> = {
    overview: 30, mainflow: 60, showcase: 90, takeaway: 60,
  }
  const threshold = 60 // fallback
  return Math.min(100, (s.time_spent_seconds / threshold) * 100)
}

function _formatMinutes(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`
  const m = Math.floor(seconds / 60)
  if (m < 60) return `${m}m`
  const h = Math.floor(m / 60)
  return `${h}h${m % 60}m`
}
