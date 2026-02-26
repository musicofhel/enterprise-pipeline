# Product FAQ

**Document Version:** 2.1
**Effective Date:** January 10, 2026
**Owner:** Product Marketing
**Last Reviewed:** January 8, 2026
**Classification:** External - Public

---

## General

### What is the Meridian AI Pipeline?

The Meridian AI Pipeline is an enterprise-grade platform for building AI-powered search and question-answering systems over your organization's documents. It combines advanced retrieval-augmented generation (RAG) with enterprise security controls, enabling teams to get accurate, sourced answers from internal knowledge bases, policy documents, technical documentation, and more.

The platform handles the full pipeline: document ingestion, chunking, embedding, vector storage, retrieval, and LLM-powered answer generation -- all through a simple REST API or web dashboard.

### Who is it designed for?

The platform is designed for:
- **Engineering teams** building internal knowledge tools or customer-facing search features
- **Operations teams** looking to automate answers to repetitive policy and process questions
- **Support teams** that need instant, accurate answers from product documentation
- **Compliance teams** managing large volumes of regulatory and policy documents

### How does it differ from a basic ChatGPT wrapper?

Unlike generic LLM wrappers, the Meridian AI Pipeline:
1. **Grounds answers in your data** -- every response includes source citations from your document corpus
2. **Enforces access controls** -- role-based permissions ensure users only see answers from documents they have access to
3. **Provides enterprise compliance** -- SOC 2 Type II certified, GDPR compliant, HIPAA BAA available
4. **Offers fine-tuning** -- Enterprise customers can fine-tune models on their domain-specific data for higher accuracy
5. **Gives full auditability** -- every query, response, and source retrieval is logged for compliance and debugging

## Accuracy and Reliability

### How does the platform handle hallucinations?

We employ a multi-layered approach to minimize hallucinations:

1. **Retrieval-first architecture:** The LLM only generates answers based on retrieved document chunks, not from its parametric knowledge. If no relevant documents are found, the system returns "I don't have enough information to answer this question" rather than guessing.
2. **Confidence scoring:** Every response includes a confidence score (0.0 to 1.0). Responses below 0.7 are flagged as low-confidence and include a disclaimer.
3. **Source attribution:** Every answer includes direct references to the source documents and specific passages used, allowing users to verify accuracy.
4. **Relevance filtering:** Retrieved chunks must pass a minimum relevance threshold (configurable, default 0.75) before being included in the generation context.
5. **Feedback loop:** The `/feedback` API endpoint allows users to flag incorrect answers, which feeds into model improvement and retrieval tuning.

### What is the uptime SLA?

- **Starter and Professional plans:** No formal SLA; historical uptime is 99.8% over the past 12 months
- **Enterprise plan:** **99.9% uptime SLA** with financial credits for downtime exceeding the guarantee
  - Monthly credit: 10% of monthly fee for each 0.1% below 99.9%
  - Maximum credit: 30% of monthly fee
  - Scheduled maintenance windows (announced 72 hours in advance) are excluded from SLA calculations

Current and historical uptime is published at https://status.meridian-ai.com.

## Data and Privacy

### What data formats are supported for ingestion?

The platform supports the following document formats:

| Format | Extension | Max Size |
|---|---|---|
| PDF | `.pdf` | 50 MB |
| Markdown | `.md` | 10 MB |
| Plain Text | `.txt` | 10 MB |
| Microsoft Word | `.docx` | 25 MB |
| HTML | `.html` | 10 MB |

Batch ingestion via API supports up to **100 documents per request**. For larger bulk imports, contact support for assisted migration.

### How is data privacy ensured?

Data privacy is a core principle of the Meridian AI Pipeline:

- **Encryption:** AES-256 at rest, TLS 1.3 in transit for all data
- **Isolation:** Each customer's data is stored in logically isolated namespaces; there is no cross-tenant data access
- **Region control:** EU customers' data is processed and stored exclusively in the eu-west-1 (Ireland) AWS region
- **No training on your data:** Customer data is **never** used to train or fine-tune our base models unless explicitly requested and contracted
- **Deletion:** Data deletion requests are fulfilled within 72 hours per GDPR Article 17
- **Certifications:** SOC 2 Type II, GDPR compliant, HIPAA BAA available for healthcare customers
- **Audit logs:** All data access is logged and available for review in the Dashboard (Enterprise plan) or via API

See our full [Data Security and Privacy Policy](/docs/data-security-privacy) for details.

### Can I self-host the platform?

Yes, self-hosted deployment is available as an **Enterprise add-on**. The self-hosted option includes:

- Docker-based deployment to your own AWS, GCP, or Azure environment
- Terraform modules for infrastructure provisioning
- Helm charts for Kubernetes deployment
- Air-gapped deployment support (no internet connectivity required after initial setup)
- Dedicated support engineer for installation and configuration
- Quarterly updates delivered as versioned releases

Self-hosted customers manage their own infrastructure, backups, and scaling. Meridian provides the application software, updates, and technical support.

Minimum infrastructure requirements for self-hosted deployment:
- 8 vCPUs, 32 GB RAM for the application tier
- PostgreSQL 15+ for metadata storage
- 100 GB SSD for vector index storage (scales with corpus size)
- GPU instance (NVIDIA A10G or better) recommended for high-throughput deployments

## Integrations

### What integration options are available?

The platform integrates with your existing tools via:

- **REST API:** Full-featured API for custom integrations (see [API Documentation](/docs/api-documentation))
- **Official SDKs:** Python, Node.js, and Go libraries for common programming languages
- **Webhooks:** Real-time notifications for ingestion events, usage thresholds, and system events
- **Pre-built connectors** (Professional and Enterprise plans):
  - Slack (query from any channel via `/meridian` slash command)
  - Microsoft Teams (bot integration)
  - Confluence (automatic sync of spaces)
  - SharePoint (document library sync)
  - Zendesk (knowledge base integration)
  - Salesforce (case deflection and agent assist)
- **Zapier:** Connect to 5,000+ apps via Zapier triggers and actions
- **Custom connectors:** Enterprise customers can work with our integrations team to build connectors for proprietary systems

### Can I use my own LLM or embedding model?

Enterprise customers can bring their own models:
- **Custom embedding models:** Deploy your own embedding model for domain-specific retrieval
- **Custom LLM:** Use your own fine-tuned model for answer generation (OpenAI-compatible API required)
- **Azure OpenAI:** Route generation through your Azure OpenAI deployment for data residency compliance

## Getting Started

### How do I get started?

1. **Sign up** at https://app.meridian-ai.com/signup for a 14-day free trial (no credit card required)
2. **Upload documents** via the Dashboard drag-and-drop interface or API
3. **Query your corpus** using the built-in playground or API
4. **Integrate** into your application using our SDKs or REST API

Most teams are up and running within **30 minutes** of signing up.

### Where can I get support?

| Plan | Support Channel | Response Time |
|---|---|---|
| Free / Starter | Email, GitHub Discussions | 48 hours |
| Professional | Email, live chat | 4 hours (business hours) |
| Enterprise | Dedicated CSM, phone, Slack | 15 minutes (P1), 1 hour (P2) |

All customers can access our documentation at https://docs.meridian-ai.com and community forum at https://community.meridian-ai.com.

---

*For questions not covered here, contact sales@meridian-ai.com or visit our documentation portal.*
