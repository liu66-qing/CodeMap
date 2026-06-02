import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  api,
  type ArchitectureSummary,
  type QuickstartInfo,
  type ModuleMap,
  type LearningPath,
  type RepoSummary,
} from '../services/api'
import './Overview.css'
import overviewBg from '../assets/pixel/backgrounds/overview-morning.png'
import {
  overviewAssets,
  stageAssets,
} from '../assets/pixel/stage-library'

interface MentalModelItem {
  title: string
  description: string
  iconChar: string
}

interface ReadingStep {
  step: number
  title: string
  description: string
  filePath?: string
  githubUrl?: string
}

export default function Overview() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [repos, setRepos] = useState<RepoSummary[]>([])
  const [repoId, setRepoId] = useState('')
  const [arch, setArch] = useState<ArchitectureSummary | null>(null)
  const [quickstart, setQuickstart] = useState<QuickstartInfo | null>(null)
  const [moduleMap, setModuleMap] = useState<ModuleMap | null>(null)
  const [learning, setLearning] = useState<LearningPath | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.listRepos().then((r) => {
      const list = r.repositories || []
      setRepos(list)
      const wanted = searchParams.get('repo')
      const ids = list.map((x) => x.repo_id)
      setRepoId(wanted && ids.includes(wanted) ? wanted : ids[0] || '')
    }).catch(() => {})
  }, [searchParams])

  useEffect(() => {
    if (!repoId) return
    setLoading(true)
    Promise.all([
      api.getArchitecture(repoId).catch(() => null),
      api.getQuickstart(repoId).catch(() => null),
      api.getModules(repoId).catch(() => null),
      api.getLearningPath(repoId).catch(() => null),
    ]).then(([ar, qs, mm, lp]) => {
      setArch(ar?.architecture || null)
      setQuickstart(qs?.quickstart || null)
      setModuleMap(mm?.module_map || null)
      setLearning(lp?.learning_path || null)
    }).finally(() => setLoading(false))
  }, [repoId])

  const positioning = useMemo(() => {
    if (arch?.summary) return arch.summary
    if (loading) return '正在生成一句话定位...'
    return '这个仓库是一个帮助开发者快速构建与扩展开源智能体应用的框架。'
  }, [arch, loading])

  const coreProblem = useMemo(() => {
    if (arch?.patterns?.length) {
      const p = arch.patterns[0]
      return `${p.name}: ${p.evidence}`
    }
    if (arch?.summary) return arch.summary
    return '帮助团队在多模型、多 Agent 场景下快速搭建可扩展的智能体应用，避免重复造轮子。'
  }, [arch])

  const mentalModel = useMemo((): MentalModelItem[] => {
    const layers = arch?.layers || []
    const stack = quickstart?.stack?.join(' / ') || arch?.patterns?.[0]?.name || '模块化代码组织'
    const layerNames = layers.slice(0, 3).map((l) => l.name).join(' -> ') || '数据 -> 逻辑 -> 接口'
    return [
      {
        title: '它是什么',
        description: arch?.summary?.split('。')[0] || `基于 ${stack} 的模块化框架。`,
        iconChar: '▣',
      },
      {
        title: '为谁服务',
        description: layers[0]?.description || '面向开发者、团队与企业，构建与扩展智能体能力。',
        iconChar: '♟',
      },
      {
        title: '怎么工作',
        description: `通过 ${arch?.module_count ?? (layers.length || '多个')} 个核心模块协同：${layerNames}。`,
        iconChar: '⚙',
      },
    ]
  }, [arch, quickstart])

  const readingOrder = useMemo((): ReadingStep[] => {
    const steps: ReadingStep[] = [
      { step: 1, title: 'README', description: '了解项目定位与价值' },
    ]
    if (moduleMap?.cards?.length) {
      steps.push({
        step: 2,
        title: '目录结构',
        description: `认识整体模块，${moduleMap.meta.cards} 张卡片 / ${moduleMap.meta.layers} 层`,
      })
    } else {
      steps.push({ step: 2, title: '目录结构', description: '认识整体模块与组织' })
    }
    const entry = quickstart?.entrypoints?.[0]
    steps.push({
      step: 3,
      title: '示例代码',
      description: entry ? `从 ${entry} 开始读起` : '通过示例快速上手',
      filePath: entry,
    })
    const firstStep = learning?.steps?.[0]
    steps.push({
      step: 4,
      title: '核心模块',
      description: firstStep ? `首先看 ${firstStep.symbol}` : '深入关键概念与接口',
      filePath: firstStep?.file_path,
    })
    return steps
  }, [quickstart, moduleMap, learning])

  const repoMeta = useMemo(() => {
    const summary = repos.find((r) => r.repo_id === repoId)
    return {
      fullName: repoId || 'letta-ai/letta',
      nodes: summary?.nodes ?? 0,
      commits: summary?.commits ?? 0,
    }
  }, [repos, repoId])

  const tasks = [
    { text: '读完一句话定位', completed: !!arch?.summary || !loading },
    { text: '理解它解决的核心问题', completed: !!arch?.patterns?.length },
    { text: '按推荐顺序规划起步路径', completed: readingOrder.length >= 4 },
  ]
  const completedCount = tasks.filter((t) => t.completed).length
  const stageProgress = Math.round((completedCount / tasks.length) * 100)
  const filledBlocks = Math.round((stageProgress / 100) * 6)

  return (
    <div className="ov-page">
      {repos.length > 1 && (
        <div className="ov-repo-row">
          <span>当前仓库:</span>
          <select value={repoId} onChange={(e) => setRepoId(e.target.value)}>
            {repos.map((r) => (
              <option key={r.repo_id} value={r.repo_id}>{r.repo_id}</option>
            ))}
          </select>
        </div>
      )}

      <section className="ov-hero" style={{ backgroundImage: `url(${overviewBg})` }}>
        <div className="ov-hero-overlay" />
        <div className="ov-topbar">
          <button className="ov-back" onClick={() => navigate('/')}>
            <span className="ov-back-arrow">←</span>
            <span>返回学习地图</span>
          </button>
          <div className="ov-stage-title">
            <img className="ov-stage-sign" src={stageAssets.woodArrowSign} alt="" />
            <h1><span>Stage 1</span><b>·</b><span>先看门道</span></h1>
            <p className="ov-subtitle">在读代码之前，先搞清这个仓库是做什么的、解决什么问题、该从哪里开始看。</p>
          </div>
          <div className="ov-progress-pill">
            <img className="ov-progress-avatar" src={overviewAssets.mentor} alt="" />
            <span className="ov-progress-label">当前进度</span>
            <div className="ov-progress-bar">
              {Array.from({ length: 6 }).map((_, i) => (
                <span key={i} className={i < filledBlocks ? 'on' : ''} />
              ))}
            </div>
            <strong>{stageProgress}%</strong>
          </div>
        </div>

        <div className="ov-hero-ground">
          <div className="ov-hero-mentor">
            <div className="ov-bubble">
              <strong>嗨！欢迎来到学习地图的第一站。</strong>
              <span>一切冒险的开始，先了解它，才能走得更远！</span>
            </div>
            <img className="ov-farm-mentor" src={overviewAssets.mentor} alt="田园探索导师" />
          </div>
          <div className="ov-board">
            <img className="ov-board-art" src={overviewAssets.woodBoard} alt="" />
            <div className="ov-board-content">
              <div className="ov-board-tag">一句话定位</div>
              <p className="ov-board-text">{positioning}</p>
              <div className="ov-board-meta">
                <span>仓库 {repoMeta.fullName}</span>
                <span>{repoMeta.nodes} 节点 · {repoMeta.commits} 提交</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="ov-grid ov-grid--top">
        <article className="ov-card ov-card--problem">
          <img className="ov-card-decor ov-card-decor--stones" src={overviewAssets.stones} alt="" />
          <header>
            <span className="ov-icon ov-icon--problem">◎</span>
            <h2>它解决的核心问题</h2>
          </header>
          <p>{coreProblem}</p>
        </article>

        <article className="ov-card ov-card--mental">
          <img className="ov-card-decor ov-card-decor--flowers" src={overviewAssets.flowers} alt="" />
          <header>
            <span className="ov-icon ov-icon--mental">✦</span>
            <h2>三步建立整体心智模型</h2>
          </header>
          <div className="ov-mental">
            {mentalModel.map((m) => (
              <div className="ov-mental-item" key={m.title}>
                <span className="ov-mental-icon">{m.iconChar}</span>
                <strong>{m.title}</strong>
                <small>{m.description}</small>
              </div>
            ))}
          </div>
        </article>

        <article className="ov-card ov-card--reading">
          <img className="ov-card-decor ov-card-decor--sign" src={overviewAssets.sign} alt="" />
          <header>
            <span className="ov-icon ov-icon--reading">↳</span>
            <h2>推荐起步顺序</h2>
          </header>
          <ol className="ov-route">
            {readingOrder.map((s, i) => (
              <li key={s.step} className={i === readingOrder.length - 1 ? 'last' : ''}>
                <span className="ov-route-num">{s.step}</span>
                <div className="ov-route-body">
                  <strong>{s.title}</strong>
                  <small>{s.description}</small>
                </div>
              </li>
            ))}
          </ol>
        </article>
      </section>

      <section className="ov-grid ov-grid--bottom">
        <article className="ov-card ov-card--gain">
          <img className="ov-card-decor ov-card-decor--grass" src={overviewAssets.grass} alt="" />
          <header>
            <span className="ov-icon ov-icon--gain">★</span>
            <h2>看完这一页你会获得</h2>
          </header>
          <div className="ov-gain">
            <div className="ov-gain-item"><img src={stageAssets.badgeMap} alt="" /><strong>知道仓库定位</strong></div>
            <div className="ov-gain-item"><span>◎</span><strong>抓住核心问题</strong></div>
            <div className="ov-gain-item"><img src={stageAssets.badgeClipboard} alt="" /><strong>建立整体认知</strong></div>
          </div>
        </article>

        <article className="ov-card ov-card--quest">
          <img className="ov-card-decor ov-card-decor--chest" src={overviewAssets.chest} alt="" />
          <header>
            <span className="ov-icon ov-icon--quest">▣</span>
            <h2>本关任务 ({completedCount}/{tasks.length})</h2>
          </header>
          <ul className="ov-quest">
            {tasks.map((t) => (
              <li key={t.text} className={t.completed ? 'done' : ''}>
                <span className="ov-quest-dot">{t.completed ? '✓' : ''}</span>
                <span>{t.text}</span>
              </li>
            ))}
          </ul>
        </article>

        <article className="ov-card ov-card--next">
          <img className="ov-card-decor ov-card-decor--bridge" src={overviewAssets.bridge} alt="" />
          <img className="ov-card-decor ov-card-decor--flag" src={overviewAssets.flag} alt="" />
          <div className="ov-next-badge">2</div>
          <header>
            <span className="ov-icon ov-icon--next">▶</span>
            <h2>下一站：跑通主线</h2>
          </header>
          <p>沿着主线流程，把项目从环境到运行完整跑通！</p>
          <button
            className="ov-cta"
            onClick={() => navigate(`/mainflow${repoId ? `?repo=${encodeURIComponent(repoId)}` : ''}`)}
          >
            进入下一步 →
          </button>
        </article>
      </section>
    </div>
  )
}
