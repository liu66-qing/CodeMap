"""Async document ingestion tasks."""

import asyncio

from evograph.tasks.celery_app import celery_app
from evograph.evolution.pipeline import evolution_pipeline


@celery_app.task(bind=True, name="evograph.ingest_document")
def ingest_document_task(self, document_id: str, file_path: str):
    """Process a document through the full evolution pipeline."""
    self.update_state(state="PROCESSING", meta={"stage": "starting"})

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            evolution_pipeline.process_document(document_id, file_path)
        )
        return result
    except Exception as e:
        self.update_state(state="FAILED", meta={"error": str(e)})
        raise
    finally:
        loop.close()


@celery_app.task(name="evograph.reindex_vectors")
def reindex_vectors_task():
    """Rebuild vector index from graph entities."""
    loop = asyncio.new_event_loop()
    try:
        # TODO: implement full reindex
        loop.run_until_complete(asyncio.sleep(0))
        return {"status": "completed"}
    finally:
        loop.close()
