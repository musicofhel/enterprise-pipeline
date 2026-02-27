# Architecture

Production-grade RAG (Retrieval-Augmented Generation) pipeline built in Python with FastAPI. Twelve pipeline stages process every query: input safety, semantic routing, multi-query expansion, vector retrieval (Qdrant), deduplication, reranking (Cohere), BM25 compression, LLM generation (OpenRouter), hallucination detection (HHEM on CPU), output validation, tracing (Langfuse or local JSON), and instrumentation (Prometheus). The system includes RBAC, immutable audit logging, right-to-deletion compliance, a data flywheel for continuous improvement, and A/B experimentation with shadow mode. Two runtime dependencies require API keys (OpenRouter, Cohere); everything else runs locally on CPU.

## Architecture Diagrams

### Diagram 1: High-Level System Architecture

```mermaid
---
config:
  flowchart:
    useMaxWidth: true
---
flowchart LR
    Client["Client Request\nPOST /api/v1/query"] --> Auth["auth.py\nAPI Key → Role\n5 roles, 13 permissions"]
    Auth --> DI["deps.py\n@lru_cache DI container"]
    DI --> Orch["PipelineOrchestrator.query()"]

    subgraph SAFETY["1–2: Safety & Routing"]
        S1["1. Input Safety\nL1 regex (15 patterns)\nPII (8 types)\nLakera Guard L2 (optional)"]
        S1 -->|blocked| Early["Early Return\n(safety violation)"]
        S1 -->|passed| S2["2. Query Routing\nall-MiniLM-L6-v2 (local CPU)\nmax-sim cosine scoring"]
    end

    subgraph RETRIEVAL["3–7: Retrieval & Compression"]
        S3["3. Query Expansion\nConditional: skip if confidence ≥ 0.75\nElse: 3 variants via Claude Haiku"]
        S3 --> S4["4. Retrieval\nconcurrent asyncio.gather()\nQdrant top-20 per query"]
        S4 --> S5["5. Dedup\ncosine 0.95"]
        S5 --> S6["6. Rerank\nCohere or passthrough"]
        S6 --> S7["7. Compression\nBM25 + token budget\n4000 max"]
    end

    subgraph GENERATION["8–10: Generation & Quality"]
        S8["8. Generation\nOpenRouter LLM\nSmart model routing\n(Haiku/Sonnet)"]
        S8 --> S9["9. Hallucination\nHHEM CPU inference\npass ≥ 0.85 / warn ≥ 0.70"]
        S9 --> S10["10. Output Schema\nPer-route JSON validation"]
    end

    subgraph OBSERVE["11–12: Tracing & Metrics"]
        S11["11. Tracing\nLangfuse or local JSON\nspans + scores + metadata"]
        S11 --> S12["12. Instrumentation\nPrometheus metrics\nshadow mode fire-and-forget"]
    end

    Orch --> S1
    S2 --> S3
    S7 --> S8
    S10 --> S11
    S12 --> Response["QueryResponse\nanswer, trace_id, sources,\nmetadata, fallback flag"]

    subgraph OBSERVABILITY["Observability Stack"]
        Prom["Prometheus\n34 metrics, 8 groups"] --> Graf["Grafana\n5 rows, 19 panels"]
        Canary["Retrieval Canary\np50/p95 alerts"]
        Drift["Embedding Drift\ncentroid shift"]
        Eval["Daily Ragas Eval\nfaithfulness, precision, relevancy"]
    end

    subgraph COMPLIANCE["Compliance Layer"]
        Audit["Audit Log (WORM)\nimmutable JSON"]
        Delete["Deletion Service\nvectors + traces + feedback"]
        Retain["Retention Checker\nTTL-based purge"]
    end

    S11 -.-> Prom
    S11 -.-> Audit
```

### Diagram 2: Module Dependency Graph

