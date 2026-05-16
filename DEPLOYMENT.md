# Deployment Guide
## AI-Assisted Prior Authorization Review Platform

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Docker | 24+ | https://docs.docker.com/get-docker/ |
| docker compose | v2.20+ | bundled with Docker Desktop |
| kubectl | 1.28+ | https://kubernetes.io/docs/tasks/tools/ |
| Python | 3.11+ | https://python.org |
| make | any | `brew install make` / `apt install make` |

---

## Local Development — Quick Start

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd pa-review-platform

# 2. Copy environment template
make env-setup          # creates .env from .env.example

# 3. Edit required secrets in .env
#    At minimum set:
#      SECRET_KEY      (openssl rand -hex 32)
#      OPENAI_API_KEY
#      PINECONE_API_KEY
#      AZURE_DOCUMENT_INTELLIGENCE_KEY (optional — falls back to PaddleOCR)

# 4. Start the full stack
make dev

# API:        http://localhost:8000
# Docs:       http://localhost:8000/docs
# Grafana:    http://localhost:3001  (admin / adminpassword)
# Prometheus: http://localhost:9090
# RabbitMQ:   http://localhost:15672  (pauser / papassword)
```

### First-run database setup

```bash
# Migrations run automatically via docker/entrypoint.sh
# To run manually:
make migrate

# To check current revision:
make migrate-status

# To create a new migration after model changes:
make new-migration NAME=add_something_useful
```

### Running tests

```bash
make test              # full suite
make test-unit         # unit tests only (fastest)
make test-security     # security + bandit SAST
make test-cov          # with HTML coverage report → htmlcov/index.html
```

---

## Staging Deployment

### Required secrets (GitHub Actions / CI environment)

Set these in **GitHub → Settings → Secrets and variables → Actions**:

| Secret | Description |
|---|---|
| `STAGING_KUBECONFIG` | base64-encoded kubeconfig for staging cluster |
| `STAGING_REVIEWER_TOKEN` | JWT reviewer token for smoke tests |
| `GHCR_TOKEN` | GitHub Container Registry push token |

Set these as **variables** (not secrets):

| Variable | Example |
|---|---|
| `STAGING_URL` | `https://staging.pa-platform.example.com` |

### Environment configuration

```bash
# Copy staging template, fill in all REPLACE_WITH_* values
cp .env.staging .env.staging.local
# Edit .env.staging.local with real values

# Create k8s secret from env file
kubectl create secret generic pa-platform-secrets \
  --from-env-file=.env.staging.local \
  --namespace=pa-platform-staging \
  --dry-run=client -o yaml | kubectl apply -f -
```

### Deploy to staging

```bash
# Via GitHub Actions (automatic on push to develop)
git push origin develop

# Or manually
make k8s-staging
```

---

## Production Deployment

### Infrastructure requirements

| Service | Recommended | Minimum |
|---|---|---|
| API pods | 4 × (2 CPU, 1GB RAM) | 2 × (0.5 CPU, 512MB RAM) |
| Worker pods | 4 × (1 CPU, 512MB RAM) | 2 × (0.25 CPU, 256MB RAM) |
| MySQL | RDS db.r6g.large Multi-AZ | db.t3.medium |
| Redis | ElastiCache r6g.large | cache.t3.micro |
| RabbitMQ | Amazon MQ mq.m5.large | self-hosted single-node |

### Pre-deployment checklist

```bash
# 1. Verify all secrets are set
make secrets-check

# 2. Generate fresh SECRET_KEY (rotate every 90 days)
make generate-secret-key

# 3. Verify DB migrations are up to date
make migrate-status

# 4. Run full test suite
make test

# 5. Build production image
make build TAG=v1.2.3

# 6. Push to registry
make push TAG=v1.2.3 REGISTRY=ghcr.io/your-org
```

### Kubernetes deployment

```bash
# Apply all manifests
kubectl apply -k k8s/

# Set specific image version
cd k8s && kustomize edit set image \
  pa-review-platform=ghcr.io/your-org/pa-review-platform:v1.2.3

# Watch rollout
make k8s-status
kubectl rollout status deployment/pa-api --namespace=pa-platform

# Verify health
make smoke-test TARGET_URL=https://pa-platform.example.com
```

### Zero-downtime deploy sequence

The deployment manifests are pre-configured for zero-downtime updates:

1. New pods start (`maxSurge: 1`)  
2. Init container runs Alembic migrations  
3. Startup probe waits up to 150 seconds  
4. Readiness probe passes → pod added to service  
5. One old pod terminates (`maxUnavailable: 0`)  
6. Repeat until all old pods replaced  
7. Graceful shutdown: 60-second `terminationGracePeriodSeconds`

