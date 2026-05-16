# Production Readiness Checklist
## AI-Assisted Prior Authorization Review Platform

Mark each item [x] before authorizing a production deployment.  
Items marked **(HIPAA)** are compliance-critical and block deployment if incomplete.

---

## 1. Security

### Authentication & Authorization
- [ ] `SECRET_KEY` is ≥ 64 hex characters (not the default placeholder)
- [ ] `SECRET_KEY` stored in Kubernetes Secret / AWS Secrets Manager — **not in code or git**
- [ ] JWT `ACCESS_TOKEN_EXPIRE_MINUTES` = 30 (not extended beyond 60)
- [ ] All API routes protected by `require_role()` — no unintended public endpoints
- [ ] Admin endpoints (`/review/{id}/assign`) verified as admin-only **(HIPAA)**
- [ ] Provider scope isolation verified: providers cannot access other providers' cases **(HIPAA)**
- [ ] RBAC security tests passing: `pytest app/tests/security/test_rbac.py`

### Transport Security
- [ ] TLS 1.2+ enforced on all external endpoints (Nginx + Ingress)
- [ ] HSTS header present: `max-age=63072000; includeSubDomains; preload`
- [ ] No HTTP endpoints reachable externally (redirect to HTTPS)
- [ ] SSL/TLS certificate valid and auto-renewing (cert-manager)
- [ ] `ALLOWED_HOSTS` tightened to production domain only

### Input Validation
- [ ] SQL injection tests passing: `pytest app/tests/security/test_injection.py`
- [ ] XSS payloads rejected or safely stored (never executed)
- [ ] Path traversal in filenames blocked
- [ ] Oversized inputs (>50MB) rejected with 413
- [ ] Prompt injection guardrails enabled and tested

### Secrets
- [ ] No secrets in `.env` committed to version control
- [ ] `.env` in `.gitignore` — verified with `git status`
- [ ] All `REPLACE_WITH_*` placeholders replaced in production secrets
- [ ] Database password unique to this environment (not reused from dev)
- [ ] OpenAI API key has usage limits set in OpenAI console

### Dependency Security
- [ ] `bandit -r app/ -ll --exclude app/tests/` — zero HIGH findings
- [ ] `pip-audit` or `safety check` — no known CVEs in dependencies
- [ ] Docker image scanned with Anchore/Trivy — no CRITICAL vulnerabilities
- [ ] Base image `python:3.11-slim` pinned to digest (not floating tag)

---

## 2. Data & Privacy (HIPAA)

- [ ] PHI (patient names, DOB, MRN, diagnoses) never appears in log output **(HIPAA)**
- [ ] `DB_ECHO=false` in production (would leak SQL with PHI to logs) **(HIPAA)**
- [ ] `DEBUG=false` in production (would expose tracebacks with data) **(HIPAA)**
- [ ] Audit log captures: every case read, every status change, every decision **(HIPAA)**
- [ ] Audit records are immutable (no `UPDATE` or `DELETE` on `audit_log` table) **(HIPAA)**
- [ ] Audit writer tested: `app/audit/` module produces records for all `AuditAction` types
- [ ] Database encrypted at rest (RDS encryption enabled)
- [ ] Database backups encrypted and tested for restore **(HIPAA)**
- [ ] Data retention policy implemented: cases archived after [N] years per BAA
- [ ] Business Associate Agreement (BAA) signed with: OpenAI, AWS, Pinecone, Azure **(HIPAA)**
- [ ] PHI does not flow to LangSmith traces (scrubbed before logging) **(HIPAA)**

---

## 3. Infrastructure

### Database
- [ ] MySQL production is Multi-AZ (RDS)
- [ ] Read replica provisioned for metrics/reporting queries
- [ ] `DB_POOL_SIZE` and `DB_MAX_OVERFLOW` tuned for replica count
- [ ] Slow query log enabled: queries > 2s captured
- [ ] Database connection count within RDS instance limits
- [ ] Latest Alembic migration applied: `alembic current` matches HEAD
- [ ] Migration tested on a production-size data copy (no lock escalation)

### Redis
- [ ] Redis in cluster mode or ElastiCache Multi-AZ
- [ ] `REDIS_PASSWORD` set (AUTH enabled)
- [ ] `maxmemory-policy allkeys-lru` configured (no OOM crashes)
- [ ] Redis memory usage < 80% of allocated
- [ ] Cache hit rate > 60% under normal load

### RabbitMQ
- [ ] Dead letter queue (`pa.dlq`) monitored — alerts if depth > 10
- [ ] Queue persistence enabled (durable=True on all queues)
- [ ] All queues declared idempotent (worker restarts safe)
- [ ] Worker `RABBITMQ_PREFETCH_COUNT` tuned per worker capacity
- [ ] RabbitMQ management UI not exposed on public internet

