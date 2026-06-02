import { useNavigate } from 'react-router-dom'
import type { ReactNode } from 'react'
import {
  BookOpen,
  CheckCircle2,
  ChevronRight,
  Clock,
  Lock,
  Map as MapIcon,
  Medal,
  Shield,
  Sparkles,
  Star,
} from 'lucide-react'
import journeyScene from '../assets/pixel/backgrounds/home-journey-scene.png'
import characterSheet from '../assets/pixel/characters/kenney-characters.png'
import { stageAssets, overviewAssets } from '../assets/pixel/stage-library'

const mapNodes = [
  {
    id: 1,
    title: '先看门道',
    desc: 'Stage 1 · 先看门道\n绕明白，先踏门槛',
    label: '先看 1',
    status: 'done',
    left: 8,
    top: 62,
    asset: overviewAssets.mentor,
    path: '/overview',
  },
  {
    id: 2,
    title: '跑通主线',
    desc: '运行项目，理解主线\n执行流程与关键逻辑',
    label: '跑通主线',
    status: 'active',
    left: 34,
    top: 56,
    asset: stageAssets.mentorRunner,
    path: '/mainflow',
  },
  {
    id: 3,
    title: '拆它绝活',
    desc: '分析核心模块，拆解\n关键实现技巧与设计亮点',
    label: '拆它绝活',
    status: 'pending',
    left: 58,
    top: 50,
    asset: stageAssets.mentorMiner,
    path: '/showcase',
  },
  {
    id: 4,
    title: '抄走一招',
    desc: '提炼可复用的思路与技巧，\n拿去解决自己的问题',
    label: '抄走一招',
    status: 'pending',
    left: 82,
    top: 56,
    asset: stageAssets.mentorTrophy,
    path: '/takeaway',
  },
]

const routeSteps = [
  { id: 1, title: '先看门道', time: '20分钟', state: '已完成' },
  { id: 2, title: '跑通主线', time: '40分钟', state: '学习中' },
  { id: 3, title: '拆它绝活', time: '60分钟', state: '未开始' },
  { id: 4, title: '抄走一招', time: '30分钟', state: '未开始' },
]

const recentItems = [
  { title: 'Stage 1 · 先看门道', meta: '完成于 2024-05-24 14:30', state: '已完成' },
  { title: 'Stage 2 · 跑通主线', meta: '进行中 ...', state: '学习中' },
  { title: '快速开始：项目结构与目录概览', meta: '学习于 2024-05-24 10:15', state: '已完成' },
]

const badges = [
  { title: '初探者', desc: '完成第一个阶段', icon: 'portrait', unlocked: true },
  { title: '探索者', desc: '完成两个阶段', icon: 'medal', unlocked: true },
  { title: '分析师', desc: '完成拆解阶段', icon: 'sword', unlocked: true },
  { title: '实战派', desc: '完成实战项目', icon: 'lock', unlocked: false },
]

