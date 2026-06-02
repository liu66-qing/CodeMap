import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Progress, TextInput } from '@mantine/core'
import { ArrowRight, Copy, Flame, Gift, Github, RefreshCcw, Star } from 'lucide-react'
import { api, type RepoSummary } from '../services/api'
import heroSkyBg from '../assets/pixel/backgrounds/home-hero-combined.png'
import journeyScene from '../assets/pixel/backgrounds/home-journey-scene.png'
import characterSheet from '../assets/pixel/characters/kenney-characters.png'
import { overviewAssets, stageAssets } from '../assets/pixel/stage-library'

type Phase = 'idle' | 'analyzing' | 'done'

type JourneyNode = {
  num: string
  title: string
  desc: string
  path: string
  left: number
  top: number
  mascot: string
  mascotClass: string
}

const hotRepos = ['facebook/react', 'vuejs/core', 'microsoft/vscode', 'langchain-ai/langchain']

const journeyNodes: JourneyNode[] = [
  {
    num: '1',
    title: '先看门道',
    desc: '快速了解仓库定位、技术栈与整体结构。',
    path: '/overview',
    left: 12,
    top: 54,
    mascot: overviewAssets.mentor,
    mascotClass: 'is-guide',
  },
  {
    num: '2',
    title: '跑通主线',
    desc: '运行项目，理解主线执行流程与关键逻辑。',
    path: '/mainflow',
    left: 36,
    top: 39,
    mascot: stageAssets.mentorRunner,
    mascotClass: 'is-runner',
  },
  {
    num: '3',
    title: '拆它绝活',
    desc: '分析核心模块，拆解关键实现技巧与设计亮点。',
    path: '/showcase',
    left: 60,
    top: 54,
    mascot: stageAssets.mentorMiner,
    mascotClass: 'is-miner',
  },
  {
    num: '4',
    title: '抄走一招',
    desc: '提炼可复用的思路与技巧，拿去解决自己的问题。',
    path: '/takeaway',
    left: 84,
    top: 39,
    mascot: stageAssets.mentorTrophy,
    mascotClass: 'is-trophy',
  },
]

const rewardCards = [
  { icon: '🗺️', title: '全局视野', text: '快速建立对仓库的整体认知' },
  { icon: '▶️', title: '跑通思维', text: '理解项目运行逻辑' },
  { icon: '🎯', title: '硬核拆解', text: '掌握关键实现技巧' },
  { icon: '💎', title: '迁移复用', text: '提炼可复用能力' },
]

