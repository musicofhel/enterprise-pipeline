# ADR-011: scipy for Experiment Analysis over Statsig

**Status:** Accepted
**Date:** Wave 5 completion
**Wave:** 5
**Deciders:** AI Platform Engineering

## Context

The experimentation framework needs statistical analysis to determine whether A/B test results are significant. After collecting traces from control and treatment variants, we need to compute p-values, effect sizes, and confidence intervals to make promotion decisions. The analysis must support standard statistical tests and be reproducible.

## Decision

We use `scipy.stats` for experiment analysis, specifically `ttest_ind` for parametric comparison, `mannwhitneyu` for non-parametric comparison, and Cohen's d for effect size measurement. Analysis results include p-values, confidence intervals, and a minimum sample size requirement (30 traces per variant) before significance is evaluated.

## Alternatives Considered

- **Statsig:** Managed experimentation platform with automated analysis, dashboards, and statistical rigor. Per-event pricing, vendor dependency, and requires data export to their platform.
- **Eppo:** Feature flagging and experimentation platform with built-in statistical engine. Same vendor dependency and cost concerns as Statsig.
- **Custom implementation:** Build statistical tests from scratch using numpy. Error-prone and unnecessary when scipy provides validated implementations.

## Rationale

`scipy.stats` is already available as a transitive dependency in our Python environment, so it adds no new installation or licensing burden. The library provides well-tested, peer-reviewed implementations of standard statistical tests. Using scipy directly gives us full control over the analysis methodology: we can choose which tests to run, set our own significance thresholds, and customize the output format.

For our experiment volume (single-digit concurrent experiments with tens to hundreds of traces each), a managed platform provides no meaningful advantage over direct statistical computation. The analysis runs as a batch process after experiment completion, not in real-time.

## Consequences

### Positive
- Already available as a transitive dependency -- no new installation needed
- Full control over statistical methodology and significance thresholds
- Reproducible analysis: same input traces produce the same results
- No vendor cost or data export requirements
- Standard statistical tests understood by any data scientist

### Negative
- No dashboard or web UI for viewing experiment results -- output is programmatic
- Requires manual triggering of analysis (no automated significance monitoring)
- Minimum 30 traces per variant required for meaningful analysis, which may extend experiment duration

### Risks
- Incorrect application of statistical tests (e.g., assuming normality when data is skewed) could lead to wrong conclusions; mitigated by including both parametric (t-test) and non-parametric (Mann-Whitney U) tests
- Small sample sizes may produce misleading p-values; mitigated by enforcing the 30-trace minimum and reporting effect size (Cohen's d) alongside p-values
