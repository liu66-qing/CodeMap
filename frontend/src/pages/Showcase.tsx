import { useMemo, useState } from 'react'
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  Copy,
  ExternalLink,
  FileCode2,
  Flag,
  GitBranch,
  Lightbulb,
  MapPin,
  Search,
  Star,
} from 'lucide-react'
import { stageAssets, stageBackgrounds, overviewAssets } from '../assets/pixel/stage-library'
import { PixelAsset } from '../components/common/PixelStageKit'
import type { StageAssetKey } from '../assets/pixel/stage-library'

interface SourcePoint {
  file: string
  symbol: string
  why: string
  takeaway: string
  url: string
}

interface Highlight {
  id: number
  title: string
  crystal: StageAssetKey
  summary: string
  problem: string
  naive: string
  solution: string
  readingPath: SourcePoint[]
  code: {
    title: string
    file: string
    url: string
    lines: string[]
    notes: string[]
  }
}

const highlights: Highlight[] = [
  {
    id: 1,
    title: '记忆不是外挂，是系统核心',
    crystal: 'crystalMemoryPurple',
    summary: '记忆决定上下文连续性、个性化体验与长期行为，不是可选插件。',
    problem: '普通聊天机器人只依赖当前 prompt。会话一长、跨天继续或用户画像变化时，它就很难稳定记住关键事实。',
    naive: '把所有历史都塞进 prompt。结果是 token 成本上涨、重要事实被噪声淹没，而且无法精确控制哪些信息该常驻。',
    solution: '把记忆拆成结构化状态块、长期存储和运行时上下文，让 Agent 每轮行动前先组织“它应该知道什么”。',
    readingPath: [
      {
        file: 'letta/memory.py',
        symbol: 'Memory / Block',
        why: '先看记忆如何被建模，理解“记忆不是字符串，而是可管理的状态块”。',
        takeaway: '知道 persona、human、custom blocks 如何进入上下文。',
        url: 'https://github.com/letta-ai/letta/blob/main/letta/memory.py',
      },
      {
        file: 'letta/schemas/state.py',
        symbol: 'AgentState',
        why: '再看状态结构，确认 memory 如何成为 Agent 持久状态的一部分。',
        takeaway: '把 memory、tools、system prompt 和 identity 串起来。',
        url: 'https://github.com/letta-ai/letta/blob/main/letta/schemas/state.py',
      },
      {
        file: 'letta/agent.py',
        symbol: 'context build',
        why: '最后看运行时如何读取记忆，并把它转成模型可用的上下文。',
        takeaway: '理解记忆如何参与每一次推理，而不是事后补丁。',
        url: 'https://github.com/letta-ai/letta/blob/main/letta/agent.py',
      },
    ],
    code: {
      title: '结构化记忆进入上下文',
      file: 'letta/memory.py',
      url: 'https://github.com/letta-ai/letta/blob/main/letta/memory.py',
      lines: [
        'class Memory(BaseModel):',
        '    blocks: List[Block] = Field(default_factory=list)',
        '',
        '    def compile(self) -> str:',
        '        return "\\n".join(block.render() for block in self.blocks)',
        '',
        'class Block(BaseModel):',
        '    label: str',
        '    value: str',
        '    limit: int',
      ],
      notes: [
        'Block 让记忆拥有标签、容量和边界，不再是一段不可控长文本。',
        'compile 是关键动作：把结构化记忆转成模型能读的上下文。',
        '读源码时重点追踪 Block 如何被更新、截断和注入 prompt。',
      ],
    },
  },
  {
    id: 2,
    title: 'Agent 不是一次性回答器',
    crystal: 'crystalAgentBlue',
    summary: 'Agent 被当成持续存在的实体，跨多轮对话保存身份、工具与状态。',
    problem: '如果 Agent 只是一次函数调用，它就无法稳定拥有身份、工具权限、历史状态和长期目标。',
    naive: '做成 stateless API：请求进来、模型回答、请求结束。看似简单，但下一次请求无法恢复现场。',
    solution: '围绕 agent_id 加载实体状态，每次运行都读取、更新并保存 Agent，让它能跨轮次继续工作。',
    readingPath: [
      {
        file: 'letta/agent.py',
        symbol: 'Agent',
        why: '先看 Agent 类本体，确认它不是工具函数，而是运行时实体。',
        takeaway: '找到 step、messages、memory、tools 之间的关系。',
        url: 'https://github.com/letta-ai/letta/blob/main/letta/agent.py',
      },
      {
        file: 'letta/orm/agent.py',
        symbol: 'Agent ORM',
        why: '再看数据库模型，理解 Agent 如何跨服务重启持续存在。',
        takeaway: '把“智能体实体”落实到持久化字段。',
        url: 'https://github.com/letta-ai/letta/blob/main/letta/orm/agent.py',
      },
      {
        file: 'letta/server/server.py',
        symbol: 'load_agent',
        why: '最后看服务入口如何通过 ID 找回 Agent，再把请求交给它处理。',
        takeaway: '理解 API 请求如何回到同一个 Agent 身上。',
        url: 'https://github.com/letta-ai/letta/blob/main/letta/server/server.py',
      },
    ],
    code: {
      title: '持久 Agent 的最小读法',
      file: 'letta/agent.py',
      url: 'https://github.com/letta-ai/letta/blob/main/letta/agent.py',
      lines: [
        'class Agent:',
        '    def __init__(self, agent_state, interface, tools):',
        '        self.agent_state = agent_state',
        '        self.interface = interface',
        '        self.tools = tools',
        '',
        '    def step(self, input_message):',
        '        context = self._build_context(self.agent_state)',
        '        response = self._run_llm(context, input_message)',
        '        self._persist_state()',
        '        return response',
      ],
      notes: [
        'agent_state 是源码阅读的主线，身份、记忆、工具都围绕它展开。',
        'step 不是纯函数：它读状态、产生新状态，并在结束时保存。',
        '这解释了为什么 Letta 的 Agent 能跨会话继续工作。',
      ],
    },
  },
  {
    id: 3,
    title: '这些能力其实是一个闭环',
    crystal: 'crystalLoopGreen',
    summary: '记忆读取、决策、工具执行和状态写回彼此强化，形成行动闭环。',
    problem: '很多 Agent demo 会调用工具，但工具结果不会沉淀成新状态，下一轮仍然像第一次见到问题。',
    naive: 'tool call 后直接回复用户，不反思、不写回、不改变未来上下文。',
    solution: '每次行动后把工具结果、用户反馈和状态变化写回系统，让下一步基于更新后的世界。',
    readingPath: [
      {
        file: 'letta/agent.py',
        symbol: 'step / inner_step',
        why: '先看一轮交互如何拆成推理、工具调用、结果处理。',
        takeaway: '找到“行动之后再更新”的闭环结构。',
        url: 'https://github.com/letta-ai/letta/blob/main/letta/agent.py',
      },
      {
        file: 'letta/tools/',
        symbol: 'Tool execution',
        why: '再看工具如何注册、执行和返回结构化结果。',
        takeaway: '理解工具不是外设，而是 Agent 行动能力的一部分。',
        url: 'https://github.com/letta-ai/letta/tree/main/letta/tools',
      },
      {
        file: 'letta/memory.py',
        symbol: 'memory update',
        why: '最后看工具结果如何影响记忆或状态。',
        takeaway: '确认闭环最后一环：结果写回未来上下文。',
        url: 'https://github.com/letta-ai/letta/blob/main/letta/memory.py',
      },
    ],
    code: {
      title: '工具调用到状态写回',
      file: 'letta/agent.py',
      url: 'https://github.com/letta-ai/letta/blob/main/letta/agent.py',
      lines: [
        'def step(self, user_message):',
        '    context = self.memory.compile()',
        '    decision = self.llm.call(context, user_message)',
        '',
        '    if decision.tool_call:',
        '        result = self.tools.run(decision.tool_call)',
        '        self.memory.update(result)',
        '        self.state.save()',
        '        return self.step(user_message)',
        '',
        '    return decision.message',
      ],
      notes: [
        '闭环的关键不是“会调用工具”，而是工具结果会改变 memory/state。',
        '一次用户请求可能包含多轮内部行动。',
        '读源码时重点找 tool result 被写回哪里，以及写回后如何影响下一次 prompt。',
      ],
    },
  },
]

