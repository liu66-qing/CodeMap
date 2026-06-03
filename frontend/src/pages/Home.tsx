import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Progress, TextInput } from '@mantine/core'
import { ArrowRight, Copy, Flame, Gift, Github, RefreshCcw, Star } from 'lucide-react'
import { api, type RepoSummary } from '../services/api'
import { useLanguage } from '../i18n/LanguageContext'
import heroSkyBg from '../assets/pixel/backgrounds/home-hero-combined.png'
import journeyScene from '../assets/pixel/backgrounds/home-journey-scene.png'
import characterSheet from '../assets/pixel/characters/kenney-characters.png'
import { overviewAssets, stageAssets } from '../assets/pixel/stage-library'

type Phase = 'idle' | 'analyzing' | 'done'

type JourneyNode = {
  num: string
  titleKey: string
  descKey: string
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
    titleKey: 'home.node1.title',
    descKey: 'home.node1.desc',
    path: '/overview',
    left: 12,
    top: 54,
    mascot: overviewAssets.mentor,
    mascotClass: 'is-guide',
  },
  {
    num: '2',
    titleKey: 'home.node2.title',
    descKey: 'home.node2.desc',
    path: '/mainflow',
    left: 36,
    top: 39,
    mascot: stageAssets.mentorRunner,
    mascotClass: 'is-runner',
  },
  {
    num: '3',
    titleKey: 'home.node3.title',
    descKey: 'home.node3.desc',
    path: '/showcase',
    left: 60,
    top: 54,
    mascot: stageAssets.mentorMiner,
    mascotClass: 'is-miner',
  },
  {
    num: '4',
    titleKey: 'home.node4.title',
    descKey: 'home.node4.desc',
    path: '/takeaway',
    left: 84,
    top: 39,
    mascot: stageAssets.mentorTrophy,
    mascotClass: 'is-trophy',
  },
]

const rewardCards = [
  { icon: '🗺️', titleKey: 'home.reward1.title', textKey: 'home.reward1.text' },
  { icon: '▶️', titleKey: 'home.reward2.title', textKey: 'home.reward2.text' },
  { icon: '🎯', titleKey: 'home.reward3.title', textKey: 'home.reward3.text' },
  { icon: '💎', titleKey: 'home.reward4.title', textKey: 'home.reward4.text' },
]

