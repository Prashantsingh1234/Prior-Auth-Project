# Scalability Guide
## AI-Assisted Prior Authorization Review Platform

---

## Current Capacity Baseline

| Metric | Single Node | 4-Node Cluster | 10-Node Cluster |
|---|---|---|---|
| API RPS (sustained) | 500 | 2,000 | 5,000 |
| PA cases/hour | 300 | 1,200 | 3,000 |
| Concurrent reviewers | 50 | 200 | 500 |
| LLM calls/minute | 60 | 240 | 600 |
| OCR docs/minute | 20 | 80 | 200 |
| Redis hit rate (warm) | 89% | 89% | 89% |
| DB connections | 10 | 40 | 100 |

Bottlenecks in order: **LLM API rate limits → OCR throughput → DB connections → Redis memory**

---

## 1. Horizontal Scaling

### API Layer

Already configured — just adjust HPA thresholds:

```yaml
# k8s/06-hpa.yaml — current setting
minReplicas: 2
maxReplicas: 10
targetCPUUtilization: 70%
```

For burst traffic (open enrollment, end-of-month surges):
```bash
# Pre-scale before known peak
kubectl scale deployment/pa-api --replicas=8 --namespace=pa-platform
```

### Worker Layer

Worker throughput scales linearly. Add more pods:
```bash
kubectl scale deployment/pa-worker --replicas=6 --namespace=pa-platform
```

**Queue-based autoscaling (KEDA):**  
For reactive scaling based on RabbitMQ queue depth:
```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: pa-worker-scaler
  namespace: pa-platform
spec:
  scaleTargetRef:
    name: pa-worker
  minReplicaCount: 2
  maxReplicaCount: 20
  triggers:
    - type: rabbitmq
      metadata:
        host: amqp://pauser:pass@rabbitmq:5672/
        queueName: pa.ingestion.queue
        queueLength: "10"        # 1 worker per 10 queued items
```

---

## 2. Database Scaling

### Connection Pooling

Current: 10 connections per API pod. At 10 pods = 100 connections.

RDS db.r6g.large supports 1,000 connections. Well within limit.

For 50+ pods, use **PgBouncer / ProxySQL connection pooler**:
```yaml
# Add to docker-compose or k8s as a sidecar
image: proxysql/proxysql:latest
# Routes all API connections through pooler → DB sees far fewer connections
```

### Read Replicas

Add a read replica for metrics queries and case list endpoints:
```python
# app/core/config/settings.py — add:
database_url_read: str = ""  # RDS read replica endpoint

# app/db/session/database.py — add:
read_engine = create_async_engine(settings.database_url_read, ...)
```

Route these endpoints to the read replica:
- `GET /api/v1/cases` (list)
- `GET /api/v1/metrics`
- `GET /api/v1/cases/{id}` (after adding cache layer)

**Expected impact:** Reduces primary DB load by ~60% at scale.

### Partitioning

At 1M+ cases, partition `pa_cases` by submission date:
```sql
ALTER TABLE pa_cases PARTITION BY RANGE (YEAR(submitted_at)) (
  PARTITION p2024 VALUES LESS THAN (2025),
  PARTITION p2025 VALUES LESS THAN (2026),
  PARTITION p_future VALUES LESS THAN MAXVALUE
);
```

---

## 3. Caching Improvements

### Current Cache Architecture

All caching is already implemented in `app/services/caching/`. Key TTLs:
- LLM responses: 24h (deterministic at T=0.0 — effectively infinite)
- Embeddings: 7 days
- Policy retrieval: 1h
- Case detail: 5min

### Improvements for Scale

**Cache warming on startup:**
```python
# app/services/caching/manager.py — add:
async def warm_cache(self) -> None:
    """Pre-load high-frequency policy embeddings into Redis on startup."""
    top_policies = await self._get_top_n_policies(n=100)
    for policy in top_policies:
        await self.embedding_cache.set(policy.id, policy.embedding)
```

**Cache stampede prevention (already using jitter — verify):**
```python
import random
ttl = base_ttl + random.randint(-60, 60)  # ±1 minute jitter
await redis.setex(key, ttl, value)
```

**Multi-tier caching for LLM responses:**
```
Request → L1 (in-process dict, 100 entries) → L2 (Redis, 24h) → LLM API
```

**Redis Cluster for > 100GB cache:**
```yaml
# Replace single Redis with Redis Cluster
# AWS ElastiCache: enable cluster mode
# Update REDIS_URL to cluster endpoint
REDIS_URL=rediss://cluster-endpoint:6379/0
```

---

## 4. LLM Throughput Scaling

### Current Limit

OpenAI GPT-4o: 10,000 TPM (tokens per minute) on Tier 1.  
~8 PA cases/minute at 1,200 tokens/case.

### Scaling Options (in order of cost)

**Option A: Upgrade OpenAI tier** (simplest)
- Tier 4 (>$250/month): 800,000 TPM → 650 cases/minute
- Cost: ~$0.003/case → $1.80/hour at peak

