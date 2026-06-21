# CodeMap Agent 架构设计文档

## 概述

CodeMap 是一个多智能体代码分析系统，将复杂代码仓库转化为结构化的学习路径。区别于传统 RAG 系统的"检索-生成"单次循环，CodeMap 采用 4-Agent 流水线架构，每个 Agent 承担独立分析职责，通过显式上下文传递完成协作。

本文档阐述系统的核心架构决策及其 trade-off。读者对象：需要理解多智能体系统设计模式的工程师。

---

## 系统架构总览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CodeMap Agent System                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────┐    ┌──────────────────────────────────────────────┐   │
│  │   Frontend   │    │         API Layer (FastAPI + WebSocket)       │   │
│  │  React/Vite  │◄──►│  /api/v1/analysis  /api/v1/query  /ws       │   │
│  └─────────────┘    └──────────────┬───────────────────────────────┘   │
│                                     │                                   │
│  ┌──────────────────────────────────▼───────────────────────────────┐  │
│  │              AnalysisOrchestrator (4-Stage Pipeline)              │  │
│  │                                                                   │  │
│  │   ┌──────────┐    ┌───────────┐ ┌───────────┐    ┌──────────┐   │  │
│  │   │ Overview │───►│ MainFlow  │ │ Showcase  │───►│ Takeaway │   │  │
│  │   │  Agent   │    │  Agent    │ │  Agent    │    │  Agent   │   │  │
│  │   └────┬─────┘    └─────┬─────┘ └─────┬─────┘    └────┬─────┘   │  │
│  │        │                │              │               │          │  │
│  │        └────────────────┴──────┬───────┴───────────────┘          │  │
│  │                                │                                   │  │
│  └────────────────────────────────┼───────────────────────────────┘  │
│                                   │                                    │
│  ┌────────────────────────────────▼───────────────────────────────┐  │
│  │                    Shared Infrastructure                         │  │
│  │                                                                  │  │
│  │  ┌────────────┐  ┌────────────┐  ┌───────────┐  ┌───────────┐  │  │
│  │  │  Tool      │  │  Memory    │  │   LLM     │  │  Observ-  │  │  │
│  │  │  Registry  │  │  System    │  │  Client   │  │  ability  │  │  │
│  │  └─────┬──────┘  └─────┬──────┘  └─────┬─────┘  └─────┬─────┘  │  │
│  │        │                │               │              │         │  │
│  └────────┼────────────────┼───────────────┼──────────────┼─────┘  │
│           │                │               │              │          │
│  ┌────────▼────────────────▼───────────────▼──────────────▼─────┐  │
│  │                   Storage & External Services                   │  │
│  │                                                                 │  │
│  │  ┌─────────┐  ┌─────────┐  ┌──────────────┐  ┌────────────┐  │  │
│  │  │  Redis  │  │  Neo4j  │  │ Vector Store │  │  LLM API   │  │  │
│  │  │ (Cache) │  │ (Graph) │  │  (Qdrant)    │  │ (OpenAI等) │  │  │
│  │  └─────────┘  └─────────┘  └──────────────┘  └────────────┘  │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**数据流**:
```
GitHub URL → Ingestion (AST Parse + Graph Build) → Storage
                                                      │
User Query → Planner → Tool Execution Loop → Synthesis → Response
                                                      │
Repo Analysis → Overview → [MainFlow ║ Showcase] → Takeaway → Learning Map
```

---

## 1. 记忆系统 (Memory Architecture)

### 1.1 设计哲学

Agent 的记忆问题本质上是**信息生命周期管理**问题。一条信息在不同阶段有不同价值：

- 当前推理步骤的上下文 → 必须快速、完整地获取
- 本次会话的历史对话 → 需要做指代消解，但不需要原文
- 跨会话的知识积累 → 需要持久化，但访问频率低

这对应人类认知的三层结构：工作记忆、情景记忆、语义记忆。

### 1.2 工作记忆 (Working Memory)

```python
@dataclass
class WorkingMemory:
    question: str              # 当前查询
    intent: str                # 分类后的意图
    graph_facts: list[dict]    # 本轮检索的图谱事实
    text_chunks: list[dict]    # 本轮检索的文本片段
    steps_executed: list[dict] # 已执行的推理步骤
    total_tokens_used: int     # Token 预算消耗
```

