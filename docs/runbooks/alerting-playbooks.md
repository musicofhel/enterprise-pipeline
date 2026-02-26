# Alert Playbooks

Every alert condition in the pipeline has a documented investigation and remediation procedure below. Alerts are ordered by severity.

---

## CRITICAL: Retrieval Quality p50 Drop >10%

**Trigger:** `retrieval_cosine_sim_p50` drops >10% from 7-day rolling baseline (`retrieval_quality_alert_level == 2`)

**Investigation:**
1. Open Grafana → Row 3 (Retrieval Health). Check when the drop started.
2. Check Arize Phoenix for embedding drift (`embedding_drift_detected == 1`).
3. Check recent document ingestion jobs — did a bad batch get ingested?
4. Check if the embedding model was updated or its endpoint changed.
5. Compare query distribution — are users asking new types of questions not covered by existing documents?
6. Check Qdrant health — is the vector store responding correctly?

**Remediation:**
- If embedding drift: re-embed affected documents with the current model.
- If bad ingestion: rollback ingested documents (delete by doc_id), fix parser, re-ingest.
- If model change: rollback to previous embedding model version.
- If query distribution shift: expand retrieval coverage, add new document sources.
- If Qdrant issue: restart Qdrant, verify collection health.

**Escalation:** If unresolved after 30 minutes, escalate to ML Engineering team lead.

---

## CRITICAL: Retrieval Empty Result Rate >5%

**Trigger:** `retrieval_empty_result_rate > 0.05` (`retrieval_quality_alert_level == 2`)

**Investigation:**
1. Check Qdrant connectivity — is the vector store reachable?
2. Check if the collection still exists and has vectors.
3. Check if tenant_id filtering is too restrictive — are new tenants missing data?
4. Check if the embedding service is returning valid embeddings (not zeros/NaNs).
5. Check query logs — are queries malformed or extremely short?

**Remediation:**
- If Qdrant is down: restart the Qdrant container/service.
- If collection missing: restore from backup, re-index documents.
- If tenant data missing: verify ingestion pipeline for the affected tenant.
- If embedding service broken: restart embedding service, verify API keys.

**Escalation:** If Qdrant is unrecoverable, escalate to Platform Engineering.

---

## CRITICAL: Retrieval p95 Below 0.3

**Trigger:** `retrieval_cosine_sim_p95 < 0.3`

**Investigation:**
1. This means even the best results are barely relevant. Check if the embedding model is returning garbage.
2. Verify the embedding model is loaded correctly (check model version, warm-up status).
3. Check if the query expansion is generating nonsensical expanded queries.
4. Verify the vector store hasn't been corrupted or overwritten.

**Remediation:**
- Restart the embedding service and verify with a known good query.
- If model is corrupted: re-download and re-load the model.
- Disable query expansion temporarily if it's generating bad queries.
- Re-index the full corpus if the vector store is corrupted.

**Escalation:** If model integrity cannot be verified, escalate to ML Engineering.

---

## CRITICAL: HHEM Faithfulness Below Threshold

**Trigger:** `hallucination_score` consistently below 0.70 (multiple requests), `hallucination_check_failed_total` increasing rapidly

**Investigation:**
1. Open Grafana → Row 2 (Quality Scores). Check HHEM score distribution.
2. Open recent traces in Langfuse — look at the context chunks and generated answers.
3. Check if the LLM model was changed or its behavior shifted (provider-side update).
4. Check if retrieval quality degraded first (Row 3) — bad context leads to bad answers.
5. Check if the prompt template was modified recently.

**Remediation:**
- If LLM model changed: switch to a known-good model version via `pipeline_config.yaml`.
- If retrieval degraded: fix retrieval first (see retrieval playbooks above).
- If prompt changed: revert to the last known-good prompt via git.
- If persistent: enable shadow mode with a candidate fix and validate before promoting.

**Escalation:** If faithfulness remains below threshold after model/prompt rollback, escalate to ML Engineering.

---

## WARN: HHEM Faithfulness in Warning Zone

**Trigger:** `hallucination_score` between 0.70–0.85 for >50% of recent requests

**Investigation:**
1. Check Grafana → Row 2. Is this a gradual trend or a sudden drop?
2. Review traces for the affected time window — look for common patterns.
3. Check if specific routes or query types are affected more than others.
4. Check if a specific document source is causing low-quality context.

**Remediation:**
- Increase monitoring frequency. Check back in 1 hour.
- If a specific document source is the issue: re-process those documents.
- If a specific query type is affected: add more targeted documents or improve routing.
- Consider running a Promptfoo eval comparison to quantify the degradation.

**Escalation:** If trend continues for >4 hours, treat as CRITICAL.

---

## CRITICAL: Embedding Drift Detected

**Trigger:** `embedding_drift_detected == 1` (centroid shift >0.15 or spread change >20%)

