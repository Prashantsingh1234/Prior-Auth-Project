"""
Layout-aware parser for healthcare documents.

Responsibilities:
  1. Detect document category (prescription, lab report, med necessity cert, …)
  2. Extract named sections (Diagnosis, Medications, Lab Values, …)
  3. Identify and structure tables
  4. Extract lightweight medical entities (codes, dates, names)
  5. Classify document sections by clinical role

Category detection uses keyword signals — no ML model required.
Section detection uses heading pattern matching tuned to healthcare layouts.
"""

from __future__ import annotations

import re
from typing import NamedTuple

import structlog

from app.services.document.models import (
    DocumentCategory,
    MedicalEntities,
    NormalizedDocument,
    StructuredSection,
)

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Category detection signals
# ---------------------------------------------------------------------------

_CATEGORY_SIGNALS: list[tuple[DocumentCategory, list[str]]] = [
    (DocumentCategory.PRESCRIPTION, [
        "rx", "prescription", "sig:", "dispense", "refills",
        "controlled substance", "dose", "prescribed by", "pharmacy",
    ]),
    (DocumentCategory.LAB_REPORT, [
        "lab report", "laboratory", "specimen", "reference range",
        "hba1c", "glucose", "creatinine", "lipid panel", "cbc",
        "result:", "normal range", "units", "collected:", "reported:",
    ]),
    (DocumentCategory.MEDICAL_NECESSITY_CERT, [
        "medical necessity", "certificate of medical necessity",
        "prior authorization", "clinical justification",
        "medically necessary", "coverage criteria", "letter of medical necessity",
    ]),
    (DocumentCategory.RADIOLOGY_REPORT, [
        "radiology", "x-ray", "mri", "ct scan", "ultrasound", "impression:",
        "findings:", "technique:", "contrast:", "radiologist",
    ]),
    (DocumentCategory.OPERATIVE_REPORT, [
        "operative report", "procedure performed", "anesthesia",
        "surgeon:", "assistant surgeon", "preoperative diagnosis",
        "postoperative diagnosis", "incision",
    ]),
    (DocumentCategory.REFERRAL, [
        "referral", "refer to", "referring provider",
        "reason for referral", "referred by", "consultation request",
    ]),
    (DocumentCategory.CLINICAL_NOTE, [
        "subjective:", "objective:", "assessment:", "plan:",
        "chief complaint", "history of present illness", "hpi",
        "review of systems", "physical examination", "soap note",
    ]),
    (DocumentCategory.INSURANCE_CARD, [
        "member id", "group number", "insurance card",
        "plan name", "copay", "deductible", "effective date",
    ]),
    (DocumentCategory.POLICY_DOCUMENT, [
        "policy number", "coverage criteria", "benefit description",
        "exclusions", "limitations", "prior authorization criteria",
        "payer policy", "medical policy",
    ]),
]

# ---------------------------------------------------------------------------
# Section heading patterns
# ---------------------------------------------------------------------------

