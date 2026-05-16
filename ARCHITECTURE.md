# Architecture Documentation
## AI-Assisted Prior Authorization Review Platform

**Version:** 0.1.0  
**Stack:** FastAPI + LangGraph + GPT-4o + Pinecone + MySQL + Redis + RabbitMQ  
**Compliance:** HIPAA-aligned audit trail, PHI handling controls, role-based access

---

## 1. System Overview

The PA Review Platform automates the clinical review process for health insurance prior authorization requests. Clinical documents are ingested, OCR-processed, and analyzed by a multi-model AI pipeline that produces a structured recommendation (APPROVE / DENY / PEND / ESCALATE) with criterion-by-criterion evidence. A human reviewer validates the AI recommendation through a role-protected web interface. Every action is immutably audited.

```
Provider Portal / API
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│  FastAPI Application  (8 middleware layers)               │
│  TrustedHost → CORS → Security Headers → Tracing →       │
│  LangSmith → Audit → Guardrails → RequestLogging          │
├──────────────────────────────────────────────────────────┤
│  API Routes                                               │
│  /pa-requests  /cases  /review  /clarification  /metrics  │
└────────────────────┬─────────────────────────────────────┘
                     │
           ┌─────────┴──────────┐
           │                    │
    ┌──────▼──────┐    ┌────────▼────────┐
    │  Sync Path  │    │   Async Queue   │
    │  (HTTP API) │    │   (RabbitMQ)    │
    └──────┬──────┘    └────────┬────────┘
           │                    │
           └─────────┬──────────┘
                     │
         ┌───────────▼───────────────────────────┐
         │         LangGraph Workflow Engine       │
         │  ┌─────────────────────────────────┐   │
         │  │  OCR → Extract → Retrieve →     │   │
         │  │  Reason → [Clarify?] →          │   │
         │  │  HumanReview → Decision → Audit │   │
         │  └─────────────────────────────────┘   │
         └───────────┬───────────────────────────┘
                     │
    ┌────────────────┼────────────────────────────┐
    │                │                            │
┌───▼───┐     ┌─────▼──────┐            ┌────────▼────────┐
│MySQL  │     │  Redis     │            │  Pinecone       │
│8.0    │     │  7 (Cache) │            │  (Policy Vecs)  │
│(ORM)  │     │            │            │                 │
└───────┘     └────────────┘            └─────────────────┘
```

---

## 2. Component Architecture

### 2.1 API Layer (`app/api/`)

**Routes:**
| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/api/v1/health/live` | GET | Public | Liveness probe |
| `/api/v1/health/ready` | GET | Public | Readiness probe (DB + Redis) |
| `/api/v1/pa-requests` | POST | Provider+ | Submit new PA case |
| `/api/v1/cases` | GET | Provider+ | List cases (provider sees own only) |
| `/api/v1/cases/{id}` | GET | Provider+ | Get case detail |
| `/api/v1/cases/{id}/documents` | POST | Provider+ | Upload clinical documents |
| `/api/v1/review/{id}/approve` | POST | Reviewer+ | Approve a case |
| `/api/v1/review/{id}/deny` | POST | Reviewer+ | Deny a case |
| `/api/v1/review/{id}/escalate` | POST | Reviewer+ | Escalate to senior |
| `/api/v1/review/{id}/assign` | POST | Admin | Assign reviewer |
| `/api/v1/clarification/{id}/respond` | POST | Provider | Answer clarification |
| `/api/v1/metrics` | GET | Reviewer+ | Business metrics dashboard |

**Middleware Tower (execution order — outermost first):**
1. `TrustedHostMiddleware` — Allowlist domains (production only)
2. `CORSMiddleware` — Cross-origin headers
3. `SecurityHeadersMiddleware` — HSTS, CSP, X-Frame-Options, etc.
4. `RequestTracingMiddleware` — Injects `request_id` + `trace_id` into headers
5. `LangSmithTracingMiddleware` — Propagates `X-LangSmith-Run-ID`
6. `AuditMiddleware` — Binds `AuditContext` (actor, IP, user agent) to contextvars
7. `GuardrailMiddleware` — Scans request body for prompt injection / PII
8. `RequestLoggingMiddleware` — Structured access logs (structlog)

### 2.2 LangGraph Workflow (`app/services/workflow/`)

The AI processing pipeline is implemented as a directed state machine using LangGraph. Each node receives the immutable `WorkflowState` and returns a partial update.

```
SUBMITTED
    │
    ▼