export default function Home() {
  const navigate = useNavigate()
  const { lang, t } = useLanguage()
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
      setError(e instanceof Error ? e.message : t('action.retry'))
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
          <section
            className={`cg-hero ${lang === 'en' ? 'is-english' : 'is-chinese'}`}
            aria-label={t('home.heroAria')}
          >
            <div className="cg-tree-badge" />
            <h1
              className={`cg-pixel-title ${lang === 'en' ? 'is-english' : 'is-chinese'}`}
              aria-label={t('home.titleAria')}
            >
              {lang === 'en' ? (
                <>
                  <span className="cg-code-marks" aria-hidden="true">&lt;/&gt;</span>
                  <span className="cg-brand-word">CodeMap</span>
                  <span className="cg-code-marks" aria-hidden="true">&lt;/&gt;</span>
                  <span className="cg-title-en-line">Helping Every</span>
                  <span className="cg-title-en-line is-accent">Hometown Hero</span>
                  <span className="cg-title-en-line">Understand Code!</span>
                </>
              ) : (
                <>
                  <span className="cg-brand-word">CodeMap</span>
                  <span className="cg-title-cn">{t('home.title.cn')}<span>{t('home.title.cn2')}</span></span>
                </>
              )}
            </h1>
            <p className="cg-subtitle">{t('home.subtitle')}</p>

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
                placeholder={t('home.search.placeholder')}
                leftSection={<Github size={30} strokeWidth={3} />}
                rightSection={<Copy size={23} />}
                disabled={phase === 'analyzing'}
                className="cg-repo-input"
                aria-label={t('home.search.ariaLabel')}
              />
              <Button
                className="cg-start-button"
                loading={phase === 'analyzing'}
                disabled={!url.trim() || phase === 'analyzing'}
                onClick={() => startExplore()}
                rightSection={<ArrowRight size={27} strokeWidth={3.2} />}
              >
                {t('home.startExplore')}
              </Button>
            </div>

            {error && <p className="cg-error">{error}</p>}

            <div className="cg-hot-row">
              <span>{t('home.hotRepos')}</span>
              {hotRepos.map((repo) => (
                <button key={repo} type="button" onClick={() => useHotRepo(repo)}>
                  {repo}
                </button>
              ))}
              <button type="button" className="cg-refresh" onClick={() => useHotRepo('facebook/react')}>
                <RefreshCcw size={16} /> {t('home.shuffle')}
              </button>
            </div>
          </section>

          <section className="cg-journey-map" style={{ backgroundImage: `url(${journeyScene})` }} aria-label={t('home.journeyAria')}>
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
                <strong>{t(node.titleKey)}</strong>
                <small>{t(node.descKey)}</small>
              </button>
            ))}
          </section>
        </div>
      </div>

      <section className="cg-lower" aria-label={t('home.lowerAria')}>
        <div className="home-inner">
          <div className="cg-bottom-grid">
            <article className="cg-panel cg-recommend">
              <header>
                <div>
                  <Star size={31} fill="#65b94c" />
                  <h2>{t('home.recommend.title')}</h2>
                </div>
                <button type="button">{t('action.viewMore')}</button>
              </header>
              <div className="cg-repo-list">
                <button type="button" onClick={() => useHotRepo('facebook/react')}>
                  <span className="cg-repo-icon react">⚛</span>
                  <span>
                    <strong>facebook / react</strong>
                    <small>{t('home.recommend.react')}</small>
                  </span>
                  <em><Flame size={15} fill="#ff7a2e" />196.7k</em>
                </button>
                <button type="button" onClick={() => useHotRepo('microsoft/vscode')}>
                  <span className="cg-repo-icon vscode">⌁</span>
                  <span>
                    <strong>microsoft / vscode</strong>
                    <small>{t('home.recommend.vscode')}</small>
                  </span>
                  <em><Flame size={15} fill="#ff7a2e" />83.2k</em>
                </button>
              </div>
            </article>

            <article className="cg-panel cg-rewards">
              <header>
                <div>
                  <Gift size={29} color="#cf7826" />
                  <h2>{t('home.rewards.title')}</h2>
                </div>
              </header>
              <div className="cg-reward-grid">
                {rewardCards.map((card) => (
                  <div key={card.titleKey} className="cg-reward-card">
                    <span>{card.icon}</span>
                    <strong>{t(card.titleKey)}</strong>
                    <small>{t(card.textKey)}</small>
                  </div>
                ))}
              </div>
            </article>

            <article className="cg-panel cg-progress">
              <header>
                <div>
                  <span className="cg-flag">⚑</span>
                  <h2>{t('home.progress.title')}</h2>
                </div>
                <button type="button" onClick={() => navigate('/overview')}>{t('action.viewDetails')}</button>
              </header>
              <div className="cg-progress-main">
                <div className="cg-avatar" style={{ backgroundImage: `url(${characterSheet})` }} />
                <div className="cg-progress-copy">
                  <div className="cg-progress-meta">
                    <span>{t('home.progress.overall')}</span>
                    <span>{t('home.progress.steps')}</span>
                  </div>
                  <div className="cg-progress-number">
                    <strong>42%</strong>
                    <Progress value={42} radius="xl" size={12} />
                  </div>
                </div>
              </div>
              <div className="cg-current-stage">
                <div>
                  <strong>{t('home.progress.currentStage')}</strong>
                  <p>
                    {phase === 'analyzing'
                      ? t('home.progress.analyzing')
                      : phase === 'done' && newRepoId
                        ? t('home.progress.done')
                        : t('home.progress.idle')}
                  </p>
                  <small>{t('home.progress.eta')}</small>
                </div>
                <Button className="cg-continue-button" onClick={() => navigate('/mainflow')}>
                  {t('action.continue')}
                </Button>
              </div>
            </article>
          </div>
        </div>
      </section>
    </main>
  )
}
