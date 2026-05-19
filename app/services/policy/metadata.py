"""Policy chunk metadata extraction (CPT/ICD and basic fields)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from typing import Any


_CPT_RE = re.compile(r"\b\d{5}\b")
_HCPCS_RE = re.compile(r"\b[A-Z]\d{4}\b")
_ICD10_RE = re.compile(r"\b[A-TV-Z][0-9][0-9A-Z](?:\.[0-9A-Z]{1,4})?\b")


def _dedupe_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for i in items:
        if i in seen:
            continue
        seen.add(i)
        out.append(i)
    return out


def extract_codes(text: str) -> tuple[list[str], list[str]]:
    cpt = _dedupe_preserve(_CPT_RE.findall(text) + _HCPCS_RE.findall(text))
    icd = _dedupe_preserve(_ICD10_RE.findall(text))
    return (cpt, icd)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


@dataclass(frozen=True)
class PolicyChunkMetadata:
    policy_id: str
    policy_name: str
    policy_version: str
    policy_type: str | None
    effective_date: date | None
    namespace: str
    chunk_index: int
    chunk_id: str
    cpt_codes: list[str]
    icd_codes: list[str]

    def to_pinecone_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "policy_id": self.policy_id,
            "policy_name": self.policy_name,
            "version": self.policy_version,
            "namespace": self.namespace,
            "chunk_index": self.chunk_index,
            "chunk_id": self.chunk_id,
            "cpt_codes": self.cpt_codes,
            "icd_codes": self.icd_codes,
        }
        if self.policy_type:
            d["policy_type"] = self.policy_type
        if self.effective_date:
            d["effective_date"] = self.effective_date.isoformat()
        return d

