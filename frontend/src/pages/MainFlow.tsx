import { useState, type ReactNode } from 'react'
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ClipboardList,
  Cloud,
  ExternalLink,
  Eye,
  FileText,
  Flag,
  Gift,
  Lightbulb,
  Link as LinkIcon,
  MessageSquare,
  PackageOpen,
  Save,
  Star,
  Target,
  Wrench,
} from 'lucide-react'
import { stageAssets, stageBackgrounds, overviewAssets } from '../assets/pixel/stage-library'
import { PixelAsset } from '../components/common/PixelStageKit'

interface FlowNode {
  id: number
  title: string
  note: string
  icon: ReactNode
  detail: {
    explanation: string
    whatToLook: string
    whyFirst: string
    outcome: string
  }
}

interface EvidenceLink {
  label: string
  githubUrl: string
}

const flowNodes: FlowNode[] = [
  {
    id: 1,
    title: '收到请求',
    note: '用户输入进入系统',
    icon: <PixelAsset asset="routeArrowBlue" alt="请求" style={{ width: 36, height: 36 }} />,
    detail: {
      explanation:
        '用户通过 REST API 或 SDK 发送一条消息给 Agent。服务端接收请求，找到对应的 Agent 实例，准备启动 Agent Loop。',
      whatToLook: 'REST API 路由、请求体结构、Agent ID 路由',
      whyFirst: '这是整个流程的触发点，理解入口才能追踪后续',
      outcome: '一个待处理的用户消息进入 Agent 的处理队列',
    },
  },
  {
    id: 2,
    title: '读取记忆',
    note: '读取会话状态与长期记忆',
    icon: <PixelAsset asset="crystalMemoryPurple" alt="记忆" style={{ width: 36, height: 36 }} />,
    detail: {
      explanation:
        '在做任何决定之前，Agent 会先读取当前会话上下文、角色设定、记忆块以及有用的历史状态，确保后续动作建立在可靠信息之上。',
      whatToLook: '会话上下文、角色 / persona、记忆块、状态变量',
      whyFirst: '先掌握已有信息，避免重复、冲突或无谓的动作',
      outcome: '当前可用的上下文集合，作为后续决策依据',
    },
  },
  {
    id: 3,
    title: '规划动作',
    note: '判断是否思考、检索或调用工具',
    icon: <PixelAsset asset="crystalAgentBlue" alt="规划" style={{ width: 36, height: 36 }} />,
    detail: {
      explanation:
        'LLM 根据当前上下文进行推理，决定下一步是直接回复、调用工具、还是检索更多信息。',
      whatToLook: 'LLM 调用逻辑、prompt 组装、tool_choice 参数',
      whyFirst: '这是 Agent 的"大脑"，决定了整个行为路径',
      outcome: '一个决策：调用哪个工具 / 直接回复 / 继续思考',
    },
  },
  {
    id: 4,
    title: '执行工具',
    note: '调工具并拿回结果',
    icon: <PixelAsset asset="badgeClipboard" alt="工具" style={{ width: 36, height: 36 }} />,
    detail: {
      explanation:
        '根据 LLM 的决策，执行对应的工具调用（记忆操作、外部 API、代码执行等），获取执行结果。',
      whatToLook: '工具注册表、工具执行器、server-side vs client-side',
      whyFirst: '工具是 Agent 与外部世界交互的唯一方式',
      outcome: '工具执行结果，准备写回上下文',
    },
  },
  {
    id: 5,
    title: '更新状态',
    note: '把新信息写回记忆与状态',
    icon: <PixelAsset asset="crystalLoopGreen" alt="状态" style={{ width: 36, height: 36 }} />,
    detail: {
      explanation:
        '将工具执行结果、新学到的信息写入记忆块和数据库，更新 Agent 的持久化状态。',
      whatToLook: '记忆写入逻辑、状态持久化、数据库操作',
      whyFirst: '这是 Agent "学习"的关键步骤',
      outcome: 'Agent 状态已更新，新信息已持久化',
    },
  },
  {
    id: 6,
    title: '生成回复',
    note: '组织最终答案返回用户',
    icon: <PixelAsset asset="badgeMap" alt="回复" style={{ width: 36, height: 36 }} />,
    detail: {
      explanation:
        'Agent Loop 判断任务完成，将最终结果组织为用户可读的回复，通过 API 返回。',
      whatToLook: '回复组装逻辑、流式输出、响应格式',
      whyFirst: '这是用户唯一能看到的输出',
      outcome: '用户收到回复，一次完整的 Agent 交互结束',
    },
  },
]

