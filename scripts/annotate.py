#!/usr/bin/env python3
"""CLI for annotation workflow.

Usage:
    python scripts/annotate.py next                    # Show next pending
    python scripts/annotate.py submit --trace-id ID \\
        --correct-answer "..." --failure-type TYPE     # Submit annotation
    python scripts/annotate.py stats                   # Show counts
    python scripts/annotate.py export --output DIR     # Export to golden dataset
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.flywheel.annotation import AnnotationService


def main() -> None:
    parser = argparse.ArgumentParser(description="Annotation workflow CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # next
    subparsers.add_parser("next", help="Show next pending annotation")

    # submit
    submit_p = subparsers.add_parser("submit", help="Submit an annotation")
    submit_p.add_argument("--trace-id", required=True, help="Trace ID to annotate")
    submit_p.add_argument("--correct-answer", required=True, help="The correct answer")
    submit_p.add_argument("--failure-type", required=True, help="Failure category")
    submit_p.add_argument("--notes", default=None, help="Optional notes")
    submit_p.add_argument("--annotator", default="human", help="Annotator name")

    # stats
    subparsers.add_parser("stats", help="Show annotation stats")

    # export
    export_p = subparsers.add_parser("export", help="Export to golden dataset")
    export_p.add_argument("--output", required=True, help="Output directory")

    # Common
    parser.add_argument("--annotations-dir", default="annotations", help="Annotations directory")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    service = AnnotationService(annotations_dir=Path(args.annotations_dir))

    if args.command == "next":
        task = service.get_next_pending()
        if task is None:
            print("No pending annotations.")
        else:
            print(json.dumps(task, indent=2))

    elif args.command == "submit":
        ok = service.submit_annotation(
            trace_id=args.trace_id,
            correct_answer=args.correct_answer,
            failure_type=args.failure_type,
            notes=args.notes,
            annotator=args.annotator,
        )
        if ok:
            print(f"Annotation submitted for trace {args.trace_id}")
        else:
            print(f"Error: trace {args.trace_id} not found in pending.")
            sys.exit(1)

    elif args.command == "stats":
        pending = service.get_pending_count()
        completed = service.get_completed_count()
        print(f"Pending:   {pending}")
        print(f"Completed: {completed}")
        print(f"Total:     {pending + completed}")

    elif args.command == "export":
        count = service.export_to_golden_dataset(Path(args.output))
        print(f"Exported {count} annotations to {args.output}")


if __name__ == "__main__":
    main()
