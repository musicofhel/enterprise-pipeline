from src.pipeline.compression.token_budget import TokenBudgetEnforcer
from src.utils.tokens import count_tokens


def test_enforce_within_budget():
    enforcer = TokenBudgetEnforcer(max_tokens=10000)
    chunks = [
        {"text_content": "Short text", "id": "1"},
        {"text_content": "Another short text", "id": "2"},
    ]
    result = enforcer.enforce(chunks)
    assert len(result) == 2


def test_enforce_over_budget():
    enforcer = TokenBudgetEnforcer(max_tokens=20)
    chunks = [
        {"text_content": "word " * 100, "id": "1"},
        {"text_content": "word " * 100, "id": "2"},
    ]
    result = enforcer.enforce(chunks)
    # Should include at most 1 chunk (first gets truncated)
    assert len(result) <= 2
    total = sum(count_tokens(c["text_content"]) for c in result)
    assert total <= 20


def test_enforce_empty():
    enforcer = TokenBudgetEnforcer(max_tokens=100)
    assert enforcer.enforce([]) == []