_SECTION_HEADING_RE = re.compile(
    r"^(?P<title>"
    r"diagnosis|diagnoses|assessment|plan|medications?|allergies|"
    r"chief complaint|history of present illness|hpi|"
    r"review of systems|ros|physical examination|exam|"
    r"lab(?:oratory)? results?|laboratory values|lab values|"
    r"impression|findings|technique|procedure|indication|"
    r"coverage criteria|exclusions?|limitations?|documentation requirements?|"
    r"subjective|objective|prescription|sig|refills|dispense|"
    r"patient information|provider information|ordering provider|"
    r"clinical justification|medical necessity|"
    r"signature|date|referring physician"
    r")\s*[:\-–—]?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# ---------------------------------------------------------------------------
# Medical entity patterns
# ---------------------------------------------------------------------------

_ICD_RE       = re.compile(r"\b([A-TV-Z]\d{2}(?:\.\d{1,4})?)\b")
_CPT_RE       = re.compile(r"\b(\d{5})\b(?!\d)")
_DATE_RE      = re.compile(
    r"\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}|\d{4}[\/\-]\d{2}[\/\-]\d{2})\b"
)
_MRN_RE       = re.compile(r"\b(?:mrn|patient\s+id|chart\s+#?|acct\.?)\s*[:\s#]?\s*([A-Z0-9\-]{4,20})\b", re.I)
_DOB_RE       = re.compile(r"\b(?:dob|date of birth|birth date)[:\s]+([^\n]{5,20})", re.I)
_PATIENT_RE   = re.compile(r"\b(?:patient(?:\s+name)?|name)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", re.I)
_PROVIDER_RE  = re.compile(r"\b(?:ordering provider|prescriber|physician|dr\.?|provider)[:\s]+([^\n]{5,60})", re.I)
_FACILITY_RE  = re.compile(r"\b(?:facility|hospital|clinic|practice)[:\s]+([^\n]{5,80})", re.I)
_LAB_VALUE_RE = re.compile(
    r"(?P<test>[A-Za-z0-9 /\(\)]+)\s+(?P<value>\d+\.?\d*)\s+(?P<unit>[a-zA-Z/%]+)(?:\s+[HL])?",
)
_MED_RE       = re.compile(
    r"\b(?:metformin|insulin|glipizide|lisinopril|atorvastatin|"
    r"amlodipine|omeprazole|levothyroxine|simvastatin|"
    r"cgm|dexcom|libre|omnipod|humira|ozempic|wegovy|"
    r"\d+\s*mg|\d+\s*mcg|\d+\s*units?)\b",
    re.IGNORECASE,
)


class LayoutParser:
    """
    Parses layout and extracts structured content from NormalizedDocument.

    Mutates the document in-place: adds sections, entities, category.

    Usage:
        parser = LayoutParser()
        parser.parse(normalized_doc)
    """

    def __init__(self) -> None:
        self._log = structlog.get_logger(self.__class__.__name__)

    def parse(self, doc: NormalizedDocument) -> NormalizedDocument:
        """
        Run all layout analysis passes on the document.

        Returns the same document object with sections, entities, and
        category fields populated.
        """
        text = doc.full_text

        # 1. Detect clinical category
        if doc.document_category == DocumentCategory.GENERAL:
            doc.document_category = self._detect_category(text)

        # 2. Extract sections
        doc.sections = self._extract_sections(text, doc.total_pages)

        # 3. Extract lightweight medical entities
        doc.entities = self._extract_entities(text)

        # 4. Enrich page-level section headers
        for page in doc.pages:
            page.section_headers = self._extract_section_titles(page.text)

        self._log.info(
            "layout_parser.complete",
            document_id=doc.document_id,
            category=doc.document_category,
            sections=len(doc.sections),
            icd_codes=len(doc.entities.diagnosis_codes),
            cpt_codes=len(doc.entities.procedure_codes),
        )
        return doc

    # ------------------------------------------------------------------
    # Category detection
    # ------------------------------------------------------------------

    def _detect_category(self, text: str) -> DocumentCategory:
        lower = text.lower()
        scores: dict[DocumentCategory, int] = {}
        for category, signals in _CATEGORY_SIGNALS:
            score = sum(1 for s in signals if s in lower)
            if score > 0:
                scores[category] = score

        if not scores:
            return DocumentCategory.GENERAL
        best = max(scores, key=lambda k: scores[k])
        return best if scores[best] >= 2 else DocumentCategory.GENERAL

    # ------------------------------------------------------------------
    # Section extraction
    # ------------------------------------------------------------------

    def _extract_sections(
        self, text: str, total_pages: int
    ) -> list[StructuredSection]:
        sections: list[StructuredSection] = []
        lines = text.split("\n")
        current_title: str | None = None
        current_lines: list[str] = []
        current_page  = 1

        def _flush(next_page: int) -> None:
            if current_title and current_lines:
                content = "\n".join(current_lines).strip()
                if content:
                    sections.append(
                        StructuredSection(
                            title=current_title,
                            content=content,
                            page_start=current_page,
                            page_end=next_page,
                            section_type=self._classify_section(current_title),
                        )
                    )

        for line in lines:
            stripped = line.strip()
            m = _SECTION_HEADING_RE.match(stripped)
            if m:
                _flush(current_page)
                current_title = m.group("title").strip().title()
                current_lines = []
            elif stripped:
                current_lines.append(stripped)

        _flush(total_pages)
        return sections

    @staticmethod
    def _classify_section(title: str) -> str:
        lower = title.lower()
        if any(k in lower for k in ("diagnosis", "assessment", "impression")):
            return "diagnosis"
        if any(k in lower for k in ("medication", "prescription", "sig", "rx")):
            return "medication"
        if any(k in lower for k in ("lab", "result", "value", "finding")):
            return "lab"
        if any(k in lower for k in ("plan", "recommendation", "instruction")):
            return "plan"
        if any(k in lower for k in ("history", "hpi", "complaint")):
            return "history"
        if any(k in lower for k in ("coverage", "exclusion", "limitation", "criteria")):
            return "policy"
        return "general"

    @staticmethod
    def _extract_section_titles(page_text: str) -> list[str]:
        titles: list[str] = []
        for line in page_text.split("\n"):
            m = _SECTION_HEADING_RE.match(line.strip())
            if m:
                titles.append(m.group("title").strip().title())
        return titles

    # ------------------------------------------------------------------
    # Lightweight entity extraction
    # ------------------------------------------------------------------

    def _extract_entities(self, text: str) -> MedicalEntities:
        icd  = list(dict.fromkeys(_ICD_RE.findall(text)))
        cpt  = list(dict.fromkeys(_CPT_RE.findall(text)))
        dates = list(dict.fromkeys(_DATE_RE.findall(text)))[:10]
        meds  = list(dict.fromkeys(
            m.group(0).strip() for m in _MED_RE.finditer(text)
        ))

        # Single-value extractions
        mrn_m      = _MRN_RE.search(text)
        dob_m      = _DOB_RE.search(text)
        patient_m  = _PATIENT_RE.search(text)
        provider_m = _PROVIDER_RE.search(text)
        facility_m = _FACILITY_RE.search(text)

        # Lab value extraction
        lab_values: list[dict[str, str]] = []
        for m in _LAB_VALUE_RE.finditer(text):
            lab_values.append({
                "test":  m.group("test").strip(),
                "value": m.group("value"),
                "unit":  m.group("unit"),
            })

        return MedicalEntities(
            patient_name=patient_m.group(1).strip() if patient_m else None,
            date_of_birth=dob_m.group(1).strip() if dob_m else None,
            mrn=mrn_m.group(1).strip() if mrn_m else None,
            ordering_provider=provider_m.group(1).strip() if provider_m else None,
            facility=facility_m.group(1).strip() if facility_m else None,
            diagnosis_codes=icd,
            procedure_codes=cpt,
            medications=meds,
            dates=dates,
            lab_values=lab_values[:20],
        )
