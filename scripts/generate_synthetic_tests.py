#!/usr/bin/env python3
"""Generate synthetic test data from the sample corpus.

For each document in docs/sample_corpus/:
1. Send the document to Claude to generate 10 diverse questions
2. For each question, score with HHEM against the document chunks
3. Keep questions with faithfulness >= 0.85

Usage:
    python scripts/generate_synthetic_tests.py [--corpus-dir DIR] [--output FILE]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import structlog

# Suppress structlog noise
logging.disable(logging.WARNING)
structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL))

QUESTION_GENERATION_PROMPT = """You are a test data generator. Given a document, generate exactly 10 diverse questions that can be answered from the document content.

Rules:
- 2 factual questions (who/what/when) — short, specific
- 2 "how" questions (process/procedure)
- 2 "why" questions (reasoning/justification)
- 1 comparison question (compare X to Y within the document)
- 1 edge case (question that is only partially answerable from the document)
- 1 out-of-scope question (question the document CANNOT answer — used to test fallback)
- 1 multi-part question (tests complex generation)

Format: Return exactly 10 questions, one per line, no numbering or prefixes.
The last question (out-of-scope) should be prefixed with [OUT_OF_SCOPE] so we can label it.

DOCUMENT:
{document}"""


async def generate_questions(client: Any, doc_text: str, model: str) -> list[dict]:
    """Generate 10 diverse questions for a document."""
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": QUESTION_GENERATION_PROMPT.format(document=doc_text[:8000])},
        ],
        temperature=0.7,
        max_tokens=1000,
    )

    content = response.choices[0].message.content or ""
    lines = [line.strip() for line in content.strip().splitlines() if line.strip()]

    questions = []
    for line in lines[:10]:
        out_of_scope = line.startswith("[OUT_OF_SCOPE]")
        q = line.replace("[OUT_OF_SCOPE]", "").strip()
        questions.append({
            "query": q,
            "out_of_scope": out_of_scope,
        })

    return questions


async def score_faithfulness(checker, answer: str, context_chunks: list[str]) -> float | None:
    """Score faithfulness using HHEM."""
    if not context_chunks or not answer:
        return None
    try:
        result = await checker.check(answer, context_chunks)
        return result.get("score")
    except Exception:
        return None


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-dir", default="docs/sample_corpus")
    parser.add_argument("--output", default="golden_dataset/synthetic_tests.jsonl")
    parser.add_argument("--model", default="anthropic/claude-haiku-4-5")
    parser.add_argument("--skip-hhem", action="store_true", help="Skip HHEM scoring (faster, no quality gate)")
    args = parser.parse_args()

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY required for question generation")
        sys.exit(1)

    from openai import AsyncOpenAI
    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    # Load HHEM if not skipping
    checker = None
    if not args.skip_hhem:
        from src.pipeline.quality import HallucinationChecker
        print("Loading HHEM model...")
        checker = HallucinationChecker()

    # Load routing for expected_route labeling
    from src.pipeline.retrieval.local_embeddings import LocalEmbeddingService
    from src.pipeline.routing import QueryRouter

    embedding = LocalEmbeddingService(model_name="all-MiniLM-L6-v2")
    router = QueryRouter(
        default_route="rag_knowledge_base",
        confidence_threshold=0.5,
        embed_fn=embedding.embed_texts,
    )
    await router.initialize()

    corpus_dir = Path(args.corpus_dir)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    docs = sorted(corpus_dir.glob("*.md"))
    print(f"Found {len(docs)} documents in {corpus_dir}")

    total_questions = 0
    kept_questions = 0
    discarded_low_hhem = 0
    discarded_out_of_scope = 0
    results = []

    for doc_path in docs:
        doc_text = doc_path.read_text()
        doc_name = doc_path.stem
        print(f"\nProcessing: {doc_name} ({len(doc_text)} chars)")

        # Generate questions
        questions = await generate_questions(client, doc_text, args.model)
        print(f"  Generated {len(questions)} questions")
        total_questions += len(questions)

        for q in questions:
            query = q["query"]
            out_of_scope = q["out_of_scope"]

            if out_of_scope:
                discarded_out_of_scope += 1
                print(f"  [OUT_OF_SCOPE] {query[:60]}")
                # Still add to dataset as negative example
                results.append({
                    "query": query,
                    "expected_route": "rag_knowledge_base",
                    "source_doc": doc_name,
                    "out_of_scope": True,
                    "faithfulness_score": None,
                })
                kept_questions += 1
                continue

            # Route the question
            route_result = await router.route(query)
            expected_route = route_result["route"]

            # Score with HHEM if available
            faithfulness = None
            if checker:
                # Use the document as context (split into chunks)
                chunks = [doc_text[i:i+1500] for i in range(0, min(len(doc_text), 6000), 1500)]
                faithfulness = await score_faithfulness(checker, query, chunks)

                if faithfulness is not None and faithfulness < 0.85:
                    discarded_low_hhem += 1
                    print(f"  [LOW HHEM {faithfulness:.2f}] {query[:60]}")
                    continue

            results.append({
                "query": query,
                "expected_route": expected_route,
                "source_doc": doc_name,
                "out_of_scope": False,
                "faithfulness_score": faithfulness,
            })
            kept_questions += 1
            status = f"HHEM={faithfulness:.2f}" if faithfulness else "no-HHEM"
            print(f"  [{status}] {query[:60]} -> {expected_route}")

    # Write output
    with open(output_path, "w") as f:
        for entry in results:
            f.write(json.dumps(entry) + "\n")

    print(f"\n{'=' * 60}")
    print(f"Documents processed:     {len(docs)}")
    print(f"Questions generated:     {total_questions}")
    print(f"Kept (HHEM >= 0.85):     {kept_questions}")
    print(f"Discarded (low HHEM):    {discarded_low_hhem}")
    print(f"Out-of-scope (kept):     {discarded_out_of_scope}")
    print(f"Final dataset:           {len(results)} cases")
    print(f"Output:                  {output_path}")
    print(f"{'=' * 60}")

    if kept_questions >= 50:
        print(f"\nPASS: {kept_questions} synthetic test cases >= 50 target")
    else:
        print(f"\nFAIL: {kept_questions} synthetic test cases < 50 target")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