export default function Home() {
  const navigate = useNavigate()
  const [url, setUrl] = useState('')
  const [phase, setPhase] = useState<Phase>('idle')
  const [repos, setRepos] = useState<RepoSummary[]>([])
  const [newRepoId, setNewRepoId] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    api.listRepos().then((r) => setRepos(r.repositories || [])).catch(() => {})
  }, [])

  async function startExplore(repoUrl = url) {
    if (!repoUrl.trim() || phase === 'analyzing') return
    setPhase('analyzing')
    setError('')
    try {
      const res = await api.analyzeRepo({ repoUrl: repoUrl.trim() })
      setNewRepoId(res.repo_id)
      const poll = window.setInterval(async () => {
        const list = await api.listRepos()
        const found = (list.repositories || []).find(
          (r) => r.repo_id === res.repo_id && r.nodes > 0
        )
        if (found) {
          window.clearInterval(poll)
          setRepos(list.repositories || [])
          setPhase('done')
        }
      }, 4000)
      window.setTimeout(() => window.clearInterval(poll), 180000)
    } catch (e) {
      setError(e instanceof Error ? e.message : '分析失败，请稍后重试')
      setPhase('idle')
    }
  }

  function useHotRepo(repo: string) {
    setUrl(`https://github.com/${repo}`)
  }

  return (
    <main className="cg-home">
      <div className="cg-upper" style={{ backgroundImage: `url(${heroSkyBg})` }}>
        <div className="home-inner">
          <section className="cg-hero" aria-label="CodeGraph 首页">
            <div className="cg-tree-badge" />
            <h1 className="cg-pixel-title" aria-label="CodeGraph 让每个老乡看懂代码！">
              <span className="cg-brand-word">CodeGraph</span>
              <span className="cg-title-cn">让每个老乡<span>看懂代码！</span></span>
            </h1>
            <p className="cg-subtitle">好仓库不是拿来硬啃的，带你彻底读懂一个 github 仓库</p>

            <div className="cg-search-decor cg-search-decor-left" aria-hidden="true">
              <img src={overviewAssets.mentor} alt="" className="cg-decor-guide" />
              <img src={overviewAssets.stones} alt="" className="cg-decor-stones" />
              <img src={overviewAssets.flowers} alt="" className="cg-decor-flowers" />
            </div>
            <div className="cg-search-decor cg-search-decor-right" aria-hidden="true">
              <img src={stageAssets.mentorTrophy} alt="" className="cg-decor-trophy" />
              <img src={stageAssets.campfireCrates} alt="" className="cg-decor-camp" />
              <img src={overviewAssets.grass} alt="" className="cg-decor-grass" />
            </div>

            <div className="cg-search-row">
              <TextInput
                value={url}
                onChange={(e) => setUrl(e.currentTarget.value)}
                onKeyDown={(e) => e.key === 'Enter' && startExplore()}
                placeholder="粘贴 GitHub 仓库地址，例如：facebook/react"
                leftSection={<Github size={30} strokeWidth={3} />}
                rightSection={<Copy size={23} />}
                disabled={phase === 'analyzing'}
                className="cg-repo-input"
                aria-label="GitHub 仓库地址"
              />
              <Button
                className="cg-start-button"
                loading={phase === 'analyzing'}
                disabled={!url.trim() || phase === 'analyzing'}
                onClick={() => startExplore()}
                rightSection={<ArrowRight size={27} strokeWidth={3.2} />}
              >
                开始探索
              </Button>
            </div>

            {error && <p className="cg-error">{error}</p>}

            <div className="cg-hot-row">
              <span>热门仓库：</span>
              {hotRepos.map((repo) => (
                <button key={repo} type="button" onClick={() => useHotRepo(repo)}>
                  {repo}
                </button>
              ))}
              <button type="button" className="cg-refresh" onClick={() => useHotRepo('facebook/react')}>
                <RefreshCcw size={16} /> 换一换
              </button>
            </div>
          </section>

          <section className="cg-journey-map" style={{ backgroundImage: `url(${journeyScene})` }} aria-label="学习路径图">
            <svg className="cg-journey-arrows" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
              <defs>
                <marker id="cg-arrowhead" viewBox="0 0 10 10" markerWidth="7" markerHeight="7" refX="8" refY="5" orient="auto" markerUnits="strokeWidth">
                  <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(255,255,255,0.98)" />
                </marker>
              </defs>
              <path
                d={`M ${journeyNodes[0].left} ${journeyNodes[0].top} Q ${(journeyNodes[0].left + journeyNodes[1].left) / 2} ${journeyNodes[0].top - 4}, ${journeyNodes[1].left} ${journeyNodes[1].top} T ${journeyNodes[2].left} ${journeyNodes[2].top} T ${journeyNodes[3].left} ${journeyNodes[3].top}`}
                stroke="rgba(255,255,255,0.98)"
                strokeLinecap="round"
                fill="none"
                vectorEffect="non-scaling-stroke"
                markerEnd="url(#cg-arrowhead)"
                style={{ strokeWidth: 5, strokeDasharray: '12 10' } as React.CSSProperties}
              />
            </svg>
            {journeyNodes.map((node) => (
              <button
                key={node.num}
                type="button"
                className={`cg-journey-node ${node.mascotClass}`}
                style={{ left: `${node.left}%`, top: `${node.top}%` }}
                onClick={() => navigate(node.path)}
              >
                <span className="cg-node-num">{node.num}</span>
                <strong>{node.title}</strong>
                <small>{node.desc}</small>
              </button>
            ))}
          </section>
        </div>
      </div>

      <section className="cg-lower" aria-label="学习信息">
        <div className="home-inner">
          <div className="cg-bottom-grid">
            <article className="cg-panel cg-recommend">
              <header>
                <div>
                  <Star size={31} fill="#65b94c" />
                  <h2>推荐仓库</h2>
                </div>
                <button type="button">查看更多 ›</button>
              </header>
              <div className="cg-repo-list">
                <button type="button" onClick={() => useHotRepo('facebook/react')}>
                  <span className="cg-repo-icon react">⚛</span>
                  <span>
                    <strong>facebook / react</strong>
                    <small>用于构建用户界面的 JavaScript 库</small>
                  </span>
                  <em><Flame size={15} fill="#ff7a2e" />196.7k</em>
                </button>
                <button type="button" onClick={() => useHotRepo('microsoft/vscode')}>
                  <span className="cg-repo-icon vscode">⌁</span>
                  <span>
                    <strong>microsoft / vscode</strong>
                    <small>开源的轻量级代码编辑器</small>
                  </span>
                  <em><Flame size={15} fill="#ff7a2e" />83.2k</em>
                </button>
              </div>
            </article>

            <article className="cg-panel cg-rewards">
              <header>
                <div>
                  <Gift size={29} color="#cf7826" />
                  <h2>你将获得</h2>
                </div>
              </header>
              <div className="cg-reward-grid">
                {rewardCards.map((card) => (
                  <div key={card.title} className="cg-reward-card">
                    <span>{card.icon}</span>
                    <strong>{card.title}</strong>
                    <small>{card.text}</small>
                  </div>
                ))}
              </div>
            </article>

            <article className="cg-panel cg-progress">
              <header>
                <div>
                  <span className="cg-flag">⚑</span>
                  <h2>当前进度</h2>
                </div>
                <button type="button" onClick={() => navigate('/overview')}>查看详情 ›</button>
              </header>
              <div className="cg-progress-main">
                <div className="cg-avatar" style={{ backgroundImage: `url(${characterSheet})` }} />
                <div className="cg-progress-copy">
                  <div className="cg-progress-meta">
                    <span>总体进度</span>
                    <span>已完成 2 / 4 步</span>
                  </div>
                  <div className="cg-progress-number">
                    <strong>42%</strong>
                    <Progress value={42} radius="xl" size={12} />
                  </div>
                </div>
              </div>
              <div className="cg-current-stage">
                <div>
                  <strong>当前阶段：跑通主线</strong>
                  <p>
                    {phase === 'analyzing'
                      ? '正在为你生成仓库学习路线...'
                      : phase === 'done' && newRepoId
                        ? '路线已生成，可以继续学习。'
                        : '正在理解主线执行流程与关键逻辑'}
                  </p>
                  <small>预计 25 分钟可完成</small>
                </div>
                <Button className="cg-continue-button" onClick={() => navigate('/mainflow')}>
                  继续学习
                </Button>
              </div>
            </article>
          </div>
        </div>
      </section>
    </main>
  )
}