const evidenceLinks: EvidenceLink[] = [
  {
    label: 'main.py / server entry',
    githubUrl: 'https://github.com/letta-ai/letta/blob/main/letta/server/server.py',
  },
  {
    label: 'agent loop',
    githubUrl: 'https://github.com/letta-ai/letta/blob/main/letta/agent.py',
  },
  {
    label: 'memory manager',
    githubUrl: 'https://github.com/letta-ai/letta/blob/main/letta/memory.py',
  },
]

const PROGRESS = 58

export default function MainFlow() {
  const [selectedNode, setSelectedNode] = useState(1)
  const current = flowNodes[selectedNode]

  return (
    <div className="mf-page">
      <section
        className="mf-hero"
        style={{ backgroundImage: `url(${stageBackgrounds.mainflow})` }}
      >
        <button type="button" className="mf-back-btn">
          <ArrowLeft size={18} />
          返回学习地图
        </button>

        <div className="mf-progress-card">
          <img
            src={stageAssets.mentorRunner}
            alt=""
            className="mf-progress-avatar"
          />
          <div className="mf-progress-body">
            <strong>当前进度</strong>
            <div className="mf-progress-track">
              <i style={{ width: `${PROGRESS}%` }} />
            </div>
          </div>
          <b>{PROGRESS}%</b>
        </div>

        <h1 className="mf-hero-title">Stage 2 · 跑通主线</h1>
        <p className="mf-hero-subtitle">
          沿着主请求流程走一遍，先在脑中把这个仓库真正跑起来。
        </p>

        <div className="mf-sign mf-sign-main">
          <img src={stageAssets.woodArrowSign} alt="主流程" />
          <span>
            主流程
            <ArrowRight size={14} />
          </span>
        </div>

        <img
          src={stageAssets.mentorRunner}
          alt="像素跑步小人"
          className="mf-hero-character"
        />

        <svg className="mf-glow-path" viewBox="0 0 1120 90" preserveAspectRatio="none">
          <defs>
            <filter id="mf-glow" x="-20%" y="-50%" width="140%" height="200%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          <path
            d="M0,50 C120,85 220,20 350,45 C500,90 650,70 760,25 C900,-10 980,65 1120,55"
            stroke="#75d8ff"
            strokeWidth="6"
            fill="none"
            strokeLinecap="round"
            filter="url(#mf-glow)"
          />
          <g fill="#ffffff" stroke="#3aa9ff" strokeWidth="1.5">
            <polygon points="280,38 296,46 280,54" />
            <polygon points="600,42 616,50 600,58" />
            <polygon points="900,30 916,38 900,46" />
          </g>
        </svg>

        <div className="mf-sign mf-sign-next">
          <img src={overviewAssets.sign} alt="继续前进" />
          <span>
            继续前进
            <ArrowRight size={14} />
          </span>
        </div>
      </section>

      <div className="mf-content-area">
        <div className="mf-top-row">
          <section className="mf-flow-card">
            <header className="mf-card-header">
              <LinkIcon size={20} color="#2c5070" />
              <h2>主请求执行链路</h2>
            </header>

            <div className="mf-flow-grid">
              {flowNodes.map((node, index) => {
                const active = index === selectedNode
                const isLast = index === flowNodes.length - 1
                return (
                  <div key={node.id} className="mf-flow-node-wrap">
                    <button
                      type="button"
                      onClick={() => setSelectedNode(index)}
                      className="mf-flow-node"
                    >
                      <span className="mf-node-index">{node.id}</span>
                      <div className={`mf-node-icon-box ${active ? 'is-active' : ''}`}>
                        {node.icon}
                      </div>
                      <strong>{node.title}</strong>
                      <small>{node.note}</small>
                    </button>
                    {!isLast && (
                      <span className="mf-node-arrow" aria-hidden>
                        <ArrowRight size={20} />
                      </span>
                    )}
                  </div>
                )
              })}
            </div>
          </section>

          <section className="mf-explain-card">
            <header className="mf-card-header mf-explain-header">
              <BookOpen size={20} color="#9c6a1a" />
              <h2>节点说明：{current.title}</h2>
            </header>

            <p className="mf-explain-lead">{current.detail.explanation}</p>

            <div className="mf-explain-section">
              <h4><Eye size={15} /> 看什么</h4>
              <p>{current.detail.whatToLook}</p>
            </div>
            <div className="mf-explain-section">
              <h4><Lightbulb size={15} /> 为什么先看</h4>
              <p>{current.detail.whyFirst}</p>
            </div>
            <div className="mf-explain-section">
              <h4><Gift size={15} /> 跑完后得到什么</h4>
              <p>{current.detail.outcome}</p>
            </div>
          </section>
        </div>

        <div className="mf-bottom-grid">
          <section className="mf-card mf-evidence-card">
            <header className="mf-card-header">
              <LinkIcon size={18} color="#3a6b2c" />
              <h2>最小证据链接</h2>
            </header>
            <ul className="mf-evidence-list">
              {evidenceLinks.map((link) => (
                <li key={link.githubUrl}>
                  <a href={link.githubUrl} target="_blank" rel="noopener noreferrer">
                    <FileText size={14} />
                    <span>{link.label}</span>
                    <ArrowRight size={14} />
                  </a>
                </li>
              ))}
            </ul>
          </section>

          <section className="mf-card mf-reward-card">
            <header className="mf-card-header">
              <Star size={18} color="#7a8a2c" />
              <h2>这一页你会获得</h2>
            </header>
            <div className="mf-reward-grid">
              <div className="mf-reward-item">
                <img src={stageAssets.badgeMap} alt="" />
                <strong>看懂主流程</strong>
                <small>建立整体心智地图</small>
              </div>
              <div className="mf-reward-item">
                <Target size={28} color="#c2410c" strokeWidth={2.4} />
                <strong>知道关键节点</strong>
                <small>理解每步的职责</small>
              </div>
              <div className="mf-reward-item">
                <img src={stageAssets.badgeClipboard} alt="" />
                <strong>能自己复述执行链路</strong>
                <small>把流程讲给别人听</small>
              </div>
            </div>
          </section>

          <section className="mf-card mf-task-card">
            <header className="mf-card-header">
              <ClipboardList size={18} color="#a16207" />
              <h2>本关任务（3/3）</h2>
            </header>
            <ul className="mf-task-list">
              <li>
                <CheckCircle2 size={16} color="#2b8a3e" />
                沿着主流程走一遍，理解每个节点做什么
              </li>
              <li>
                <CheckCircle2 size={16} color="#2b8a3e" />
                在代码中找到对应片段并标注位置
              </li>
              <li>
                <CheckCircle2 size={16} color="#2b8a3e" />
                尝试用自己的话复述整条执行链路
              </li>
            </ul>
            <img
              src={overviewAssets.chest}
              alt=""
              className="mf-chest-decoration"
            />
          </section>

          <section className="mf-card mf-next-card">
            <header className="mf-card-header">
              <Flag size={18} color="#1d4ed8" />
              <h2>下一站：拆它绝活</h2>
              <em className="mf-next-badge">3</em>
            </header>
            <p className="mf-next-body">
              深入核心模块与设计细节，
              <br />看懂它的拿手好戏。
            </p>
            <img
              src={stageAssets.mineEntrance}
              alt=""
              className="mf-mine-decoration"
            />
            <button type="button" className="mf-next-button">
              进入下一步
              <ArrowRight size={18} />
            </button>
          </section>
        </div>
      </div>

      <style>{styles}</style>
    </div>
  )
}