```mermaid
---
config:
  flowchart:
    useMaxWidth: true
---
flowchart LR
    subgraph API["Public API"]
        main["main.py\nFastAPI factory"]
        router["api/router.py"]
        query_ep["api/v1/query.py"]
        ingest_ep["api/v1/ingest.py"]
        feedback_ep["api/v1/feedback.py"]
        deletion_ep["api/v1/deletion.py"]
        health_ep["api/v1/health.py"]
    end

    subgraph WIRING["Wiring"]
        auth["api/auth.py\nRBAC"]
        deps["api/deps.py\nDI container"]
    end

    subgraph CONFIG["Config"]
        settings["config/settings.py\nPydantic env vars"]
        pipeline_cfg["config/pipeline_config.py\nYAML + env overlays"]
    end

    subgraph MODELS["Models"]
        schemas["models/schemas.py"]
        rbac["models/rbac.py"]
        audit_m["models/audit.py"]
        metadata_m["models/metadata.py"]
    end

    subgraph PIPELINE["Pipeline"]
        orch["orchestrator.py"]
        inject["injection_detector.py"]
        pii["pii_detector.py"]
        lakera["lakera_guard.py"]
        routing["routing/__init__.py"]
        vstore["vector_store.py"]
        embed_svc["local_embeddings.py"]
        expander["query_expander.py"]
        dedup["deduplication.py"]
        rrf["reciprocal_rank_fusion.py"]
        meta_val["metadata_validator.py"]
        reranker["cohere_reranker.py"]
        bm25["bm25_compressor.py"]
        token_bgt["token_budget.py"]
        llm["llm_client.py"]
        model_rt["model_router.py"]
        hhem["quality/__init__.py"]
        out_schema["output_schema.py"]
    end

    subgraph OBS["Observability"]
        tracing["tracing.py"]
        audit_log["audit_log.py"]
        logging_m["logging.py"]
        metrics["metrics.py"]
        instrument["instrumentation.py"]
        emb_mon["embedding_monitor.py"]
        canary["retrieval_canary.py"]
        daily_eval["daily_eval.py"]
    end

    subgraph EXP["Experimentation"]
        flags["feature_flags.py"]
        shadow["shadow_mode.py"]
        analysis["analysis.py"]
    end

    subgraph FLY["Flywheel"]
        triage["failure_triage.py"]
        annotate["annotation.py"]
        dataset["dataset_manager.py"]
        eval_exp["eval_expansion.py"]
    end

    subgraph SVC["Services"]
        del_svc["deletion_service.py"]
        fb_svc["feedback_service.py"]
        ret_chk["retention_checker.py"]
    end

    %% API wiring
    main --> router
    router --> query_ep & ingest_ep & feedback_ep & deletion_ep & health_ep
    query_ep --> deps
    deps --> orch & settings & pipeline_cfg & tracing & audit_log & flags & shadow & canary

    %% Auth
    query_ep --> auth
    deletion_ep --> auth
    auth --> rbac

    %% Orchestrator imports
    orch --> inject & pii & lakera
    orch --> routing
    orch --> embed_svc & vstore & expander & dedup & rrf
    orch --> reranker
    orch --> bm25 & token_bgt
    orch --> llm & model_rt
    orch --> hhem
    orch --> tracing & instrument
    orch --> flags & shadow & canary

    %% Services
    del_svc --> vstore & tracing & fb_svc & audit_log
    fb_svc --> audit_log & metrics

    %% Flywheel
    triage --> tracing & embed_svc
    annotate --> audit_log
    dataset --> audit_log
    eval_exp --> dataset

    %% Observability internals
    instrument --> metrics
    canary --> metrics
    emb_mon --> metrics
    daily_eval --> tracing
```

### Diagram 3: Request Pipeline Data Flow

