# ADR-007: OpenRouter as Unified LLM Gateway

**Status:** Accepted
**Date:** Wave 3 completion
**Wave:** 3
**Deciders:** AI Platform Engineering

## Context

The pipeline requires LLM capabilities for response generation, query expansion, and context augmentation. We needed a way to access multiple LLM providers (Claude, GPT-4, Llama) without managing separate API keys, SDKs, and billing relationships for each. The solution should allow switching models without code changes and provide cost visibility across providers.

## Decision

We adopted OpenRouter as our unified LLM gateway, accessed via the `AsyncOpenAI` SDK pointed at OpenRouter's OpenAI-compatible API endpoint. All LLM calls route through OpenRouter, with the model specified per-request in the API call.

## Alternatives Considered

- **Direct OpenAI API:** Native integration, lowest latency to OpenAI models. Locks us to one provider, no Claude/Llama access without separate integrations.
- **Direct Anthropic API:** Native integration for Claude. Different SDK and API shape from OpenAI, would require separate code paths.
- **Portkey:** AI gateway with caching, fallbacks, and observability. More features than we needed, additional infrastructure to self-host, and vendor lock-in to Portkey's config format.
- **LiteLLM:** Open-source LLM proxy. Requires self-hosting, managing the proxy process, and maintaining compatibility with provider API changes.

## Rationale

OpenRouter provides a single API key and billing account across all major LLM providers. Its OpenAI-compatible API means we can use the standard `AsyncOpenAI` SDK with a single base URL change, avoiding custom HTTP client code or provider-specific SDKs. Model switching is a configuration change (pass a different model string), not a code change.

Built-in cost tracking per model and per request gives us visibility without building our own metering. The managed nature of OpenRouter means we do not need to self-host a proxy or manage provider API compatibility ourselves.

## Consequences

### Positive
- Single API key for Claude, GPT-4, Llama, and other models
- Standard `AsyncOpenAI` SDK -- no custom HTTP clients or provider-specific code
- Model switching via configuration, not code changes
- Built-in cost tracking and usage analytics per model
- No self-hosted infrastructure required

### Negative
- Adds ~50-100ms proxy latency on top of provider latency
- Vendor dependency on OpenRouter's availability and pricing
- Cannot use provider-specific features not exposed through the OpenAI-compatible API (e.g., Anthropic's extended thinking)

### Risks
- OpenRouter could experience outages, causing pipeline-wide LLM unavailability; mitigated by the ability to quickly point `AsyncOpenAI` directly at a provider's API as a fallback
- OpenRouter's pricing markup over direct provider pricing increases per-token cost; acceptable given the operational simplicity
- OpenRouter could change their API compatibility layer, breaking assumptions in our code; mitigated by using only standard OpenAI chat completion parameters
