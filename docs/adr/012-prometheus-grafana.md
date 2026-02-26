# ADR-012: Prometheus + Grafana over Datadog

**Status:** Accepted
**Date:** Wave 6 completion
**Wave:** 6
**Deciders:** AI Platform Engineering

## Context

The pipeline needs comprehensive observability: metrics collection for latency, throughput, error rates, and business-specific KPIs (retrieval quality, hallucination rates, token usage). We need dashboards for real-time monitoring and historical analysis. The solution must support custom metrics beyond standard infrastructure monitoring.

## Decision

We adopted Prometheus for metrics collection (scrape-based pull model) and Grafana for dashboarding, both self-hosted via Docker Compose. The pipeline exposes a `/metrics` endpoint with 34 custom metrics, and Grafana is configured with 19 dashboard panels organized by pipeline stage.

## Alternatives Considered

- **Datadog:** Fully managed observability platform with APM, logs, metrics, and dashboards. Per-host pricing becomes expensive at scale, and sends telemetry data to a third-party service.
- **New Relic:** Similar to Datadog with per-host pricing and SaaS dependency. Provides APM and distributed tracing but is overkill for our single-service pipeline.
- **CloudWatch:** AWS-native monitoring. Ties us to AWS, limited custom metric support, and the dashboard experience is significantly worse than Grafana.

## Rationale

Prometheus + Grafana is the industry-standard open-source observability stack. Self-hosting eliminates per-host pricing that makes managed platforms expensive as infrastructure scales. Prometheus's pull-based model (scraping `/metrics`) means the pipeline only needs to expose an HTTP endpoint -- no SDK, agent, or data shipping configuration.

Grafana provides best-in-class dashboarding with support for custom panels, variables, and alerting. Our 34 custom metrics cover pipeline-specific KPIs (retrieval latency, hallucination scores, token usage, injection detection rates) that would require custom instrumentation in any platform. By owning the stack, we can define exactly the metrics and dashboards we need without platform constraints.

Docker Compose deployment keeps the monitoring stack co-located with the pipeline, simplifying development and testing. The same `docker-compose.monitoring.yaml` works in local development and staging.

## Consequences

### Positive
- No per-host or per-metric pricing -- costs are fixed (infrastructure only)
- Open-source with large community and ecosystem (exporters, dashboards, alerting)
- 34 custom metrics tailored to pipeline-specific KPIs
- 19 Grafana dashboard panels organized by pipeline stage
- Pull-based scraping requires minimal pipeline-side instrumentation
- Self-hosted: all telemetry data stays on our infrastructure

### Negative
- Self-managed infrastructure: we are responsible for Prometheus storage, Grafana availability, and upgrades
- No built-in APM or distributed tracing (would need Jaeger/Tempo for tracing)
- Alerting requires manual configuration in Grafana (no out-of-the-box alert rules)

### Risks
- Prometheus storage can grow quickly with high-cardinality metrics; mitigated by using label discipline and configuring retention policies
- Self-hosted monitoring creates a "who monitors the monitors" problem; mitigated by basic health checks on the monitoring stack itself