```mermaid
---
config:
  flowchart:
    useMaxWidth: true
---
flowchart LR
    REQ["QueryRequest\n{query, user_id,\ntenant_id, session_id}"] --> TRACE["create_trace(variant)\nLangfuse or LocalTrace"]
    TRACE --> LOG["bind_trace_context()\nstructlog adds trace_id"]

    subgraph SAFETY_CHECK["Safety Check"]
        direction TB
        SAFETY["SafetyChecker.check_input()"]
        SAFETY --> INJ["InjectionDetector\n15 regex patterns\n9 attack vectors"]
        SAFETY --> PII["PIIDetector\n8 types: email, SSN,\nphone, credit card, ..."]
        SAFETY --> LAK["LakeraGuard (optional)\nML-based L2"]
        INJ & PII & LAK --> SAFE_RESULT{passed?}
    end

    LOG --> SAFETY
    SAFE_RESULT -->|No| BLOCK["Return blocked response\nlog safety event"]

    subgraph ROUTING["Routing"]
        direction TB
        ROUTE["QueryRouter.route()"]
        ROUTE --> EMBED_Q["embed_query()\nall-MiniLM-L6-v2\n384-dim, local CPU"]
        EMBED_Q --> COSINE["max-sim cosine scoring\nvs 5 route utterance sets"]
        COSINE --> CONF{confidence ≥ 0.5?}
        CONF -->|No| DEFAULT["default_route\n(rag_knowledge_base)"]
        CONF -->|Yes| MATCHED["matched route\n+ confidence score"]
        DEFAULT & MATCHED --> DISPATCH{route type}
    end

    SAFE_RESULT -->|Yes| ROUTE
    DISPATCH -->|direct_llm| DIRECT["Skip retrieval\nDirect LLM call"]
    DISPATCH -->|escalate_human| ESCALATE["Return fallback=true\nHuman handoff"]

    subgraph RAG_PATH["RAG Path (stages 3–7)"]
        direction TB
        EXPAND{confidence ≥ 0.75?}
        EXPAND -->|Yes| SKIP_EXP["Skip expansion\nuse original query only"]
        EXPAND -->|No| MULTI["QueryExpander\n3 variants via Claude Haiku"]
        SKIP_EXP & MULTI --> CONCURRENT["asyncio.gather()\nembed + search per query"]
        CONCURRENT --> QDRANT["Qdrant search\ntop-20 per query, cosine"]
        QDRANT --> RRF["Reciprocal Rank Fusion\nmerge multi-query results"]
        RRF --> DEDUP["Deduplicator\ncosine sim > 0.95 → remove"]
        DEDUP --> RERANK["CohereReranker\n(or passthrough) → top-5"]
        RERANK --> BM25["BM25Compressor\nre-score sentences"]
        BM25 --> BUDGET["TokenBudgetEnforcer\ndrop until ≤ 4000 tokens"]
    end

    DISPATCH -->|rag_knowledge_base| EXPAND

    subgraph GEN_QUALITY["Generation & Quality"]
        direction TB
        TIER["ModelRouter.resolve_model()\nFAST → Haiku\nSTANDARD/COMPLEX → Sonnet"]
        TIER --> GEN["LLMClient.generate()\nOpenRouter (AsyncOpenAI SDK)\nsystem prompt + context"]
        GEN --> HHEM["HallucinationChecker.check()\nVectara HHEM, CPU inference\nmax aggregation across chunks"]
        HHEM --> SCORE{score}
        SCORE -->|"≥ 0.85"| PASS["PASS — return answer"]
        SCORE -->|"0.70–0.85"| WARN["WARN — answer + disclaimer"]
        SCORE -->|"< 0.70"| FAIL["FAIL — fallback response"]
    end

    BUDGET --> TIER
    DIRECT --> TIER

    subgraph FINALIZE["Finalize"]
        direction TB
        INSTRUMENT["PipelineInstrumentation\nPrometheus counters/histograms"]
        INSTRUMENT --> SHADOW["ShadowRunner.maybe_run()\nasyncio.create_task()"]
        SHADOW --> SAVE["trace.save_local()\nJSON to traces/local/"]
        SAVE --> FLUSH["tracing.flush()\nsend to Langfuse (if enabled)"]
    end

    PASS & WARN & FAIL --> INSTRUMENT
    FLUSH --> RESP["QueryResponse"]
```

### Diagram 4: Observability & Monitoring Stack

