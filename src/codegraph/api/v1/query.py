"""Agent query endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import structlog

from codegraph.models.api_schemas import QueryRequest, CausalQueryRequest, QueryResponse
from codegraph.models.domain import QueryIntent
from codegraph.agent.orchestrator import AgentOrchestrator

logger = structlog.get_logger()
router = APIRouter()

orchestrator = AgentOrchestrator()


@router.post("", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    query_id = str(uuid.uuid4())
    logger.info("query_received", query_id=query_id, question=request.question)

    # Bind session to memory if available
    if hasattr(request, 'session_id') and request.session_id:
        if hasattr(orchestrator, '_engine') and hasattr(orchestrator._engine, '_memory'):
            if orchestrator._engine._memory:
                orchestrator._engine._memory.set_session(request.session_id)

    result = await orchestrator.run(
        question=request.question,
        session_id=request.session_id,
        max_iterations=request.max_iterations,
    )

    return QueryResponse(
        query_id=query_id,
        answer=result.answer,
        confidence=result.confidence,
        intent=QueryIntent.FACTUAL,
        reasoning_trace=result.reasoning_trace if request.include_reasoning else [],
        sources=[],
        conflicts=[],
    )


@router.post("/stream")
async def query_stream(request: QueryRequest) -> StreamingResponse:
    async def generate():
        async for chunk in orchestrator.stream(
            question=request.question,
            session_id=request.session_id,
        ):
            yield f"data: {chunk}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/causal", response_model=QueryResponse)
async def causal_query(request: CausalQueryRequest) -> QueryResponse:
    query_id = str(uuid.uuid4())
    logger.info("causal_query", query_id=query_id, question=request.question)

    result = await orchestrator.run(
        question=request.question,
        query_type=QueryIntent.CAUSAL,
    )

    return QueryResponse(
        query_id=query_id,
        answer=result.answer,
        confidence=result.confidence,
        intent=QueryIntent.CAUSAL,
        reasoning_trace=result.reasoning_trace,
        sources=[],
        conflicts=[],
    )