void PackageOpen

const styles = `
.mf-page {
  width: 100%;
  height: 100%;
  overflow-y: auto;
  background: #f5f8fb;
  padding: 0 22px 24px;
  display: flex;
  flex-direction: column;
}

.mf-hero {
  position: relative;
  width: 100%;
  height: 372px;
  margin-top: 0;
  overflow: hidden;
  border-radius: 0;
  background-size: cover;
  background-position: center;
  image-rendering: pixelated;
  flex-shrink: 0;
}

.mf-back-btn {
  position: absolute;
  top: 24px;
  left: 34px;
  width: 170px;
  height: 46px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid #9db4e8;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 700;
  color: #0d2f70;
  cursor: pointer;
  z-index: 6;
  font-family: inherit;
}

.mf-back-btn:hover {
  background: rgba(255, 255, 255, 0.96);
}

.mf-progress-card {
  position: absolute;
  top: 90px;
  right: 32px;
  width: 280px;
  height: 52px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid rgba(180, 200, 220, 0.8);
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 14px;
  z-index: 6;
}

.mf-progress-avatar {
  width: 36px;
  height: 36px;
  image-rendering: pixelated;
}

.mf-progress-body {
  flex: 1;
  min-width: 0;
}

.mf-progress-body strong {
  display: block;
  font-size: 12px;
  font-weight: 700;
  color: #1B2A3A;
  margin-bottom: 4px;
}

.mf-progress-track {
  height: 6px;
  border-radius: 999px;
  background: #dbe7f3;
  overflow: hidden;
}

.mf-progress-track i {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, #58b24f, #88d66a);
  border-radius: inherit;
}

.mf-progress-card b {
  font-size: 16px;
  font-weight: 800;
  color: #17213a;
}

.mf-hero-title {
  position: absolute;
  top: 30px;
  left: 50%;
  transform: translateX(-50%);
  margin: 0;
  font-size: clamp(40px, 5vw, 64px);
  font-weight: 900;
  line-height: 1;
  letter-spacing: 1px;
  color: #0b1c34;
  text-shadow: 3px 3px 0 rgba(255, 255, 255, 0.55);
  white-space: nowrap;
  z-index: 3;
  pointer-events: none;
}

.mf-hero-subtitle {
  position: absolute;
  top: 115px;
  left: 50%;
  transform: translateX(-50%);
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #132238;
  white-space: nowrap;
  z-index: 3;
  pointer-events: none;
  text-shadow: 1px 1px 0 rgba(255, 255, 255, 0.5);
}

.mf-hero-character {
  position: absolute;
  left: 245px;
  top: 155px;
  width: 160px;
  height: auto;
  z-index: 4;
  image-rendering: pixelated;
  filter: drop-shadow(0 5px 0 rgba(0, 0, 0, 0.24));
}

.mf-glow-path {
  position: absolute;
  left: 160px;
  right: 160px;
  top: 245px;
  height: 90px;
  z-index: 3;
  pointer-events: none;
  filter: drop-shadow(0 0 8px #6fdcff);
}

.mf-sign {
  position: absolute;
  z-index: 5;
  display: flex;
  flex-direction: column;
  align-items: center;
  pointer-events: none;
}

.mf-sign img {
  width: 100%;
  height: auto;
  image-rendering: pixelated;
  filter: drop-shadow(0 4px 0 rgba(0, 0, 0, 0.22));
}

.mf-sign span {
  position: absolute;
  top: 38%;
  left: 50%;
  transform: translateX(-50%);
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 16px;
  font-weight: 900;
  color: #ffffff;
  white-space: nowrap;
  text-shadow: 1px 1px 0 #3a2008, 0 0 6px rgba(0, 0, 0, 0.5);
  letter-spacing: 0.5px;
}

.mf-sign-main {
  left: 65px;
  top: 190px;
  width: 130px;
  height: 70px;
}

.mf-sign-next {
  right: 80px;
  top: 215px;
  width: 150px;
  height: 78px;
}

.mf-content-area {
  margin-top: -18px;
  position: relative;
  z-index: 10;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.mf-top-row {
  display: grid;
  grid-template-columns: minmax(0, 2.05fr) minmax(0, 1fr);
  gap: 20px;
}

@media (max-width: 1023px) {
  .mf-top-row { grid-template-columns: 1fr; }
}

.mf-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 14px;
}

.mf-card-header h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 900;
  color: #1B2A3A;
  flex: 1;
  min-width: 0;
}

.mf-explain-header h2 { color: #6e4a0c; }

.mf-flow-card {
  height: 340px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #bdd6f0;
  padding: 22px 24px 18px;
  box-shadow: 0 2px 8px rgba(20, 50, 90, 0.08);
}

.mf-flow-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 4px;
  align-items: start;
  padding-top: 18px;
}

.mf-flow-node-wrap {
  position: relative;
  display: flex;
  align-items: flex-start;
  justify-content: center;
}

.mf-flow-node {
  width: 100%;
  max-width: 130px;
  text-align: center;
  position: relative;
  background: transparent;
  border: none;
  padding: 0;
  cursor: pointer;
  font-family: inherit;
  color: inherit;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.mf-node-index {
  position: absolute;
  top: -16px;
  left: 50%;
  transform: translateX(-50%);
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: #5fa34b;
  color: white;
  font-weight: 800;
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2;
  border: 2px solid #ffffff;
  box-shadow: 0 2px 0 rgba(0, 0, 0, 0.15);
}

.mf-node-icon-box {
  width: 96px;
  height: 86px;
  margin: 0 auto 14px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #cbdaf0;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
}

.mf-flow-node:hover .mf-node-icon-box {
  transform: translateY(-2px);
  border-color: #88c4ff;
}

.mf-node-icon-box.is-active {
  border: 2px solid #58b9ff;
  box-shadow: 0 0 12px rgba(88, 185, 255, 0.55);
}

.mf-flow-node strong {
  display: block;
  font-size: 14px;
  font-weight: 800;
  color: #1B2A3A;
  margin-bottom: 4px;
}

.mf-flow-node small {
  display: block;
  font-size: 11px;
  line-height: 1.4;
  color: #5a6a80;
  padding: 0 4px;
}

.mf-node-arrow {
  position: absolute;
  right: -10px;
  top: 50px;
  z-index: 1;
  color: #58b9ff;
  filter: drop-shadow(0 0 4px rgba(88, 185, 255, 0.6));
}

.mf-explain-card {
  height: 340px;
  border-radius: 8px;
  background: rgba(255, 249, 232, 0.94);
  border: 1px solid #e7c98f;
  padding: 20px 24px;
  overflow-y: auto;
  box-shadow: 0 2px 8px rgba(140, 100, 30, 0.1);
}

.mf-explain-lead {
  margin: 0 0 14px;
  font-size: 13.5px;
  line-height: 1.7;
  color: #3a2c10;
}

.mf-explain-section {
  padding-top: 12px;
  border-top: 1px dashed #e4cfa2;
  margin-top: 12px;
}

.mf-explain-section h4 {
  margin: 0 0 4px;
  font-size: 13px;
  font-weight: 800;
  color: #6e4a0c;
  display: flex;
  align-items: center;
  gap: 6px;
}

.mf-explain-section p {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: #4a3a18;
}

.mf-bottom-grid {
  margin-top: 14px;
  display: grid;
  grid-template-columns: 1fr 1.15fr 1.4fr 1.3fr;
  gap: 14px;
}

@media (max-width: 1279px) {
  .mf-bottom-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 639px) {
  .mf-bottom-grid { grid-template-columns: 1fr; }
}

.mf-card {
  position: relative;
  height: 185px;
  border-radius: 8px;
  padding: 16px 18px;
  box-shadow: 0 2px 8px rgba(20, 50, 90, 0.08);
  overflow: hidden;
}

.mf-evidence-card {
  background: rgba(245, 251, 240, 0.95);
  border: 1px solid #c8ddb5;
}

.mf-evidence-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.mf-evidence-list a {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  background: #ffffff;
  border: 1px solid #d5e6c2;
  border-radius: 5px;
  font-size: 12.5px;
  color: #2c5070;
  text-decoration: none;
  transition: background 0.15s ease, border-color 0.15s ease;
}

.mf-evidence-list a span {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mf-evidence-list a:hover {
  background: #e8f5db;
  border-color: #5fa34b;
}

.mf-reward-card {
  background: rgba(247, 252, 231, 0.95);
  border: 1px solid #d6e8a6;
}

.mf-reward-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.mf-reward-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 4px;
}

.mf-reward-item img {
  width: 36px;
  height: 36px;
  image-rendering: pixelated;
}

.mf-reward-item strong {
  font-size: 12px;
  font-weight: 800;
  color: #1B2A3A;
}

.mf-reward-item small {
  font-size: 10.5px;
  color: #5a6a80;
  line-height: 1.4;
}

.mf-task-card {
  background: rgba(255, 247, 225, 0.95);
  border: 1px solid #ecc988;
}

.mf-task-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: calc(100% - 100px);
}

.mf-task-list li {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 12.5px;
  line-height: 1.45;
  color: #4a3a18;
}

.mf-task-list li svg {
  flex-shrink: 0;
  margin-top: 2px;
}

.mf-chest-decoration {
  position: absolute;
  right: 14px;
  bottom: 12px;
  width: 84px;
  height: auto;
  image-rendering: pixelated;
  pointer-events: none;
  filter: drop-shadow(0 3px 0 rgba(0, 0, 0, 0.18));
}

.mf-next-card {
  background: rgba(239, 248, 255, 0.95);
  border: 1px solid #bdd7f0;
  display: flex;
  flex-direction: column;
}

.mf-next-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #5fa34b;
  color: white;
  font-size: 11px;
  font-weight: 800;
  font-style: normal;
  border: 2px solid #ffffff;
}

.mf-next-body {
  margin: 0 0 auto;
  font-size: 12.5px;
  line-height: 1.55;
  color: #1f3a60;
  max-width: 60%;
}

.mf-mine-decoration {
  position: absolute;
  right: 8px;
  top: 30px;
  width: 90px;
  height: auto;
  image-rendering: pixelated;
  pointer-events: none;
  filter: drop-shadow(0 3px 0 rgba(0, 0, 0, 0.18));
}

.mf-next-button {
  width: 170px;
  height: 40px;
  background: #5fa34b;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 800;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  cursor: pointer;
  margin-top: 8px;
  box-shadow: 0 2px 0 #3a7a2c;
  font-family: inherit;
}

.mf-next-button:hover {
  background: #6fbb58;
}
`
