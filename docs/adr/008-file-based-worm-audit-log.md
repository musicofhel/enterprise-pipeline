# ADR-008: File-Based WORM Audit Log

**Status:** Accepted
**Date:** Wave 4 completion
**Wave:** 4
**Deciders:** AI Platform Engineering

## Context

Enterprise compliance requirements (GDPR, SOC2) demand an immutable audit trail of all pipeline operations: who queried what, which documents were retrieved, what the LLM generated, and any content that was filtered or flagged. The audit log must be append-only (Write Once, Read Many / WORM) to prevent tampering. We needed a solution that works in development, CI, and production environments without heavy infrastructure.

## Decision

We implemented a file-based WORM audit log using local JSON files. Each audit event is serialized as a JSON object and appended to date-partitioned log files. The audit log module exposes only `append()` and `read()` methods -- no `update()` or `delete()` methods exist in the API. WORM semantics are enforced at the code level.

## Alternatives Considered

- **Database table:** Append-only table with no DELETE/UPDATE grants. Provides indexing and querying, but requires database infrastructure and careful permission management to enforce immutability.
- **S3 Object Lock:** True WORM storage with regulatory-grade immutability guarantees. Requires AWS infrastructure, not available in local development, and adds complexity for CI testing.
- **Append-only Kafka:** Immutable log by design, with retention policies. Heavy infrastructure (Kafka + ZooKeeper), overkill for our audit volume, and does not provide easy random access to historical events.

## Rationale

File-based logging provides the simplest path to WORM semantics that works identically across development, CI, and production. By not implementing delete or update methods in the audit module, we enforce append-only behavior at the API level. JSON serialization makes events human-readable and easily parseable. Date-partitioned files keep individual files manageable and support time-based queries.

This approach explicitly trades true infrastructure-level immutability for simplicity and portability. In production, we plan to layer S3 Object Lock on top (uploading completed log files to S3 with WORM policies), gaining true immutability where it matters while keeping the development experience simple.

## Consequences

### Positive
- Zero infrastructure dependency -- works on any filesystem
- Append-only semantics enforced at the API level (no delete/update methods)
- Human-readable JSON format for debugging and auditing
- Works identically in development, CI, and production environments
- Date-partitioned files support time-based queries and log rotation

### Negative
- Not truly immutable at the filesystem level -- a privileged user can delete or modify files
- No built-in indexing -- querying requires scanning files sequentially
- No native support for concurrent writers (requires file-level locking)

### Risks
- Filesystem-level mutability may not satisfy strict compliance auditors; mitigated by the planned S3 Object Lock production layer and file integrity checksums
- Log files can grow large without rotation; mitigated by date partitioning and planned archival to object storage
