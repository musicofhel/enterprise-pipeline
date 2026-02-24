# Enterprise AI Pipeline — Tool Gap Fixes

Everywhere the previous docs named a concept but not a tool to fulfill it.

---

## Groundedness / Hallucination Detection

Previously said: "custom NLI models", "groundedness checks"

| Tool | What It Does |
|---|---|
| **Vectara HHEM** (Hughes Hallucination Evaluation Model) | Open-source, purpose-built for detecting hallucinations in RAG. Cross-encoder that scores whether an output is grounded in the retrieved context. |
| **TruLens** (Snowflake) | Groundedness scoring as a library — compares each sentence in LLM output against source chunks, returns per-sentence grounding scores. |
| **Lynx** (Patronus AI) | Open-source hallucination detection model, fine-tuned specifically for RAG faithfulness. |
| **DeepEval's FaithfulnessMetric** | Programmatic — breaks LLM output into claims, checks each against context. Runs in CI. |
| **Galileo Luna / ChainPoll** | Commercial platform for hallucination detection with production monitoring. |

**Pick:** Vectara HHEM if you want open-source and self-hosted. TruLens if you want it integrated into your eval framework. Lynx for the best open-weight accuracy.

---

## Semantic Deduplication (Retrieval Results)

Previously said: "deduplicate" with no tool.

| Tool | What It Does |
|---|---|
| **MinHash / LSH** via **datasketch** (Python) | Fast approximate dedup on text chunks before they hit the LLM context. |
| **Qdrant's built-in grouping** | Groups similar results at query time — `group_by` parameter. |
| **Custom cosine similarity threshold** | After retrieval, pairwise cosine sim on results, drop anything >0.95 similarity. 5 lines of numpy. |
| **Superlinked** | Embeds data with multiple vector spaces and handles dedup/fusion natively. |

**Pick:** Custom cosine threshold is the simplest and works. Qdrant grouping if you're already on Qdrant.

---

## Context Compression / Prompt Minimization

Previously named LLMLingua and RECOMP but didn't explain alternatives.

| Tool | What It Does |
|---|---|
| **LLMLingua-2** (Microsoft) | Token-level compression — removes low-information tokens from context. 2-5x compression with minimal quality loss. |
| **RECOMP** (UMass) | Trains a compressor that produces a short summary of retrieved docs tuned for downstream QA. |
| **Extractive snippet selection** via **BM25 sub-scoring** | Don't send whole chunks. Score sentences within each chunk against the query, send only top-k sentences. No model needed. |
| **LongLLMLingua** | Extension of LLMLingua specifically for long-context scenarios (>100k tokens). |

**Pick:** BM25 sub-scoring within chunks is free and effective. LLMLingua-2 if you need aggressive compression.

---

## Query Expansion (Beyond "HyDE")

Previously named HyDE as a technique with no implementation path.

| Tool | What It Does |
|---|---|
| **HyDE implementation** → **LangChain HypotheticalDocumentEmbedder** | Generates a hypothetical answer, embeds that instead of the query. Built into LangChain. |
| **Multi-query** → **LangChain MultiQueryRetriever** | LLM generates 3-5 rephrasings of the query, runs all of them, merges results. |
| **RAG-Fusion** | Similar to multi-query but applies Reciprocal Rank Fusion to merge results. Implementation in LangChain and LlamaIndex. |
| **Step-back prompting** → custom chain | LLM generates a more abstract version of the query ("What are the tax implications of X?" → "What are the general tax rules for this category?"). No library — it's a prompt pattern. |
| **Cohere rerank with query expansion** | Cohere's reranker handles query-document mismatch natively — partial replacement for explicit expansion. |

**Pick:** MultiQueryRetriever is the easiest win. RAG-Fusion if you want better merge logic.

---

## Prompt Injection / Input Sanitization

Previously said: "custom regex + LLM-based detection layered together"

| Tool | What It Does |
|---|---|
| **Lakera Guard** | API call — classifies inputs for prompt injection, jailbreaks, PII. Production-grade, low latency. |
| **Rebuff** | Open-source, multi-layer detection (heuristic + LLM + vector similarity to known attacks). |
| **Prompt Armor** | API-based, specializes in indirect injection detection (malicious instructions in retrieved documents). |
| **Arthur Shield** | Commercial, wraps your LLM calls with input/output filtering. |
| **lm-format-enforcer** | Not injection detection, but prevents the LLM from generating outside a defined schema — limits the blast radius. |
| **Regex/heuristic layer** → **Guardrails AI validators** | Guardrails AI has built-in validators for common injection patterns. Use as the fast first pass before an LLM-based detector. |