```mermaid
---
config:
  flowchart:
    useMaxWidth: true
---
flowchart LR
    subgraph SOURCES["Data Sources"]
        direction TB
        ORCH["Pipeline Orchestrator\n(every query)"]
        TRACES["Local Trace Files\ntraces/local/*.json"]
        QDRANT_M["Qdrant Vectors\nembedding samples"]
    end

    subgraph COLLECT["Collection Layer"]
        direction TB
        INSTR["PipelineInstrumentation\nStatic methods per stage"]
        TRACE_SVC["TracingService\nLangfuse SDK or LocalTrace"]
        AUDIT["AuditLogService\nWORM JSON files"]
        STRUCT["structlog\nJSON logging + trace_id"]
    end

    subgraph PROM_METRICS["Prometheus Metrics (34 total)"]
        M_PIPE["Pipeline\nrequests, errors,\nduration, active"]
        M_SAFE["Safety\ninjection blocks,\nPII detections"]
        M_HALL["Hallucination\nHHEM scores,\npass/warn/fail"]
        M_LLM["LLM\ncost, tokens,\nlatency by model"]
        M_EMB["Embedding\ndrift score,\nspread change"]
        M_RET["Retrieval\ncanary p50/p95,\nempty rate"]
        M_FB["Feedback\nreceived total,\ncorrection rate"]
        M_EXP["Experiment\nassignments,\nvariant counts"]
    end

    subgraph MONITORS["Monitors"]
        direction TB
        EMB_MON["EmbeddingMonitor\ncentroid cosine drift (0.15)\nspread change (0.20)"]
        RET_CAN["RetrievalCanary\nrolling: 1000 / baseline: 7000\nCRITICAL: p50 drop >10%\nCRITICAL: empty rate >5%"]
        DAILY["DailyEvalRunner\nRagas via OpenRouter\nfaithfulness, precision, relevancy"]
    end

    subgraph DASHBOARDS["Dashboards"]
        direction TB
        PROM["Prometheus\nport 9090, scrape /metrics"]
        GRAFANA["Grafana\nport 3001, 5 rows, 19 panels"]
        LANGFUSE["Langfuse\nport 3100, trace viewer"]
        PHOENIX["Arize Phoenix\nembedding projections"]
    end

    subgraph ALERTS["Alerting"]
        ALERT["11 Alert Playbooks\n7 CRITICAL + 4 WARN\nTrigger → Investigation\n→ Remediation → Escalation"]
    end

    ORCH --> INSTR --> M_PIPE & M_SAFE & M_HALL & M_LLM & M_EXP
    ORCH --> TRACE_SVC --> TRACES
    ORCH --> STRUCT
    ORCH --> AUDIT
    QDRANT_M --> EMB_MON --> M_EMB
    ORCH --> RET_CAN --> M_RET
    TRACES --> DAILY

    M_PIPE & M_SAFE & M_HALL & M_LLM & M_EMB & M_RET & M_FB & M_EXP --> PROM
    PROM --> GRAFANA
    GRAFANA --> ALERT
    TRACE_SVC --> LANGFUSE
    EMB_MON -.-> PHOENIX
```

### Diagram 5: Data Flywheel

