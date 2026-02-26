# ADR-009: Hash-Based Feature Flags over LaunchDarkly

**Status:** Accepted
**Date:** Wave 5 completion
**Wave:** 5
**Deciders:** AI Platform Engineering

## Context

The experimentation framework requires feature flags to assign users to A/B test variants for prompt and model experiments. Each user must be deterministically assigned to the same variant across sessions (sticky assignment), and the assignment must be auditable. We needed a feature flag system that supports percentage-based rollouts and variant assignment without external service dependencies.

## Decision

We implemented hash-based feature flags using MD5 hashing. The user's ID is hashed, the hash is mapped to a bucket (0-99), and the bucket determines variant assignment based on traffic allocation percentages defined in YAML configuration files. The assignment is fully deterministic -- the same user ID always maps to the same bucket and variant.

## Alternatives Considered

- **LaunchDarkly:** Industry-standard feature flag platform with dashboard, real-time flag changes, and targeting rules. Per-seat pricing, vendor dependency, and requires network connectivity for flag evaluation.
- **Flagsmith:** Open-source feature flag platform. Can be self-hosted, but adds infrastructure to manage and maintain.
- **Unleash:** Open-source feature flag system. Similar to Flagsmith -- requires self-hosted infrastructure and operational overhead.

## Rationale

Hash-based flags are the simplest possible implementation that meets our requirements. MD5 hashing of the user ID produces a deterministic, uniformly distributed bucket assignment without any external service. YAML configuration files make experiment definitions version-controlled, reviewable, and auditable. The entire implementation is under 100 lines of code with no dependencies beyond Python's standard library.

For our use case -- A/B testing prompt variants and model configurations -- we do not need real-time flag changes or complex targeting rules. Experiments are defined ahead of time, run for a fixed period, and analyzed after completion. The flag configuration changes via code deployment, which provides natural version control and review.

## Consequences

### Positive
- Zero vendor dependency -- works offline, in CI, and in air-gapped environments
- Deterministic assignment: same user always gets the same variant (sticky sessions)
- YAML configuration is version-controlled and reviewable in PRs
- Full audit trail through git history
- No per-seat or per-evaluation cost

### Negative
- No real-time flag changes -- requires a restart or redeployment to modify flag configuration
- No dashboard for non-engineers to view or modify experiments
- No built-in analytics or experiment tracking (handled separately by the analysis module)

### Risks
- MD5 distribution uniformity could be insufficient for very small user populations; mitigated by using the full hash space and verifying distribution in tests
- If real-time flag changes become a requirement (e.g., emergency kill switches), this approach cannot support them; would need to add a lightweight flag service or adopt a managed platform