**存储选型**: 纯内存 dataclass，无序列化开销。

**容量策略**: 基于 token budget (50,000 tokens hard cap) 而非消息条数。原因：一条包含大型代码片段的消息可能消耗 5,000 tokens，而 10 条简短确认消息可能只占 500 tokens。按条数限制会导致不公平的淘汰。

**淘汰机制**: 工具返回结果截断至 2,000 字符 (`content[:2000]`)，preview 截断至 400 字符。这是 production 中最常见的 context overflow 防护。

**为什么不用 Redis**: 工作记忆是 hot path 上的数据结构，每次 LLM 调用都要读取完整内容构造 messages。Redis 引入 ~1ms 网络延迟，在 5 轮迭代中累积 5-10ms，且序列化/反序列化 Python dict 的 CPU 开销超过收益。内存 dataclass 是零成本抽象。

### 1.3 会话记忆 (Session Memory)

```python
@dataclass
class SessionMemory:
    session_id: str
    conversation_history: list[dict]  # 最近对话摘要
    entity_focus: dict[str, int]      # 实体出现频率
```

**核心能力 — 指代消解 (Coreference Resolution)**:

```
用户: "分析一下 React 的架构"
系统: [记录 entity_focus: {"React": 1}]
用户: "它的虚拟 DOM 是怎么实现的？"
系统: [将 "它" 替换为 "React"] → "React的虚拟DOM是怎么实现的？"
```

**存储选型**: 进程内 dict (`_sessions: dict[str, SessionMemory]`)。

**为什么不用 Redis/数据库**: 当前部署为单进程 FastAPI，Session 生命周期与进程一致。引入外部存储只在以下场景有价值：
- 多实例部署 (需要 session affinity 或共享存储)
- 服务器重启后恢复 (对一个分析工具而言优先级很低)

当系统需要水平扩展时，Session Memory 是第一个需要外移到 Redis 的组件。当前设计为此预留了接口——`get_session()` 函数是唯一的访问入口，替换实现不影响调用方。

### 1.4 长期记忆 (Long-Term Memory / Knowledge Graph)

```
┌─────────────────────────────────────────────┐
│           Neo4j Knowledge Graph              │
│                                              │
│  (Entity)──[CALLS]──►(Entity)               │
│  (Entity)──[IMPORTS]──►(Entity)             │
│  (Commit)──[MODIFIES]──►(Entity)            │
│  (Conflict)──[INTRODUCED_IN]──►(Commit)     │
│                                              │
│  全量持久化，TTL = 永久                       │
│  检索方式: Cypher 查询 + 图遍历              │
└─────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│        Vector Store (Qdrant/Chroma)          │
│                                              │
│  文档片段 → Embedding → 语义检索             │
│  检索方式: Cosine similarity + re-ranking    │
└─────────────────────────────────────────────┘
```

**为什么用 Neo4j 而非纯向量检索**:

代码理解的核心问题是**关系推理**，不是文本相似度。"谁调用了这个函数"、"改了这个接口影响哪些模块" 这类问题需要图遍历 (BFS/DFS on CALLS edges)，向量检索对此无能为力。

但语义搜索在"这段代码做什么"类问题上比结构化查询更灵活。因此采用 Hybrid Retrieval:

```
Query → [Vector Search (语义)] + [Graph Retrieval (结构)] → Merge + Rank → Context
```

### 1.5 记忆巩固 (Memory Consolidation)

当前实现中，巩固路径为：

```
WorkingMemory (per-request) ──分析完成──► Neo4j (持久化)
     │                                        ▲
     └── tool 执行结果写入 ──────────────────┘
         (graph_query/vector_search 结果
          被写入 working_memory.graph_facts)
```

**晋升规则**:
1. 代码结构信息 (AST、调用关系) → 直接写入 Neo4j，无需巩固判断
2. 分析结论 (架构风格、设计模式) → 以 `RepoAnalysis` 节点持久化
3. 对话摘要 → 不持久化 (设计决策：分析工具不需要跨会话记忆用户偏好)

---

## 2. 执行模式 (Execution Modes)

### 2.1 ReAct 模式 (AgentExecutionEngine)

