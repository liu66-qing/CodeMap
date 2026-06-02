"""Unified LLM client supporting OpenAI-compatible APIs (DeepSeek, etc.)."""

from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI
import structlog

from evograph.config import settings

logger = structlog.get_logger()


class LLMClient:
    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            timeout=90.0,   # DeepSeek can be slow on large prompts; avoid premature timeouts
            max_retries=1,
        )
        self._model = settings.llm_model_id

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 4096,
        response_format: dict[str, str] | None = None,
    ) -> str:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = await self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
    ) -> str:
        return await self.chat(
            messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        temperature: float = 0.0,
    ):
        """Call LLM with OpenAI Function Calling protocol."""
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=temperature,
        )
        return response

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
    ):
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


llm_client = LLMClient()