const decodeSteps = [
  { icon: 'badgeMap' as StageAssetKey, label: '先问痛点', title: '它解决了什么真实麻烦？', body: '先看普通方案会在哪里断掉。' },
  { icon: 'badgeClipboard' as StageAssetKey, label: '再拆取舍', title: '为什么要这样设计？', body: '把方案、边界和 tradeoff 放在一起看。' },
  { icon: 'routeArrowBlue' as StageAssetKey, label: '最后找证据', title: '代码里哪段证明它成立？', body: '带着问题去看文件与调用链。' },
]

const PROGRESS = 79

export default function Showcase() {
  const [active, setActive] = useState(0)
  const current = highlights[active]
  const codeText = useMemo(() => current.code.lines.join('\n'), [current])

  function copyPath(path: string) {
    navigator.clipboard.writeText(path).catch(() => {})
  }

  return (
    <div className="sc-page">
      <section className="sc-hero" style={{ backgroundImage: `url(${stageBackgrounds.showcase})` }}>
        <button type="button" className="sc-back-btn"><ArrowLeft size={18} />返回学习地图</button>
        <div className="sc-progress-card">
          <img src={stageAssets.mentorMiner} alt="" className="sc-progress-avatar" />
          <div className="sc-progress-body"><strong>当前进度</strong><div className="sc-progress-track"><i style={{ width: `${PROGRESS}%` }} /></div></div>
          <b>{PROGRESS}%</b>
        </div>
        <h1 className="sc-hero-title"><PixelAsset asset="badgeClipboard" alt="" style={{ width: 42, height: 42 }} />Stage 3 · 拆它绝活</h1>
        <p className="sc-hero-subtitle">走到这里，不只是看懂它怎么跑，还要看懂它为什么厉害。</p>
        <div className="sc-hero-dialog">原来它厉害的根本，<br />就藏在这些精妙的<br />源码设计里！</div>
        <img src={stageAssets.mentorMiner} alt="矿工导师" className="sc-hero-character" />
        <img src={stageAssets.mineEntrance} alt="" className="sc-mine-entrance" />
        <div className="sc-hero-crystals">
          <PixelAsset asset="crystalMemoryPurple" alt="" style={{ width: 68 }} />
          <PixelAsset asset="crystalAgentBlue" alt="" style={{ width: 62 }} />
          <PixelAsset asset="crystalLoopGreen" alt="" style={{ width: 65 }} />
        </div>
        <div className="sc-hero-sign"><img src={overviewAssets.sign} alt="" /><span>letta-ai<br />/letta</span></div>
      </section>

      <section className="sc-decode-strip" aria-label="拆解方法">
        <header><span>拆解顺序</span><strong>别急着背结论，先按这三问看懂它为什么值钱</strong></header>
        <div className="sc-decode-steps">
          {decodeSteps.map((step, index) => (
            <article key={step.title} className="sc-decode-step">
              <PixelAsset asset={step.icon} alt="" style={{ width: 42, height: 42 }} />
              <em>{index + 1}</em>
              <div><small>{step.label}</small><h3>{step.title}</h3><p>{step.body}</p></div>
            </article>
          ))}
        </div>
      </section>

      <div className="sc-highlight-grid">
        {highlights.map((item, index) => (
          <button key={item.id} type="button" className={`sc-highlight-card ${index === active ? 'is-active' : ''}`} onClick={() => setActive(index)}>
            <PixelAsset asset={item.crystal} alt="" style={{ width: 78, height: 78 }} />
            <div><h3>{item.title}</h3><p>{item.summary}</p></div>
          </button>
        ))}
      </div>

      <section className="sc-source-workbench">
        <div className="sc-story-panel">
          <header><Search size={20} /><h2>{current.title}</h2></header>
          <div className="sc-story-block"><strong>它解决的问题</strong><p>{current.problem}</p></div>
          <div className="sc-story-block is-warn"><strong>朴素方案会怎样</strong><p>{current.naive}</p></div>
          <div className="sc-story-block is-good"><strong>它的做法</strong><p>{current.solution}</p></div>
        </div>

        <div className="sc-reading-panel">
          <header><GitBranch size={20} /><h2>原仓库阅读路线</h2><small>按这个顺序打开源码</small></header>
          <ol className="sc-source-list">
            {current.readingPath.map((point, index) => (
              <li key={point.file}>
                <span>{index + 1}</span>
                <div>
                  <strong>{point.file}</strong>
                  <em>{point.symbol}</em>
                  <p>{point.why}</p>
                  <small>{point.takeaway}</small>
                </div>
                <div className="sc-source-actions">
                  <button type="button" onClick={() => copyPath(point.file)} title="复制路径"><Copy size={15} /></button>
                  <a href={point.url} target="_blank" rel="noreferrer" title="打开 GitHub"><ExternalLink size={15} /></a>
                </div>
              </li>
            ))}
          </ol>
        </div>

        <div className="sc-code-panel">
          <header>
            <FileCode2 size={20} />
            <div><h2>{current.code.title}</h2><small>{current.code.file}</small></div>
            <a href={current.code.url} target="_blank" rel="noreferrer">GitHub <ExternalLink size={14} /></a>
          </header>
          <pre>{current.code.lines.map((line, index) => `${String(index + 1).padStart(2, '0')}  ${line}`).join('\n')}</pre>
        </div>

        <div className="sc-notes-panel">
          <header><Lightbulb size={20} /><h2>读代码时盯住这几处</h2></header>
          <ul>
            {current.code.notes.map((note) => <li key={note}><CheckCircle2 size={16} />{note}</li>)}
          </ul>
          <button type="button" onClick={() => copyPath(codeText)}>复制片段</button>
        </div>
      </section>

      <div className="sc-bottom-grid">
        <section className="sc-card sc-evidence-card">
          <header className="sc-card-header"><ClipboardList size={18} /><h2>代码定位清单</h2></header>
          {current.readingPath.map((point) => (
            <a key={point.file} href={point.url} target="_blank" rel="noreferrer"><MapPin size={15} /><span>{point.file}</span><ChevronRight size={15} /></a>
          ))}
        </section>
        <section className="sc-card sc-reward-card">
          <header className="sc-card-header"><Star size={18} /><h2>这一页你会获得</h2></header>
          <ul className="sc-task-list compact">
            <li><CheckCircle2 size={16} />识别设计亮点</li>
            <li><CheckCircle2 size={16} />定位核心源码</li>
            <li><CheckCircle2 size={16} />能讲清楚为什么这样写</li>
          </ul>
        </section>
        <section className="sc-card sc-task-card">
          <header className="sc-card-header"><ClipboardList size={18} /><h2>本关任务（3/3）</h2></header>
          <ul className="sc-task-list">
            <li><CheckCircle2 size={16} />读完一个绝活的源码路线</li>
            <li><CheckCircle2 size={16} />打开至少两个 GitHub 文件</li>
            <li><CheckCircle2 size={16} />用自己的话复述代码证据</li>
          </ul>
        </section>
        <section className="sc-card sc-next-card">
          <header className="sc-card-header"><Flag size={18} /><h2>下一站：抄走一招</h2><em className="sc-next-badge">4</em></header>
          <p>把源码里的设计模式，变成你项目里能复用的一招。</p>
          <img src={stageAssets.campfireCrates} alt="" />
          <button type="button">进入下一步 <ArrowRight size={18} /></button>
        </section>
      </div>

      <style>{styles}</style>
    </div>
  )
}

