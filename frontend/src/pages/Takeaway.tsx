import { useNavigate } from 'react-router-dom'
import { ArrowLeft, BookOpen, CheckCircle2, Code2, RefreshCcw, Star, Trophy } from 'lucide-react'
import { stageAssets, stageBackgrounds, overviewAssets } from '../assets/pixel/stage-library'

const patterns = [
  {
    icon: '🧠',
    title: '1 Hot / cold memory layering',
    sub: '冷热记忆分层',
    body: '把近期对话放在热存，长期信息放在冷存，按需检索，降低成本并提升相关性。',
    scene: '需要长期记住偏好、历史与对话线索的助手。',
  },
  {
    icon: '💾',
    title: '2 Persistent stateful agent entity',
    sub: '持久化有状态的智能体实体',
    body: '每个智能体都有自己的配置、记忆、工具权限与状态，持久化存储，保证连续性。',
    scene: '多轮连续提交互、需要记住用户习惯和上下文的场景。',
  },
  {
    icon: '🔁',
    title: '3 Tool call + state update loop',
    sub: '工具调用 + 状态更新循环',
    body: '通过工具获取外部能力，并将结果写回状态/记忆，形成行动到更新再行动的闭环。',
    scene: '需要执行任务、检索外部数据或触发流程的智能体。',
  },
]

const code = [
  '# 1. 接收输入',
  'input = receive_input(user_message)',
  '',
  '# 2. 加载记忆/状态',
  'state = load_state(agent_id)',
  'context = load_memory_hot(state) + retrieve_memory_cold(state, input)',
  '',
  '# 3. 决策或调用工具',
  'action, tool, args = decide(context, input)',
  'result = call_tool(tool, args) if tool else None',
  '',
  '# 4. 更新状态/记忆',
  'update_state(state, input, result)',
  'write_memory(state, input, result)',
  '',
  '# 5. 回复用户',
  'reply = generate_reply(context, result)',
  'send_reply(reply)',
]

export default function Takeaway() {
  const navigate = useNavigate()

  return (
    <div className="tw-page">
      <section className="tw-hero" style={{ backgroundImage: `url(${stageBackgrounds.takeaway})` }}>
        <button type="button" className="tw-back" onClick={() => navigate('/map')}>
          <ArrowLeft size={18} /> 返回学习地图
        </button>
        <div className="tw-progress">
          <img src={stageAssets.mentorTrophy} alt="" />
          <div><strong>当前进度</strong><span><i /></span></div>
          <b>100%</b>
        </div>
        <h1>Stage 4 · 抄走一招</h1>
        <p>真正的收获不是看过，而是能把它的方法带走，变成你自己的能力。</p>
        <img src={stageAssets.mentorTrophy} alt="" className="tw-mentor" />
        <div className="tw-bubble">把有用的装进背包，下一段旅程就能用上！</div>
        <div className="tw-board">
          <img src={overviewAssets.woodBoard} alt="" />
          <strong>这一站带走什么</strong>
          <p>这不是某个仓库的特定技巧，而是可以复用的智能体构建模式。把它们带走，才是真正的收获。</p>
        </div>
      </section>

      <main className="tw-content">
        <section className="tw-patterns">
          <header><Star size={22} fill="#ffd966" /><h2>三大可复用构建模式（来自 letta-ai/letta）</h2></header>
          <div className="tw-pattern-grid">
            {patterns.map((item) => (
              <article key={item.title} className="tw-pattern-card">
                <div className="tw-pattern-title"><span>{item.icon}</span><div><strong>{item.title}</strong><small>{item.sub}</small></div></div>
                <p>{item.body}</p>
                <em>适合场景：{item.scene}</em>
              </article>
            ))}
          </div>
          <div className="tw-scenario-grid">
            <article className="tw-good"><h3>适用场景</h3><p>长期存在的智能体、多轮复杂任务与工作流、需要个性化与长期记忆的场景。</p></article>
            <article className="tw-bad"><h3>不适用场景</h3><p>一次性问答、极其简单的脚本命令工具、无需记忆或状态的临时任务。</p></article>
          </div>
        </section>

        <aside className="tw-code">
          <header><Code2 size={22} /><h2>最小实现片段</h2></header>
          <pre>{code.map((line, index) => `${String(index + 1).padStart(2, '0')}  ${line}`).join('\n')}</pre>
        </aside>

        <section className="tw-rewards">
          <header><Star size={22} fill="#ffd966" /><h2>你已经收获</h2></header>
          {['可复用模式 x3', '最小实现片段', '适用边界判断', '工程化视角'].map((item) => <span key={item}>{item}</span>)}
        </section>

        <section className="tw-complete">
          <div>
            <Trophy size={28} />
            <strong>旅程完成</strong>
            <b>100%</b>
            <p>你已经从看门道走到能带走一招！</p>
          </div>
          <img src={stageAssets.mentorTrophy} alt="" />
        </section>

        <section className="tw-actions">
          <button type="button" onClick={() => navigate('/map')}><BookOpen size={20} /> 返回学习地图</button>
          <button type="button" onClick={() => navigate('/')}><RefreshCcw size={20} /> 再换一个仓库</button>
        </section>

        <section className="tw-tasks">
          <header><h2>本关任务（3/3）</h2></header>
          {['理解三种可复用模式', '知道什么时候该用/不该用', '能把模式迁移到自己的项目'].map((task) => (
            <p key={task}><CheckCircle2 size={17} />{task}</p>
          ))}
        </section>
      </main>
      <style>{twStyles}</style>
    </div>
  )
}

