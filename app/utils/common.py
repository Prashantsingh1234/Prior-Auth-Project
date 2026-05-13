"""
Shared utility functions used across the platform.

Keeps utility functions pure (no side effects), typed, and independently testable.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
import uuid
from datetime import UTC, datetime
from typing import Any


def generate_uuid() -> str:
    """Generate a new UUID4 string."""
    return str(uuid.uuid4())


def utc_now() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(UTC)


def utc_now_iso() -> str:
    """Return the current UTC datetime as an ISO 8601 string."""
    return utc_now().isoformat()


def hash_content(content: str | bytes, algorithm: str = "sha256") -> str:
    """
    Return a hex digest of the given content.

    Used for:
    - Embedding cache keys (hash document text)
    - Duplicate document detection
    - Content-addressed storage

    Args:
        content:   String or bytes to hash
        algorithm: Hash algorithm (default: sha256)

    Returns:
        Hex string digest
    """
    if isinstance(content, str):
        content = content.encode("utf-8")
    h = hashlib.new(algorithm)
    h.update(content)
    return h.hexdigest()


def normalize_text(text: str) -> str:
    """
    Normalize text for consistent processing.

    - Normalize unicode (NFC)
    - Collapse multiple whitespace characters to single space
    - Strip leading/trailing whitespace
    """
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_cpt_codes(text: str) -> list[str]:
    """
    Extract CPT codes from free text using regex.

    CPT codes are 5-digit numeric codes.
    This is a fast regex pass — the LLM extraction layer provides higher accuracy.
    """
    # CPT codes: 5 digits, optionally preceded by whitespace or word boundary
    matches = re.findall(r"\b(\d{5})\b", text)
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_codes: list[str] = []
    for code in matches:
        if code not in seen:
            seen.add(code)
            unique_codes.append(code)
    return unique_codes


def extract_icd_codes(text: str) -> list[str]:
    """
    Extract ICD-10-CM codes from free text using regex.

    ICD-10 format: Letter + 2 digits + optional decimal + up to 4 more chars
    Examples: E11.9, Z87.891, M79.3
    """
    pattern = r"\b([A-Z][0-9]{2}(?:\.[A-Z0-9]{1,4})?)\b"
    matches = re.findall(pattern, text.upper())
    seen: set[str] = set()
    unique_codes: list[str] = []
    for code in matches:
        if code not in seen:
            seen.add(code)
            unique_codes.append(code)
    return unique_codes


def safe_truncate(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to max_length characters, appending suffix if truncated.

    Used when logging or displaying extracted text snippets.
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def flatten_dict(d: dict[str, Any], parent_key: str = "", sep: str = ".") -> dict[str, Any]:
    """
    Flatten a nested dictionary using dot notation.

    Example:
        flatten_dict({"a": {"b": 1}}) → {"a.b": 1}
    """
    items: list[tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def chunk_list(lst: list[Any], chunk_size: int) -> list[list[Any]]:
    """
    Split a list into chunks of at most chunk_size items.

    Used for batch processing (e.g., batch embedding calls).
    """
    return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]


def mask_pii(text: str) -> str:
    """
    Mask common PII patterns in text before logging.

    Masks:
    - Social Security Numbers (XXX-XX-XXXX)
    - Phone numbers
    - Email addresses

    This is a best-effort pass — not a substitute for proper PII classification.
    """
    # SSN: 123-45-6789
    text = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[SSN REDACTED]", text)
    # Phone: various formats
    text = re.sub(
        r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
        "[PHONE REDACTED]",
        text,
    )
    # Email
    text = re.sub(
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}\b",
        "[EMAIL REDACTED]",
        text,
    )
    return text