```
                    ┌──────────────┐
                    │   Planning   │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
              ┌────►│  Executing   │◄────┐
              │     └──────┬───────┘     │
              │            │             │
              │     ┌──────▼───────┐     │
              │     │  Tool Call   │     │
              │     └──────┬───────┘     │
              │            │             │
              │     Tool Result ≠ Done   │
              └────────────┘             │
                                         │
                    ┌──────────────┐      │
                    │ Synthesizing │──────┘ (if validation fails)
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │     Done     │
                    └──────────────┘
```

**适用场景**: 单跳查询、简单工具调用。例："谁调用了 `parse_ast` 函数？"

**反循环机制**:
- **Token budget hard cap**: `total_tokens_used >= 50,000` 时强制退出
- **Iteration cap**: `max_iterations = 5`，防止无限 tool-call 循环
- **Output truncation**: 每次 tool 返回截断到 2,000 chars，防止单次调用撑爆 context

**为什么用状态机而非递归**: 状态机的每个状态转换都是可观测的 (`state_history`)。面试官问"你的 Agent 卡在哪了？"时，看 `["planning", "executing", "executing", "executing", "done"]` 立刻知道是 3 轮 tool call 后自然收敛。递归调用栈无法提供这种可观测性。

### 2.2 Plan-Execute 模式 (AgentOrchestrator + QueryPlanner)

```
Question ──► QueryPlanner ──► Execution Plan (Steps with dependencies)
                                    │
                    ┌───────────────▼───────────────┐
                    │  for step in plan:            │
                    │    result = tool.execute()    │
                    │    working_memory.append()    │
                    │  end                          │
                    └───────────────┬───────────────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │  Synthesis (LLM call)          │
                    └───────────────┬───────────────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │  Validation (LLM call)         │
                    │  valid? → Done                 │
                    │  invalid? → Replan remaining   │
                    └───────────────────────────────┘
```

**适用场景**: 多跳分析、因果推理。例："React 的 Fiber 架构为什么比 Stack Reconciler 快？"

**Plan 结构**:
```json
{
  "intent": "causal",
  "steps": [
    {"step_id": 1, "action": "find_entity", "tool": "graph_query", "depends_on": []},
    {"step_id": 2, "action": "trace_causality", "tool": "causal_reason", "depends_on": [1]},
    {"step_id": 3, "action": "verify_evidence", "tool": "vector_search", "depends_on": [2]}
  ]
}
```

**自适应重规划**: 当 Validation 阶段返回 `is_valid: false` 时，不会重新执行全部步骤，而是根据 `evidence_gaps` 生成补充检索步骤。这避免了"重头再来"的浪费。

**为什么分离 Plan 和 Execute**:
1. **可解释性**: Plan 作为中间产物可以展示给用户 ("我准备这样分析...")
2. **可干预性**: 未来可以在 Plan 阶段加入人机协作 (human-in-the-loop)
3. **错误定位**: 如果最终答案错误，可以判断是 Plan 错了还是某个 Step 执行错了

### 2.3 模式选择 (Mode Selection)

```
┌─────────────────────────────────────────┐
│         Query Complexity Router          │
│                                          │
│  Intent Classification (LLM, ~100 tok)  │
│         │                                │
│         ├─ factual → ReAct              │
│         ├─ temporal → Plan-Execute      │
│         ├─ causal → Plan-Execute        │
│         ├─ comparative → Plan-Execute   │
│         └─ exploratory → Plan-Execute   │
│                                          │
│  Fast path: 如果 query 只含 1 个实体    │
│  且无时间/因果关键词 → 直接 ReAct       │
└─────────────────────────────────────────┘
```

**启发式快速路径**: 对明显简单的查询 (单实体、无修饰词)，跳过 LLM 分类调用，直接走 ReAct。这节省 ~100 tokens 和 ~500ms 延迟。

**为什么不全走 Plan-Execute**: 简单查询的 Plan 几乎总是 "step 1: search; step 2: answer"。走 Plan-Execute 会多一次 LLM 调用 (Planner) + 一次 LLM 调用 (Validator)，对简单查询是纯浪费。

---

## 3. 上下文压缩 (Context Compression)

### 3.1 策略对比

