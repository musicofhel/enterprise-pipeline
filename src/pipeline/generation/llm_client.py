from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

from src.utils.tokens import count_tokens

if TYPE_CHECKING:
    from openai import AsyncOpenAI

logger = structlog.get_logger()

DEFAULT_PROMPT_PATH = Path("prompts/rag_system.txt")


class LLMClient:
    def __init__(
        self,
        client: AsyncOpenAI,
        model: str = "anthropic/claude-sonnet-4-5",
        temperature: float = 0.1,
        max_output_tokens: int = 1000,
        system_prompt_path: Path = DEFAULT_PROMPT_PATH,
    ) -> None:
        self._client = client
        self._model = model
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._system_prompt = self._load_prompt(system_prompt_path)

    @staticmethod
    def _load_prompt(path: Path) -> str:
        if path.exists():
            return path.read_text().strip()
        return "Answer the question based on the provided context.\n\nContext:\n{context}\n\nQuestion: {query}"

    async def generate(
        self,
        query: str,
        context_chunks: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generate an answer from context chunks.

        Accepts optional ``model_override`` and ``max_tokens_override`` kwargs
        to support smart model routing (model tier selection).
        """
        model = kwargs.pop("model_override", None) or self._model
        max_tokens = kwargs.get("max_tokens") or kwargs.pop("max_tokens_override", None) or self._max_output_tokens

        context = "\n\n---\n\n".join(
            f"[Source: {c.get('metadata', {}).get('doc_id', 'unknown')}]\n{c.get('text_content', '')}"
            for c in context_chunks
        )

        system_message = self._system_prompt.format(context=context, query=query)
        input_tokens = count_tokens(system_message + query, model=model)

        logger.info(
            "llm_generating",
            model=model,
            input_tokens=input_tokens,
            num_context_chunks=len(context_chunks),
        )

        response = await self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": query},
            ],
            temperature=kwargs.get("temperature", self._temperature),
            max_tokens=max_tokens,
        )

        answer = response.choices[0].message.content or ""
        usage = response.usage

        result = {
            "answer": answer,
            "model": model,
            "tokens_in": usage.prompt_tokens if usage else input_tokens,
            "tokens_out": usage.completion_tokens if usage else count_tokens(answer, model),
        }

        logger.info(
            "llm_generation_complete",
            model=model,
            tokens_in=result["tokens_in"],
            tokens_out=result["tokens_out"],
        )
        return result
