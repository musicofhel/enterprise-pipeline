from __future__ import annotations

import tiktoken


def count_tokens(text: str, model: str = "anthropic/claude-sonnet-4-5") -> int:
    """Count the number of tokens in text for a given model."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def truncate_to_token_budget(text: str, max_tokens: int, model: str = "anthropic/claude-sonnet-4-5") -> str:
    """Truncate text to fit within a token budget."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")

    tokens = encoding.encode(text)
    if len(tokens) <= max_tokens:
        return text

    return encoding.decode(tokens[:max_tokens])