| 策略 | 信息损失 | 计算成本 | 适用场景 |
|------|---------|---------|---------|
| Verbatim (原文) | 0% | 0 | 最近 1-2 轮对话 |
| Summary (摘要) | 20-40% | 1 LLM call | 中距离历史 (3-8 轮前) |
| Entity Extraction | 50-70% | 解析 | 远距离历史 (>8 轮前) |
| Truncation (截断) | Variable | 0 | Tool 输出防溢 |

### 3.2 分区压缩策略 (Production Default)

```
Context Window Budget: 128K tokens (model limit)
┌─────────────────────────────────────────────────────────┐
│                                                          │
│  Zone 1 (Recent) ──── Verbatim ──── 50% budget          │
│  最近 1-2 轮对话 + 当前 tool 输出，保持原文完整性         │
│                                                          │
│  Zone 2 (Middle) ──── Summary ──── 30% budget            │
│  3-8 轮前的对话，压缩为 "用户问了X，系统回答了Y"         │
│                                                          │
│  Zone 3 (Distant) ──── Entity Extract ──── 20% budget   │
│  更早的历史，只保留 "涉及实体: [A, B, C]"               │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 3.3 当前实现的压缩手段

CodeMap 当前采用**实用主义压缩**，而非完整的多策略切换：

1. **Tool 输出截断**: `content[:2000]` — 硬截断，简单有效
2. **Preview 压缩**: `_preview(obj, max_chars=400)` — trace 存储时压缩
3. **Working Memory 不累积**: 每次 request 重建，自然避免历史膨胀
4. **Session Memory 摘要**: `answer_summary: answer[:200]` — 只存答案前 200 字符

**压缩触发时机**:
- Token budget 达到 80% → 当前实现中表现为 iteration 退出
- Tool 输出 > 2,000 chars → 立即截断

**为什么不做更精细的压缩**: 当前系统的对话深度有限 (max 5 iterations)。在 5 轮以内，原始 context + truncated tool outputs 通常不超过 20K tokens。精细压缩的 ROI 在这个规模下为负。当系统扩展到支持 20+ 轮自主推理时，分区压缩会成为必要。

---

## 4. 会话管理 (Session Management)

### 4.1 状态机

```
              create_session()
                    │
                    ▼
┌──────┐    ┌──────────┐    complete()    ┌───────────┐
│      │    │          │─────────────────►│           │
│ INIT │───►│  ACTIVE  │                  │ COMPLETED │
│      │    │          │◄─────┐           │           │
└──────┘    └──────────┘      │           └───────────┘
                │    ▲        │
          pause()│    │resume()│
                ▼    │        │
            ┌──────────┐      │
            │  PAUSED  │──────┘ (timeout → expire)
            └──────────┘
                │
                │ TTL expired
                ▼
            ┌──────────┐
            │ EXPIRED  │
            └──────────┘
```

### 4.2 持久化策略

| 存储层 | 数据内容 | TTL | 失败行为 |
|--------|---------|-----|---------|
| In-Memory Dict | Session state, entity_focus | 进程生命周期 | 服务重启丢失 |
| Redis (计划中) | Session state 序列化 | 7 天 | Graceful degradation to in-memory |
| Neo4j | 分析结果 (RepoAnalysis) | 永久 | 分析需要重跑 |

**Graceful Degradation 设计**:

```python
async def get_session(session_id: str) -> SessionMemory:
    # 1. 尝试 in-memory
    if session_id in _sessions:
        return _sessions[session_id]
    # 2. 未来: 尝试 Redis 恢复
    # 3. 兜底: 创建新 session
    _sessions[session_id] = SessionMemory(session_id=session_id)
    return _sessions[session_id]
```

核心原则：**从不因为存储层失败而拒绝服务**。丢失历史 context 的代价是回答质量下降，但这远好于返回 500 错误。

### 4.3 会话分叉 (Fork) — 设计预留

对于探索性分析，用户可能想同时探索两个方向 ("这个函数是做缓存的还是做序列化的？两个方向都看看")。分叉语义：

```
Session A (active)
    ├── Fork B: "假设是缓存" → 继续分析
    └── Fork C: "假设是序列化" → 继续分析