const styles = `
.sc-page{width:100%;min-height:100vh;overflow:auto;background:#f4f7fb;padding:0 22px 28px;color:#071832}.sc-hero{position:relative;height:370px;background-size:cover;background-position:center;image-rendering:pixelated;overflow:hidden}.sc-back-btn,.sc-progress-card{position:absolute;z-index:6;top:26px;border:2px solid #93aef5;border-radius:10px;background:rgba(255,255,255,.9);box-shadow:0 3px 0 rgba(33,72,130,.18);font-weight:900;color:#0d2f70}.sc-back-btn{left:28px;height:48px;padding:0 18px;display:flex;align-items:center;gap:8px;cursor:pointer}.sc-progress-card{right:26px;width:290px;height:56px;display:grid;grid-template-columns:38px 1fr auto;align-items:center;gap:12px;padding:0 14px}.sc-progress-avatar{width:34px;height:34px;image-rendering:pixelated}.sc-progress-body strong{font-size:12px}.sc-progress-track{height:7px;margin-top:4px;background:#dbe7f3;border-radius:999px;overflow:hidden}.sc-progress-track i{display:block;height:100%;background:#62bd55}.sc-progress-card b{font-size:16px}.sc-hero-title{position:absolute;z-index:7;top:20px;left:50%;transform:translateX(-50%);display:flex;align-items:center;gap:14px;margin:0;color:#0e1630;font-size:clamp(38px,4.5vw,64px);font-weight:950;line-height:1;text-shadow:2px 2px 0 rgba(255,255,255,.5);white-space:nowrap}.sc-hero-subtitle{position:absolute;z-index:7;top:100px;left:50%;transform:translateX(-50%);margin:0;color:#fff;font-size:18px;font-weight:800;text-shadow:1px 1px 5px rgba(0,0,0,.7);white-space:nowrap}.sc-hero-dialog{position:absolute;left:180px;top:145px;z-index:5;width:170px;min-height:100px;padding:12px 14px;border:3px solid #5d4b43;border-radius:6px;background:#fff9ef;box-shadow:3px 3px 0 rgba(0,0,0,.15);font-size:13px;font-weight:800;line-height:1.6}.sc-hero-character{position:absolute;left:340px;top:150px;z-index:4;width:180px;image-rendering:pixelated;filter:drop-shadow(0 5px 0 rgba(0,0,0,.24))}.sc-mine-entrance{position:absolute;right:240px;top:130px;z-index:2;width:160px;image-rendering:pixelated;opacity:.86}.sc-hero-crystals{position:absolute;left:500px;top:220px;z-index:3;display:flex;gap:14px}.sc-hero-sign{position:absolute;right:70px;top:185px;z-index:5;width:110px}.sc-hero-sign img{width:100%;image-rendering:pixelated}.sc-hero-sign span{position:absolute;top:32%;left:50%;transform:translateX(-50%);font-size:12px;font-weight:950;color:#3a2008;text-align:center;line-height:1.4;white-space:nowrap}
.sc-decode-strip{position:relative;z-index:10;margin:16px 0 0;padding:14px 16px 16px;border:1px solid #c6d7ea;border-radius:12px;background:linear-gradient(180deg,rgba(255,252,242,.97),rgba(239,247,255,.96));box-shadow:0 8px 20px rgba(15,39,74,.08)}.sc-decode-strip header{display:flex;align-items:center;gap:12px;margin-bottom:12px}.sc-decode-strip header span{padding:7px 12px;border-radius:6px;background:#4a9a3f;color:#fff;font-size:13px;font-weight:950;box-shadow:0 2px 0 #2d6f28}.sc-decode-strip header strong{font-size:16px;font-weight:950}.sc-decode-steps{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.sc-decode-step{display:grid;grid-template-columns:44px 28px 1fr;gap:10px;align-items:center;min-height:82px;padding:10px 12px;border:1px solid #d7c48d;border-radius:10px;background:rgba(255,255,255,.75)}.sc-decode-step:nth-child(2){border-color:#b8d1ef;background:#f2f8ff}.sc-decode-step:nth-child(3){border-color:#b6d9a8;background:#f4fcee}.sc-decode-step em{display:grid;place-items:center;width:28px;height:28px;border-radius:8px;border:2px solid #fff;background:#58ad48;color:#fff;font-style:normal;font-weight:950}.sc-decode-step small{color:#6c4d13;font-size:12px;font-weight:950}.sc-decode-step h3{margin:2px 0 3px;font-size:15px}.sc-decode-step p{margin:0;color:#4a596b;font-size:12px;font-weight:750;line-height:1.4}
.sc-highlight-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-top:18px}.sc-highlight-card{min-height:170px;display:grid;grid-template-columns:78px 1fr;gap:18px;align-items:center;width:100%;padding:20px 22px;border-radius:12px;border:1px solid #bfd5ef;background:#f8fbff;text-align:left;font-family:inherit;cursor:pointer;transition:.15s}.sc-highlight-card:first-child{background:#fbf3ff;border-color:#d5b3f4}.sc-highlight-card:nth-child(3){background:#f0fff4;border-color:#a8e6b8}.sc-highlight-card:hover{transform:translateY(-2px)}.sc-highlight-card.is-active{box-shadow:0 0 0 3px rgba(91,184,255,.26),0 10px 22px rgba(15,39,74,.12)}.sc-highlight-card h3{margin:0 0 10px;font-size:18px;font-weight:950}.sc-highlight-card p{margin:0;color:#334155;font-size:13.5px;line-height:1.7;font-weight:700}
.sc-source-workbench{display:grid;grid-template-columns:1.05fr 1.05fr 1.25fr;grid-template-areas:"story reading code" "notes reading code";gap:16px;margin-top:18px}.sc-story-panel,.sc-reading-panel,.sc-code-panel,.sc-notes-panel{border-radius:12px;border:1px solid #c7d8ee;background:rgba(255,255,255,.94);box-shadow:0 8px 20px rgba(15,39,74,.06);padding:16px}.sc-story-panel{grid-area:story;background:#fffaf0;border-color:#e8ca89}.sc-reading-panel{grid-area:reading;background:#f7fbff}.sc-code-panel{grid-area:code;background:#eef7ff}.sc-notes-panel{grid-area:notes;background:#f4f9e9;border-color:#c9dfa2}.sc-source-workbench header{display:flex;align-items:center;gap:8px;margin-bottom:12px}.sc-source-workbench h2{margin:0;font-size:17px;font-weight:950}.sc-source-workbench header small{display:block;color:#667085;font-size:12px;font-weight:800}.sc-story-block{padding:12px 14px;border-radius:8px;background:#fff;border:1px solid #ead7a3;margin-top:10px}.sc-story-block strong{display:block;margin-bottom:6px;color:#6e4a0c}.sc-story-block p{margin:0;color:#3d2d13;font-size:13px;line-height:1.65;font-weight:750}.sc-story-block.is-warn{background:#fff4ef;border-color:#efb5aa}.sc-story-block.is-good{background:#eff9e8;border-color:#b8d79a}
.sc-source-list{list-style:none;margin:0;padding:0;display:grid;gap:10px}.sc-source-list li{display:grid;grid-template-columns:30px 1fr 62px;gap:10px;align-items:start;padding:12px;border-radius:9px;border:1px solid #d4e3f3;background:#fff}.sc-source-list li>span{display:grid;place-items:center;width:30px;height:30px;border-radius:8px;background:#5fa34b;color:#fff;font-weight:950}.sc-source-list strong,.sc-source-list em,.sc-source-list small{display:block}.sc-source-list strong{font-family:Consolas,monospace;font-size:13px;color:#143866}.sc-source-list em{margin-top:2px;color:#7c4a13;font-size:12px;font-style:normal;font-weight:850}.sc-source-list p{margin:7px 0;color:#334155;font-size:12px;line-height:1.55}.sc-source-list small{color:#2f7a43;font-size:12px;font-weight:850}.sc-source-actions{display:flex;gap:6px}.sc-source-actions button,.sc-source-actions a{display:grid;place-items:center;width:28px;height:28px;border:1px solid #b8d1ef;border-radius:7px;background:#f8fbff;color:#164081;cursor:pointer}
.sc-code-panel header{justify-content:space-between}.sc-code-panel header>div{flex:1}.sc-code-panel header a{display:flex;align-items:center;gap:5px;color:#164081;text-decoration:none;font-size:12px;font-weight:950}.sc-code-panel pre{margin:0;padding:16px;border-radius:10px;background:#101927;color:#d8e8ff;font-size:12px;line-height:1.65;overflow:auto;max-height:390px}.sc-notes-panel ul{display:grid;gap:9px;margin:0 0 12px;padding:0;list-style:none}.sc-notes-panel li{display:flex;gap:8px;color:#2a3a1a;font-size:13px;line-height:1.55;font-weight:750}.sc-notes-panel li svg{flex:0 0 auto;color:#2b8a3e;margin-top:2px}.sc-notes-panel button{height:38px;padding:0 16px;border:0;border-radius:8px;background:#58a744;color:#fff;font-weight:950;cursor:pointer;box-shadow:0 2px 0 #357a2d}
.sc-bottom-grid{display:grid;grid-template-columns:1.25fr 1fr 1fr 1.1fr;gap:16px;margin-top:18px}.sc-card{position:relative;min-height:170px;padding:16px;border-radius:12px;border:1px solid #c7d8ee;background:#fff;overflow:hidden}.sc-card-header{display:flex;align-items:center;gap:8px;margin-bottom:12px}.sc-card-header h2{flex:1;margin:0;font-size:15px;font-weight:950}.sc-evidence-card{background:#f8fbff}.sc-evidence-card a{display:grid;grid-template-columns:18px 1fr 18px;gap:8px;align-items:center;min-height:34px;padding:7px 9px;border-radius:7px;color:#164081;text-decoration:none;font-size:12px;font-weight:850}.sc-evidence-card a:hover{background:#eaf3ff}.sc-reward-card{background:#f4f9e9;border-color:#c9dfa2}.sc-task-card{background:#fff7e7;border-color:#edcb88}.sc-task-list{display:grid;gap:8px;margin:0;padding:0;list-style:none}.sc-task-list li{display:flex;gap:8px;color:#4a3a18;font-size:12.5px;line-height:1.45;font-weight:800}.sc-task-list.compact li{color:#2a3a1a}.sc-next-card{background:#eef6ff;border-color:#bdd6f0}.sc-next-badge{display:grid;place-items:center;width:24px;height:24px;border-radius:50%;background:#5fa34b;color:#fff;font-style:normal}.sc-next-card p{max-width:62%;margin:0;color:#1f3a60;font-size:13px;line-height:1.55}.sc-next-card img{position:absolute;right:6px;top:42px;width:96px;image-rendering:pixelated}.sc-next-card button{position:absolute;left:16px;bottom:14px;height:40px;padding:0 18px;border:0;border-radius:8px;background:#62aa47;color:#fff;font-weight:950;display:flex;align-items:center;gap:6px}
@media(max-width:1280px){.sc-source-workbench{grid-template-columns:1fr;grid-template-areas:"story" "reading" "code" "notes"}.sc-bottom-grid,.sc-highlight-grid,.sc-decode-steps{grid-template-columns:1fr}.sc-hero-title{font-size:42px}}
`
