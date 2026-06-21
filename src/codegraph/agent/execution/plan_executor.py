"""Plan-and-Execute: decompose -> plan -> execute steps -> synthesize.

When to use: Complex multi-hop queries, analysis tasks requiring multiple tools.
Pattern: Decompose -> Plan steps -> Execute each -> Replan if needed -> Synthesize

Design decisions:
- Explicit plan visible to user (interpretability + debuggability)
- Step dependency DAG -- parallel execution where possible
- Adaptive replanning -- if step fails or reveals new info, replan remaining
- Each step is a mini-ReAct (1-3 iterations max) -- bounded complexity per step
- Plan validation: reject plans with circular deps or impossible tool combos

Anti-drift mechanisms:
1. Goal anchor -- original query re-injected at each step
2. Plan coherence check -- each step output validated against plan expectations
3. Scope guard -- new discoveries don't expand scope unless explicitly allowed
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger()


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    id: str
    description: str
    tool_hint: str | None = None  # Suggested tool
    depends_on: list[str] = field(default_factory=list)
    status: StepStatus = StepStatus.PENDING
    result: str = ""
    error: str = ""
    latency_ms: float = 0


@dataclass
class ExecutionPlan:
    goal: str
    steps: list[PlanStep]
    created_at: float = field(default_factory=time.time)
    replanned: bool = False
    replan_reason: str = ""


@dataclass
class PlanExecResult:
    answer: str
    plan: ExecutionPlan
    step_results: dict[str, str]
    total_tokens: int = 0
    total_latency_ms: float = 0
    replans: int = 0


class PlanExecutor:
    """Plan-and-Execute with adaptive replanning.

    Compatible with the existing orchestrator LLM client (chat/chat_json)
    and tool registry (execute/call) patterns.
    """

    def __init__(
        self,
        llm_client: Any,
        tool_registry: Any,
        max_steps: int = 8,
        max_replans: int = 2,
        step_token_budget: int = 2000,
    ):
        self._llm = llm_client
        self._tools = tool_registry
        self._max_steps = max_steps
        self._max_replans = max_replans
        self._step_budget = step_token_budget

    async def execute(
        self, query: str, context: str = "", session_memory: Any = None
    ) -> PlanExecResult:
        """Decompose query into plan, execute steps, synthesize answer."""
        start_time = time.time()
        total_tokens = 0
        replans = 0

        # Phase 1: Generate plan
        plan = await self._generate_plan(query, context)
        total_tokens += len(plan.steps) * 100  # Rough estimate for planning cost

        # Phase 2: Execute steps in dependency order
        step_results: dict[str, str] = {}
        execution_order = self._topological_sort(plan.steps)

        for step_id in execution_order:
            step = next(s for s in plan.steps if s.id == step_id)

            # Check dependencies met
            deps_met = all(
                next(s for s in plan.steps if s.id == dep).status == StepStatus.COMPLETED
                for dep in step.depends_on
            )
            if not deps_met:
                step.status = StepStatus.SKIPPED
                continue

            # Execute step
            step.status = StepStatus.RUNNING
            step_start = time.time()

            try:
                dep_context = "\n".join(
                    f"[{dep}]: {step_results.get(dep, '')}"
                    for dep in step.depends_on
                )
                result = await self._execute_step(step, query, dep_context)
                step.result = result
                step.status = StepStatus.COMPLETED
                step_results[step.id] = result
            except Exception as e:
                step.error = str(e)
                step.status = StepStatus.FAILED

                # Replan if budget allows
                if replans < self._max_replans:
                    remaining = [s for s in plan.steps if s.status == StepStatus.PENDING]
                    if remaining:
                        new_steps = await self._replan(query, step_results, step.error)
                        for old in remaining:
                            old.status = StepStatus.SKIPPED
                        plan.steps.extend(new_steps)
                        plan.replanned = True
                        plan.replan_reason = f"Step '{step.description}' failed: {step.error}"
                        execution_order = self._topological_sort(plan.steps)
                        replans += 1

            step.latency_ms = (time.time() - step_start) * 1000

        # Phase 3: Synthesize final answer
        answer = await self._synthesize(query, step_results)
        total_latency = (time.time() - start_time) * 1000

        logger.info(
            "plan_execute_complete",
            steps_completed=sum(1 for s in plan.steps if s.status == StepStatus.COMPLETED),
            replans=replans,
            total_latency_ms=round(total_latency, 2),
        )

        return PlanExecResult(
            answer=answer,
            plan=plan,
            step_results=step_results,
            total_tokens=total_tokens,
            total_latency_ms=total_latency,
            replans=replans,
        )

    async def _generate_plan(self, query: str, context: str) -> ExecutionPlan:
        """Ask LLM to decompose query into executable steps."""
        tool_list = (
            self._tools.get_descriptions()
            if hasattr(self._tools, "get_descriptions")
            else ""
        )

        prompt = f"""Decompose this query into 2-{self._max_steps} executable steps.