[ingestion_node]        Read documents from DB
    │
    ▼
[ocr_node]              Azure Doc Intelligence → PaddleOCR fallback
    │
    ▼
[extraction_node]       GPT-4o: extract ICD/CPT codes, clinical findings
    │
    ▼
[retrieval_node]        Hybrid search: dense (Pinecone) + sparse (BM25)
                        → RRF fusion → cross-encoder reranking
    │
    ▼
[reasoning_node]        Multi-model reasoning pipeline:
                        complexity → tier (small/medium/large model)
                        → criteria evaluation → confidence scoring
    │
    ├──[confidence < 0.65]──► [clarification_node] → PENDING_CLARIFICATION
    │
    ├──[clarification_count ≥ 3]──► ESCALATED
    │
    └──[confidence ≥ 0.65]──► [human_review_node] → UNDER_REVIEW
                                        │
                              ┌─────────┴────────────┐
                              │                      │
                        [approve]               [deny / pend]
                              │                      │
                        [decision_node]        [decision_node]
                              │                      │
                        [audit_node]──────────────────┘
                              │
                          COMPLETED
```

**State Schema (`WorkflowState`):**  
All fields are append-only. Reducers merge incoming diffs — no field is overwritten destructively. Checkpoint serialization uses Pydantic v2 model dump for JSON-safe persistence.

### 2.3 AI Reasoning (`app/services/reasoning/`)

**Multi-model routing:**
| Complexity Score | Model Tier | Model | Use Case |
|---|---|---|---|
| < 0.35 | small | gpt-4o-mini | Routine cases, high confidence |
| 0.35–0.70 | medium | gpt-4o | Standard complexity |
| > 0.70 | large | gpt-4o (full context) | Complex, multi-criteria |
| EMERGENT priority | large | gpt-4o | Always escalated regardless of score |

**Guardrails pipeline:**
- Pre-LLM: prompt injection detection, jailbreak detection, PII scanning
- Post-LLM: hallucination detection, groundedness check, schema validation, medical safety

### 2.4 Hybrid Retrieval (`app/services/retrieval/`)

```
Query (CPT + ICD + clinical text)
         │
    ┌────┴────┐
    │         │
Dense Search  Sparse Search
(Pinecone     (BM25 / TF-IDF
 embeddings)   keyword match)
    │         │
    └────┬────┘
         │
    RRF Fusion          score = Σ 1/(k + rank_i)  where k=60
         │
  Cross-Encoder
   Re-ranking           bi-encoder recall → cross-encoder precision
         │
  Top-K Policy Chunks   returned to reasoning node
```

**Embedding model:** `text-embedding-3-small` (1536d)  
**Index:** Pinecone serverless, cosine similarity, metadata filters on `service_type` + `insurance_plan`

### 2.5 Caching Strategy (`app/services/caching/`)

| Cache Layer | Key Pattern | TTL | Invalidation |
|---|---|---|---|
| LLM responses | `llm:{prompt_hash}` | 24h | Never (deterministic at T=0) |
| Embeddings | `embed:{text_hash}` | 7 days | On model change |
| Retrieval results | `retrieval:{query_hash}` | 1h | On index update |
| Case detail | `case:{case_id}` | 5min | On status change |
| Workflow result | `workflow:result:{case_id}` | 5min | On decision |
| Session tokens | `session:{token_hash}` | 30min | On logout |

**Redis pattern:** Sliding-window rate limiter uses ZADD/ZREMRANGEBYSCORE/ZCARD pipeline. Fail-open on Redis unavailability.

### 2.6 Async Queue Architecture (`app/queues/`)

```
API Route (publish)
     │
     ▼
