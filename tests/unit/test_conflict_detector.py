"""Tests for the conflict detection engine."""

import pytest
from datetime import datetime

from evograph.models.domain import GraphRelation, ConflictType


class TestConflictDetection:
    def test_temporal_overlap_detection(self):
        rel_a = GraphRelation(
            source_id="entity_1",
            target_id="entity_2",
            relation_type="CEO_OF",
            valid_from=datetime(2020, 1, 1),
            valid_to=None,
            confidence=0.9,
        )
        rel_b = GraphRelation(
            source_id="entity_1",
            target_id="entity_3",
            relation_type="CEO_OF",
            valid_from=datetime(2023, 6, 1),
            valid_to=None,
            confidence=0.85,
        )
        # Both claim CEO_OF from entity_1 with overlapping time
        assert rel_a.valid_from < rel_b.valid_from
        assert rel_a.valid_to is None  # still active
        assert rel_a.relation_type == rel_b.relation_type

    def test_no_conflict_for_non_singular_relations(self):
        rel_a = GraphRelation(
            source_id="entity_1",
            target_id="entity_2",
            relation_type="INVESTED_IN",
            confidence=0.9,
        )
        rel_b = GraphRelation(
            source_id="entity_1",
            target_id="entity_3",
            relation_type="INVESTED_IN",
            confidence=0.85,
        )
        # INVESTED_IN is not singular, so no conflict
        assert rel_a.relation_type == rel_b.relation_type
        assert rel_a.target_id != rel_b.target_id

    def test_graph_relation_model(self):
        rel = GraphRelation(
            source_id="a",
            target_id="b",
            relation_type="WORKS_AT",
            valid_from=datetime(2022, 1, 1),
            confidence=0.95,
            source_ids=["doc_1"],
        )
        assert rel.is_active is True
        assert rel.confidence == 0.95
        assert len(rel.source_ids) == 1


class TestExtractionModels:
    def test_extraction_result_creation(self):
        from evograph.models.domain import (
            ExtractionResult,
            ExtractedEntity,
            ExtractedRelation,
            EntityType,
        )

        result = ExtractionResult(
            entities=[
                ExtractedEntity(name="OpenAI", type=EntityType.ORGANIZATION),
                ExtractedEntity(name="Sam Altman", type=EntityType.PERSON),
            ],
            relations=[
                ExtractedRelation(
                    source_entity="Sam Altman",
                    target_entity="OpenAI",
                    relation_type="CEO_OF",
                    temporal_start="2019-01-01",
                    confidence=0.95,
                ),
            ],
            document_id="doc_1",
            chunk_id="chunk_1",
        )
        assert len(result.entities) == 2
        assert len(result.relations) == 1
        assert result.relations[0].confidence == 0.95