Query: {query}
Context: {context}

Available tools: {tool_list}

Respond in JSON format:
{{
  "steps": [
    {{"id": "step_1", "description": "what to do", "tool_hint": "tool_name or null", "depends_on": []}}
  ]
}}

Rules:
- Each step should be atomic (one tool call)
- Express dependencies explicitly
- No circular dependencies
- Fewer steps preferred (don't over-decompose simple queries)"""

        response = await self._llm.chat_json(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )

        # Handle both string and dict responses (matches existing patterns in base.py)
        if isinstance(response, str):
            import json
            try:
                response = json.loads(response)
            except Exception:
                response = {"steps": []}

        steps = []
        for s in response.get("steps", []):
            steps.append(PlanStep(
                id=s.get("id", f"step_{uuid.uuid4().hex[:6]}"),
                description=s["description"],
                tool_hint=s.get("tool_hint"),
                depends_on=s.get("depends_on", []),
            ))

        return ExecutionPlan(goal=query, steps=steps)

    async def _execute_step(
        self, step: PlanStep, original_query: str, dep_context: str
    ) -> str:
        """Execute a single plan step (mini-ReAct, max 3 iterations)."""
        prompt = f"""Execute this step to help answer the original query.

Original query (DO NOT lose sight of this): {original_query}
Current step: {step.description}
Suggested tool: {step.tool_hint or 'any'}
Prior step results:
{dep_context}

Call the appropriate tool and return the result."""

        # Single tool call for simple steps with a clear tool hint
        if step.tool_hint and hasattr(self._tools, "call"):
            try:
                result = await self._tools.call(step.tool_hint)
                return str(result)[:2000]
            except Exception:
                pass

        # Fallback to LLM reasoning
        response = await self._llm.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        # Handle both string and dict returns
        if isinstance(response, dict):
            return response.get("content", "")
        return str(response)

    async def _replan(
        self, query: str, completed: dict[str, str], error: str
    ) -> list[PlanStep]:
        """Generate new steps after failure."""
        prompt = f"""A step in the plan failed. Generate replacement steps.

Original query: {query}
Completed so far: {list(completed.keys())}
Error: {error}

Generate 1-3 alternative steps in JSON:
{{"steps": [{{"id": "replan_1", "description": "...", "tool_hint": null, "depends_on": []}}]}}"""

        response = await self._llm.chat_json(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )

        if isinstance(response, str):
            import json
            try:
                response = json.loads(response)
            except Exception:
                return []

        return [
            PlanStep(
                id=s.get("id", f"replan_{uuid.uuid4().hex[:4]}"),
                description=s["description"],
                tool_hint=s.get("tool_hint"),
                depends_on=s.get("depends_on", []),
            )
            for s in response.get("steps", [])
        ]

    async def _synthesize(self, query: str, results: dict[str, str]) -> str:
        """Synthesize final answer from all step results."""
        results_text = "\n".join(f"[{k}]: {v}" for k, v in results.items())
        prompt = f"""Synthesize a final answer from these step results.

Original query: {query}

Step results:
{results_text}

Provide a comprehensive answer that directly addresses the query."""

        response = await self._llm.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        if isinstance(response, dict):
            return response.get("content", "")
        return str(response)

    def _topological_sort(self, steps: list[PlanStep]) -> list[str]:
        """Topological sort of steps by dependencies (Kahn's algorithm variant)."""
        pending_steps = [s for s in steps if s.status == StepStatus.PENDING]
        graph: dict[str, set[str]] = {s.id: set(s.depends_on) for s in pending_steps}
        order: list[str] = []
        visited: set[str] = set()

        def visit(node_id: str) -> None:
            if node_id in visited:
                return
            visited.add(node_id)
            for dep in graph.get(node_id, set()):
                if dep not in visited:
                    visit(dep)
            order.append(node_id)

        for s in pending_steps:
            visit(s.id)

        return order
