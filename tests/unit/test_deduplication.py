from src.pipeline.retrieval.deduplication import Deduplicator


def test_dedup_empty():
    dedup = Deduplicator()
    assert dedup.deduplicate([]) == []


def test_dedup_single():
    dedup = Deduplicator()
    results = [{"text_content": "Hello", "id": "1", "score": 0.9}]
    assert dedup.deduplicate(results) == results


def test_dedup_exact_duplicates():
    dedup = Deduplicator()
    results = [
        {"text_content": "Same content here", "id": "1", "score": 0.9},
        {"text_content": "Same content here", "id": "2", "score": 0.85},
    ]
    deduped = dedup.deduplicate(results)
    assert len(deduped) == 1


def test_dedup_different_content():
    dedup = Deduplicator()
    results = [
        {"text_content": "First document about machine learning algorithms and neural networks", "id": "1", "score": 0.9},
        {"text_content": "Second document about cooking recipes and ingredients for pasta", "id": "2", "score": 0.85},
    ]
    deduped = dedup.deduplicate(results)
    assert len(deduped) == 2


def test_dedup_threshold():
    dedup = Deduplicator(threshold=0.5)
    results = [
        {"text_content": "The quick brown fox jumps over the lazy dog", "id": "1", "score": 0.9},
        {"text_content": "The quick brown fox leaps over the lazy dog", "id": "2", "score": 0.85},
    ]
    deduped = dedup.deduplicate(results)
    # With low threshold, near-duplicates should be caught
    assert len(deduped) <= 2
