"""Base abstractions for the multi-agent code-analysis pipeline.

Defines:
- ToolCall: record of a single tool invocation
- AgentTrace: full execution trace of one agent run
- BaseAgent: abstract base class with call_tool/call_llm/run

Design notes:
- Tools are plain async callables registered in a dict by name.
- The agent does not know how a tool is implemented; it only knows the name.
- LLM calls record token usage when available.
- Every Agent.run() captures timing and errors into AgentTrace for observability.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Awaitable
import json
import time

import structlog

from codegraph.llm.client import llm_client as default_llm_client
from codegraph.agent.tools.stats import tool_stats_collector

logger = structlog.get_logger()


ToolFn = Callable[..., Awaitable[Any]]


@dataclass
class ToolCall:
    tool_name: str
    args: dict
    result: Any
    duration_ms: float
    token_cost: int = 0
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "tool_name": self.tool_name,
            "args": self.args,
            "result_preview": _preview(self.result),
            "duration_ms": round(self.duration_ms, 2),
            "token_cost": self.token_cost,
            "error": self.error,
        }


@dataclass
class LLMCall:
    prompt_chars: int
    response_chars: int
    duration_ms: float
    tokens_in: int = 0
    tokens_out: int = 0
    model: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AgentTrace:
    agent_name: str
    started_at: float
    finished_at: float = 0.0
    tool_calls: list[ToolCall] = field(default_factory=list)
    llm_calls_detail: list[LLMCall] = field(default_factory=list)
    llm_calls: int = 0
    total_tokens: int = 0
    output: Any = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": round((self.finished_at - self.started_at) * 1000, 2)
            if self.finished_at
            else 0,
            "tool_calls": [t.to_dict() for t in self.tool_calls],
            "llm_calls_detail": [c.to_dict() for c in self.llm_calls_detail],
            "llm_calls": self.llm_calls,
            "total_tokens": self.total_tokens,
            "output": self.output,
            "error": self.error,
        }


def _preview(obj: Any, max_chars: int = 400) -> Any:
    """Compact preview of a tool result for trace storage."""
    try:
        s = json.dumps(obj, ensure_ascii=False, default=str)
    except Exception:
        s = str(obj)
    if len(s) > max_chars:
        return s[:max_chars] + "...(truncated)"
    return s


class BaseAgent(ABC):
    """Abstract base for stage agents.

    Subclasses implement analyze(context) and return a JSON-serializable dict.
    """

    def __init__(
        self,
        name: str,
        tools: dict[str, ToolFn],
        llm_client: Any | None = None,
    ) -> None:
        self.name = name
        self.tools = tools
        self.llm = llm_client or default_llm_client
        self.trace = AgentTrace(agent_name=name, started_at=0.0)

    @abstractmethod
    async def analyze(self, context: dict) -> dict:
        """Run the agent's analysis given a context dict."""

    async def call_tool(self, tool_name: str, **kwargs: Any) -> Any:
        if tool_name not in self.tools:
            raise ValueError(
                f"Tool '{tool_name}' not registered for agent '{self.name}'"
            )
        start = time.time()
        err: str | None = None
        result: Any = None
        try:
            result = await self.tools[tool_name](**kwargs)
            return result
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            logger.warning(
                "tool_call_failed", agent=self.name, tool=tool_name, error=err
            )
            raise
        finally:
            duration = (time.time() - start) * 1000
            success = err is None

            # Record in trace
            self.trace.tool_calls.append(
                ToolCall(
                    tool_name=tool_name,
                    args=kwargs,
                    result=result,
                    duration_ms=duration,
                    error=err,
                )
            )

            # Record in global stats collector
            tool_stats_collector.record_call(
                tool_name=tool_name,
                duration_ms=duration,
                success=success,
                agent_name=self.name,
            )

            logger.info(
                "tool_call",
                agent=self.name,
                tool=tool_name,
                duration_ms=round(duration, 2),
                ok=success,
            )

    async def call_llm(
        self,
        prompt: str,
        system: str = "",
        json_schema: dict | None = None,
        temperature: float = 0.0,
    ) -> str | dict:
        """Call the LLM. If json_schema provided, returns parsed dict.

        json_schema is embedded in the system prompt as documentation; the LLM is
        also asked for json_object output format. The schema therefore guides the
        output but is not enforced by the SDK (DeepSeek does not support
        json_schema response_format yet).
        """
        sys_msg = system
        want_json = json_schema is not None
        if want_json:
            sys_msg = (
                f"{system}\n\n"
                "Output a single JSON object that conforms to this JSON Schema. "
                "Do not wrap in markdown or add any commentary.\n"
                f"SCHEMA:\n{json.dumps(json_schema, ensure_ascii=False)}"
            )

        messages = [
            {"role": "system", "content": sys_msg or "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ]

        start = time.time()
        if want_json:
            content = await self.llm.chat_json(messages, temperature=temperature)
        else:
            content = await self.llm.chat(messages, temperature=temperature)
        duration = (time.time() - start) * 1000

        # Best-effort token accounting (real values not exposed by current client).
        tokens_in = len(prompt) // 4 + len(sys_msg) // 4
        tokens_out = len(content) // 4
        self.trace.llm_calls += 1
        self.trace.total_tokens += tokens_in + tokens_out
        self.trace.llm_calls_detail.append(
            LLMCall(
                prompt_chars=len(prompt) + len(sys_msg),
                response_chars=len(content),
                duration_ms=duration,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                model=getattr(self.llm, "_model", ""),
            )
        )

        if want_json:
            try:
                return json.loads(content)
            except Exception as e:
                logger.warning(
                    "llm_json_parse_failed",
                    agent=self.name,
                    error=str(e),
                    snippet=content[:200],
                )
                return _coerce_json(content)
        return content

    async def run(self, context: dict) -> dict:
        self.trace = AgentTrace(agent_name=self.name, started_at=time.time())
        try:
            output = await self.analyze(context)
            self.trace.output = output
            return output
        except Exception as e:
            self.trace.error = f"{type(e).__name__}: {e}"
            logger.error("agent_failed", agent=self.name, error=self.trace.error)
            raise
        finally:
            self.trace.finished_at = time.time()


def _coerce_json(text: str) -> dict:
    """Best-effort parse if LLM returned text around a JSON block."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        # drop leading 'json\n' if present
        if text.startswith("json"):
            text = text[4:].lstrip()
    try:
        return json.loads(text)
    except Exception:
        # Try to extract first {...} block.
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except Exception:
                pass
    return {"_raw": text, "_parse_error": True}
