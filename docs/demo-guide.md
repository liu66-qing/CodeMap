# EvoGraph 演示文档

> 在线 Demo：https://evo-graph.vercel.app/
> GitHub：https://github.com/liu66-qing/KG-RAG-Agent

---

## 页面 1：Graph Explorer（知识图谱浏览器）

**截图位置**：打开首页 https://evo-graph.vercel.app/ 即可看到

**演示内容**：
- 左侧边栏导航（5个功能模块）
- 中央 D3.js 力导向图谱可视化（节点 = 实体，边 = 关系）
- 不同颜色节点代表不同实体类型（Person/Organization/Product/Event/Location/Technology/Concept）
- 右下角图例面板
- 顶部搜索栏 + 缩放/重置按钮

**字幕**：
```
EvoGraph 知识图谱浏览器 — 基于 D3.js 的交互式力导向图谱可视化。
节点代表实体（人物、组织、产品、事件等），边代表实体间的语义关系。
支持拖拽交互、缩放浏览、实体搜索，直观展示知识网络结构。
```

---

## 页面 2：Query Console（智能问答控制台）

**截图位置**：点击左侧 "Query Console" 导航

**演示内容**：
- 聊天式问答界面
- 预设示例问题按钮（"Who is the CEO of OpenAI?" / "What caused the leadership crisis..." / "Compare Microsoft and Google..."）
- 底部输入框
- 回答区域展示：答案文本 + 推理轨迹（Reasoning Trace）+ 溯源引用

**字幕**：
```
智能问答控制台 — Agent 自适应推理循环驱动。
支持事实查询、时序推理、因果分析、对比分析四类问题。
每个回答附带完整推理轨迹和事实溯源链，可追溯到原始文档片段。
Agent 动态选择工具（图查询/向量搜索/时序查询/因果推理），最多 5 轮迭代直到置信度达标。
```

---

## 页面 3：Document Ingestion（文档上传与知识演化）

**截图位置**：点击左侧 "Documents" 导航

**演示内容**：
- 拖拽上传区域（支持 PDF/TXT/MD/HTML）
- "Browse Files" 按钮
- 下方 Evolution Pipeline 流水线状态展示：
  Ingest → Extract → Resolve → Conflict Check → Merge
- 每个阶段的状态指示

**字幕**：
```
文档上传与知识图谱演化 — 上传文档自动触发异步演化流水线。
流水线包含 5 个阶段：文档加载 → LLM 实体/关系抽取 → 实体消歧去重 → 冲突检测 → 时序版本化合并。
新知识实时合并入图谱，通过 WebSocket 推送前端更新。
支持 PDF、TXT、Markdown、HTML 格式。
```

---

## 页面 4：Conflict Dashboard（知识冲突管理）

**截图位置**：点击左侧 "Conflicts" 导航

**演示内容**：
- 冲突列表（每条冲突显示类型、涉及实体、状态）
- 三类冲突标签：Temporal Overlap / Logical Contradiction / Source Disagreement
- 冲突详情：对比两个矛盾的事实来源
- 解决操作按钮

**字幕**：
```
知识冲突管理面板 — 自动检测三类知识矛盾。
时序重叠：同一角色在重叠时间段被多人占据（如两人同时担任 CEO）。
逻辑矛盾：互斥关系同时存在（如某人同时在职和离职）。
来源分歧：多个文档对同一事实给出不同说法。
检测到冲突后通知用户裁决，保留完整证据链供对比。
```

---

## 页面 5：Timeline（时序演化回放）

**截图位置**：点击左侧 "Timeline" 导航

**演示内容**：
- 时间轴滑块（可拖动选择时间点）
- 图谱快照对比（不同时间点的知识状态）
- 演化事件列表（文档处理记录、实体变更记录）
- 时间范围选择器

**字幕**：
```
时序演化回放 — 知识图谱的"时间旅行"功能。
每条关系携带 valid_from/valid_to 时间窗口，支持查看任意历史时刻的图谱状态。
可对比两个时间点之间的知识变化，追踪实体关系的演变历程。
适用于追踪公司高管变动、产品迭代、政策法规更新等时序场景。
```

---

## 整体项目介绍字幕（用于开头/结尾）

**开头**：
```
EvoGraph — 实时知识图谱演化智能体
一个生产级 Agentic RAG 系统，将传统 RAG 升级为：
文档 → 知识图谱自动构建 → 时序版本化 → 冲突检测 → 多跳推理 → 溯源回答
```

**技术栈展示**：
```
技术栈：Python + FastAPI | Neo4j 知识图谱 | Qdrant 向量检索 | DeepSeek LLM
前端：React + TypeScript + D3.js 图谱可视化 + TailwindCSS
部署：Vercel（前端）+ Render（后端）+ 全云服务架构
```

**结尾**：
```
GitHub: github.com/liu66-qing/KG-RAG-Agent
在线 Demo: evo-graph.vercel.app
核心创新：自适应推理循环 | 时序知识版本化 | 三类冲突检测 | 因果链推理 | 图感知混合检索 | 全链路溯源
```

---

## 截图建议顺序

1. 开头字幕（项目介绍）
2. **Graph Explorer 全屏截图** — 展示图谱可视化效果
3. **Query Console 截图** — 展示问答界面 + 示例问题
4. **Document Ingestion 截图** — 展示上传区域 + 流水线
5. **Conflict Dashboard 截图** — 展示冲突列表
6. **Timeline 截图** — 展示时间轴
7. 技术栈字幕
8. 结尾字幕（链接信息）