**Pick:** Lakera Guard for the fastest path to production. Layer it: Guardrails AI regex validators (fast, cheap) → Lakera Guard (ML-based) → LLM-based detection for edge cases.

---

## Semantic / Query Routing (Classifier)

Previously said: "custom classifier" without naming one.

| Tool | What It Does |
|---|---|
| **Semantic Router** (Aurelio Labs) | Define routes as sets of example utterances, uses embedding similarity to classify. No training needed. Sub-millisecond. |
| **SetFit** (Hugging Face) | Few-shot text classifier. Give it 8-16 examples per class, fine-tunes a small model in seconds. |
| **ONNX-exported DistilBERT** | Train a small classifier, export to ONNX, run at <5ms inference. |
| **Portkey prompt router** | Routes based on model capability/cost — not query type, but complementary. |
| **LangChain RunnableBranch** | Code-level routing — if/else on classifier output to pick retrieval strategy. |

**Pick:** Semantic Router for zero-training setup. SetFit if you have labeled examples and want higher accuracy.

---

## NLI (Natural Language Inference) Models for Fact Checking

Previously said: "NLI model" without naming one.

| Model | What It Does |
|---|---|
| **microsoft/deberta-v3-large-mnli** | Best open-source NLI model. Takes (premise, hypothesis) → entailment/contradiction/neutral. |
| **cross-encoder/nli-deberta-v3-base** | Lighter, faster. Good enough for most grounding checks. |
| **Vectara HHEM** | Specifically fine-tuned for hallucination detection — NLI adapted for RAG outputs. |
| **AlignScore** (Zhao et al.) | Unified alignment scoring that outperforms vanilla NLI on factual consistency. |

**Pick:** deberta-v3-base for speed, HHEM for RAG-specific accuracy, AlignScore if you want SOTA.

---

## Right-to-Deletion in Vector Stores (GDPR)

Previously said: "design your metadata" — here's how.

| Approach | Implementation |
|---|---|
| **pgvector + Postgres** | `DELETE FROM embeddings WHERE user_id = X;` — this is why pgvector wins for regulated industries. Standard SQL deletion with ACID guarantees. |
| **Qdrant** | Delete by filter: `client.delete(collection, filter={"user_id": X})`. Supports metadata-based deletion natively. |
| **Weaviate** | `client.batch.delete_objects(where={"path": ["userId"], "operator": "Equal", "valueString": X})`. |
| **Pinecone** | Delete by metadata filter or by ID namespace. Use namespaces per tenant for clean deletion. |
| **Milvus** | `collection.delete(expr=f"user_id == '{X}'")`. Supports expression-based deletion. |

**Pick:** pgvector makes this trivial because it's just Postgres. For dedicated vector DBs, always store `user_id`, `doc_id`, `tenant_id` as metadata on every vector from day one.

---

## Shadow Mode / Canary Deploys for LLM Pipelines

Previously described the pattern without tools.

| Tool | What It Does |
|---|---|
| **Braintrust** | Run two prompt/model variants side by side, score both, compare before promoting. |
| **Promptfoo** | `promptfoo eval --compare` — runs same dataset through two configs, shows diff. CI-friendly. |
| **LaunchDarkly + custom logging** | Feature flag determines which pipeline version runs. Log both outputs, eval offline. |
| **Statsig** | A/B testing platform — can randomize users into pipeline variants and track outcome metrics. |
| **Custom shadow mode** → **Temporal workflow** | Fork the workflow: primary path serves the user, shadow path runs new version, logs output, doesn't serve. Compare async. |

**Pick:** Promptfoo for pre-deploy comparison. LaunchDarkly + custom logging for production shadow mode. Braintrust if you want a managed platform.

---

## Immutable Audit Logging

Previously said: "immutable log store" without specifics.

| Tool | What It Does |
|---|---|
| **S3 + Object Lock** (WORM) | Write-once-read-many. Logs can't be deleted or modified. Cheapest option. |
| **AWS CloudTrail Lake** | Managed immutable audit logs with SQL query support. |
| **Elasticsearch / OpenSearch** with ILM | Index lifecycle management — hot/warm/cold tiers, immutable cold storage. |
| **Datadog Log Archives** | If you're already on Datadog, archive to S3 with retention policies. |
| **QuestDB / TimescaleDB** | Time-series databases for structured LLM call logs with fast analytical queries. |
| **Langfuse** | Stores every LLM call with full trace. Self-hostable. Not immutable by default — pair with S3 export for compliance. |