RabbitMQ Exchange: pa.direct
     │
     ├──► pa.ingestion.queue    → IngestionWorker  (PDF parse + chunk)
     ├──► pa.ocr.queue          → OCRWorker        (Azure + PaddleOCR)
     ├──► pa.embedding.queue    → EmbeddingWorker  (Pinecone upsert)
     ├──► pa.evaluation.queue   → EvaluationWorker (DeepEval + RAGAS)
     └──► pa.notification.queue → NotificationWorker (email / webhook)

Dead Letter Exchange: pa.dlx
     └──► pa.dlq  (max 3 retries → manual inspection)
```

### 2.7 Security Architecture (`app/core/security/`, `app/guardrails/`)

**Authentication:** JWT (HS256), 30-minute access tokens, 7-day refresh tokens.  
**Authorization:** `require_role("provider" | "reviewer" | "admin")` decorator factory. Providers see only their own cases (enforced at repository layer, not just route layer).

**Guardrail detectors (7):**
1. PII detector — Regex + NER for SSN, DOB, MRN patterns
2. Prompt injection — Instruction override patterns
3. Jailbreak — Known bypass patterns + semantic similarity
4. Output safety — Harmful content classification
5. Policy grounding — Hallucination via contradiction detection
6. Retrieval poisoning — Adversarial chunk detection
7. Schema validator — JSON output structure enforcement

**HIPAA controls:**
- PHI never logged in plaintext (redacted in structured logs)
- All DB access through repositories (no raw SQL in routes)
- Audit trail: every create/read/update triggers `AuditAction` record
- TLS enforced at Nginx (HSTS with 2-year max-age)
- Secrets managed via Kubernetes Secrets / environment variables (never in code)

### 2.8 Observability Stack

**Metrics (Prometheus + Grafana):**
- HTTP: request rate, latency p50/p95/p99, error rate by endpoint
- Business: cases by status, AI recommendation distribution, avg confidence
- AI: LLM latency, token usage, cost per case, guardrail trigger rate
- Infrastructure: DB pool usage, Redis hit rate, RabbitMQ queue depth

**Tracing (LangSmith):**
- Every LLM call traced with inputs, outputs, token counts, and latency
- Workflow runs linked by `run_id` → full node-by-node execution trace
- Evaluation results stored as LangSmith dataset runs

**Logging (structlog):**
- JSON format in production, console in development
- Every request: `request_id`, `trace_id`, method, path, status, duration_ms
- PHI fields explicitly excluded from log payloads

**Alerting (Prometheus Alertmanager):**
- `PAHighErrorRate`: error rate > 1% for 5 minutes
- `PAHighLatency`: p95 latency > 5s for 10 minutes
- `PALowAIConfidence`: avg confidence < 0.70 for 15 minutes
- `PAQueueDepth`: queue depth > 100 for 5 minutes
- `PADatabaseDown`: DB health check failing

---

## 3. Data Model

### Core Entities (MySQL)

```
Patient ──────────┐
                  │
Provider ─────────┤
                  ▼
              PACase ──── Document[] ──── OCRResult
                  │
                  ├──── ExtractedEntity[]
                  │
                  ├──── PolicyMatch[]
                  │
                  ├──── Evaluation[]
                  │
                  ├──── Clarification[] ──── ClarificationAnswer
                  │
                  ├──── ReviewerAction[]
                  │
                  ├──── Decision
                  │
                  └──── AuditLog[]
```

**PACase lifecycle states:**
```
SUBMITTED → PROCESSING → PENDING_CLARIFICATION → (back to PROCESSING)
                      └──────────────────────────► UNDER_REVIEW
                                                        │
                                          ┌─────────────┼─────────────┐
                                          ▼             ▼             ▼
                                       APPROVED       DENIED        PENDED
                                                                      │
                                                              ESCALATED
                                                         (at any point)
