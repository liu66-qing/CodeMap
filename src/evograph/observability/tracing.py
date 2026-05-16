"""Observability: OpenTelemetry tracing setup."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator
import time

import structlog

logger = structlog.get_logger()


class SpanTracer:
    """Lightweight tracing for agent reasoning steps."""

    def __init__(self) -> None:
        self.spans: list[dict] = []

    @contextmanager
    def span(self, name: str, attributes: dict | None = None) -> Generator[dict, None, None]:
        span_data = {
            "name": name,
            "start_time": time.time(),
            "attributes": attributes or {},
            "status": "ok",
        }
        try:
            yield span_data
        except Exception as e:
            span_data["status"] = "error"
            span_data["error"] = str(e)
            raise
        finally:
            span_data["duration_ms"] = int((time.time() - span_data["start_time"]) * 1000)
            self.spans.append(span_data)
            logger.debug(
                "span_complete",
                span=name,
                duration_ms=span_data["duration_ms"],
                status=span_data["status"],
            )

    def get_trace(self) -> list[dict]:
        return self.spans.copy()

    def reset(self) -> None:
        self.spans.clear()
