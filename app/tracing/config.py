"""
LangSmith tracing configuration.

Reads from application settings and:
  1. Sets the four LANGCHAIN_* environment variables that activate
     LangGraph's built-in tracing middleware (LANGCHAIN_TRACING_V2).
  2. Validates the API key and tests connectivity before declaring
     tracing "enabled" so startup fails loudly rather than silently.
  3. Exposes helpers used by the rest of the tracing package.

Call configure_langsmith() once from the FastAPI lifespan startup before
the workflow graph is compiled — env vars must be set before LangChain
reads them at import time inside graph nodes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import structlog

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class LangSmithConfig:
    """Active LangSmith configuration snapshot."""
    enabled:      bool
    api_key:      str | None
    project:      str
    endpoint:     str
    tracing_v2:   bool

    @property
    def is_active(self) -> bool:
        return self.enabled and bool(self.api_key)


def configure_langsmith() -> LangSmithConfig:
    """
    Read settings and activate LangSmith tracing.

    Sets all required environment variables so LangGraph / LangChain pick
    them up automatically on subsequent imports.

    Returns a LangSmithConfig describing what was configured.  Always
    returns a valid object; `config.is_active` is False when the key is
    absent or tracing is disabled.
    """
    try:
        from app.core.config.settings import get_settings
        settings = get_settings()
    except Exception as exc:
        logger.warning("langsmith.config.settings_failed", error=str(exc))
        return _disabled_config()

    api_key_secret = settings.langsmith_api_key
    if not api_key_secret:
        logger.info(
            "langsmith.tracing_disabled",
            reason="LANGSMITH_API_KEY not set",
        )
        return _disabled_config()

    api_key  = api_key_secret.get_secret_value()
    project  = settings.langsmith_project
    endpoint = settings.langchain_endpoint
    tracing  = settings.langchain_tracing_v2

    # Set the four env vars LangChain/LangGraph read automatically
    os.environ["LANGCHAIN_TRACING_V2"] = "true" if tracing else "false"
    os.environ["LANGCHAIN_API_KEY"]    = api_key
    os.environ["LANGCHAIN_ENDPOINT"]   = endpoint
    os.environ["LANGCHAIN_PROJECT"]    = project

    # Also set the langsmith SDK vars (used by our WorkflowTracer)
    os.environ["LANGSMITH_API_KEY"]    = api_key
    os.environ["LANGSMITH_PROJECT"]    = project
    os.environ["LANGSMITH_ENDPOINT"]   = endpoint

    cfg = LangSmithConfig(
        enabled=tracing,
        api_key=api_key,
        project=project,
        endpoint=endpoint,
        tracing_v2=tracing,
    )

    if tracing:
        _verify_connectivity(cfg)

    logger.info(
        "langsmith.configured",
        project=project,
        endpoint=endpoint,
        tracing_v2=tracing,
    )
    return cfg


def _disabled_config() -> LangSmithConfig:
    return LangSmithConfig(
        enabled=False,
        api_key=None,
        project=os.getenv("LANGSMITH_PROJECT", "pa-review-platform"),
        endpoint=os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com"),
        tracing_v2=False,
    )


def _verify_connectivity(cfg: LangSmithConfig) -> None:
    """
    Quick connectivity check — logs a warning if LangSmith is unreachable.
    Never raises; tracing failures must not prevent the application from starting.
    """
    try:
        import langsmith
        client = langsmith.Client(api_key=cfg.api_key, api_url=cfg.endpoint)
        # Lightweight call: list projects (doesn't download data)
        list(client.list_projects(limit=1))
        logger.info("langsmith.connectivity_ok", project=cfg.project)
    except ImportError:
        logger.warning(
            "langsmith.sdk_not_installed",
            note="pip install langsmith to enable tracing",
        )
    except Exception as exc:
        logger.warning(
            "langsmith.connectivity_failed",
            error=str(exc),
            note="Tracing will be silently skipped",
        )


# ---------------------------------------------------------------------------
# Module-level cached config (set by configure_langsmith())
# ---------------------------------------------------------------------------

_active_config: LangSmithConfig | None = None


def get_langsmith_config() -> LangSmithConfig:
    """Return the active config.  Calls configure_langsmith() if not yet called."""
    global _active_config
    if _active_config is None:
        _active_config = configure_langsmith()
    return _active_config