```

---

## 4. Deployment Architecture

### Local Development
```
docker compose up
  pa-api (port 8000) + pa-worker
  mysql (port 3306)
  redis (port 6379)
  rabbitmq (port 5672, 15672)
  prometheus (port 9090)
  grafana (port 3001)
```

### Production (Kubernetes)
```
Namespace: pa-platform
  Deployment: pa-api         (2–10 replicas, HPA on CPU/memory)
  Deployment: pa-worker      (2–8 replicas, HPA on CPU)
  Service: pa-api            (ClusterIP)
  Ingress: pa-platform       (nginx-ingress + cert-manager TLS)
  HPA: pa-api-hpa
  HPA: pa-worker-hpa
  PDB: pa-api-pdb            (minAvailable: 1)
  PDB: pa-worker-pdb         (minAvailable: 1)
  ConfigMap: pa-platform-config
  Secret: pa-platform-secrets

External Managed Services (production):
  MySQL 8.0     → AWS RDS Multi-AZ
  Redis 7       → AWS ElastiCache
  RabbitMQ      → Amazon MQ
  Pinecone      → Serverless (us-east-1)
  OpenAI        → API Gateway with org-level rate limiting
```

### CI/CD Pipeline
```
git push → GitHub Actions CI:
  lint (ruff + black + mypy)
  unit-tests (pytest --cov-fail-under=70)
  integration-tests (MySQL + Redis containers)
  security-tests (pytest + bandit SAST)
  workflow-tests (reasoning + retrieval benchmarks)

CI passes → GitHub Actions Deploy:
  build + push (ghcr.io, multi-arch amd64/arm64)
  SBOM + CVE scan (anchore)
  deploy to staging → smoke tests
  manual approval gate
  deploy to production (rolling update, zero-downtime)
  auto-rollback on health check failure
```

---

## 5. Performance Characteristics

| Operation | P50 | P95 | P99 | Notes |
|---|---|---|---|---|
| Health check | 2ms | 5ms | 10ms | DB ping + Redis ping |
| Submit PA case | 80ms | 200ms | 500ms | DB write + queue publish |
| Get case detail | 15ms | 40ms | 100ms | Cache hit: < 5ms |
| AI workflow (full) | 3.5s | 6s | 12s | OCR + extraction + retrieval + LLM |
| OCR (single doc) | 1.2s | 3s | 8s | Azure endpoint; PaddleOCR: 5–15s |
| Entity extraction | 0.8s | 1.5s | 3s | GPT-4o, 4096 token context |
| Policy retrieval | 200ms | 500ms | 1s | Pinecone + BM25 + reranker |
| LLM reasoning | 1.5s | 3s | 8s | GPT-4o, streamed response |

**Throughput targets:**
- API: 500 RPS (single node), 5,000 RPS (10-node HPA ceiling)
- Workers: 300 PA cases/hour per worker pod
- Concurrent reviewers: 50 simultaneous

---

## 6. Key Design Decisions

| Decision | Chosen | Alternative | Rationale |
|---|---|---|---|
| Async web framework | FastAPI | Django, Flask | Native async, OpenAPI docs, Pydantic v2 |
| AI orchestration | LangGraph | Custom FSM, Temporal | State checkpointing, retry semantics, LangSmith tracing |
| Vector DB | Pinecone serverless | pgvector, Weaviate | No infra ops, hybrid search built-in |
| ORM | SQLAlchemy 2.0 async | Tortoise, Beanie | Mature, type-safe, alembic migrations |
| Message queue | RabbitMQ | Celery+Redis, SQS | Per-queue DLQ, priority queues, management UI |
| Caching | Redis | Memcached | Sorted sets for rate limiter, rich data types |
| Serialization | orjson | stdlib json | 3–5× faster, handles datetime natively |
| Container runtime | Gunicorn + uvicorn workers | Pure uvicorn | Gunicorn handles worker management, OS signals |
| Secret management | K8s Secrets + env vars | Vault, AWS SSM | Portable; Sealed Secrets for GitOps |