export default function LearningPathView() {
  const navigate = useNavigate()

  return (
    <main className="lm-page">
      <header className="lm-header">
        <div className="lm-title-row">
          <img src={stageAssets.badgeMap} alt="" className="lm-title-icon" />
          <div>
            <h1>学习地图</h1>
            <p>探索学习路径，循序渐进掌握项目精髓</p>
          </div>
        </div>
        <div className="lm-header-actions">
          <div className="lm-top-progress">
            <Star size={26} fill="#ffd866" color="#9a6a1e" />
            <div>
              <span>总体进度</span>
              <i><b /></i>
            </div>
            <strong>42%</strong>
          </div>
          <button type="button" className="lm-guide-btn">
            <BookOpen size={20} />
            学习指南
          </button>
        </div>
      </header>

      <section className="lm-map" style={{ backgroundImage: `url(${journeyScene})` }}>
        <svg className="lm-map-path" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <path d="M 9 70 C 22 58, 27 66, 34 62 S 52 54, 58 58 S 72 68, 82 62" />
        </svg>

        <div className="lm-location-pin">
          <span>您的位置</span>
          <strong>Stage 1 · 先看门道</strong>
        </div>

        {mapNodes.map((node) => (
          <button
            key={node.id}
            type="button"
            className={`lm-node lm-node-${node.status}`}
            style={{ left: `${node.left}%`, top: `${node.top}%` }}
            onClick={() => navigate(node.path)}
          >
            <img src={node.asset} alt="" />
            <em>{node.id}</em>
            <div>
              <strong>{node.label}</strong>
              <p>{node.desc}</p>
            </div>
          </button>
        ))}
      </section>

      <section className="lm-grid">
        <article className="lm-panel lm-progress-panel">
          <PanelHeader icon={<MapIcon size={22} />} title="学习进度总览" action="查看详情" />
          <div className="lm-progress-main">
            <img src={stageAssets.badgeMap} alt="" />
            <div>
              <span>总体进度</span>
              <strong>42%</strong>
            </div>
            <i><b /></i>
            <small>已完成 2 / 4 个阶段</small>
          </div>
          <div className="lm-stats">
            <StatCard icon="🧊" label="已学习知识点" value="28 / 68" />
            <StatCard icon="🕒" label="累计学习时长" value="12h 36m" />
            <StatCard icon="🧳" label="连续学习天数" value="5 天" />
          </div>
          <div className="lm-recent">
            <h3>最近学习</h3>
            {recentItems.map((item) => (
              <div key={item.title} className="lm-recent-item">
                <span className="lm-mini-avatar" />
                <div><strong>{item.title}</strong><small>{item.meta}</small></div>
                <em>{item.state}</em>
              </div>
            ))}
          </div>
        </article>

        <article className="lm-panel lm-route-panel">
          <PanelHeader icon={<Sparkles size={22} />} title="推荐学习路径" action="切换路径" />
          <div className="lm-tabs">
            <button type="button" className="active">默认路径</button>
            <button type="button">速通路径</button>
            <button type="button">深度路径</button>
          </div>
          <ol className="lm-route-list">
            {routeSteps.map((step) => (
              <li key={step.id} className={`lm-route-${step.state}`}>
                <span>{step.id}</span>
                <div>
                  <strong>{step.title}</strong>
                  <small>建议时长：{step.time}</small>
                </div>
                <em>{step.state}</em>
              </li>
            ))}
          </ol>
        </article>

        <div className="lm-right-stack">
          <article className="lm-panel lm-badges-panel">
            <PanelHeader icon={<Medal size={22} />} title="成就徽章" action="查看全部" />
            <div className="lm-badges">
              {badges.map((badge) => (
                <div key={badge.title} className={badge.unlocked ? '' : 'locked'}>
                  <BadgeIcon kind={badge.icon} />
                  <strong>{badge.title}</strong>
                  <small>{badge.desc}</small>
                </div>
              ))}
            </div>
          </article>

          <article className="lm-panel lm-tip-panel">
            <header>
              <Sparkles size={22} color="#d89a11" />
              <h2>学习小贴士</h2>
            </header>
            <div className="lm-tip-box">
              <p>建议每天坚持学习 30 分钟，循序渐进，效果更佳！</p>
              <p>遇到困难时，可以查看帮助中心或加入社区讨论。</p>
              <img src={stageAssets.mentorTrophy} alt="" />
            </div>
          </article>
        </div>
      </section>

      <style>{styles}</style>
    </main>
  )
}

function PanelHeader({ icon, title, action }: { icon: ReactNode; title: string; action: string }) {
  return (
    <header className="lm-panel-header">
      <span>{icon}</span>
      <h2>{title}</h2>
      <button type="button">{action}<ChevronRight size={14} /></button>
    </header>
  )
}