**Option B: Request batching**
```python
# Process multiple cases in one LLM call using batch prompt
# app/services/reasoning/orchestrator.py
async def batch_reason(self, cases: list[dict]) -> list[ReasoningResult]:
    batch_prompt = self._build_batch_prompt(cases[:5])  # max 5 per call
    response = await self.client.chat.completions.create(...)
    return self._parse_batch_response(response)
```

**Option C: Model cascade** (already implemented in `ModelRouter`)
- Route simple/high-confidence cases to `gpt-4o-mini` (10× cheaper, 5× faster)
- Reserve `gpt-4o` for complex or low-confidence cases
- Expected: 70% of cases served by mini at 30% of the cost

**Option D: Self-hosted LLM (advanced)**
```python
# app/services/reasoning/orchestrator.py — add tier:
"local": {
    "model": "mistral-7b-medical",
    "base_url": "http://ollama:11434/v1",  # internal LLM service
    "max_tokens": 2048,
}
```
- Suitable for routine cases only
- HIPAA: self-hosted means PHI never leaves your infrastructure

**Option E: Anthropic Claude fallback**
```python
# Already uses OpenAI client — add Anthropic as fallback
from anthropic import AsyncAnthropic
anthropic_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
```

---

## 5. Vector Search Scaling

### Current: Pinecone Serverless

Pinecone serverless auto-scales to billions of vectors. No action needed until ~10M policy chunks.

### Optimization at Scale

**Namespace-based multi-tenancy** (already used):
```python
# Each insurance plan gets its own namespace
namespace = f"plan-{insurance_plan_id}"
results = index.query(vector=..., namespace=namespace, top_k=10)
```
Reduces search space by 10-100× per query.

**Metadata pre-filtering:**
```python
# Filter before vector search (free, reduces compute)
results = index.query(
    vector=embedding,
    filter={
        "service_type": {"$eq": case.service_type},
        "effective_date": {"$lte": date.today().isoformat()},
    },
    top_k=10,
)
```

**Embedding caching** (already implemented — verify hit rate):
```bash
redis-cli eval "return redis.call('info', 'stats')" 0 | grep keyspace_hits
```

---

## 6. Async Worker Scaling

### Current Worker Types & Throughput

| Worker | Current Throughput | Bottleneck |
|---|---|---|
| IngestionWorker | 1,000 docs/hr/pod | PDF parse (CPU) |
| OCRWorker | 120 docs/hr/pod | Azure API calls |
| EmbeddingWorker | 600 embeddings/hr/pod | Pinecone write |
| EvaluationWorker | 200 evals/hr/pod | DeepEval LLM calls |
| NotificationWorker | 10,000 msgs/hr/pod | Network I/O |

### Scaling recommendations

**OCR**: Scale horizontally — Azure Doc Intelligence supports 25 concurrent requests.
```bash
kubectl scale deployment/pa-worker --replicas=10
# Each pod handles a separate Azure quota slice
```

**Ingestion**: Add CPU-optimized nodes for PDF parsing (CPU-bound, not I/O-bound).
```yaml
# nodeSelector:
#   node.kubernetes.io/instance-type: c5.2xlarge  # compute-optimized
```

**Priority queue routing**: Route EMERGENT cases to a dedicated high-priority queue:
```python
# app/queues/publisher.py
routing_key = "pa.ingestion.priority" if case.priority == "EMERGENT" else "pa.ingestion.queue"
```

---

## 7. Multi-Region Deployment

For national healthcare networks (> 1M cases/year):

```
Region: us-east-1 (primary)         Region: us-west-2 (secondary)
  ├── API cluster                     ├── API cluster
  ├── MySQL primary                   ├── MySQL replica (read-only)
  ├── Redis primary                   ├── Redis replica
  ├── RabbitMQ cluster                ├── RabbitMQ cluster
  └── Pinecone (shared)               └── Pinecone (shared)
           │                                    │
           └──────── Global Load Balancer ───────┘
                    (Route53 latency-based)
```

**Data sovereignty note:** Ensure patient PHI stays within the required geographic region per state/federal regulations. Pinecone namespace + index region selection may need to match RDS region.

---

## 8. Cost Optimization

### At 10,000 cases/day

| Component | Current Cost | Optimized Cost |
|---|---|---|
| OpenAI (GPT-4o) | ~$30/day | ~$10/day (70% routed to mini) |
| Pinecone | $0.09/day | $0.09/day (serverless) |
| Azure OCR | ~$5/day | ~$5/day |
| RDS db.r6g.large | ~$14/day | ~$14/day |
| ElastiCache r6g.large | ~$8/day | ~$4/day (reserved) |
| EKS (4 nodes) | ~$20/day | ~$10/day (spot instances) |
| **Total** | **~$77/day** | **~$43/day** |

### Spot instance strategy

Use spot instances for worker pods (they are stateless and restart-safe):
```yaml
# k8s/05-worker-deployment.yaml — add:
tolerations:
  - key: "spot"
    operator: "Equal"
    value: "true"
    effect: "NoSchedule"
nodeSelector:
  node.kubernetes.io/capacity-type: spot
```

Estimated savings: 60-70% on worker compute costs.