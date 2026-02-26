# ADR-001: Qdrant over pgvector for Vector Storage

**Status:** Accepted
**Date:** Wave 1 completion
**Wave:** 1
**Deciders:** AI Platform Engineering

## Context

The Enterprise AI Pipeline requires a vector database to store and retrieve document embeddings for RAG (Retrieval-Augmented Generation). The retrieval layer is a core component of the system, and the choice of vector storage directly impacts query latency, tenant isolation, filtering capabilities, and operational complexity.

Key requirements included async client support for our asyncio-based pipeline, robust filtering for multi-tenant isolation, and the ability to scale vector collections independently from relational data.

## Decision

We chose Qdrant as our vector database, accessed via the `AsyncQdrantClient` Python SDK. Vectors are stored in Qdrant collections with payload-based filtering for tenant and document-level isolation.

## Alternatives Considered

- **pgvector (PostgreSQL extension):** Embeds vector search into an existing Postgres instance. Simpler operationally (one fewer service), but couples vector workloads with relational queries and lacks a purpose-built filter DSL.
- **Pinecone (SaaS):** Fully managed, but introduces a hard vendor dependency, sends data off-premise, and has per-vector pricing that scales poorly for our use case.
- **Weaviate:** Full-featured vector DB with GraphQL API. Heavier resource footprint and more complex schema management than we needed.
- **Milvus:** Powerful at scale but operationally complex (requires etcd, MinIO). Overengineered for our current throughput.

## Rationale

Qdrant provides the best balance of developer ergonomics, async support, and operational simplicity for our scale. The `AsyncQdrantClient` integrates naturally with our asyncio pipeline. Qdrant's filter DSL supports complex payload-based filtering, which we use for tenant isolation without needing separate collections per tenant. Docker deployment is straightforward, and Qdrant's resource footprint is modest compared to Milvus or Weaviate.

Choosing a dedicated vector DB over pgvector allows us to scale vector workloads independently, avoid contention with relational queries, and take advantage of purpose-built indexing (HNSW) that outperforms pgvector's IVFFlat at our embedding dimensionality.

## Consequences

### Positive
- Async-native client integrates cleanly with our asyncio pipeline
- Filter DSL enables tenant isolation without collection-per-tenant overhead
- Independent scaling of vector workloads from relational data
- Docker-friendly deployment with persistent volume support
- HNSW indexing provides better recall/latency tradeoffs than pgvector's IVFFlat

### Negative
- Additional infrastructure component to deploy and maintain (separate from PostgreSQL)
- Team must learn Qdrant's filter syntax and collection management
- Backup and restore procedures are separate from existing PostgreSQL workflows

### Risks
- Qdrant is a younger project than PostgreSQL; long-term maintenance risk is mitigated by its active open-source community and commercial backing
- If we later need transactional consistency between relational and vector data, the split architecture adds complexity
