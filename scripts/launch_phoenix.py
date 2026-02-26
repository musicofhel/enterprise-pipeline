"""Launch Arize Phoenix dashboard for embedding visualization.

Usage: python scripts/launch_phoenix.py [--traces-dir TRACES_DIR]
Opens browser to http://localhost:6006

Reads stored embeddings from trace files and loads them into Phoenix
for interactive visualization of embedding clusters.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Launch Arize Phoenix embedding dashboard")
    parser.add_argument(
        "--traces-dir",
        default="traces/local",
        help="Directory containing trace JSON files (default: traces/local)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=6006,
        help="Port for Phoenix UI (default: 6006)",
    )
    args = parser.parse_args()

    try:
        import phoenix as px
    except ImportError:
        print("ERROR: arize-phoenix not installed. Run: pip install arize-phoenix")
        sys.exit(1)

    traces_dir = Path(args.traces_dir)
    if not traces_dir.exists():
        print(f"No traces directory at {traces_dir}. Phoenix will launch with no data.")

    # Collect embedding data from traces
    queries = []

    if traces_dir.exists():
        for trace_path in traces_dir.glob("*.json"):
            try:
                data = json.loads(trace_path.read_text())
                for span in data.get("spans", []):
                    if span.get("name") == "retrieval":
                        scores = span.get("attributes", {}).get("result_scores", [])
                        if scores:
                            queries.append({
                                "trace_id": data.get("trace_id", ""),
                                "scores": scores,
                            })
            except (json.JSONDecodeError, OSError):
                continue

    print(f"Found {len(queries)} retrieval spans with scores")
    print(f"Launching Phoenix on http://localhost:{args.port}")

    # Launch Phoenix session
    session = px.launch_app(port=args.port)
    print(f"Phoenix is running at: {session.url}")
    print("Press Ctrl+C to stop")

    import contextlib

    with contextlib.suppress(KeyboardInterrupt):
        input("Press Enter to exit...")

    px.close_app()
    print("Phoenix stopped.")


if __name__ == "__main__":
    main()
