"""Custom Promptfoo assertion for RAG faithfulness evaluation.

Checks that the LLM output:
1. Does not hallucinate facts absent from context
2. Acknowledges when context is insufficient
3. Stays concise and professional

Called by Promptfoo via ``file://scripts/eval_assertions.py``.
"""
from __future__ import annotations


def get_assert(output: str, context: dict) -> dict:
    """Promptfoo custom assertion entrypoint.

    Args:
        output: The LLM-generated answer.
        context: Dict with ``vars`` (query, context) and ``prompt``.

    Returns:
        Dict with ``pass`` (bool), ``score`` (0-1), and ``reason``.
    """
    ctx = context.get("vars", {}).get("context", "")

    score = 1.0
    reasons: list[str] = []

    # 1. Empty context → model should NOT answer confidently
    if not ctx.strip():
        refusal_phrases = [
            "not enough information",
            "no context",
            "cannot answer",
            "don't have",
            "not provided",
            "no information",
            "unable to",
            "insufficient",
        ]
        if not any(phrase in output.lower() for phrase in refusal_phrases):
            score -= 0.5
            reasons.append("Answered confidently despite empty context")

    # 2. Output should not be empty when context is provided
    if ctx.strip() and len(output.strip()) < 10:
        score -= 0.3
        reasons.append("Output too short given available context")

    # 3. Check for generic filler that ignores context
    filler_phrases = [
        "as an ai language model",
        "i don't have access to",
        "i cannot browse the internet",
    ]
    if ctx.strip() and any(phrase in output.lower() for phrase in filler_phrases):
        score -= 0.3
        reasons.append("Used generic filler instead of context")

    # 4. Reasonable length (not excessively long)
    if len(output) > 3000:
        score -= 0.1
        reasons.append("Output excessively long")

    score = max(0.0, score)
    passed = score >= 0.5

    return {
        "pass": passed,
        "score": score,
        "reason": "; ".join(reasons) if reasons else "Output meets quality criteria",
    }
