# Operations Runbook

## Daily Checks

1. **Health endpoint** -- verify all services connected:
   ```bash
   curl -s http://localhost:8000/health | python -m json.tool
   ```
   All fields should show `"connected": true` or equivalent healthy status.

2. **Grafana dashboard** -- open `http://localhost:3001` and review all 5 rows:
   - Row 1: No elevated error rate (target: <1% 5xx)
   - Row 2: No unexpected injection block spikes
   - Row 3: Retrieval cosine sim p50 within 10% of baseline
   - Row 4: HHEM scores above 0.85 threshold; no hallucination rate spike
   - Row 5: Feedback rate trending; no annotation backlog

3. **Prometheus alerts** -- check for any firing alerts:
   ```bash
   curl -s http://localhost:9090/api/v1/alerts | python -m json.tool
   ```

4. **Review alert playbooks** -- cross-reference any active alerts with `docs/runbooks/alerting-playbooks.md` (11 documented alerts with investigation/remediation steps).

5. **Log review** -- check for ERROR-level entries:
   ```bash
   docker compose logs pipeline --since 24h | grep '"level":"error"'
   ```

## Weekly Tasks

1. **Run flywheel cycle** (two-phase):
   ```bash
   # Phase 1: Triage failures + generate annotation tasks
   python scripts/run_weekly_flywheel.py --week $(date +%Y-W%V)

   # Human annotation step (review pending tasks in annotations/pending/)
   python scripts/annotate.py next
   python scripts/annotate.py submit <trace_id> ...

   # Phase 2: Import annotations + expand eval suite + report
   python scripts/run_weekly_flywheel.py --week $(date +%Y-W%V) --continue
   ```

2. **Review triage report** -- check `reports/` directory for the latest triage output. Look for:
   - New failure clusters (indicates emerging issues)
   - Recurring failures (indicates unresolved root causes)
   - Failure type distribution changes

3. **Annotate failures** -- work through pending annotation tasks:
   ```bash
   python scripts/annotate.py next            # Get next task
   python scripts/annotate.py submit ...      # Submit with corrections
   python scripts/annotate.py export --output-dir golden_dataset/
   ```

4. **Run eval regression** -- verify no quality regression:
   ```bash
   python scripts/run_daily_eval.py \
     --traces-dir traces/local \
     --output-dir eval_reports/
   ```

5. **Check embedding drift** -- review Grafana Row 3 for drift detection alerts. If `embedding_drift_detected == 1`, investigate per the alerting playbook.

## Monthly Tasks

1. **Load test** -- run against staging environment:
   ```bash
   python scripts/load_test.py \
     --queries 100 \
     --concurrency 5 \
     --target http://localhost:8000
   ```
   Compare results against `docs/baselines/production-baseline.json`. Flag any p95 regression >20%.

2. **Dependency audit**:
   ```bash
   pip audit
   pip list --outdated
   ```
   Review and apply security patches. The HHEM model requires `transformers>=4.40,<5` -- do not upgrade transformers to v5.x.

3. **Key rotation check**:
   - Verify `OPENROUTER_API_KEY` is still valid and within budget
   - Rotate any API keys older than 90 days
   - Review `API_KEY_ROLES` for stale or unused keys
   - Check Langfuse keys if tracing is configured

4. **Free tier usage check**:
   - OpenRouter: check usage dashboard for remaining credits
   - Cohere: check monthly API call count against free tier limit
   - Qdrant Cloud (if used): check storage and request limits

5. **Golden dataset health**:
   ```bash
   python scripts/expand_golden_dataset.py stats
   python scripts/expand_golden_dataset.py coverage
   ```
   Review coverage gaps and plan annotation sprints for underrepresented categories.

6. **Audit log review** -- verify WORM integrity:
   ```bash
   ls -la audit_logs/local/
   # Verify no gaps in timestamp sequence
   # Verify file count matches expected event count
   ```

## Incident Response

### Pipeline Returning 500 Errors

