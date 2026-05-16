"""Core domain entities for EvoGraph."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class EntityType(str, Enum):
    PERSON = "person"
    ORGANIZATION = "organization"
    PRODUCT = "product"
    EVENT = "event"
    LOCATION = "location"
    CONCEPT = "concept"
    TECHNOLOGY = "technology"


class ConflictType(str, Enum):
    TEMPORAL_OVERLAP = "temporal_overlap"
    LOGICAL_CONTRADICTION = "logical_contradiction"
    SOURCE_DISAGREEMENT = "source_disagreement"


class ConflictStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class QueryIntent(str, Enum):
    FACTUAL = "factual"
    TEMPORAL = "temporal"
    CAUSAL = "causal"
    COMPARATIVE = "comparative"
    EXPLORATORY = "exploratory"


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    EXTRACTING = "extracting"
    MERGING = "merging"
    COMPLETED = "completed"
    FAILED = "failed"


# === Graph Domain Models ===


class GraphEntity(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: EntityType
    aliases: list[str] = Field(default_factory=list)
    description: str = ""
    properties: dict[str, str | int | float | bool] = Field(default_factory=dict)
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class GraphRelation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str
    target_id: str
    relation_type: str
    properties: dict[str, str | int | float | bool] = Field(default_factory=dict)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    observed_at: datetime = Field(default_factory=datetime.utcnow)
    confidence: float = 1.0
    source_ids: list[str] = Field(default_factory=list)
    is_active: bool = True


class KnowledgeConflict(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: ConflictType
    status: ConflictStatus = ConflictStatus.OPEN
    description: str
    fact_a: GraphRelation
    fact_b: GraphRelation
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: datetime | None = None
    resolution_note: str | None = None


class ProvenanceRecord(BaseModel):
    fact_id: str
    document_id: str
    chunk_id: str
    chunk_text: str
    confidence: float
    extracted_at: datetime


# === Agent Domain Models ===


class ReasoningStep(BaseModel):
    step_id: int
    action: str
    tool: str
    input_params: dict[str, str | int | float | bool | list[str]] = Field(default_factory=dict)
    output_summary: str = ""
    confidence: float = 0.0
    duration_ms: int = 0


class AgentResponse(BaseModel):
    answer: str
    confidence: float
    reasoning_trace: list[ReasoningStep] = Field(default_factory=list)
    sources: list[ProvenanceRecord] = Field(default_factory=list)
    conflicts: list[KnowledgeConflict] = Field(default_factory=list)
    entities_referenced: list[str] = Field(default_factory=list)


# === Extraction Models ===


class ExtractedEntity(BaseModel):
    name: str
    type: EntityType
    aliases: list[str] = Field(default_factory=list)
    description: str = ""


class ExtractedRelation(BaseModel):
    source_entity: str
    target_entity: str
    relation_type: str
    temporal_start: str | None = None
    temporal_end: str | None = None
    confidence: float = 1.0


class ExtractionResult(BaseModel):
    entities: list[ExtractedEntity]
    relations: list[ExtractedRelation]
    document_id: str
    chunk_id: str