```mermaid
---
config:
  flowchart:
    useMaxWidth: true
---
flowchart LR
    subgraph PHASE1["Phase 1: Triage (automated)"]
        direction TB
        TRACES["Local Trace Files\ntraces/local/*.json"] --> SCAN["FailureTriageService.scan()\nLast N days of traces"]
        SCAN --> CLASSIFY["Classify failures\n6 categories:\nretrieval_failure, hallucination,\nwrong_route, context_gap,\ncompression_loss, other"]
        CLASSIFY --> CLUSTER["Cluster similar failures\ngreedy cosine sim (0.7)\nvia embedding_service"]
        CLUSTER --> REPORT["Triage Report\nreports/triage-YYYY-WNN.json"]
        REPORT --> TASKS["AnnotationService.generate()\nCreate pending tasks\nannotations/pending/*.json"]
    end

    subgraph HUMAN["Human-in-the-Loop"]
        direction TB
        ANNOTATE["scripts/annotate.py\nnext → review → submit\nLabel: correct_answer,\nfailure_category, notes"]
        ANNOTATE --> COMPLETED["annotations/completed/*.json"]
    end

    subgraph PHASE2["Phase 2: Import & Expand (automated)"]
        direction TB
        IMPORT["GoldenDatasetManager.import()\nEmbedding dedup (0.95 cosine)\nValidation + versioning"]
        IMPORT --> GOLDEN["golden_dataset/\nfaithfulness_tests.jsonl\npromptfoo_tests.jsonl\nmetadata.json (semver)"]
        GOLDEN --> EXPAND["EvalSuiteExpander\nAuto-generate eval entries\nCoverage report per category"]
        EXPAND --> COVERAGE["Gap Analysis\nWhich categories need\nmore test coverage?"]
    end

    subgraph EVAL["Evaluation"]
        direction TB
        DEEPEVAL["DeepEval\nFaithfulness CI gate\n20+ golden cases"]
        PROMPTFOO["Promptfoo\nA/B prompt comparison\nRegression gate (>2%)"]
        RAGAS["Daily Ragas Eval\nfaithfulness, precision,\nrelevancy"]
    end

    subgraph WEEKLY["Weekly Automation"]
        CRON["scripts/run_weekly_flywheel.py"]
    end

    TASKS --> ANNOTATE
    COMPLETED --> IMPORT
    GOLDEN --> DEEPEVAL
    GOLDEN --> PROMPTFOO
    GOLDEN --> RAGAS

    CRON -->|"Phase 1"| SCAN
    CRON -->|"--continue (Phase 2)"| IMPORT

    COVERAGE -.->|"identifies gaps"| ANNOTATE
    DEEPEVAL & PROMPTFOO & RAGAS -.->|"failures feed back"| TRACES
```

### Diagram 6: Experimentation & A/B Testing

```mermaid
---
config:
  flowchart:
    useMaxWidth: true
---
flowchart LR
    subgraph FLAGS["Feature Flag System"]
        direction TB
        CONFIG["experiment_configs/flags.yaml\nvariants:\n  control: 0.9 weight\n  treatment_a: 0.1 weight\nuser_overrides + tenant_overrides"]
        CONFIG --> FFS["FeatureFlagService"]
        FFS --> HASH["Deterministic Assignment\nMD5(user_id)[:8] → int\nmod 10000 → [0,1) bucket"]
        FFS --> OVERRIDE["Priority Resolution\n1. tenant override\n2. user override\n3. hash-based\n4. default variant"]
    end

    subgraph REQUEST["Request Path"]
        direction TB
        REQ["Incoming Query\n{user_id, tenant_id}"] --> RESOLVE["get_variant()\nresolve variant name"]
        RESOLVE --> TRACE["create_trace(variant=...)\nTag trace with variant"]
        TRACE --> PIPELINE["Run primary pipeline\n(control or treatment)"]
        PIPELINE --> RESPONSE["Return response"]
    end

    subgraph SHADOW_MODE["Shadow Mode"]
        direction TB
        SHADOW["ShadowRunner.maybe_run()"]
        SHADOW --> CHECKS{gates}
        CHECKS -->|"enabled?"| EN["shadow_mode.enabled"]
        CHECKS -->|"budget ok?"| BUD["budget_limit_usd\n(in-memory tracking)"]
        CHECKS -->|"circuit breaker?"| CB["latency < 3x primary"]
        CHECKS -->|"sample rate?"| SR["10% sample rate"]
        EN & BUD & CB & SR --> FIRE["asyncio.create_task()\nfire-and-forget"]
        FIRE --> SHADOW_GEN["Re-run generation only\ncandidate model/prompt\nReuse retrieval results"]
        SHADOW_GEN --> SHADOW_TRACE["Save trace\nvariant='shadow'"]
    end

    subgraph ANALYSIS["Experiment Analysis"]
        direction TB
        TRACES_DIR["traces/local/*.json\nGrouped by variant"] --> ANALYZER["ExperimentAnalyzer"]
        ANALYZER --> METRICS["Compute per-variant:\nfaithfulness mean\nlatency p50/p95\ncost total"]
        METRICS --> STATS["Statistical Tests\n(min 30 traces per variant)"]
        STATS --> TTEST["Welch's t-test"]
        STATS --> MANN["Mann-Whitney U"]
        STATS --> COHEN["Cohen's d"]
        TTEST & MANN & COHEN --> REC["Auto-Recommendation\npromote | regress | continue"]
    end

    subgraph AUDIT_TRAIL["Audit Trail"]
        AUDIT["AuditLogService\nEXPERIMENT_ASSIGNMENT event\nuser_id, tenant_id, variant"]
    end

    FFS --> RESOLVE
    RESPONSE --> SHADOW
    RESOLVE --> AUDIT
    SHADOW_TRACE --> TRACES_DIR
    TRACE --> TRACES_DIR
```

