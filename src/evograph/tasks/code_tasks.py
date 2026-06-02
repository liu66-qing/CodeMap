"""Async tasks for code repository analysis."""

import asyncio

from evograph.tasks.celery_app import celery_app
from evograph.evolution.code_repo_pipeline import code_repo_pipeline

import structlog

logger = structlog.get_logger()


@celery_app.task(bind=True, name="evograph.analyze_repository")
def analyze_repository_task(self, repo_id: str, repo_path: str, max_commits: int | None = None,
                            entry_point: str | None = None):
    """Walk a git repo's history, build its code graph, detect breaking changes,
    and run the code-understanding agents (architecture / tour / review)."""
    self.update_state(state="PROCESSING", meta={"stage": "walking_history"})

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            code_repo_pipeline.process_repository(
                repo_id, repo_path, max_commits=max_commits, entry_point=entry_point
            )
        )
        return result
    except Exception as e:
        logger.error("repo_analysis_failed", repo_id=repo_id, error=str(e))
        self.update_state(state="FAILED", meta={"error": str(e)})
        raise
    finally:
        loop.close()
