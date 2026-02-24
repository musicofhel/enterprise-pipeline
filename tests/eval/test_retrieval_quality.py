"""Evaluation tests for retrieval quality metrics."""
from __future__ import annotations

import pytest

from src.pipeline.compression.bm25_compressor import BM25Compressor
from src.pipeline.compression.token_budget import TokenBudgetEnforcer
from src.pipeline.retrieval.deduplication import Deduplicator
from src.utils.tokens import count_tokens


@pytest.mark.eval
class TestDeduplicationRate:
    def test_dedup_removes_duplicates(self):
        """Dedup should remove >90% of exact duplicates."""
        dedup = Deduplicator(threshold=0.95)
        results = [
            {"text_content": "The same text repeated", "id": f"chunk-{i}", "score": 0.9}
            for i in range(10)
        ]
        deduped = dedup.deduplicate(results)
        removal_rate = 1 - (len(deduped) / len(results))
        assert removal_rate >= 0.9, f"Dedup removal rate {removal_rate:.2%} < 90%"

    def test_dedup_preserves_unique(self):
        """Dedup should preserve all unique content."""
        dedup = Deduplicator(threshold=0.95)
        results = [
            {"text_content": f"Completely unique content number {i} with distinct words xyz{i*13}", "id": f"chunk-{i}", "score": 0.9}
            for i in range(10)
        ]
        deduped = dedup.deduplicate(results)
        assert len(deduped) == 10


@pytest.mark.eval
class TestCompressionRatio:
    def test_bm25_compression_reduces_tokens(self):
        """BM25 compression should reduce token count by at least 40%."""
        compressor = BM25Compressor(sentences_per_chunk=3)
        chunks = [
            {
                "text_content": (
                    "Machine learning is a subset of artificial intelligence. "
                    "Deep learning uses neural networks with many layers. "
                    "Natural language processing handles text data. "
                    "Computer vision processes images and video. "
                    "Reinforcement learning optimizes sequential decisions. "
                    "Transfer learning reuses pre-trained models. "
                    "Generative models create new data samples. "
                    "Supervised learning uses labeled training data. "
                    "Unsupervised learning finds patterns without labels. "
                    "Semi-supervised learning combines both approaches."
                ),
                "id": "chunk-1",
            }
        ]
        tokens_before = sum(count_tokens(c["text_content"]) for c in chunks)
        compressed = compressor.compress("neural networks deep learning", chunks)
        tokens_after = sum(count_tokens(c["text_content"]) for c in compressed)

        ratio = 1 - (tokens_after / tokens_before)
        assert ratio >= 0.4, f"Compression ratio {ratio:.2%} < 40%"


@pytest.mark.eval
class TestTokenBudget:
    def test_budget_enforcement(self):
        """Token budget should never be exceeded."""
        budget = 100
        enforcer = TokenBudgetEnforcer(max_tokens=budget)

        chunks = [
            {"text_content": "word " * 50, "id": f"chunk-{i}"}
            for i in range(10)
        ]

        result = enforcer.enforce(chunks)
        total = sum(count_tokens(c["text_content"]) for c in result)
        assert total <= budget, f"Token budget exceeded: {total} > {budget}"
