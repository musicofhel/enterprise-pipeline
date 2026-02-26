# ADR-010: asyncio Shadow Mode over Temporal

**Status:** Accepted
**Date:** Wave 5 completion
**Wave:** 5
**Deciders:** AI Platform Engineering

## Context

Before promoting a new prompt version or model to production, we need to validate it against real traffic without affecting users. A shadow mode runs the candidate configuration in parallel with the production pipeline, comparing outputs for quality regression detection. The shadow pipeline must not add latency to the primary response path and should reuse retrieval results to minimize resource usage.

## Decision

We implemented shadow mode using Python's `asyncio.create_task()` for fire-and-forget execution. When shadow mode is enabled, the primary pipeline runs normally and returns its response to the user. Simultaneously, a background task re-runs only the generation step with the candidate model/prompt configuration, using the same retrieved context. Shadow results are logged for offline comparison.

## Alternatives Considered

- **Temporal workflow fork:** Fork the pipeline workflow at the generation step, running both primary and shadow as Temporal activities. Provides persistence, retry, and observability, but requires deploying Temporal infrastructure (server, database, workers).
- **Celery background task:** Queue the shadow generation as a Celery task. Requires Redis/RabbitMQ broker infrastructure and Celery worker management.
- **Separate deployment:** Deploy the candidate configuration as a separate service and mirror traffic. Doubles infrastructure cost and requires a traffic mirroring layer.

## Rationale

`asyncio.create_task()` provides shadow execution with near-zero overhead on the primary path (<0.01ms to spawn the task). Since our pipeline is already asyncio-based, no new infrastructure or dependencies are needed. The shadow task reuses the retrieval results from the primary pipeline, so only the LLM generation call is duplicated.

This approach explicitly trades persistence and retry guarantees for simplicity. Shadow results are logged but not critical -- if a shadow task fails, we lose one comparison data point but the user is unaffected. For our current scale, in-memory budget tracking (limiting concurrent shadow tasks) is sufficient.

## Consequences

### Positive
- Near-zero overhead on the primary response path (<0.01ms to spawn task)
- No new infrastructure required -- uses existing asyncio event loop
- Reuses retrieval results, only re-runs generation (minimizes API cost)
- Shadow failures are invisible to users
- Simple implementation with clear separation from primary logic

### Negative
- In-memory budget tracking is not shared across workers -- each process tracks its own shadow task count independently
- No workflow persistence -- if the process crashes, in-flight shadow tasks are lost
- No built-in retry for failed shadow tasks

### Risks
- If shadow tasks consume significant LLM API budget, the in-memory rate limiting may be insufficient for multi-worker deployments; mitigated by configuring conservative shadow sampling rates
- Unhandled exceptions in shadow tasks could affect the event loop if not properly caught; mitigated by wrapping all shadow tasks in try/except with logging