1. **Check health endpoint**: `curl http://localhost:8000/health`
2. **Check service connectivity**:
   - Qdrant: `curl http://localhost:6333/healthz`
   - Langfuse: `curl http://localhost:3100` (non-blocking -- fallback exists)
   - Redis: `docker compose exec redis redis-cli ping`
3. **Review logs**: `docker compose logs pipeline --tail 100`
4. **Check OpenRouter status**: verify API key is valid and service is up
5. **Restart if needed**: `docker compose restart pipeline`
6. **If persists**: check for code regression, roll back to last known good tag

### Hallucination Score Spike

1. Check Grafana Row 4 for HHEM score distribution
2. Review recent traces in Langfuse for low-scoring responses
3. Check if new documents were ingested that may contain contradictory information
4. Verify HHEM model is loaded correctly (cold start can cause transient failures)
5. If caused by bad retrieval: check Row 3 for retrieval quality degradation
6. If caused by model issue: restart the pipeline to reload the HHEM model

### Injection Attack Detected

1. Check Grafana Row 2 for injection block volume
2. Review blocked queries in logs:
   ```bash
   docker compose logs pipeline | grep "injection_detected"
   ```
3. Verify L1 regex patterns are catching the attacks
4. If social engineering attacks bypass L1: these require Lakera L2 (see ISSUE-010)
5. Check source IPs/API keys for the attacking requests
6. Consider rate limiting or blocking the source API key via RBAC

### Retrieval Quality Degradation

1. Check Grafana Row 3 for cosine similarity p50 drop
2. Check embedding drift metric -- if drift detected:
   - Review recently ingested documents
   - Consider re-embedding the collection
3. Check Qdrant collection health:
   ```bash
   curl http://localhost:6333/collections/documents | python -m json.tool
   ```
4. If empty result rate >5%: verify collection has vectors, check query routing
5. Run retrieval canary manually to confirm the degradation

### PII Leak Detected

1. Immediately identify the affected trace(s) in Langfuse
2. Execute right-to-deletion for affected user:
   ```bash
   curl -X DELETE http://localhost:8000/api/v1/users/<user_id>/data \
     -H "X-API-Key: <admin-key>"
   ```
3. Verify deletion completed (check response for per-step status)
4. Review PII detection patterns -- add missing patterns if needed (see ISSUE-007)
5. Create audit trail entry documenting the incident and remediation

## Rollback Procedure

### Application Rollback

```bash
# 1. Stop the current deployment
docker compose stop pipeline

# 2. Deploy the previous version
docker compose up -d pipeline --build  # after checking out the previous tag

# Or with tagged images:
# docker compose pull pipeline:previous-tag
# docker compose up -d pipeline
```

### Configuration Rollback

```bash
# Pipeline config is mounted as a volume
# Revert pipeline_config.yaml to the previous version
git checkout <previous-commit> -- pipeline_config.yaml

# Restart to pick up the change
docker compose restart pipeline
```

### Database Rollback

Qdrant data is persisted in a Docker volume. To roll back:

```bash
# WARNING: This deletes all vector data
docker compose stop qdrant
docker volume rm enterprise-pipeline_qdrant_data
docker compose up -d qdrant

# Re-ingest documents
python scripts/ingest_documents.py \
  --input-dir docs/sample_corpus/ \
  --user-id system \
  --tenant-id default
```

### Full Rollback

```bash
# Stop everything
docker compose down
docker compose -f docker-compose.monitoring.yaml down

# Check out previous release
git checkout <tag>

# Rebuild and restart
docker compose up -d --build
docker compose -f docker-compose.monitoring.yaml up -d
```

## Scaling Notes

- The pipeline is single-process by default. For multi-worker deployments, use `uvicorn --workers N` or deploy behind a load balancer.
- Shadow mode budget tracking is in-memory per process. Multi-worker deployments need a Redis counter for accurate budget enforcement.
- Feedback rate tracking uses in-memory deques -- doesn't survive process restarts.
- HHEM model is loaded once per process (~500 MB). Each worker loads its own copy.
- Qdrant handles concurrent reads well. Write throughput may need collection sharding at scale.
