"""API request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from evograph.models.domain import (
    AgentResponse,
    ConflictStatus,
    ConflictType,
    DocumentStatus,
    EntityType,
    GraphEntity,
    GraphRelation,
    KnowledgeConflict,
    QueryIntent,
    ReasoningStep,
)


# === Document Schemas ===


class DocumentUploadResponse(BaseModel):
    id: str
    filename: str
    status: DocumentStatus
    message: str = "Document queued for processing"


class DocumentDetail(BaseModel):
    id: str
    filename: str
    status: DocumentStatus
    file_size: int
    entity_count: int = 0
    relation_count: int = 0
    ingested_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None


# === Query Schemas ===


class QueryRequest(BaseModel):
    question: str
    session_id: str | None = None
    max_iterations: int = Field(default=5, ge=1, le=10)
    include_reasoning: bool = True


class CausalQueryRequest(BaseModel):
    question: str
    hypothesis: str | None = None


class SourceReference(BaseModel):
    document_id: str
    document_title: str
    chunk_text: str
    confidence: float
    relevance_score: float


class ConflictSummary(BaseModel):
    id: str
    type: ConflictType
    description: str


class QueryResponse(BaseModel):
    query_id: str
    answer: str
    confidence: float
    intent: QueryIntent
    reasoning_trace: list[ReasoningStep] = Field(default_factory=list)
    sources: list[SourceReference] = Field(default_factory=list)
    conflicts: list[ConflictSummary] = Field(default_factory=list)


# === Graph Schemas ===


class EntityResponse(BaseModel):
    entity: GraphEntity
    relations: list[GraphRelation] = Field(default_factory=list)
    degree: int = 0


class SubgraphResponse(BaseModel):
    entities: list[GraphEntity]
    relations: list[GraphRelation]
    total_entities: int
    total_relations: int


class NeighborhoodRequest(BaseModel):
    hops: int = Field(default=2, ge=1, le=5)
    relation_types: list[str] | None = None
    entity_types: list[EntityType] | None = None
    limit: int = Field(default=50, ge=1, le=200)


# === Conflict Schemas ===


class ConflictListResponse(BaseModel):
    conflicts: list[KnowledgeConflict]
    total: int
    open_count: int


class ConflictResolveRequest(BaseModel):
    resolution: str  # accept_a, accept_b, merge, dismiss
    note: str | None = None


# === Timeline Schemas ===


class TimelineEntry(BaseModel):
    timestamp: datetime
    event_type: str  # entity_created, relation_added, relation_expired, conflict_detected
    description: str
    entity_id: str | None = None
    relation_id: str | None = None


class TimelineResponse(BaseModel):
    entity_id: str
    entity_name: str
    events: list[TimelineEntry]


class SnapshotRequest(BaseModel):
    timestamp: datetime
    entity_ids: list[str] | None = None
    entity_types: list[EntityType] | None = None


# === Admin Schemas ===


class HealthResponse(BaseModel):
    status: str
    neo4j: str
    postgres: str
    redis: str
    chromadb: str


class GraphStats(BaseModel):
    total_entities: int
    total_relations: int
    total_documents: int
    active_conflicts: int
    entity_type_distribution: dict[str, int]
    relation_type_distribution: dict[str, int]