**Pick:** Langfuse for the LLM-specific logging + S3 Object Lock for immutable compliance archive. Two layers.

---

## Late Chunking / Advanced Chunking

Previously mentioned "late chunking" without tools.

| Tool | What It Does |
|---|---|
| **Jina AI Late Chunking** | Embed the full document with jina-embeddings-v3, then segment embeddings post-hoc. Preserves cross-chunk context. |
| **Chonkie** | Python library for semantic chunking — splits on semantic boundaries, not fixed token counts. |
| **LlamaIndex SemanticSplitter** | Chunks based on embedding similarity between sentences. Groups semantically similar sentences together. |
| **Unstructured.io chunking** | Document-aware chunking — respects headers, tables, lists. Chunks by document structure, not tokens. |

**Pick:** Unstructured.io for document-aware chunking as baseline. Jina Late Chunking if you want the frontier approach. Chonkie for a lightweight middle ground.

---

## Embedding Drift / Retrieval Quality Monitoring

Previously said: "track retrieval quality metrics over time" without tools.

| Tool | What It Does |
|---|---|
| **Arize Phoenix** | Open source. Tracks embedding drift, retrieval relevance, LLM response quality over time. Dashboards and alerts. |
| **WhyLabs / LangKit** | Data quality monitoring. Tracks statistical properties of embeddings, flags distribution shifts. |
| **Ragas** continuous mode | Run Ragas metrics (context precision, faithfulness) on a sample of production queries daily. Plot trends. |
| **Custom** → cosine sim distribution tracking | Track the average/p50/p95 cosine similarity between queries and retrieved docs. If it drops, your retrieval is degrading. 20 lines of Python + a Grafana dashboard. |

**Pick:** Arize Phoenix for a full dashboard. Custom cosine sim tracking as a cheap canary signal.

---

## Data Flywheel — Specific Tools at Each Step

Previously had a diagram without tools on each arrow.

```
Production Outputs
       │
       ▼
┌──────────────────────┐
│ Feedback Collection   │  Langfuse (thumbs up/down, user corrections)
│                       │  Argilla (structured annotation by reviewers)
│                       │  LangSmith (inline annotations on traces)
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│ Failure Triaging      │  Langfuse dashboard (filter low-score responses)
│                       │  Arize Phoenix (cluster failure patterns)
│                       │  Grafana alerts (quality score drops below threshold)
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│ Golden Dataset        │  Argilla (export annotated examples)
│ Expansion             │  Lilac (dataset curation, dedup, clustering)
│                       │  Curator (LLM-powered synthetic data generation)
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│ Eval & Regression     │  Promptfoo (CI integration, snapshot tests)
│                       │  DeepEval (pytest plugin, metric assertions)
│                       │  Braintrust (comparison experiments)
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│ Prompt / Config       │  Humanloop (A/B test prompt variants)
│ Optimization          │  DSPy (automated prompt optimization)
│                       │  Eppo / Statsig (experiment analysis)
└──────────────────────┘
```

---

## Bonus: Tools I Should Have Named Earlier

| Gap | Tool |
|---|---|
| API rate limiting / throttling | **Portkey** (built-in), **Kong** (API gateway level), **Cloudflare Workers** (edge) |
| Structured logging format | **structlog** (Python), **pino** (Node.js) — always log structured JSON, not strings |
| Secret rotation for LLM API keys | **HashiCorp Vault** auto-rotation, **AWS Secrets Manager** rotation lambdas |
| Load testing LLM pipelines | **Locust**, **k6** — simulate concurrent users hitting your pipeline |
| PDF form filling / generation | **WeasyPrint**, **ReportLab**, **Puppeteer** for HTML→PDF |
| Synthetic test data generation | **Curator** (Bespokelabs), **Gretel.ai**, **Argilla + distilabel** |
| Model fine-tuning (when needed) | **Axolotl**, **Unsloth** (fast LoRA), **OpenAI fine-tuning API**, **Anyscale** |
| Prompt testing locally | **Promptfoo** CLI, **Humanloop** playground, **LangSmith** playground |
