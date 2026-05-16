"""Query planner: decomposes complex questions into reasoning steps."""

from __future__ import annotations

import json

import structlog

from evograph.llm.client import llm_client
from evograph.models.domain import QueryIntent, ReasoningStep

logger = structlog.get_logger()

PLANNING_PROMPT = """You are a reasoning planner for a knowledge graph-based Q&A system. Given a user question, decompose it into a sequence of retrieval and reasoning steps.

Available tools:
1. graph_query - Query the knowledge graph for structured facts (entities, relationships, paths)
2. vector_search - Semantic similarity search over document chunks
3. temporal_query - Query facts valid at a specific time or trace temporal evolution
4. conflict_check - Check if there are conflicting facts about a topic
5. causal_reason - Trace cause-effect chains between events

For each step, specify:
- action: what to do (e.g., "find entity", "get relationships", "check temporal validity")
- tool: which tool to use
- input_params: parameters for the tool
- depends_on: list of step IDs this step depends on (empty for first steps)

Also classify the query intent: factual, temporal, causal, comparative, or exploratory.

Output JSON:
{
  "intent": "factual|temporal|causal|comparative|exploratory",
  "steps": [
    {"step_id": 1, "action": "...", "tool": "...", "input_params": {...}, "depends_on": []}
  ]
}

Question: {question}

Plan the reasoning steps. Be thorough but efficient - don't add unnecessary steps."""


class QueryPlanner:
    async def plan(self, question: str) -> tuple[QueryIntent, list[ReasoningStep]]:
        prompt = PLANNING_PROMPT.format(question=question)

        try:
            response = await llm_client.chat_json(
                messages=[{"role": "user", "content": prompt}]
            )
            data = json.loads(response)
        except (json.JSONDecodeError, Exception) as e:
            logger.error("planning_failed", error=str(e))
            return QueryIntent.FACTUAL, [
                ReasoningStep(
                    step_id=1,
                    action="hybrid_search",
                    tool="vector_search",
                    input_params={"query": question},
                )
            ]

        intent_str = data.get("intent", "factual")
        try:
            intent = QueryIntent(intent_str)
        except ValueError:
            intent = QueryIntent.FACTUAL

        steps = []
        for step_data in data.get("steps", []):
            steps.append(ReasoningStep(
                step_id=step_data.get("step_id", len(steps) + 1),
                action=step_data.get("action", ""),
                tool=step_data.get("tool", "vector_search"),
                input_params=step_data.get("input_params", {}),
            ))

        if not steps:
            steps = [
                ReasoningStep(
                    step_id=1,
                    action="hybrid_search",
                    tool="vector_search",
                    input_params={"query": question},
                )
            ]

        logger.info("plan_created", intent=intent.value, steps=len(steps))
        return intent, steps