### Rollback

```bash
# Immediate rollback (Kubernetes tracks last 10 revisions)
make k8s-rollback

# Rollback to specific revision
kubectl rollout undo deployment/pa-api \
  --to-revision=3 \
  --namespace=pa-platform

# Verify rollback completed
kubectl rollout status deployment/pa-api --namespace=pa-platform
```

---

## Secrets Management

### Kubernetes Secrets (recommended for k8s deployments)

```bash
# Create from env file
kubectl create secret generic pa-platform-secrets \
  --from-env-file=.env.production \
  --namespace=pa-platform

# Or use Sealed Secrets (GitOps-safe)
# Install: https://github.com/bitnami-labs/sealed-secrets
kubeseal --format yaml < k8s/02-secret.yaml > k8s/02-sealed-secret.yaml
git add k8s/02-sealed-secret.yaml   # safe to commit
```

### AWS Secrets Manager (alternative)

```bash
# Store secrets
aws secretsmanager create-secret \
  --name pa-platform/production \
  --secret-string file://.env.production

# Use External Secrets Operator to sync to k8s:
# https://external-secrets.io/
```

### Secret rotation schedule

| Secret | Rotation | Method |
|---|---|---|
| `SECRET_KEY` | Every 90 days | `openssl rand -hex 32`, redeploy |
| `DB_PASSWORD` | Every 90 days | RDS rotation + redeploy |
| `REDIS_PASSWORD` | Every 90 days | ElastiCache rotation |
| `OPENAI_API_KEY` | On suspicion | OpenAI console, immediate |
| JWT tokens | Per session | Self-expiring (30min) |
| Service accounts | Annual | Cloud IAM rotation |

---

## Monitoring & Observability

### Grafana dashboards

Access: `http://localhost:3001` (dev) or configure Ingress for production.

Pre-provisioned dashboards:
- **PA Overview** — case queue, throughput, decisions, SLA compliance
- **LLM Performance** — model latency, token usage, cost per case, confidence distribution
- **Security** — auth failures, guardrail triggers, rate limit hits

### Prometheus alerts

Critical alerts (PagerDuty-ready):
```yaml
- PADatabaseDown        # DB health check failing for > 1 minute
- PAHighErrorRate       # 5xx rate > 1% for 5 minutes
- PAQueueBacklog        # Queue depth > 500 for 10 minutes
```

Warning alerts:
```yaml
- PAHighLatency         # p95 > 5s for 10 minutes
- PALowAIConfidence     # avg confidence < 0.70 for 15 minutes
- PAWorkerLag           # Worker processing time > 2× baseline
```

### LangSmith tracing

Enable in `.env`:
```bash
LANGCHAIN_TRACING_V2=true
LANGSMITH_API_KEY=ls-...
LANGSMITH_PROJECT=pa-review-platform-production
```

Every AI workflow run is linked to a LangSmith trace showing:
- Node-by-node execution timeline
- LLM inputs and outputs
- Token counts and cost per node
- Evaluation scores

---

## Health Check Endpoints

| Endpoint | Type | Expected |
|---|---|---|
| `GET /api/v1/health/live` | Liveness | 200 `{"status": "ok"}` |
| `GET /api/v1/health/ready` | Readiness | 200 with component breakdown |

Readiness checks: database connectivity, Redis ping, optional Pinecone verify.

---

## Running the Demo

```bash
# Quick demo against local stack
python scripts/demo_workflow.py

# Against staging with custom token
python scripts/demo_workflow.py \
  --base-url https://staging.pa-platform.example.com \
  --token eyJhbGc... \
  --decision approve

# Evaluator demo (shows deny flow)
python scripts/demo_workflow.py --decision deny
```

Requirements: `pip install httpx rich`

---

## Troubleshooting

### "Connection refused" on startup

```bash
docker compose ps          # check all containers running
docker compose logs mysql  # check DB init
make migrate               # run migrations manually
```

### "JWT validation failed"

```bash
# Verify SECRET_KEY matches between API instances
kubectl get secret pa-platform-secrets -o jsonpath='{.data.SECRET_KEY}' | base64 -d
```

### High LLM latency

```bash
# Check OpenAI API status: https://status.openai.com
# Enable LLM response caching (already on by default — check Redis)
redis-cli keys "llm:*" | wc -l
```

### Workers not processing

```bash
# Check RabbitMQ queues
docker compose exec rabbitmq rabbitmqctl list_queues name messages consumers
# Restart workers
docker compose restart pa-worker
```