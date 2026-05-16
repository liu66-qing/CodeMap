"""Agent orchestrator: the adaptive reasoning loop that differentiates EvoGraph from linear RAG pipelines."""

from __future__ import annotations

import json
import time
from typing import Any, AsyncGenerator

import structlog

from evograph.llm.client import llm_client
from evograph.agent.planner import QueryPlanner
from evograph.agent.tools.registry import tool_registry
from evograph.models.domain import AgentResponse, ReasoningStep, QueryIntent

logger = structlog.get_logger()

SYNTHESIS_PROMPT = """You are a knowledge graph reasoning agent. Based on the retrieved evidence, synthesize a comprehensive answer.

Question: {question}

Evidence gathered through reasoning:
{evidence}

Graph context (structured facts):
{graph_context}

Instructions:
1. Answer the question based ONLY on the provided evidence
2. If evidence is insufficient, say so explicitly
3. If there are conflicting facts, mention them
4. Assign a confidence score (0.0-1.0) based on evidence quality
5. Reference specific sources when making claims

Output JSON:
{{
  "answer": "your comprehensive answer",
  "confidence": 0.85,
  "key_facts": ["fact1", "fact2"],
  "unresolved_conflicts": ["conflict description if any"],
  "evidence_gaps": ["what information is missing if any"]
}}"""

VALIDATION_PROMPT = """Validate this answer against the evidence. Check:
1. Is every claim grounded in the evidence?
2. Are there any hallucinations (claims not supported by evidence)?
3. Is the confidence score appropriate?

Answer: {answer}
Evidence: {evidence}

Output JSON:
{{
  "is_valid": true/false,
  "issues": ["list of issues if any"],
  "suggested_confidence": 0.85
}}"""


class AgentOrchestrator:
    def __init__(self, max_iterations: int = 5):
        self.planner = QueryPlanner()
        self.max_iterations = max_iterations

    async def run(
        self,
        question: str,
        session_id: str | None = None,
        max_iterations: int | None = None,
        query_type: QueryIntent | None = None,
    ) -> AgentResponse:
        max_iter = max_iterations or self.max_iterations
        start_time = time.time()

        # Step 1: Plan
        intent, steps = await self.planner.plan(question)
        if query_type:
            intent = query_type

        # Step 2: Execute reasoning steps
        working_memory: list[dict[str, Any]] = []
        executed_steps: list[ReasoningStep] = []

        for iteration in range(max_iter):
            for step in steps:
                step_start = time.time()

                result = await tool_registry.execute(
                    step.tool, step.input_params
                )

                step.output_summary = _summarize_result(result)
                step.duration_ms = int((time.time() - step_start) * 1000)

                if result.get("success"):
                    working_memory.append({
                        "step": step.step_id,
                        "tool": step.tool,
                        "data": result["data"],
                    })

                executed_steps.append(step)

            # Step 3: Synthesize answer
            evidence_text = _format_evidence(working_memory)
            graph_context = _extract_graph_context(working_memory)

            synthesis = await self._synthesize(question, evidence_text, graph_context)

            # Step 4: Validate
            is_valid, confidence = await self._validate(
                synthesis.get("answer", ""), evidence_text
            )

            if is_valid or iteration >= max_iter - 1:
                total_ms = int((time.time() - start_time) * 1000)
                logger.info(
                    "agent_complete",
                    question=question[:100],
                    iterations=iteration + 1,
                    confidence=confidence,
                    duration_ms=total_ms,
                )

                return AgentResponse(
                    answer=synthesis.get("answer", "I could not find sufficient information."),
                    confidence=confidence,
                    reasoning_trace=executed_steps,
                    sources=[],
                    conflicts=[],
                    entities_referenced=[],
                )

            # Re-plan if validation failed
            logger.info("agent_replan", iteration=iteration, reason="validation_failed")
            steps = [
                ReasoningStep(
                    step_id=len(executed_steps) + 1,
                    action="deeper_search",
                    tool="hybrid_search",
                    input_params={"query": question, "entities": synthesis.get("evidence_gaps", [])},
                )
            ]

        return AgentResponse(
            answer="I was unable to find a confident answer after multiple reasoning attempts.",
            confidence=0.0,
            reasoning_trace=executed_steps,
        )

    async def stream(
        self,
        question: str,
        session_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        result = await self.run(question, session_id)
        # Stream the answer token by token for SSE
        words = result.answer.split()
        for i, word in enumerate(words):
            yield json.dumps({"type": "token", "content": word + " "})
        yield json.dumps({
            "type": "done",
            "confidence": result.confidence,
            "steps": len(result.reasoning_trace),
        })

    async def _synthesize(
        self, question: str, evidence: str, graph_context: str
    ) -> dict[str, Any]:
        prompt = SYNTHESIS_PROMPT.format(
            question=question, evidence=evidence, graph_context=graph_context
        )
        try:
            response = await llm_client.chat_json(
                messages=[{"role": "user", "content": prompt}]
            )
            return json.loads(response)
        except (json.JSONDecodeError, Exception):
            return {"answer": "Error synthesizing answer", "confidence": 0.0}

    async def _validate(self, answer: str, evidence: str) -> tuple[bool, float]:
        prompt = VALIDATION_PROMPT.format(answer=answer, evidence=evidence)
        try:
            response = await llm_client.chat_json(
                messages=[{"role": "user", "content": prompt}]
            )
            data = json.loads(response)
            return data.get("is_valid", True), data.get("suggested_confidence", 0.5)
        except (json.JSONDecodeError, Exception):
            return True, 0.5


def _summarize_result(result: dict[str, Any]) -> str:
    if not result.get("success"):
        return f"Error: {result.get('error', 'unknown')}"
    data = result.get("data", {})
    if isinstance(data, list):
        return f"Retrieved {len(data)} results"
    if isinstance(data, dict):
        chunks = data.get("chunks", [])
        graph = data.get("graph_context", [])
        return f"Retrieved {len(chunks)} chunks, {len(graph)} graph facts"
    return "Completed"


def _format_evidence(working_memory: list[dict]) -> str:
    parts = []
    for entry in working_memory:
        data = entry.get("data", {})
        if isinstance(data, list):
            for item in data[:5]:
                if isinstance(item, dict):
                    parts.append(str(item))
        elif isinstance(data, dict):
            for chunk in data.get("chunks", [])[:5]:
                parts.append(chunk.get("text", ""))
    return "\n---\n".join(parts[:10])


def _extract_graph_context(working_memory: list[dict]) -> str:
    facts = []
    for entry in working_memory:
        data = entry.get("data", {})
        if isinstance(data, dict) and "graph_context" in data:
            for fact in data["graph_context"][:10]:
                if isinstance(fact, dict):
                    source = fact.get("source", "?")
                    rel = fact.get("rel_type", fact.get("relation", "?"))
                    target = fact.get("target", "?")
                    facts.append(f"{source} --[{rel}]--> {target}")
        elif isinstance(data, list):
            for item in data[:5]:
                if isinstance(item, dict) and "source" in item and "target" in item:
                    facts.append(
                        f"{item['source']} --[{item.get('rel_type', '?')}]--> {item['target']}"
                    )
    return "\n".join(facts[:20])
