"""Agent execution engine with explicit state machine and structured working memory."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator

import structlog

from codegraph.llm.client import llm_client
from codegraph.agent.tools.registry import tool_registry
from codegraph.models.domain import AgentResponse, ReasoningStep

try:
    from codegraph.agent.memory.manager import MemoryManager
    from codegraph.agent.memory.base import MemoryType, MemoryPriority
    from codegraph.agent.compression.context_manager import ContextWindowManager

    _MEMORY_AVAILABLE = True
except ImportError:
    _MEMORY_AVAILABLE = False

logger = structlog.get_logger()


class AgentState(str, Enum):
    PLANNING = "planning"
    EXECUTING = "executing"
    SYNTHESIZING = "synthesizing"
    VALIDATING = "validating"
    REPLANNING = "replanning"
    SEARCHING = "searching"
    DONE = "done"
    FAILED = "failed"


@dataclass
class WorkingMemory:
    question: str
    intent: str = ""

    graph_facts: list[dict] = field(default_factory=list)
    text_chunks: list[dict] = field(default_factory=list)
    temporal_facts: list[dict] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)

    steps_executed: list[dict] = field(default_factory=list)
    state_history: list[str] = field(default_factory=list)

    total_tokens_used: int = 0
    total_tool_calls: int = 0
    iteration_count: int = 0


TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "graph_query",
            "description": "查询知识图谱中的实体关系。适用于：查找人物关系、组织结构、已知事实。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "自然语言查询"},
                    "entities": {"type": "array", "items": {"type": "string"}, "description": "实体名称列表"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "vector_search",
            "description": "语义相似度搜索文档片段。适用于：查找具体细节、引用原文。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "n_results": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "temporal_query",
            "description": "查询特定时间点的事实状态或追踪时间演变。",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_name": {"type": "string"},
                    "timestamp": {"type": "string", "description": "ISO格式"},
                    "mode": {"type": "string", "enum": ["snapshot", "evolution"]},
                },
                "required": ["entity_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "causal_trace",
            "description": "追踪事件因果链。适用于：'为什么发生''导致了什么'类问题。",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_name": {"type": "string"},
                    "direction": {"type": "string", "enum": ["causes", "effects", "both"]},
                    "depth": {"type": "integer", "default": 3},
                },
                "required": ["event_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "conflict_check",
            "description": "检查某个事实是否存在多源矛盾。适用于：验证信息可靠性。",
            "parameters": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string", "description": "要验证的事实声明"},
                },
                "required": ["claim"],
            },
        },
    },
]


SYSTEM_PROMPT = """你是 PulseGraph 的智能分析 Agent。你可以使用工具来查询知识图谱、搜索文档、追踪因果链。
根据用户的问题，选择合适的工具获取信息，然后综合回答。

