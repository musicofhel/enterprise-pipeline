# ADR-013: File-Based Annotation over Argilla

**Status:** Accepted
**Date:** Wave 7 completion
**Wave:** 7
**Deciders:** AI Platform Engineering

## Context

A data flywheel requires human annotation to continuously improve pipeline quality. Annotators review LLM responses, mark them as correct or incorrect, provide corrections, and rate retrieval relevance. These annotations feed back into evaluation datasets, prompt tuning, and retrieval optimization. We needed an annotation workflow that supports our single-annotator team without introducing heavyweight infrastructure.

## Decision

We implemented a file-based annotation pipeline using JSON files. Pending annotation tasks are written to `annotations/pending/`, and completed annotations are moved to `annotations/completed/`. A CLI-based workflow allows the annotator to review, annotate, and submit tasks. The annotation schema is compatible with Argilla's data format for future migration.

## Alternatives Considered

- **Argilla:** Open-source annotation platform with web UI, multi-annotator support, inter-annotator agreement metrics, and active learning integration. Requires deploying Elasticsearch and the Argilla server.
- **Label Studio:** Open-source annotation tool with rich UI and multi-format support. Similar infrastructure requirements to Argilla (server + database).
- **Prodigy:** Commercial annotation tool by Explosion (spaCy creators). Per-seat licensing cost and Python-specific.

## Rationale

For a single annotator, a file-based workflow provides all the functionality we need without any infrastructure overhead. JSON files in a directory are simple to create, read, and process programmatically. The CLI workflow is sufficient for reviewing one annotation at a time. By making the annotation schema compatible with Argilla's expected format, we preserve the option to migrate to Argilla when (and if) we need multi-annotator support.

The annotation pipeline is fully testable -- unit tests can create pending files, run the annotation processor, and verify completed output. This testability would be harder to achieve with a server-based platform that requires API mocking.

## Consequences

### Positive
- Zero infrastructure dependency -- annotations are just JSON files on disk
- Fully testable annotation pipeline with standard file I/O assertions
- Argilla-compatible export format preserves migration path
- Version-controllable: annotation files can be committed to git for auditability
- Works in CI for automated annotation pipeline testing

### Negative
- No web UI -- annotator must use CLI or edit JSON files directly
- No multi-annotator workflow or task assignment
- No inter-annotator agreement metrics (only one annotator)
- No active learning integration for prioritizing annotation tasks

### Risks
- If the annotation team grows beyond one person, the file-based workflow will not support concurrent annotation, conflict resolution, or agreement metrics; mitigated by the Argilla-compatible schema enabling migration when needed
- File-based annotation at scale (thousands of pending tasks) could become unwieldy without indexing; mitigated by current low annotation volume and planned batch processing