```

当前未实现，但 SessionMemory 的 dataclass 设计支持 deepcopy 分叉，不需要架构改动。

---

## 5. 多智能体通信 (Multi-Agent Communication)

### 5.1 4-Stage Pipeline 通信模型

```
┌────────────┐  architectureSummary  ┌────────────┐
│  Overview  │──────────────────────►│  MainFlow  │
│   Agent    │──────────────────┐    └────────────┘
└────────────┘                  │
                                │    ┌────────────┐
                    _signals    └───►│  Showcase  │
                                     └─────┬──────┘
                                           │ highlights
                                     ┌─────▼──────┐
                                     │  Takeaway  │
                                     └────────────┘
```

**通信机制**: 显式 context dict 传递 (非消息总线)

```python
# AnalysisOrchestrator.analyze_repo()
context["architectureSummary"] = overview.get("architectureSummary", "")
context["_signals"] = overview.get("_signals", {})
# ... MainFlow 和 Showcase 并行执行，各自从 context 读取
context["highlights"] = showcase.get("highlights", [])
# Takeaway 从完整 context 读取所有前置结果
```

**为什么用 Context Dict 而非 Message Bus**:

4 个 Agent 的执行拓扑是静态已知的 (DAG)，不需要运行时路由。Message Bus 的价值在于：
- 动态参与者 (agents 可以运行时加入/离开)
- 1-to-N 广播
- 异步解耦

这些在固定 4-stage pipeline 中都不需要。Context Dict 的优势：
- 零序列化成本 (Python dict 直接传递)
- 类型安全 (IDE 可以追踪 key 的使用)
- 调试时 `print(context)` 即可看到全部状态

### 5.2 并行执行与依赖管理

```python
# Stage 2 & 3 并行执行
mainflow_task = asyncio.create_task(self._safe_run(self.mainflow_agent, ...))
showcase_task = asyncio.create_task(self._safe_run(self.showcase_agent, ...))
mainflow, showcase = await asyncio.gather(mainflow_task, showcase_task)
```

**执行 DAG**:
```
Overview ──┬──► MainFlow  ─┐
           │                ├──► Takeaway
           └──► Showcase  ─┘
```

拓扑约束:
- MainFlow 和 Showcase 都依赖 Overview 的 `architectureSummary`
- Takeaway 依赖 Showcase 的 `highlights`
- MainFlow 和 Showcase 之间无依赖，可并行

**容错**: 任何一个 Stage 失败不会 abort 整个 pipeline。失败 Stage 返回 error stub:

```python
async def _safe_run(self, agent, context, stage_name) -> dict:
    try:
        return await agent.run(context)
    except Exception as e:
        return {"_error": f"{type(e).__name__}: {e}", "_stage": stage_name}
```

下游 Agent 需要处理上游输出为空的情况。这是 **partial degradation** 策略 — 给用户 3/4 的分析结果好过什么都不给。

### 5.3 Query-Answer 模式的通信 (AgentOrchestrator)

在非 pipeline 模式下 (用户自由提问)，通信模式变为：

```
Planner ──plan──► Executor ──evidence──► Synthesizer ──answer──► Validator
                                                                      │
                                                         invalid ─────┘
                                                              │
                                                         Replanner
```

这是 Blackboard 模式的变体：Working Memory 作为共享黑板，每个阶段往上面写入信息，后续阶段从中读取。

---

## 6. 工具系统 (Tool System)

### 6.1 架构设计

```
┌──────────────────────────────────────────────────────────┐
│                    ToolRegistry                            │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ _tools: dict[str, Callable]                         │ │
│  │                                                      │ │
│  │  "graph_query"      → _graph_query()                │ │
│  │  "vector_search"    → _vector_search()              │ │
│  │  "temporal_query"   → _temporal_query()             │ │
│  │  "causal_reason"    → _causal_reason()              │ │
│  │  "find_callers"     → _find_callers()               │ │
│  │  "analyze_impact"   → _analyze_impact()             │ │
│  │  "explain_symbol"   → _explain_symbol()             │ │
│  │  ...                                                 │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                           │
│  execute(tool_name, params) → {"success": bool, "data"}  │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

### 6.2 Schema-Driven Dispatch

Tool 的输入通过 JSON Schema 定义，LLM 通过 function calling 自主选择工具：

```json
{
  "type": "function",
  "function": {
    "name": "graph_query",
    "description": "查询知识图谱中的实体关系",
    "parameters": {
      "type": "object",
      "properties": {
        "query": {"type": "string"},
        "entities": {"type": "array", "items": {"type": "string"}}
      },
      "required": ["query"]
    }
  }
}
```

