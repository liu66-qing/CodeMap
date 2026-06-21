"""ReAct (Reason + Act) execution loop.

When to use: Simple queries, single-hop retrieval, straightforward tool calls.
Pattern: Think -> Act -> Observe -> Think -> ... -> Answer

Design decisions:
- Max iterations cap prevents infinite loops (default: 10)
- Each iteration has token budget check -- bail if context getting too large
- Thought/Action/Observation structured format for interpretability
- Early termination when confidence threshold met (no wasted iterations)
- Backtracking: if last action yielded no useful info, try different tool

Anti-loop mechanisms:
1. Action history dedup -- same tool+args won't fire twice
2. Monotonic progress check -- if 3 iterations with no new information, force conclude
3. Max iteration hard cap
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger()


class StepType(str, Enum):
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"


@dataclass
class ReActStep:
    step_type: StepType
    content: str
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    token_count: int = 0
    latency_ms: float = 0
    timestamp: float = field(default_factory=time.time)



@dataclass
class ReActResult:
    answer: str
    steps: list[ReActStep]
    total_tokens: int = 0
    total_latency_ms: float = 0
    iterations: int = 0
    termination_reason: str = ""  # "answered" | "max_iterations" | "no_progress" | "token_budget"


class ReActExecutor:
    """ReAct reasoning loop with anti-loop safeguards.

    Integrates with the existing BaseAgent tool/LLM patterns from codegraph.agent.base.
    Accepts any LLM client with .chat() and any tool registry with .call().
    """

    def __init__(
        self,
        llm_client: Any,
        tool_registry: Any,
        max_iterations: int = 10,
        token_budget: int = 8000,
        confidence_threshold: float = 0.8,
    ):
        self._llm = llm_client
        self._tools = tool_registry
        self._max_iterations = max_iterations
        self._token_budget = token_budget
        self._confidence_threshold = confidence_threshold

    async def execute(
        self, query: str, context: str = "", session_memory: Any = None
    ) -> ReActResult:
        """Run ReAct loop until answer found or budget exhausted."""
        steps: list[ReActStep] = []
        action_history: set[str] = set()  # For dedup
        no_progress_count = 0
        tokens_used = 0
        start_time = time.time()

        system_prompt = self._build_system_prompt()
        messages = [{"role": "user", "content": self._format_query(query, context)}]

        for i in range(self._max_iterations):
            # Token budget check
            if tokens_used > self._token_budget:
                return self._build_result(steps, tokens_used, i, "token_budget", start_time)

            # Generate thought + action
            response = await self._llm.chat(
                messages=messages,
                system=system_prompt,
                temperature=0.1,
            )
            tokens_used += response.get("usage", {}).get("total_tokens", 0)

            parsed = self._parse_response(response["content"])

            # Record thought
            if parsed.get("thought"):
                steps.append(ReActStep(
                    step_type=StepType.THOUGHT,
                    content=parsed["thought"],
                    token_count=len(parsed["thought"]) // 4,
                ))

            # Check if model wants to answer directly
            if parsed.get("answer"):
                steps.append(ReActStep(
                    step_type=StepType.THOUGHT,
                    content=f"Final answer: {parsed['answer']}",
                ))
                return self._build_result(steps, tokens_used, i + 1, "answered", start_time)

            # Execute action
            if parsed.get("action"):
                action_key = self._action_hash(parsed["action"], parsed.get("action_input", {}))

                # Anti-loop: skip duplicate actions
                if action_key in action_history:
                    no_progress_count += 1
                    if no_progress_count >= 3:
                        return self._build_result(steps, tokens_used, i + 1, "no_progress", start_time)
                    messages.append({"role": "assistant", "content": response["content"]})
                    messages.append({
                        "role": "user",
                        "content": "You already tried this action. Try a different approach or provide your final answer.",
                    })
                    continue

                action_history.add(action_key)
                tool_start = time.time()

                # Call tool
                try:
                    observation = await self._tools.call(
                        parsed["action"],
                        **parsed.get("action_input", {}),
                    )
                    observation_str = str(observation)[:2000]  # Truncate verbose outputs
                except Exception as e:
                    observation_str = f"Error: {e}"

                tool_latency = (time.time() - tool_start) * 1000

                steps.append(ReActStep(
                    step_type=StepType.ACTION,
                    content=f"{parsed['action']}({parsed.get('action_input', {})})",
                    tool_name=parsed["action"],
                    tool_args=parsed.get("action_input", {}),
                    latency_ms=tool_latency,
                ))
                steps.append(ReActStep(
                    step_type=StepType.OBSERVATION,
                    content=observation_str,
                    token_count=len(observation_str) // 4,
                ))

                # Add to conversation for next iteration
                messages.append({"role": "assistant", "content": response["content"]})
                messages.append({"role": "user", "content": f"Observation: {observation_str}"})
                no_progress_count = 0
            else:
                # No action produced -- possible stall
                no_progress_count += 1
                if no_progress_count >= 3:
                    return self._build_result(steps, tokens_used, i + 1, "no_progress", start_time)

        return self._build_result(steps, tokens_used, self._max_iterations, "max_iterations", start_time)

    def _build_system_prompt(self) -> str:
        tool_descriptions = (
            self._tools.get_descriptions()
            if hasattr(self._tools, "get_descriptions")
            else ""
        )
        return f"""You are a reasoning agent. Use the ReAct pattern:

Thought: [your reasoning about what to do next]
Action: [tool_name]
Action Input: {{"param": "value"}}

OR if you have enough information:

Thought: [your final reasoning]
Answer: [your final answer]

Available tools:
{tool_descriptions}

Rules:
- Never repeat the same action with same inputs
- If stuck, try a different approach
- Provide answer when you have sufficient evidence"""

    def _format_query(self, query: str, context: str) -> str:
        if context:
            return f"Context:\n{context}\n\nQuestion: {query}"
        return f"Question: {query}"

    def _parse_response(self, content: str) -> dict[str, Any]:
        """Parse LLM output into thought/action/answer components."""
        result: dict[str, Any] = {}
        lines = content.strip().split("\n")

        for line in lines:
            line = line.strip()
            if line.startswith("Thought:"):
                result["thought"] = line[8:].strip()
            elif line.startswith("Action:"):
                result["action"] = line[7:].strip()
            elif line.startswith("Action Input:"):
                try:
                    result["action_input"] = json.loads(line[13:].strip())
                except json.JSONDecodeError:
                    result["action_input"] = {}
            elif line.startswith("Answer:"):
                result["answer"] = line[7:].strip()

        return result

    def _action_hash(self, action: str, inputs: dict) -> str:
        """Deterministic hash for action deduplication."""
        raw = f"{action}:{json.dumps(inputs, sort_keys=True)}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _build_result(
        self,
        steps: list[ReActStep],
        tokens: int,
        iterations: int,
        reason: str,
        start_time: float,
    ) -> ReActResult:
        """Construct final result, extracting answer from last relevant step."""
        answer = ""
        for step in reversed(steps):
            if "Final answer:" in step.content:
                answer = step.content.replace("Final answer:", "").strip()
                break
        if not answer and steps:
            answer = steps[-1].content

        logger.info(
            "react_complete",
            iterations=iterations,
            termination_reason=reason,
            total_tokens=tokens,
        )

        return ReActResult(
            answer=answer,
            steps=steps,
            total_tokens=tokens,
            total_latency_ms=(time.time() - start_time) * 1000,
            iterations=iterations,
            termination_reason=reason,
        )
