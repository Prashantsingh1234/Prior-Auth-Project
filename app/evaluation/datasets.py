"""
Benchmark dataset management.

Responsibilities:
  - Load / save BenchmarkDatasets from disk (JSON) and from LangSmith
  - Provide pre-built PA-domain seed datasets for each EvalDomain
  - Push datasets to LangSmith for versioned storage and experiment tracking
  - Support synthetic case generation (stub — real generation uses the LLM pipeline)

File layout on disk:
  {EVAL_DATASET_DIR}/{domain}/{name}_{version}.json
  Default EVAL_DATASET_DIR = data/eval_datasets/
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from app.evaluation.models import (
    BenchmarkCase,
    BenchmarkDataset,
    CaseComplexity,
    EvalDomain,
)

logger = structlog.get_logger(__name__)

_DEFAULT_DATASET_DIR = Path("data") / "eval_datasets"


# ---------------------------------------------------------------------------
# Seed datasets (hardcoded minimal examples for cold-start / CI)
# ---------------------------------------------------------------------------

def _seed_extraction_cases() -> list[BenchmarkCase]:
    return [
        BenchmarkCase(
            domain=EvalDomain.EXTRACTION,
            complexity=CaseComplexity.MEDIUM,
            input_text=(
                "Patient Jane Doe, 54F, diagnosed with Type 2 Diabetes Mellitus (ICD-10: E11.9). "
                "HbA1c 9.2% (2024-11-15). Requesting Ozempic 1mg weekly. "
                "Current meds: Metformin 1000mg BID, Glipizide 10mg QD. "
                "Prescriber: Dr. Alice Chen, NPI 1234567890."
            ),
            context_docs=[],
            expected_entities={
                "diagnoses":   ["Type 2 Diabetes Mellitus"],
                "icd_codes":   ["E11.9"],
                "medications": ["Ozempic 1mg weekly", "Metformin 1000mg BID", "Glipizide 10mg QD"],
                "hba1c_readings": [{"value": 9.2, "unit": "%", "date": "2024-11-15"}],
            },
            source="manual",
            tags=["diabetes", "extraction", "seed"],
        ),
        BenchmarkCase(
            domain=EvalDomain.EXTRACTION,
            complexity=CaseComplexity.HIGH,
            input_text=(
                "52-year-old male with CKD Stage 3 (ICD-10: N18.3), hypertension (I10), "
                "and recent MI (I21.9, 2024-09-01). eGFR: 38 mL/min/1.73m². "
                "Creatinine: 2.1 mg/dL. Requesting Jardiance 10mg QD. "
                "Previous therapy: Lisinopril 20mg, Atorvastatin 40mg."
            ),
            context_docs=[],
            expected_entities={
                "diagnoses": ["CKD Stage 3", "Hypertension", "MI"],
                "icd_codes": ["N18.3", "I10", "I21.9"],
                "medications": ["Jardiance 10mg QD", "Lisinopril 20mg", "Atorvastatin 40mg"],
                "lab_values": [
                    {"name": "eGFR", "value": 38, "unit": "mL/min/1.73m²"},
                    {"name": "Creatinine", "value": 2.1, "unit": "mg/dL"},
                ],
            },
            source="manual",
            tags=["ckd", "cardiac", "extraction", "seed"],
        ),
    ]


def _seed_retrieval_cases() -> list[BenchmarkCase]:
    return [
        BenchmarkCase(
            domain=EvalDomain.RETRIEVAL,
            complexity=CaseComplexity.MEDIUM,
            input_text="Prior authorization for GLP-1 receptor agonist for Type 2 Diabetes",
            query="GLP-1 agonist coverage criteria diabetes",
            context_docs=[
                "Policy GLP-001: GLP-1 receptor agonists are covered for Type 2 Diabetes "
                "when HbA1c ≥ 8% and at least two prior oral agents have been trialed.",
                "Policy CARD-012: Cardiovascular risk reduction indication requires documented "
                "ASCVD or high-risk features.",
            ],
            ground_truth_policies=["Policy GLP-001"],
            ground_truth_answer=(
                "GLP-1 agonists require HbA1c ≥ 8% and failure of two prior oral agents."
            ),
            source="manual",
            tags=["glp1", "retrieval", "seed"],
        ),
    ]


def _seed_reasoning_cases() -> list[BenchmarkCase]:
    return [
        BenchmarkCase(
            domain=EvalDomain.REASONING,
            complexity=CaseComplexity.HIGH,
            input_text=(
                "Patient with T2DM, HbA1c 9.2%, failed Metformin + Glipizide. "
                "Requesting Ozempic. Policy requires HbA1c ≥ 8% and ≥2 prior agents."
            ),
            context_docs=[
                "Policy GLP-001: GLP-1 receptor agonists covered for T2DM when HbA1c ≥ 8% "
                "AND at least two prior oral antidiabetic agents trialed and failed."
            ],
            expected_verdict="APPROVE",
            ground_truth_answer=(
                "All criteria met: HbA1c 9.2% ≥ 8%, Metformin and Glipizide documented."
            ),
            source="manual",
            tags=["diabetes", "reasoning", "approve", "seed"],
        ),
        BenchmarkCase(
            domain=EvalDomain.REASONING,
            complexity=CaseComplexity.MEDIUM,
            input_text=(
                "Patient requesting Ozempic. HbA1c 7.1%. No prior oral agents documented."
            ),
            context_docs=[
                "Policy GLP-001: GLP-1 receptor agonists covered for T2DM when HbA1c ≥ 8% "
                "AND at least two prior oral antidiabetic agents trialed and failed."
            ],
            expected_verdict="DENY",
            ground_truth_answer=(
                "Criteria not met: HbA1c 7.1% < 8% threshold; no prior agent trials documented."
            ),
            source="manual",
            tags=["diabetes", "reasoning", "deny", "seed"],
        ),
    ]


_SEED_FACTORY: dict[EvalDomain, list[BenchmarkCase]] = {
    EvalDomain.EXTRACTION: _seed_extraction_cases(),
    EvalDomain.RETRIEVAL:  _seed_retrieval_cases(),
    EvalDomain.REASONING:  _seed_reasoning_cases(),
}


# ---------------------------------------------------------------------------
# Dataset manager
# ---------------------------------------------------------------------------

class BenchmarkDatasetManager:
    """
    Load, save, and publish benchmark datasets.

    Datasets are stored as JSON files on disk and optionally mirrored
    to LangSmith for experiment tracking.
    """

    def __init__(
        self,
        dataset_dir: Path | None = None,
        langsmith_client=None,
    ) -> None:
        self._dir = dataset_dir or _DEFAULT_DATASET_DIR
        self._langsmith = langsmith_client   # LangSmithClient | None

    # ------------------------------------------------------------------
    # Seed / default
    # ------------------------------------------------------------------

    def get_seed_dataset(self, domain: EvalDomain) -> BenchmarkDataset:
        """Return the built-in seed dataset for a domain."""
        cases = _SEED_FACTORY.get(domain, [])
        return BenchmarkDataset(
            name=f"seed_{domain.value}",
            description=f"Built-in seed cases for {domain.value} evaluation",
            version="1.0.0",
            domain=domain,
            cases=cases,
        )

    # ------------------------------------------------------------------
    # Disk I/O
    # ------------------------------------------------------------------

    def save(self, dataset: BenchmarkDataset) -> Path:
        """Serialise dataset to JSON on disk.  Returns the file path."""
        domain_dir = self._dir / dataset.domain.value
        domain_dir.mkdir(parents=True, exist_ok=True)
        path = domain_dir / f"{dataset.name}_{dataset.version}.json"
        with path.open("w", encoding="utf-8") as fh:
            json.dump(dataset.model_dump(mode="json"), fh, indent=2, default=str)
        logger.info("dataset.saved", path=str(path), cases=len(dataset.cases))
        return path

    def load(self, domain: EvalDomain, name: str, version: str = "1.0.0") -> BenchmarkDataset:
        """Load a dataset from disk."""
        path = self._dir / domain.value / f"{name}_{version}.json"
        if not path.exists():
            raise FileNotFoundError(f"Dataset not found: {path}")
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        dataset = BenchmarkDataset(**data)
        logger.info("dataset.loaded", name=name, cases=len(dataset.cases))
        return dataset

    def load_or_seed(self, domain: EvalDomain, name: str = "", version: str = "1.0.0") -> BenchmarkDataset:
        """Load from disk if present, otherwise return the seed dataset."""
        try:
            return self.load(domain, name or f"seed_{domain.value}", version)
        except FileNotFoundError:
            return self.get_seed_dataset(domain)

    # ------------------------------------------------------------------
    # LangSmith sync
    # ------------------------------------------------------------------

    async def push_to_langsmith(self, dataset: BenchmarkDataset) -> str | None:
        """
        Push dataset to LangSmith and return the LangSmith dataset ID.
        No-ops gracefully when LangSmith client is not configured.
        """
        if self._langsmith is None:
            logger.debug("dataset.langsmith_push_skipped", reason="no client")
            return None

        try:
            ls_id = await self._langsmith.create_or_update_dataset(dataset)
            dataset.langsmith_dataset_id = ls_id
            logger.info(
                "dataset.pushed_to_langsmith",
                dataset=dataset.name,
                langsmith_id=ls_id,
            )
            return ls_id
        except Exception as exc:
            logger.error("dataset.langsmith_push_failed", error=str(exc))
            return None

    # ------------------------------------------------------------------
    # Synthetic generation stub
    # ------------------------------------------------------------------

    def generate_synthetic_cases(
        self,
        domain: EvalDomain,
        n: int = 10,
        complexity: CaseComplexity = CaseComplexity.MEDIUM,
    ) -> list[BenchmarkCase]:
        """
        Stub for LLM-based synthetic case generation.
        Returns empty list until the generation pipeline is wired up.
        Override or replace with a real implementation that calls the
        extraction/reasoning pipeline in reverse (generate from templates).
        """
        logger.warning(
            "dataset.synthetic_generation_stub",
            domain=domain.value,
            n=n,
            note="Returning empty list — implement generate_synthetic_cases()",
        )
        return []


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_manager_instance: BenchmarkDatasetManager | None = None


def get_dataset_manager(langsmith_client=None) -> BenchmarkDatasetManager:
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = BenchmarkDatasetManager(langsmith_client=langsmith_client)
    return _manager_instance