const twStyles = `
.tw-page{min-height:100vh;background:#f4f8fb;padding:0 22px 22px;overflow:auto}
.tw-hero{position:relative;height:340px;background-size:cover;background-position:center;image-rendering:pixelated;overflow:hidden}
.tw-hero:after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(6,12,36,.1),rgba(6,12,36,.22));pointer-events:none}
.tw-back,.tw-progress{position:absolute;z-index:3;top:26px;border:2px solid #9dbcf2;border-radius:10px;background:rgba(255,255,255,.92);box-shadow:0 3px 0 rgba(33,72,130,.18);font-weight:900;color:#12346e}
.tw-back{left:28px;height:46px;padding:0 18px;display:flex;align-items:center;gap:8px;cursor:pointer}
.tw-progress{right:28px;width:300px;height:56px;display:grid;grid-template-columns:42px 1fr auto;align-items:center;gap:10px;padding:6px 12px}
.tw-progress img{width:40px;height:40px;object-fit:contain;image-rendering:pixelated}.tw-progress strong{font-size:13px}.tw-progress span{display:block;height:7px;background:#dbe7f3;border-radius:99px;margin-top:4px;overflow:hidden}.tw-progress i{display:block;width:100%;height:100%;background:#67bf55}.tw-progress b{font-size:18px}
.tw-hero h1{position:absolute;z-index:3;left:50%;top:18px;transform:translateX(-50%);margin:0;color:#071832;font-size:clamp(48px,5vw,72px);font-weight:950;line-height:1;text-shadow:3px 3px 0 rgba(255,255,255,.35);white-space:nowrap}
.tw-hero>p{position:absolute;z-index:3;left:50%;top:104px;transform:translateX(-50%);margin:0;color:#fff;font-size:18px;font-weight:900;text-shadow:0 2px 5px rgba(0,0,0,.7);white-space:nowrap}
.tw-mentor{position:absolute;z-index:3;left:33%;bottom:14px;width:158px;image-rendering:pixelated;filter:drop-shadow(0 5px 0 rgba(0,0,0,.25))}
.tw-bubble{position:absolute;z-index:4;left:16%;bottom:118px;width:184px;padding:10px 13px;border:2px solid #2a2d34;border-radius:4px;background:#fffaf0;font-size:13px;font-weight:850;line-height:1.5;box-shadow:3px 4px 0 rgba(0,0,0,.18)}
.tw-bubble:after{content:"";position:absolute;right:-10px;bottom:18px;width:16px;height:16px;border-right:2px solid #2a2d34;border-bottom:2px solid #2a2d34;background:#fffaf0;transform:rotate(-45deg)}
.tw-board{position:absolute;z-index:3;right:10%;bottom:24px;width:456px;height:168px;text-align:center}.tw-board img{position:absolute;inset:0;width:100%;height:100%;object-fit:fill;image-rendering:pixelated}.tw-board strong{position:relative;display:inline-block;margin-top:24px;padding:6px 42px;background:#4e9d3e;color:#fff;border-radius:4px;font-size:17px}.tw-board p{position:relative;width:300px;margin:14px auto 0;color:#3a260f;font-size:14px;font-weight:850;line-height:1.55}
.tw-content{display:grid;grid-template-columns:2.2fr 1fr;grid-template-areas:"patterns code" "rewards complete" "rewards actions" "tasks actions";gap:14px;margin-top:-12px;position:relative;z-index:5}
.tw-content section,.tw-code{border:1px solid #c7d8ee;border-radius:12px;background:rgba(255,255,255,.94);box-shadow:0 8px 20px rgba(15,39,74,.06);padding:14px 16px}
.tw-patterns{grid-area:patterns}.tw-code{grid-area:code;background:#eef7ff}.tw-rewards{grid-area:rewards;background:#fff8e7;border-color:#efcb84}.tw-complete{grid-area:complete;background:#fff8e7;border-color:#efcb84}.tw-actions{grid-area:actions}.tw-tasks{grid-area:tasks;background:#fff8e7;border-color:#efcb84}
.tw-content header{display:flex;align-items:center;gap:10px;margin-bottom:12px}.tw-content h2{margin:0;font-size:17px;font-weight:950}.tw-pattern-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.tw-pattern-card{min-height:166px;padding:14px;border-radius:10px;border:1px solid #d9c2c2;background:#fffafa}.tw-pattern-card:nth-child(2){border-color:#bad5b1;background:#f7fff3}.tw-pattern-card:nth-child(3){border-color:#b6cef0;background:#f5faff}.tw-pattern-title{display:flex;gap:10px;align-items:start}.tw-pattern-title span{font-size:28px}.tw-pattern-title strong,.tw-pattern-title small{display:block}.tw-pattern-title strong{font-size:15px;font-weight:950}.tw-pattern-title small{font-size:12px;font-weight:800;color:#4b5969}.tw-pattern-card p{font-size:13px;line-height:1.65;margin:14px 0;color:#2b3445}.tw-pattern-card em{font-style:normal;font-size:12px;color:#596778;font-weight:800}
.tw-scenario-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}.tw-scenario-grid article{min-height:86px;border-radius:10px;padding:12px 16px}.tw-good{background:#eef9e8;border:1px solid #badb9a}.tw-bad{background:#fff0ed;border:1px solid #efb5aa}.tw-scenario-grid h3{margin:0 0 8px;font-size:15px}.tw-scenario-grid p{margin:0;font-size:13px;line-height:1.6}
.tw-code pre{margin:0;padding:16px;border-radius:10px;background:#101927;color:#d8e8ff;font-size:12px;line-height:1.55;overflow:auto;max-height:350px}.tw-rewards{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;align-content:start}.tw-rewards header{grid-column:1/-1}.tw-rewards span{min-height:58px;display:grid;place-items:center;border:1px solid #efcb84;border-radius:8px;background:rgba(255,255,255,.65);font-weight:900;text-align:center}.tw-complete{display:grid;grid-template-columns:1fr 112px;align-items:center}.tw-complete div{display:grid;grid-template-columns:32px 1fr;gap:2px 10px}.tw-complete strong{font-size:24px}.tw-complete b{grid-column:2;font-size:42px;color:#9b5d10;line-height:1}.tw-complete p{grid-column:1/-1;margin:8px 0 0;font-weight:800}.tw-complete img{width:110px;image-rendering:pixelated}.tw-actions{display:grid;gap:10px}.tw-actions button{height:52px;border-radius:8px;border:2px solid #4c9438;background:#58a744;color:white;font-weight:950;font-size:16px;display:flex;align-items:center;justify-content:center;gap:10px;cursor:pointer}.tw-actions button+button{background:#fff;color:#164081;border-color:#76a4ef}.tw-tasks p{display:flex;align-items:center;gap:8px;margin:9px 0;font-weight:850;color:#5a4814}
@media(max-width:1100px){.tw-content{grid-template-columns:1fr;grid-template-areas:"patterns" "code" "rewards" "complete" "tasks" "actions"}.tw-pattern-grid{grid-template-columns:1fr}.tw-board{display:none}}
`
