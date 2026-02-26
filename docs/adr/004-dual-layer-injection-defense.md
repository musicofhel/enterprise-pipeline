# ADR-004: Dual-Layer Injection Defense (Guardrails AI + Lakera)

**Status:** Accepted
**Date:** Wave 2 completion
**Wave:** 2
**Deciders:** AI Platform Engineering

## Context

Prompt injection is a critical security risk for any LLM-powered system. Attackers can craft inputs that override system instructions, exfiltrate data, or cause the model to produce harmful outputs. Our pipeline processes user queries that are combined with retrieved context and system prompts before being sent to the LLM, creating multiple injection surfaces. We needed a defense strategy that balances detection accuracy, latency, and cost.

## Decision

We implemented a dual-layer injection defense system. Layer 1 (L1) uses Guardrails AI with regex and heuristic pattern matching for known injection patterns. Layer 2 (L2) uses Lakera Guard, an ML-based classifier, to catch sophisticated attacks that bypass pattern matching. Both layers run sequentially -- if L1 flags an input, L2 is skipped. If L1 passes, L2 provides a second opinion.

## Alternatives Considered

- **LLM-as-judge:** Use a second LLM call to evaluate whether the input contains injection. Adds significant latency (1-3s per call) and cost, and is itself vulnerable to adversarial inputs.
- **Single regex layer:** Fast and free, but brittle against paraphrased or obfuscated attacks. High false negative rate on novel attack patterns.
- **Rebuff:** Open-source injection detection framework. Less mature than Guardrails AI at the time of evaluation, with fewer maintained rule sets.

## Rationale

The layered approach combines the strengths of both methods while mitigating their individual weaknesses. L1 (Guardrails AI regex/heuristic) runs in under 5ms, is free, and catches the majority of known injection patterns -- the "low-hanging fruit" attacks that make up most real-world attempts. L2 (Lakera Guard) is an ML model trained specifically on adversarial prompts, capable of detecting social engineering, context manipulation, and obfuscated attacks that regex cannot catch.

Running L1 first as a fast filter means most legitimate queries never hit L2, keeping average latency low. Only queries that pass L1 incur the additional L2 latency and cost. This architecture also provides defense in depth: even if one layer has a gap, the other can compensate.

## Consequences

### Positive
- Defense in depth: two independent detection mechanisms reduce false negatives
- L1 is free and fast (<5ms), keeping latency low for the majority of requests
- L2 catches sophisticated attacks (social engineering, indirect injection) that regex misses
- Each layer can be updated independently as new attack patterns emerge
- Clear escalation path: L1 flag = definite block, L2 flag = ML-confidence block

### Negative
- Lakera Guard is a vendor dependency with associated cost (per-request pricing)
- L2 adds latency (~50-100ms) for queries that pass L1
- Two systems to maintain, update, and monitor

### Risks
- Lakera Guard could change pricing, deprecate the API, or degrade model quality; mitigated by the L1 layer providing baseline protection even if L2 is removed
- False positives from either layer could block legitimate queries; mitigated by logging all blocks for review and tuning thresholds
