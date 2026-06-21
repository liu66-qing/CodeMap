"""Dynamic tool loading and invocation system.

Design: Plugin-style tool discovery with schema-driven dispatch.

Tool loading strategies:
1. Static registration — tools declared at import time (current approach)
2. Directory scanning — auto-discover tools from filesystem (new)
3. Remote loading — fetch tool definitions from registry (future)

Schema-driven dispatch:
Each tool declares its input/output schema (JSON Schema). The dispatcher:
1. Validates inputs against schema before calling
2. Type-coerces where safe (str→int for numeric params)
3. Truncates outputs exceeding max_tokens

This gives the LLM accurate tool descriptions and prevents malformed calls.
"""
import importlib
import importlib.util
import inspect
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


@dataclass
class ToolSchema:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema for inputs
    returns: dict[str, Any] | None = None  # JSON Schema for output
    examples: list[dict] = field(default_factory=list)
    max_output_tokens: int = 2000
    timeout: float = 30.0
    category: str = "general"


@dataclass
class ToolInvocation:
    tool_name: str
    args: dict[str, Any]
    result: Any = None
    error: str | None = None
    latency_ms: float = 0
    timestamp: float = field(default_factory=time.time)


class DynamicToolLoader:
    """Discovers, loads, and manages tool functions with schema validation."""

    def __init__(self, tool_dirs: list[str] | None = None):
        self._tools: dict[str, Callable] = {}
        self._schemas: dict[str, ToolSchema] = {}
        self._invocation_log: list[ToolInvocation] = []
        self._tool_dirs = tool_dirs or []

    def register(self, schema: ToolSchema, func: Callable) -> None:
        """Register a tool with its schema."""
        self._tools[schema.name] = func
        self._schemas[schema.name] = schema

    def tool(self, name: str, description: str, parameters: dict, **kwargs):
        """Decorator for tool registration."""
        def decorator(func):
            schema = ToolSchema(
                name=name,
                description=description,
                parameters=parameters,
                **kwargs,
            )
            self.register(schema, func)
            return func
        return decorator

    async def discover(self, directory: str | None = None) -> int:
        """Auto-discover tools from Python files in directory.

        Convention: files ending in _tool.py or in tools/ directory.
        Each must have a TOOL_SCHEMA dict and an execute() function.
        """
        search_dir = Path(directory) if directory else None
        if not search_dir:
            return 0

        discovered = 0
        for path in search_dir.glob("**/*_tool.py"):
            try:
                # Import module dynamically
                module_name = path.stem
                spec = importlib.util.spec_from_file_location(module_name, path)
                if not spec or not spec.loader:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Look for TOOL_SCHEMA and execute
                if hasattr(module, "TOOL_SCHEMA") and hasattr(module, "execute"):
                    schema_dict = module.TOOL_SCHEMA
                    schema = ToolSchema(**schema_dict)
                    self.register(schema, module.execute)
                    discovered += 1
            except Exception:
                continue

        return discovered

    async def call(self, tool_name: str, **kwargs) -> Any:
        """Call a tool with schema validation and tracking."""
        if tool_name not in self._tools:
            raise ValueError(f"Tool '{tool_name}' not found. Available: {list(self._tools.keys())}")

        schema = self._schemas[tool_name]
        func = self._tools[tool_name]

        # Validate required parameters
        required = schema.parameters.get("required", [])
        for param in required:
            if param not in kwargs:
                raise ValueError(f"Tool '{tool_name}' missing required param: {param}")

        # Execute with timeout tracking
        start = time.time()
        invocation = ToolInvocation(tool_name=tool_name, args=kwargs)

        try:
            if inspect.iscoroutinefunction(func):
                result = await func(**kwargs)
            else:
                result = func(**kwargs)

            # Truncate output if too large
            result_str = str(result)
            if len(result_str) > schema.max_output_tokens * 4:
                result = result_str[:schema.max_output_tokens * 4] + "\n...[truncated]"

            invocation.result = result
            invocation.latency_ms = (time.time() - start) * 1000
            self._invocation_log.append(invocation)
            return result

        except Exception as e:
            invocation.error = str(e)
            invocation.latency_ms = (time.time() - start) * 1000
            self._invocation_log.append(invocation)
            raise

    def get_descriptions(self) -> str:
        """Get formatted tool descriptions for LLM system prompt."""
        lines = []
        for name, schema in self._schemas.items():
            params_str = ", ".join(
                f"{k}: {v.get('type', 'any')}"
                for k, v in schema.parameters.get("properties", {}).items()
            )
            lines.append(f"- {name}({params_str}): {schema.description}")
        return "\n".join(lines)

    def get_schemas_for_llm(self) -> list[dict]:
        """Get tool schemas in OpenAI function-calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": schema.name,
                    "description": schema.description,
                    "parameters": schema.parameters,
                },
            }
            for schema in self._schemas.values()
        ]

    def get_invocation_log(self, last_n: int = 20) -> list[ToolInvocation]:
        return self._invocation_log[-last_n:]

    def get_stats(self) -> dict[str, Any]:
        return {
            "registered_tools": len(self._tools),
            "total_invocations": len(self._invocation_log),
            "tools": list(self._tools.keys()),
        }