**为什么用 Schema 而非硬编码路由**:
- LLM function calling 是自适应的 — 新增工具只需添加 schema，无需修改路由逻辑
- Schema 同时服务于文档和验证 (self-documenting)
- 支持不同 LLM provider (OpenAI, DeepSeek) 的统一接口

### 6.3 双轨工具体系

系统有两套工具注册方式，服务于不同执行模式：

| 体系 | 注册方式 | 调用方式 | 用途 |
|------|---------|---------|------|
| ToolRegistry (全局) | 字符串名 → async 函数 | `tool_registry.execute(name, params)` | AgentOrchestrator/Engine |
| BaseAgent.tools (实例) | 字符串名 → async 函数 | `self.call_tool(name, **kwargs)` | 4-Stage Pipeline Agents |

**为什么两套**: 全局 Registry 服务于 LLM function calling (需要 JSON Schema 描述)；实例 tools 服务于确定性分析流程 (Agent 知道要调用什么，不需要 LLM 决策)。

### 6.4 调用追踪 (Auto-Tracing)

每次 `call_tool()` 自动记录：

```python
ToolCall(
    tool_name="call_graph_tracer",
    args={"repo_url": "...", "entry_point": "main.py"},
    result=<truncated preview>,
    duration_ms=342.5,
    error=None
)
```

同时写入两个目的地：
1. `AgentTrace.tool_calls` — 本次 Agent 运行的完整 trace (给前端展示)
2. `tool_stats_collector` — 全局统计 (调用次数、成功率、P99 延迟)

**为什么在 BaseAgent 层做追踪而非在 Tool 内部**: 关注点分离。Tool 只负责"做事"，不应该知道自己被谁追踪。如果追踪逻辑在 Tool 内部，每个新 Tool 都要记得加追踪代码 — 必然会遗漏。

---

## 7. 技能系统 (Skill System)

### 7.1 当前设计: 4-Stage Agent = 4 Skills

在 CodeMap 中，Skill 以 Agent 为粒度：

```
OverviewAgent  → "理解仓库定位" skill
MainFlowAgent  → "追踪执行流程" skill
ShowcaseAgent  → "识别设计亮点" skill
TakeawayAgent  → "提取可复用模式" skill
```

每个 Agent 的 `analyze()` 方法就是一个完整的 skill 执行单元。

### 7.2 Trigger 机制

| Trigger 类型 | 示例 | 实现 |
|-------------|------|------|
| Explicit API Call | `POST /api/v1/analysis` | AnalysisOrchestrator.analyze_repo() |
| Intent Classification | "这个函数为什么这么设计？" | QueryPlanner → causal intent → Plan-Execute |
| Pipeline Position | Stage 2 depends on Stage 1 | DAG 拓扑顺序 |
| Progress Callback | 前端状态更新 | `on_progress("mainflow", "running")` |

### 7.3 Skill 组合 (Composition)

4-Stage Pipeline 本身就是 Skill 组合的实例:

```python
class AnalysisOrchestrator:
    def __init__(self):
        self.overview_agent = OverviewAgent(tools)   # Skill 1
        self.mainflow_agent = MainFlowAgent(tools)   # Skill 2
        self.showcase_agent = ShowcaseAgent(tools)    # Skill 3
        self.takeaway_agent = TakeawayAgent(tools)    # Skill 4
    
    async def analyze_repo(self, repo_url):
        # Skill 组合逻辑: 1 → [2,3] → 4
        overview = await self._safe_run(self.overview_agent, ...)
        mainflow, showcase = await asyncio.gather(...)
        takeaway = await self._safe_run(self.takeaway_agent, ...)
```

**组合规则**:
- `depends_on`: Takeaway depends on [Showcase]
- `parallel_with`: MainFlow parallel with Showcase  
- `requires_context`: 所有 Agent 都需要 Overview 的 architectureSummary

---

## 8. 防护机制 (Guardrails)

### 8.1 循环检测 (Loop Detection)

**问题**: LLM 可能重复调用相同工具 + 相同参数，永远无法退出。

**实现的防护层**:

```
Layer 1: Iteration Cap (max_iterations = 5)
    → 无论如何，5 轮后强制退出
    → 最简单、最可靠的防护

Layer 2: Token Budget Cap (50,000 tokens)
    → 即使每轮不算多，累积也有上限
    → 防止 "每轮只用一点点但跑了很多轮" 的情况

Layer 3: State Machine Convergence
    → SYNTHESIZING 状态只能转向 DONE
    → 状态机设计保证不可能无限循环

Layer 4: Output Truncation (2,000 chars per tool result)
    → 防止单次 tool call 吃掉全部 context budget
    → 间接限制了 LLM 的 "好奇心" (没有无限长的输入可供分析)
```

**为什么没有 Action Fingerprint Dedup**: 当前 max_iterations=5 足够短，重复调用在 5 轮内的影响有限。当 max_iterations 增大到 20+ 时，需要加入 fingerprint dedup:

```python
# 未来实现
seen_actions = set()
fingerprint = hash((tool_name, frozenset(args.items())))
if fingerprint in seen_actions:
    force_exit("repeated action detected")
seen_actions.add(fingerprint)
```

### 8.2 漂移检测 (Drift Detection)

**问题**: Agent 在多步推理中逐渐偏离原始问题。例如用户问"React 的性能优化策略"，Agent 追到第 4 步变成在分析 JavaScript 引擎的 JIT 编译原理。

**当前实现**: 通过 Validation 阶段间接实现:

```python
VALIDATION_PROMPT = """Validate this answer against the evidence. Check:
1. Is every claim grounded in the evidence?
2. Are there any hallucinations?
3. Is the confidence score appropriate?"""
```

Validator 检查的是 answer 与 evidence 的对齐度。如果 Agent 漂移了，最终 synthesis 会引用不相关的 evidence，Validator 会返回 `is_valid: false`，触发 replan。

**设计决策**: 为什么检测漂移放在末尾而非每步:
- 每步检测成本高 (每步多一次 LLM 调用)
- 有些看似偏离的中间步骤实际是必要的上下文收集
- 只在最终答案时检测，允许 Agent 有"探索空间"

### 8.3 失控保护 (Runaway Protection)

```
┌────────────────────────────────────────────┐
│         Protection Layer Stack             │
│                                            │
│  ┌──────────────────────────────────────┐  │
│  │ L1: Token Budget    (50K tokens)     │  │
│  │     → 所有 LLM 调用的总 token 消耗  │  │
│  └──────────────────────────────────────┘  │
│  ┌──────────────────────────────────────┐  │
│  │ L2: Iteration Limit (5 iterations)   │  │
│  │     → Plan-Execute-Validate 循环次数 │  │
│  └──────────────────────────────────────┘  │
│  ┌──────────────────────────────────────┐  │
│  │ L3: Output Truncation (2K chars)     │  │
│  │     → 每次 tool 输出的字符上限       │  │
│  └──────────────────────────────────────┘  │
│  ┌──────────────────────────────────────┐  │
│  │ L4: Exception Isolation              │  │
│  │     → _safe_run 确保单 Agent 失败    │  │
│  │       不影响其他 Agent               │  │
│  └──────────────────────────────────────┘  │
│  ┌──────────────────────────────────────┐  │
│  │ L5: Graceful Degradation             │  │
│  │     → 超时/失败时返回部分结果        │  │
│  │       而非空错误                     │  │
│  └──────────────────────────────────────┘  │
└────────────────────────────────────────────┘
```

**设计哲学**: 多层防护、各层独立。即使某一层被绕过 (比如 token 计算不精确)，其他层仍然保护系统。这是 defense-in-depth 思想在 Agent 系统中的应用。

---

## 9. 设计决策与权衡 (Design Trade-offs)

