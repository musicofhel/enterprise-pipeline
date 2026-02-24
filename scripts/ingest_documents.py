#!/usr/bin/env python3
"""Batch document ingestion script.

Usage:
    python scripts/ingest_documents.py --input-dir ./docs --user-id test --tenant-id test
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def main(input_dir: str, user_id: str, tenant_id: str) -> None:
    from src.api.deps import get_orchestrator

    orchestrator = get_orchestrator()
    await orchestrator._vector_store.ensure_collection()

    input_path = Path(input_dir)
    if not input_path.exists():
        print(f"Error: {input_path} does not exist")
        sys.exit(1)

    files = list(input_path.glob("**/*"))
    files = [f for f in files if f.is_file() and f.suffix in {".md", ".txt", ".pdf", ".docx", ".html"}]

    if not files:
        print(f"No supported files found in {input_path}")
        sys.exit(1)

    print(f"Found {len(files)} files to ingest")

    for file_path in files:
        try:
            doc_type = {
                ".md": "markdown",
                ".txt": "markdown",
                ".pdf": "pdf",
                ".docx": "docx",
                ".html": "html",
            }.get(file_path.suffix, "markdown")

            result = await orchestrator.ingest_file(
                file_path=str(file_path),
                user_id=user_id,
                tenant_id=tenant_id,
                doc_type=doc_type,
            )
            print(f"  OK: {file_path.name} -> {result['chunks_created']} chunks (doc_id: {result['doc_id']})")
        except Exception as e:
            print(f"  FAIL: {file_path.name} -> {e}")

    print("Ingestion complete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest documents into the pipeline")
    parser.add_argument("--input-dir", required=True, help="Directory of documents to ingest")
    parser.add_argument("--user-id", required=True, help="User ID for metadata")
    parser.add_argument("--tenant-id", required=True, help="Tenant ID for metadata")
    args = parser.parse_args()

    asyncio.run(main(args.input_dir, args.user_id, args.tenant_id))