## File Tree

```
enterprise-pipeline/
├── Dockerfile                              # Production container image
├── Makefile                                # dev, test, lint, typecheck, infra targets
├── docker-compose.yaml                     # Qdrant + Langfuse + Redis
├── docker-compose.monitoring.yaml          # Prometheus + Grafana
├── pipeline_config.yaml                    # Master config (11 nested sections)
├── promptfoo.config.yaml                   # Promptfoo eval config (OpenRouter)
├── pyproject.toml                          # Dependencies, build config, tool settings
├── requirements.lock                       # Locked dependency versions
│
├── src/
│   ├── main.py                             # FastAPI app factory + lifespan events
│   │
│   ├── config/
│   │   ├── settings.py                     # Pydantic env var schema
│   │   └── pipeline_config.py              # YAML config + env overlay loader (deepmerge)
│   │
│   ├── models/
│   │   ├── schemas.py                      # API request/response models
│   │   ├── rbac.py                         # 5 roles, 13 permissions, PermissionChecker
│   │   ├── audit.py                        # AuditEvent, AuditActor, AuditResource
│   │   └── metadata.py                     # ChunkMetadata, DocType
│   │
│   ├── api/
│   │   ├── auth.py                         # API key → Role RBAC, require_permission()
│   │   ├── deps.py                         # @lru_cache DI wiring for all services
│   │   ├── router.py                       # Route aggregator (v1 + health)
│   │   └── v1/
│   │       ├── query.py                    # POST /api/v1/query
│   │       ├── ingest.py                   # Document ingestion + chunking
│   │       ├── feedback.py                 # User feedback collection + stats
│   │       ├── deletion.py                 # Right-to-deletion endpoints
│   │       └── health.py                   # /health, /metrics, /ready
│   │
│   ├── pipeline/
│   │   ├── orchestrator.py                 # 12-stage pipeline coordinator
│   │   ├── safety/
│   │   │   ├── injection_detector.py       # L1: 15 regex patterns, 9 attack vectors
│   │   │   ├── pii_detector.py             # 8 PII types (email, SSN, phone, CC, ...)
│   │   │   └── lakera_guard.py             # L2: ML-based injection (optional API)
│   │   ├── routing/
│   │   │   ├── __init__.py                 # QueryRouter: local embeddings + max-sim
│   │   │   └── routes.yaml                 # 5 semantic routes, 12-13 utterances each
│   │   ├── retrieval/
│   │   │   ├── vector_store.py             # Qdrant client (upsert, search, delete)
│   │   │   ├── embeddings.py               # Abstract EmbeddingService interface
│   │   │   ├── local_embeddings.py         # all-MiniLM-L6-v2 (384-dim, CPU)
│   │   │   ├── query_expander.py           # Multi-query via Claude Haiku
│   │   │   ├── deduplication.py            # Cosine dedup (0.95 threshold)
│   │   │   ├── reciprocal_rank_fusion.py   # RRF for multi-query merging
│   │   │   └── metadata_validator.py       # Compliance gate (user/doc/tenant IDs)
│   │   ├── reranking/
│   │   │   └── cohere_reranker.py          # Cohere API (passthrough fallback)
│   │   ├── compression/
│   │   │   ├── bm25_compressor.py          # BM25 sentence re-scoring
│   │   │   └── token_budget.py             # 4000 token max enforcement
│   │   ├── generation/
│   │   │   ├── llm_client.py               # OpenRouter (AsyncOpenAI SDK)
│   │   │   └── model_router.py             # Heuristic tier: FAST/STANDARD/COMPLEX
│   │   ├── quality/
│   │   │   └── __init__.py                 # HHEM hallucination check (CPU inference)
│   │   └── output_schema.py               # Per-route JSON schema validation
│   │
│   ├── observability/
│   │   ├── tracing.py                      # Langfuse or local JSON fallback
│   │   ├── audit_log.py                    # Immutable WORM audit log
│   │   ├── logging.py                      # structlog JSON config + trace binding
│   │   ├── metrics.py                      # 34 Prometheus metrics, 8 groups
│   │   ├── instrumentation.py              # Static methods for metric recording
│   │   ├── embedding_monitor.py            # Cosine centroid drift detection
│   │   ├── retrieval_canary.py             # Rolling window p50/p95 alerts
│   │   └── daily_eval.py                   # Ragas eval runner (OpenRouter judge)
│   │
│   ├── experimentation/
│   │   ├── feature_flags.py                # MD5 hash deterministic variant assignment
│   │   ├── shadow_mode.py                  # Fire-and-forget candidate generation
│   │   └── analysis.py                     # Welch t-test, Mann-Whitney U, Cohen's d
│   │
│   ├── flywheel/
│   │   ├── failure_triage.py               # Scan, classify (6 types), cluster failures
│   │   ├── annotation.py                   # Task generation + submission + export
│   │   ├── dataset_manager.py              # Golden dataset import, dedup, versioning
│   │   └── eval_expansion.py               # Auto-expand eval suite + coverage report
│   │
│   ├── services/
│   │   ├── deletion_service.py             # Right-to-deletion (vectors + traces + feedback)
│   │   ├── feedback_service.py             # Feedback collection + rate tracking
│   │   └── retention_checker.py            # TTL-based data purge
│   │
│   └── utils/
│       └── tokens.py                       # tiktoken helpers
│
├── scripts/
│   ├── ingest_documents.py                 # Load, chunk, embed, upsert to Qdrant
│   ├── run_e2e_trace.py                    # Full pipeline trace (mocked externals)
│   ├── run_adversarial_tests.py            # 20 injection payloads + PII patterns
│   ├── test_routing_accuracy.py            # Labeled routing test set
│   ├── test_multi_query_recall.py          # Single vs multi-query recall comparison
│   ├── generate_synthetic_tests.py         # 77 synthetic HHEM test cases
│   ├── load_test.py                        # Concurrent load testing
│   ├── run_daily_eval.py                   # Ragas eval on recent traces
│   ├── run_failure_triage.py               # Failure scan + classify + cluster
│   ├── run_weekly_flywheel.py              # Two-phase flywheel automation
│   ├── annotate.py                         # Interactive annotation CLI
│   ├── expand_golden_dataset.py            # Import, stats, coverage
│   ├── run_experiment_analysis.py          # Statistical variant analysis
│   ├── validate_environment.py             # API key + service connectivity check
│   ├── validate_routing.py                 # Routing accuracy validation
│   ├── validate_production.py              # Full production checklist
│   └── check_regression.py                 # Promptfoo CI eval gate
│
├── tests/
│   ├── unit/                               # ~49 test files, ~318 tests
│   ├── eval/                               # DeepEval faithfulness + exit criteria (~56 tests)
│   └── integration/                        # E2E pipeline + API key-dependent tests
│
├── environments/
│   ├── base.yaml                           # Base config overlay
│   ├── development.yaml                    # Dev overrides
│   └── production.yaml                     # Prod overrides
│
├── experiment_configs/
│   └── flags.yaml                          # Feature flag variants + overrides
│
├── golden_dataset/
│   ├── faithfulness_tests.jsonl            # DeepEval test cases
│   ├── promptfoo_tests.jsonl               # Promptfoo test cases
│   └── metadata.json                       # Dataset versioning (semver)
│
├── prompts/
│   ├── rag_system.txt                      # Default system prompt
│   ├── current.txt                         # Promptfoo baseline prompt
│   └── candidate.txt                       # Promptfoo candidate prompt
│
├── monitoring/
│   ├── prometheus.yml                      # Scrape config
│   └── grafana/
│       └── dashboards/
│           └── pipeline-health.json        # 5 rows, 19 panels
│
├── docs/
│   ├── 02-prd.md                           # Product requirements
│   ├── 03-implementation-plan.md           # 3 phases, 8 waves
│   ├── 04-technical-specs.md               # Infrastructure, schemas, APIs
│   ├── deployment-guide.md                 # Full deployment instructions
│   ├── security-review.md                  # Security assessment
│   ├── adr/                                # 13 architecture decision records
│   ├── runbooks/
│   │   ├── operations.md                   # Daily/weekly/monthly ops
│   │   └── alerting-playbooks.md           # 11 alerts with remediation
│   └── baselines/
│       ├── production-baseline.json        # Performance + quality baselines
│       └── real-latency-baselines.json     # Measured stage latencies
│
├── annotations/                            # Flywheel annotation storage
│   ├── pending/                            # Tasks awaiting human review
│   └── completed/                          # Submitted annotations
│
├── traces/                                 # Pipeline trace storage
│   └── local/                              # LocalTrace JSON files
│
├── audit_logs/                             # Immutable WORM audit log
│   └── local/                              # Individual audit event JSON files
│
└── reports/                                # Weekly triage reports
```