function StatCard({ icon, label, value }: { icon: string; label: string; value: string }) {
  return (
    <div className="lm-stat-card">
      <span>{icon}</span>
      <small>{label}</small>
      <strong>{value}</strong>
    </div>
  )
}

function BadgeIcon({ kind }: { kind: string }) {
  if (kind === 'portrait') return <img src={overviewAssets.mentor} alt="" />
  if (kind === 'sword') return <Shield size={42} color="#1e5caa" />
  if (kind === 'lock') return <Lock size={42} color="#717780" />
  return <img src={stageAssets.mentorTrophy} alt="" />
}

const styles = `
.lm-page{min-height:100vh;padding:22px 30px 24px;background:linear-gradient(180deg,#f8fbff 0%,#eef6ff 100%);overflow:auto;color:#071832}
.lm-header{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-bottom:14px}.lm-title-row{display:flex;align-items:center;gap:16px}.lm-title-icon{width:64px;height:64px;object-fit:contain;image-rendering:pixelated;filter:drop-shadow(2px 4px 0 rgba(12,28,54,.15))}.lm-title-row h1{margin:0;font-size:40px;line-height:1;font-weight:950;text-shadow:2px 2px 0 rgba(255,255,255,.8)}.lm-title-row p{margin:6px 0 0;color:#2c4566;font-size:15px;font-weight:750}
.lm-header-actions{display:flex;align-items:center;gap:18px}.lm-top-progress,.lm-guide-btn{height:62px;border:1px solid #c6d8ef;border-radius:10px;background:rgba(255,255,255,.92);box-shadow:0 8px 20px rgba(15,39,74,.07)}.lm-top-progress{width:330px;display:grid;grid-template-columns:38px 1fr auto;align-items:center;gap:14px;padding:10px 18px}.lm-top-progress span{font-size:13px;font-weight:850;color:#4a596b}.lm-top-progress i{display:block;height:10px;margin-top:8px;border-radius:999px;background:#e1e8f1;overflow:hidden}.lm-top-progress b{display:block;width:42%;height:100%;background:linear-gradient(90deg,#6bc657,#8f80d8)}.lm-top-progress strong{font-size:18px;font-weight:950}.lm-guide-btn{width:164px;display:flex;align-items:center;justify-content:center;gap:9px;border-color:#9fc2f1;color:#153b8c;font-size:17px;font-weight:950;cursor:pointer}
.lm-map{position:relative;height:335px;border:1px solid #88bce8;border-radius:10px;background-size:cover;background-position:center;image-rendering:pixelated;box-shadow:inset 0 1px 0 rgba(255,255,255,.5),0 12px 28px rgba(15,39,74,.12);overflow:hidden}.lm-map:after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(255,255,255,.06),rgba(255,255,255,0));pointer-events:none}.lm-map-path{position:absolute;left:6%;right:5%;bottom:46px;width:89%;height:130px;z-index:1;overflow:visible}.lm-map-path path{fill:none;stroke:rgba(255,255,255,.95);stroke-width:3.5;stroke-linecap:round;stroke-dasharray:2.2 2.2;filter:drop-shadow(0 2px 0 rgba(67,83,45,.35))}
.lm-location-pin{position:absolute;left:22px;top:34px;z-index:5;display:grid}.lm-location-pin span{justify-self:center;padding:7px 32px;border-radius:6px 6px 0 0;background:linear-gradient(180deg,#98d77a,#71bd61);color:#fff;font-size:12px;font-weight:950}.lm-location-pin strong{padding:10px 16px;border-radius:5px;background:#fff;color:#132238;box-shadow:0 3px 0 rgba(15,39,74,.18);font-size:14px}
.lm-node{position:absolute;z-index:3;width:152px;transform:translate(-50%,-50%);border:0;background:transparent;cursor:pointer;font-family:inherit;color:#071832}.lm-node>img{display:block;margin:0 auto -4px;max-width:76px;max-height:76px;object-fit:contain;image-rendering:pixelated;filter:drop-shadow(0 4px 0 rgba(42,32,20,.25))}.lm-node em{position:absolute;left:50%;top:58px;z-index:2;display:grid;place-items:center;width:38px;height:38px;transform:translateX(-50%);border-radius:50%;border:3px solid #fff;background:linear-gradient(180deg,#78c65b,#51a443);box-shadow:0 3px 0 #2d612b,0 0 12px rgba(88,183,73,.35);color:#fff;font-style:normal;font-size:20px;font-weight:950}.lm-node div{min-height:86px;padding:30px 10px 10px;border:2px solid #8b6b37;border-radius:5px;background:#fff8d8;box-shadow:3px 4px 0 rgba(58,45,31,.42),inset 0 0 0 2px rgba(255,255,255,.58)}.lm-node strong{display:block;font-size:16px;font-weight:950}.lm-node p{margin:6px 0 0;white-space:pre-line;color:#334155;font-size:11px;font-weight:750;line-height:1.35}.lm-node-active em{animation:lm-pulse 1.8s ease-in-out infinite}.lm-node-locked{filter:grayscale(.4);opacity:.88}.lm-node-locked div{background:#f0f2f4;border-color:#8f969e}@keyframes lm-pulse{0%,100%{box-shadow:0 3px 0 #2d612b,0 0 0 rgba(88,183,73,0)}50%{box-shadow:0 3px 0 #2d612b,0 0 18px rgba(88,183,73,.85)}}
.lm-grid{display:grid;grid-template-columns:1.05fr .9fr 1.25fr;gap:16px;margin-top:14px}.lm-panel{border:1px solid #c8d9eb;border-radius:10px;background:rgba(255,255,255,.9);box-shadow:0 8px 20px rgba(15,39,74,.06);padding:14px}.lm-progress-panel{background:linear-gradient(180deg,#fbfff2,#eff9e8);border-color:#b8d79a}.lm-route-panel{background:linear-gradient(180deg,#fffdf8,#fff6e6);border-color:#e5c485}.lm-right-stack{display:grid;gap:14px}.lm-panel-header{display:flex;align-items:center;gap:9px;margin-bottom:12px}.lm-panel-header>span{display:grid;place-items:center;color:#3d873a}.lm-panel-header h2{flex:1;margin:0;font-size:18px;font-weight:950}.lm-panel-header button{display:flex;align-items:center;gap:2px;border:0;background:transparent;color:#2f7a43;font-size:12px;font-weight:850;cursor:pointer}
.lm-progress-main{display:grid;grid-template-columns:52px auto 1fr auto;align-items:center;gap:10px;padding:12px;border-radius:8px;background:rgba(255,255,255,.78);border:1px solid #d7e9c8}.lm-progress-main img{width:48px;image-rendering:pixelated}.lm-progress-main span{display:block;color:#91bd80;font-size:12px;font-weight:850}.lm-progress-main strong{font-size:30px;line-height:1}.lm-progress-main i{height:14px;border-radius:999px;background:#e0e7ef;overflow:hidden}.lm-progress-main b{display:block;width:42%;height:100%;background:linear-gradient(90deg,#66c756,#a49ae7)}.lm-progress-main small{font-size:12px;color:#64748b;font-weight:850}
.lm-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:10px 0}.lm-stat-card{display:grid;grid-template-columns:28px 1fr;gap:0 7px;align-items:center;padding:8px;border-radius:8px;background:#fff;border:1px solid #e4eadb}.lm-stat-card span{grid-row:span 2;font-size:22px}.lm-stat-card small{color:#7b8794;font-size:11px;font-weight:750}.lm-stat-card strong{font-size:15px}.lm-recent h3{margin:10px 0 6px;color:#667085;font-size:13px}.lm-recent-item{display:grid;grid-template-columns:34px 1fr auto;align-items:center;gap:10px;min-height:44px;padding:7px 10px;border-top:1px solid #e4eadb}.lm-mini-avatar{width:30px;height:30px;border-radius:7px;background-image:url(${characterSheet});background-size:420px 138px;background-position:0 0;image-rendering:pixelated}.lm-recent-item strong,.lm-recent-item small{display:block}.lm-recent-item strong{font-size:13px}.lm-recent-item small{color:#7b8794;font-size:11px}.lm-recent-item em{color:#4aaa43;font-style:normal;font-size:12px;font-weight:900}
.lm-tabs{display:grid;grid-template-columns:repeat(3,1fr);margin-bottom:10px;border-radius:8px;background:#f2f4f7;overflow:hidden}.lm-tabs button{height:38px;border:0;background:transparent;color:#667085;font-weight:850;cursor:pointer}.lm-tabs .active{background:#fff;border:1px solid #7daef2;border-radius:7px;color:#1d4ed8}.lm-route-list{list-style:none;margin:0;padding:0 0 0 10px}.lm-route-list li{position:relative;display:grid;grid-template-columns:38px 1fr auto;gap:10px;align-items:center;min-height:58px}.lm-route-list li:before{content:"";position:absolute;left:18px;top:42px;bottom:-18px;border-left:2px solid #d7dde6}.lm-route-list li:last-child:before{display:none}.lm-route-list span{z-index:1;display:grid;place-items:center;width:30px;height:30px;border-radius:50%;background:#d7dde6;border:2px solid #fff;box-shadow:0 2px 0 rgba(15,39,74,.16);font-weight:950}.lm-route-已完成 span{background:#70c84f;color:#fff}.lm-route-学习中 span{background:#4f83d8;color:#fff}.lm-route-list strong,.lm-route-list small{display:block}.lm-route-list strong{font-size:15px}.lm-route-list small{color:#7b8794;font-size:12px}.lm-route-list em{font-style:normal;color:#98a2b3;font-size:12px;font-weight:900}.lm-route-已完成 em{color:#47a33d}.lm-route-学习中 em{color:#2f75d5}
.lm-badges{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.lm-badges div{min-height:116px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;text-align:center;border-radius:8px;background:rgba(255,255,255,.66);border:1px solid #e4edf7}.lm-badges img{width:50px;height:50px;object-fit:contain;image-rendering:pixelated}.lm-badges strong{font-size:14px}.lm-badges small{font-size:11px;color:#667085}.lm-badges .locked{filter:grayscale(1);opacity:.6}.lm-tip-panel{background:linear-gradient(180deg,#fffaff,#f3edff);border-color:#d8c9ff}.lm-tip-panel header{display:flex;align-items:center;gap:10px;margin-bottom:10px}.lm-tip-panel h2{margin:0;font-size:18px}.lm-tip-box{position:relative;min-height:98px;padding:14px 130px 14px 16px;border-radius:8px;background:rgba(255,255,255,.65);border:1px solid #d8c9ff}.lm-tip-box p{margin:0 0 6px;color:#405066;font-size:13px;font-weight:750;line-height:1.5}.lm-tip-box img{position:absolute;right:18px;bottom:2px;width:94px;image-rendering:pixelated}
@media(max-width:1280px){.lm-grid{grid-template-columns:1fr}.lm-map{height:360px}.lm-header{align-items:flex-start;flex-direction:column}.lm-header-actions{width:100%}.lm-top-progress{flex:1;width:auto}.lm-node{width:150px}.lm-node div{min-height:86px}.lm-node strong{font-size:15px}.lm-node p{font-size:11px}}
@media(max-width:760px){.lm-page{padding:18px 14px}.lm-header-actions{flex-direction:column;align-items:stretch}.lm-guide-btn{width:100%}.lm-map{height:560px;background-position:center}.lm-node{position:relative;left:auto!important;top:auto!important;transform:none;margin:18px auto}.lm-map-path,.lm-location-pin{display:none}.lm-badges{grid-template-columns:repeat(2,1fr)}}
`