回答规则：
1. 基于证据回答，不编造
2. 标注信息来源和置信度
3. 如有矛盾信息，明确指出
4. 如信息不足，说明缺失什么"""


class AgentExecutionEngine:
    def __init__(self, max_iterations: int = 5, token_budget: int = 50000):
        self.max_iterations = max_iterations
        self.token_budget = token_budget

        # Memory and context compression integration
        if _MEMORY_AVAILABLE:
            self._memory = MemoryManager(short_term_tokens=4000)
            self._context_manager = ContextWindowManager(max_tokens=self.token_budget)
        else:
            self._memory = None
            self._context_manager = None

    async def run(self, question: str, session_context: str = "") -> AgentResponse:
        memory = WorkingMemory(question=question)
        state = AgentState.PLANNING
        start_time = time.time()

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]
        if session_context:
            messages.append({"role": "system", "content": f"对话上下文：{session_context}"})
        messages.append({"role": "user", "content": question})

        # Memory integration: store query and recall relevant context
        if self._memory:
            try:
                await self._memory.remember(
                    content=f"User query: {question}",
                    memory_type=MemoryType.EPISODIC,
                    priority=MemoryPriority.HIGH,
                )

                relevant_memories = await self._memory.recall(question, top_k=3)
                memory_context = "\n".join(f"- {m.content}" for m in relevant_memories)
                if memory_context:
                    session_context = f"{session_context}\n\nRelevant memory:\n{memory_context}"
                    messages.append({"role": "system", "content": f"Relevant memory:\n{memory_context}"})
            except Exception as e:
                logger.warning("memory_recall_failed", error=str(e))

        while state not in (AgentState.DONE, AgentState.FAILED):
            memory.state_history.append(state.value)
            memory.iteration_count += 1

            if memory.iteration_count > self.max_iterations:
                state = AgentState.DONE
                break
            if memory.total_tokens_used >= self.token_budget:
                state = AgentState.DONE
                break

            match state:
                case AgentState.PLANNING | AgentState.EXECUTING | AgentState.REPLANNING:
                    state = await self._execute_with_tools(messages, memory)
                case AgentState.SYNTHESIZING:
                    state = AgentState.DONE
                case _:
                    state = AgentState.DONE

        total_ms = int((time.time() - start_time) * 1000)
        answer = self._extract_final_answer(messages)

        logger.info(
            "agent_complete",
            question=question[:80],
            iterations=memory.iteration_count,
            tool_calls=memory.total_tool_calls,
            duration_ms=total_ms,
            states=memory.state_history,
        )

        # Store result in memory for future recall
        if self._memory:
            try:
                await self._memory.remember(
                    content=f"Q: {question}\nA: {answer}",
                    memory_type=MemoryType.SEMANTIC,
                    priority=MemoryPriority.NORMAL,
                )
                await self._memory.consolidate()
            except Exception as e:
                logger.warning("memory_store_failed", error=str(e))

        return AgentResponse(
            answer=answer,
            confidence=0.8,
            reasoning_trace=[
                ReasoningStep(
                    step_id=i + 1,
                    action=s.get("action", ""),
                    tool=s.get("tool", ""),
                    input_params=s.get("input", {}),
                    output_summary=s.get("output", "")[:200],
                    duration_ms=s.get("duration_ms", 0),
                )
                for i, s in enumerate(memory.steps_executed)
            ],
        )

    async def _execute_with_tools(
        self, messages: list[dict], memory: WorkingMemory
    ) -> AgentState:
        """Call LLM with function calling, execute tools, return next state."""
        try:
            response = await llm_client.chat_with_tools(
                messages=messages,
                tools=TOOLS_SCHEMA,
            )
        except Exception as e:
            logger.error("agent_llm_call_failed", error=str(e))
            return AgentState.FAILED

        choice = response.choices[0]

        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            messages.append(choice.message.model_dump())

            for tool_call in choice.message.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)
                step_start = time.time()

                result = await tool_registry.execute(fn_name, fn_args)
                duration_ms = int((time.time() - step_start) * 1000)

                memory.steps_executed.append({
                    "action": fn_name,
                    "tool": fn_name,
                    "input": fn_args,
                    "output": str(result.get("data", ""))[:500],
                    "duration_ms": duration_ms,
                })
                memory.total_tool_calls += 1

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result.get("data", {}), ensure_ascii=False)[:2000],
                })

            return AgentState.EXECUTING
        else:
            if choice.message.content:
                messages.append({"role": "assistant", "content": choice.message.content})
            return AgentState.SYNTHESIZING

    def _extract_final_answer(self, messages: list[dict]) -> str:
        for msg in reversed(messages):
            if msg.get("role") == "assistant" and msg.get("content"):
                return msg["content"]
        return "无法生成回答。"

    async def stream(self, question: str, session_context: str = "") -> AsyncGenerator[str, None]:
        result = await self.run(question, session_context)
        words = result.answer.split()
        for word in words:
            yield json.dumps({"type": "token", "content": word + " "}, ensure_ascii=False)
        yield json.dumps({
            "type": "done",
            "confidence": result.confidence,
            "steps": len(result.reasoning_trace),
        })