## Notable Architectural Decisions

**Constructor dependency injection, not globals.** Every service takes its dependencies as constructor arguments. Wiring happens in `deps.py` via `@lru_cache` singletons. This makes every component independently testable — swap real Qdrant for a mock, real OpenRouter for a stub, real Langfuse for a LocalTrace — without touching any service code. The orchestrator constructor takes 15 parameters, each an interface or concrete service.

**Graceful degradation as a first-class pattern.** Missing API keys never crash the pipeline. Cohere reranking falls back to passthrough (returns original list). Lakera Guard L2 is silently skipped. Query expansion fails gracefully to the original query. Langfuse tracing falls back to local JSON files with the same schema. This means the pipeline runs with zero external API keys (except OpenRouter for generation) — ideal for local development, CI testing, and cost control.

**Local-first ML inference.** Routing uses `all-MiniLM-L6-v2` (384-dim, ~80MB) on CPU — no embedding API calls. Hallucination detection uses Vectara's HHEM model on CPU (~150ms warm inference). These eliminate two API round-trips from the critical path and remove API key requirements for core quality checks.

**Max-sim over mean-sim for semantic routing.** Route scoring computes cosine similarity between the query embedding and every utterance in each route, then takes the maximum (best match) rather than the mean. Mean-sim dilutes signal when a route has diverse utterances. This single change improved routing accuracy from 40% to 90% (18/20 labeled queries).

**Immutable audit log at the API level.** `AuditLogService` has `log_event()`, `get_event()`, and `list_events()` — no `delete()` or `update()` methods exist. WORM (write-once, read-many) is enforced by the class interface, not by filesystem permissions. Every deletion request, experiment assignment, feedback submission, and compliance action creates an audit event with actor, resource, and tenant context.

**Two-phase flywheel with human-in-the-loop.** The weekly automation script runs in two phases: Phase 1 (triage + generate annotation tasks) is fully automated. A human reviews and annotates between phases. Phase 2 (`--continue` flag) imports annotations, deduplicates against the golden dataset, expands eval suites, and generates a coverage report. This keeps humans in the quality loop while automating the mechanical work.
