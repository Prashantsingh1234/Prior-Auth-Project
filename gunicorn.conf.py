# gunicorn.conf.py — Production Gunicorn configuration
# Read by: gunicorn -c gunicorn.conf.py app.main:app
import multiprocessing
import os

# ── Binding ────────────────────────────────────────────────────────────────
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")

# ── Workers ────────────────────────────────────────────────────────────────
# (2 × CPU) + 1  is the standard recommendation for I/O-bound async services
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "uvicorn.workers.UvicornWorker"

# Recycle workers after this many requests to avoid memory leaks
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", 1000))
max_requests_jitter = int(os.getenv("GUNICORN_MAX_REQUESTS_JITTER", 100))

# ── Timeouts ───────────────────────────────────────────────────────────────
timeout = int(os.getenv("GUNICORN_TIMEOUT", 120))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", 30))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", 5))

# ── Logging ────────────────────────────────────────────────────────────────
accesslog = "-"         # stdout — captured by Docker / k8s log driver
errorlog = "-"          # stderr
loglevel = os.getenv("LOG_LEVEL", "info").lower()
access_log_format = (
    '{"time":"%(t)s","remote":"%({X-Forwarded-For}i)s",'
    '"method":"%(m)s","path":"%(U)s","status":%(s)s,'
    '"bytes":%(b)s,"duration_ms":%(D)s}'
)

# ── Process title ──────────────────────────────────────────────────────────
proc_name = "pa-review-api"

# ── Hooks ──────────────────────────────────────────────────────────────────
def on_starting(server):
    server.log.info("PA Review Platform starting — %d workers", workers)

def worker_exit(server, worker):
    server.log.info("Worker %s exiting cleanly", worker.pid)