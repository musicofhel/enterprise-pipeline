from src.utils.tokens import count_tokens, truncate_to_token_budget


def test_count_tokens_basic():
    text = "Hello, world!"
    count = count_tokens(text)
    assert count > 0
    assert isinstance(count, int)


def test_count_tokens_empty():
    assert count_tokens("") == 0


def test_truncate_within_budget():
    text = "Short text"
    result = truncate_to_token_budget(text, max_tokens=100)
    assert result == text


def test_truncate_over_budget():
    text = "word " * 1000  # ~1000 tokens
    result = truncate_to_token_budget(text, max_tokens=10)
    tokens = count_tokens(result)
    assert tokens <= 10