| 决策 | 选择 | 替代方案 | 为什么选择当前方案 |
|------|------|----------|-------------------|
| Agent 间通信 | Context Dict 传递 | Message Bus / Event System | 静态 4-stage DAG 不需要动态路由；dict 零开销 |
| 执行模式 | 双模 (ReAct + Plan-Execute) | 统一用 Plan-Execute | 简单查询不需要 Plan 的开销 (~200 tokens + 500ms) |
| 工作记忆 | In-memory dataclass | Redis | Hot path 不能承受网络延迟；进程内零成本 |
| Session 存储 | Process dict | Redis + TTL | 单进程部署无需分布式；预留 Redis 迁移接口 |
| 错误处理 | Partial degradation | Fail-fast | 给用户 3/4 的结果好过给 500 错误 |
| Tool 追踪 | BaseAgent 层自动追踪 | 每个 Tool 内部追踪 | 关注点分离；不可能遗漏 |
| LLM Schema 约束 | System prompt 嵌入 schema | response_format: json_schema | DeepSeek 等 provider 不支持 structured output |
| 状态机 vs 递归 | 显式状态机 | 递归调用 | 可观测性 — state_history 是免费的调试日志 |
| 并行策略 | asyncio.gather (Stage 2+3) | 全串行 | MainFlow 和 Showcase 无依赖，并行节省 ~50% 延迟 |
| Token 计算 | len(text)//4 估算 | tiktoken 精确计算 | 估算误差 ~15%，但避免引入 tiktoken 依赖 |

---

## 10. 可观测性 (Observability)

### 10.1 追踪模型

```
AgentTrace
├── agent_name: "overview"
├── started_at / finished_at → duration
├── tool_calls: [ToolCall, ToolCall, ...]
│   └── tool_name, args, result_preview, duration_ms, error
├── llm_calls_detail: [LLMCall, LLMCall, ...]
│   └── prompt_chars, response_chars, tokens_in, tokens_out, model
├── total_tokens: 累计消耗
└── output: 最终结果 / error: 失败原因
```

每个 Agent 运行产生一个 AgentTrace。AnalysisOrchestrator 收集 4 个 traces 返回给前端:

```python
results["_traces"] = {
    "overview": self.overview_agent.trace.to_dict(),
    "mainflow": self.mainflow_agent.trace.to_dict(),
    "showcase": self.showcase_agent.trace.to_dict(),
    "takeaway": self.takeaway_agent.trace.to_dict(),
}
```

### 10.2 监控指标

| 指标 | 来源 | 用途 |
|------|------|------|
| 每 Agent 延迟 | AgentTrace.duration_ms | 发现慢 Agent |
| 每 Tool 成功率 | tool_stats_collector | 发现不稳定的外部依赖 |
| Token 消耗分布 | AgentTrace.total_tokens | LLM 成本优化 |
| Tool 调用次数 | tool_stats_collector | 识别过度调用 |
| State History | WorkingMemory.state_history | 调试 Agent 卡死 |

---

## 11. 未来规划

- [ ] **持久化 Session Memory** — Redis + TTL 7d，支持服务重启恢复
- [ ] **Multi-model routing** — 简单查询用便宜模型 (DeepSeek-V2)，复杂推理用 GPT-4
- [ ] **Action Fingerprint Dedup** — 当 max_iterations 增大后防止重复调用
- [ ] **Streaming Plan Execution** — 每完成一步就推送给前端，而非等全部完成
- [ ] **Human-in-the-loop** — Plan 阶段允许用户修改执行计划
- [ ] **Distributed Agents** — Celery worker 分布式执行，支持大仓库并行分析
- [ ] **Memory TTL Decay** — 长期记忆按访问频率衰减，自动遗忘低价值信息
- [ ] **Skill Marketplace** — 用户贡献的分析 Agent 可作为 plugin 加载

---

## 附录: 关键文件索引

| 文件 | 职责 |
|------|------|
| `src/codegraph/agent/base.py` | BaseAgent 抽象、ToolCall/AgentTrace 数据结构 |
| `src/codegraph/agent/engine.py` | ReAct 执行引擎 (状态机 + function calling) |
| `src/codegraph/agent/orchestrator.py` | Plan-Execute 编排器 (Planner + Validator) |
| `src/codegraph/agent/planner.py` | 查询分解器 (Question → Steps with deps) |
| `src/codegraph/agent/memory.py` | 会话记忆 (指代消解 + entity focus) |
| `src/codegraph/agent/tools/registry.py` | 全局工具注册表 (12+ tools) |
| `src/codegraph/agent/analysis_orchestrator.py` | 4-Stage Pipeline 编排 |
| `src/codegraph/agent/stages/overview_agent.py` | Stage 1: 仓库定位 + 阅读顺序 |
| `src/codegraph/storage/redis_cache.py` | Redis 缓存客户端 (per-event-loop) |

---

*本文档基于 CodeMap 源码撰写，反映系统的实际实现而非理想设计。*
*最后更新: 2026-06*