### Kubernetes
- [ ] PodDisruptionBudgets applied (api + worker): `kubectl get pdb -n pa-platform`
- [ ] HPA configured and tested under synthetic load
- [ ] Node pool has capacity for `maxReplicas` (API=10, Worker=8)
- [ ] `terminationGracePeriodSeconds=60` on API pods (finish in-flight requests)
- [ ] `terminationGracePeriodSeconds=120` on worker pods (finish in-flight tasks)
- [ ] Resource limits set on all containers (prevent noisy neighbor)
- [ ] Container runs as non-root user (uid 1000) — confirmed with `kubectl exec`

---

## 4. Application

### Configuration
- [ ] `ENVIRONMENT=production` set
- [ ] `LOG_FORMAT=json` (required for log aggregators)
- [ ] `LOG_LEVEL=WARNING` or `INFO` (not `DEBUG`)
- [ ] `GUNICORN_WORKERS` = (2 × CPU) + 1 per pod
- [ ] `ALLOWED_HOSTS` contains only production domains
- [ ] `CORS_ORIGINS` contains only production frontend origins
- [ ] `PROMETHEUS_ENABLED=true`

### API
- [ ] OpenAPI docs disabled in production: `docs_url=None` in `create_application()`
- [ ] Health endpoints respond within 500ms under load
- [ ] Rate limiter verified: 100 req/min per IP enforced
- [ ] Request size limits enforced: 55MB max (Nginx + FastAPI)

### AI Services
- [ ] OpenAI API key valid and has sufficient quota for peak load
- [ ] Pinecone index exists and contains policy documents
- [ ] `PINECONE_NAMESPACE=production` (not `staging` or `development`)
- [ ] Azure Document Intelligence endpoint valid and reachable
- [ ] PaddleOCR fallback tested — works when Azure is unavailable
- [ ] LLM temperature = 0.0 (deterministic medical reasoning)
- [ ] Guardrails enabled and tested against injection payloads

### Workers
- [ ] All 5 worker types registered: ingestion, ocr, embedding, evaluation, notification
- [ ] Worker liveness probes configured
- [ ] Worker crash loop handled by `restart: always` / Kubernetes restart policy

---

## 5. Observability

- [ ] Grafana dashboards provisioned and displaying data
- [ ] Prometheus scraping `/metrics` endpoint successfully
- [ ] All 3 alert rules configured: `PADatabaseDown`, `PAHighErrorRate`, `PAHighLatency`
- [ ] Alert routing verified: alerts reach on-call channel (Slack/PagerDuty)
- [ ] Log aggregator receiving JSON logs (CloudWatch / Datadog / Loki)
- [ ] LangSmith tracing active for AI workflow runs
- [ ] `audit_log` table receiving entries for all test operations

---

## 6. Testing

- [ ] `make test` passes with zero failures
- [ ] Test coverage ≥ 70%: `make test-cov`
- [ ] Security tests pass: `make test-security`
- [ ] Load test run against staging: `make load-test TARGET_URL=<staging-url>`
  - [ ] p95 latency < 5 seconds at 50 concurrent users
  - [ ] Error rate < 1% at peak load
  - [ ] No memory leaks observed over 5-minute run
- [ ] Smoke test against production URL: `make smoke-test TARGET_URL=<prod-url>`

---

## 7. Operations

### Runbooks
- [ ] Rollback procedure documented and tested (`make k8s-rollback`)
- [ ] Database restore procedure documented and tested
- [ ] Secret rotation runbook documented
- [ ] On-call escalation path defined (L1 → L2 → Engineering)

### Backup & Recovery
- [ ] Automated DB backup schedule configured (daily minimum)
- [ ] Backup restore tested in staging environment
- [ ] RTO (Recovery Time Objective): _____ minutes
- [ ] RPO (Recovery Point Objective): _____ minutes

### Capacity
- [ ] Peak load estimate documented: _____ PA cases/hour
- [ ] Load tested to 2× peak load without degradation
- [ ] Cost estimate at peak load: $_____/month

### Access Control
- [ ] Production k8s access restricted to named engineers
- [ ] Production database credentials not shared with staging
- [ ] No developer SSH access to production pods (use `kubectl exec` with audit)
- [ ] Break-glass access procedure documented for emergencies

---

## 8. Demo Readiness

- [ ] `python scripts/demo_workflow.py` runs successfully against staging
- [ ] Demo produces realistic AI recommendation with criterion breakdown
- [ ] Grafana dashboard shows demo case in real-time
- [ ] Audit trail visible for demo case
- [ ] Reviewer can approve/deny demo case through the web UI
- [ ] All 7 middleware layers verified in response headers

---

## Sign-Off

| Role | Name | Date | Signature |
|---|---|---|---|
| Engineering Lead | | | |
| Security Review | | | |
| HIPAA Compliance | | | |
| Product Owner | | | |
| Operations | | | |

**Deployment authorized:** [ ] YES  [ ] NO

**Notes:**