**Investigation:**
1. Open Arize Phoenix dashboard (`python scripts/launch_phoenix.py`).
2. Check `embedding_centroid_shift_cosine` — how far has the centroid moved?
3. Check `embedding_spread_change` — is the distribution getting tighter or wider?
4. Check if the embedding model was updated (even minor version bumps can cause drift).
5. Check if the document corpus changed significantly (large ingestion batch).

**Remediation:**
- If model update caused drift: re-embed the reference corpus with the new model, update the reference distribution.
- If corpus change caused drift: update the reference distribution to include the new documents.
- If unexpected drift with no changes: investigate data quality of recent ingestions.

**Escalation:** If drift source cannot be identified, escalate to ML Engineering.

---

## WARN: Retrieval Quality p50 Drop >5%

**Trigger:** `retrieval_cosine_sim_p50` drops >5% from baseline (`retrieval_quality_alert_level == 1`)

**Investigation:**
1. Same as CRITICAL p50 drop but less urgent.
2. Check if the drop is within normal daily variance.
3. Look for correlation with query volume changes.

**Remediation:**
- Monitor for 2 hours. If the drop stabilizes or reverses, no action needed.
- If the drop continues, escalate to CRITICAL investigation.
- Run a spot-check: manually test 5–10 queries and verify results quality.

**Escalation:** If drop persists for >4 hours, treat as CRITICAL.

---

## WARN: Daily Ragas Scores Declining

**Trigger:** `ragas_faithfulness_daily`, `ragas_context_precision_daily`, or `ragas_answer_relevancy_daily` trending down over 3+ consecutive daily runs

**Investigation:**
1. Check which specific metric is declining (faithfulness vs. precision vs. relevancy).
2. Review the daily eval reports in `eval_results/daily/`.
3. Check if the decline correlates with a specific code/config change.
4. Check if the eval dataset is still representative of production queries.

**Remediation:**
- If faithfulness is declining: check HHEM scores and LLM output quality.
- If context precision is declining: check retrieval and reranking quality.
- If answer relevancy is declining: check if the prompt is still appropriate.
- Update the golden dataset if production queries have shifted significantly.

**Escalation:** If any score drops below target (faithfulness <0.85, precision <0.85, relevancy <0.90) for 3 consecutive days, escalate to ML Engineering.

---

## CRITICAL: Shadow Mode Circuit Breaker Triggered

**Trigger:** Shadow pipeline latency exceeds 3x primary latency, circuit breaker activates

**Investigation:**
1. Check shadow mode logs — what is the shadow model/prompt?
2. Check LLM provider status for the shadow model.
3. Check if the shadow pipeline is hitting rate limits.
4. Check shadow mode budget — is it exhausted?

**Remediation:**
- If shadow model is slow: switch to a faster model or increase the circuit breaker multiplier.
- If rate limited: reduce shadow sample rate in `pipeline_config.yaml`.
- If budget exhausted: increase budget or pause shadow mode.
- Disable shadow mode temporarily: set `experimentation.shadow_mode.enabled: false`.

**Escalation:** Shadow mode is non-critical. If the issue doesn't affect primary traffic, it can wait for business hours.

---

## WARN: LLM Cost Spike (>2x Daily Average)

**Trigger:** `increase(llm_cost_usd_total[24h])` exceeds 2x the 7-day daily average

**Investigation:**
1. Check Grafana → Row 5 (Cost). Which model and route are driving the spike?
2. Check if traffic volume increased (legitimate load increase vs. abuse).
3. Check if shadow mode or experiment variants are causing extra LLM calls.
4. Check if query expansion or compression settings changed (more tokens per query).
5. Check token counts — are responses getting longer?

**Remediation:**
- If traffic spike: verify it's legitimate. If abuse, enable rate limiting.
- If shadow mode causing costs: reduce sample rate or pause shadow mode.
- If token inflation: check prompt templates, reduce `max_output_tokens`.
- Set budget alerts in the LLM gateway (OpenRouter) for immediate notification.

**Escalation:** If cost exceeds 5x daily average, escalate to Engineering Manager for budget approval.

---

## CRITICAL: Injection Attempt Spike (>10x Hourly Average)

**Trigger:** `rate(safety_injection_blocked_total[1h])` exceeds 10x the normal hourly rate

**Investigation:**
1. Check Grafana → Row 4 (Safety). Which layer is blocking — L1 regex or L2 Lakera?
2. Check audit logs for the affected time window — are attacks from a single IP/user/tenant?
3. Check if the attack pattern is new (not covered by existing rules).
4. Check if any attacks are getting through (compare blocked count vs. total requests).

**Remediation:**
- If single-source: block the IP/user at the API gateway level.
- If new attack pattern: update L1 regex patterns in `InjectionDetector`.
- If L2 is needed: ensure Lakera Guard API key is configured and active.
- Temporarily increase logging level to capture full attack payloads (redacted).
- Review rate limiting configuration per user/tenant.

**Escalation:** Immediately notify Security team. If attacks are bypassing detection, escalate to P0.
