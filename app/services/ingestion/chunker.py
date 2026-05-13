"""
Criterion-aware chunking stage of the policy ingestion pipeline.

Policy documents have well-defined structure:
  - Section headings (COVERAGE CRITERIA, EXCLUSIONS, LIMITATIONS, etc.)
  - Numbered criteria  (1. The member must have ...)
  - Lettered sub-criteria (a. HbA1c ≥ 7% documented ...)
  - Bullet criteria    (• Physician order on file ...)
  - Prose paragraphs   (free-form background / definition text)

This chunker treats each of those structural units as ONE criterion rather
than slicing arbitrarily at a character boundary.  A criterion that spans
multiple sentences stays intact.  Only if a single item exceeds MAX_CHUNK_CHARS
is it split at the last sentence boundary inside the limit.

Output: ChunkingResult with a list[PolicyCriterion], one per chunk.
"""

from __future__ import annotations

import re
import structlog
from typing import NamedTuple

from app.services.ingestion.models import (
    ChunkingResult,
    CriterionType,
    ParsedDocument,
    PolicyCriterion,
)

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_CHUNK_CHARS = 2_000      # Hard ceiling — force-split anything above this
MIN_CHUNK_CHARS = 30         # Discard degenerate chunks shorter than this

# Negation signals that mark a chunk as "not covered"
_NEGATION_PATTERNS = re.compile(
    r"\b(not covered|not a benefit|non-covered|excluded|does not cover|"
    r"will not be covered|is not considered|is not medically necessary|"
    r"denial|denied|no benefit|not eligible)\b",
    re.IGNORECASE,
)

# Section header signals — used to classify the enclosing section
_SECTION_HEADER_RE = re.compile(
    r"^(?P<header>"
    r"coverage criteria|coverage indications|indications for coverage|"
    r"covered services|covered benefits|"
    r"exclusions?|excluded services?|non-covered|"
    r"limitations?|quantity limits?|frequency limits?|"
    r"documentation requirements?|required documentation|supporting documentation|"
    r"definitions?|background|overview|general|clinical criteria|"
    r"medical necessity criteria|prior authorization criteria"
    r")\s*[:\-–—]?\s*$",
    re.IGNORECASE,
)

# Criterion type → section header keyword mapping (order matters: first match wins)
_SECTION_TO_TYPE: list[tuple[re.Pattern[str], CriterionType]] = [
    (re.compile(r"exclusion|non.covered|excluded", re.I), CriterionType.EXCLUSION),
    (re.compile(r"limitation|quantity|frequency|limit", re.I), CriterionType.LIMITATION),
    (re.compile(r"documentation|supporting|required doc", re.I), CriterionType.DOCUMENTATION),
    (re.compile(r"definition|background|overview", re.I), CriterionType.DEFINITION),
    (re.compile(r"coverage|indication|criteria|medically necessary", re.I), CriterionType.COVERAGE_CRITERIA),
]

# List-item patterns — each marks the start of a new criterion
_NUMBERED_ITEM_RE = re.compile(r"^(\d+\.|[a-z]\.|[IVXivx]+\.)\s+", re.MULTILINE)
_BULLET_ITEM_RE   = re.compile(r"^([•·\-–—*])\s+", re.MULTILINE)

# CPT/ICD extraction (rough — the extractor.py stage does the authoritative pass)
_CPT_INLINE_RE = re.compile(r"\b(\d{5})\b")
_ICD_INLINE_RE = re.compile(r"\b([A-Z]\d{2}(?:\.\d{1,4})?)\b")


# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------

class _Block(NamedTuple):
    """One structural unit extracted from the document."""
    text: str
    list_marker: str | None    # "1.", "a.", "•", etc.
    source_page: int


# ---------------------------------------------------------------------------
# Public chunker
# ---------------------------------------------------------------------------

class PolicyChunker:
    """
    Splits a ParsedDocument into one PolicyCriterion per structural unit.

    Usage:
        chunker = PolicyChunker()
        result = chunker.chunk(parsed_doc)
    """

    def __init__(
        self,
        max_chunk_chars: int = MAX_CHUNK_CHARS,
        min_chunk_chars: int = MIN_CHUNK_CHARS,
    ) -> None:
        self._max = max_chunk_chars
        self._min = min_chunk_chars
        self._log = structlog.get_logger(self.__class__.__name__)

    def chunk(self, document: ParsedDocument) -> ChunkingResult:
        """
        Chunk a ParsedDocument into criterion-sized pieces.

        Returns ChunkingResult with one PolicyCriterion per criterion.
        """
        blocks, sections_found, strategy = self._extract_blocks(document)
        criteria: list[PolicyCriterion] = []
        warnings: list[str] = []

        current_section: str | None = None
        chunk_index = 0

        for block in blocks:
            # Detect section headers — update context, don't emit a chunk
            if self._is_section_header(block.text):
                current_section = block.text.strip().rstrip(":–—-").strip()
                continue

            text = block.text.strip()
            if len(text) < self._min:
                continue

            # Force-split oversized blocks at sentence boundary
            sub_texts = self._split_if_oversized(text)

            for sub_text in sub_texts:
                if len(sub_text) < self._min:
                    warnings.append(
                        f"Skipped short chunk at page {block.source_page}: "
                        f"{sub_text[:40]!r}"
                    )
                    continue

                ctype = self._classify_criterion(sub_text, current_section)
                has_neg = bool(_NEGATION_PATTERNS.search(sub_text))
                cpt = _CPT_INLINE_RE.findall(sub_text)
                icd = _ICD_INLINE_RE.findall(sub_text)

                criteria.append(
                    PolicyCriterion(
                        chunk_index=chunk_index,
                        text=sub_text,
                        criterion_type=ctype,
                        section_header=current_section,
                        list_marker=block.list_marker,
                        source_page=block.source_page,
                        cpt_codes=list(dict.fromkeys(cpt)),
                        icd_codes=list(dict.fromkeys(icd)),
                        has_negation=has_neg,
                        confidence=1.0,
                    )
                )
                chunk_index += 1

        self._log.info(
            "chunker.complete",
            strategy=strategy,
            total_chunks=len(criteria),
            sections=len(sections_found),
            warnings=len(warnings),
        )

        return ChunkingResult(
            criteria=criteria,
            total_chunks=len(criteria),
            strategy_used=strategy,
            sections_found=sections_found,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # Block extraction — the structural analysis step
    # ------------------------------------------------------------------

    def _extract_blocks(
        self, document: ParsedDocument
    ) -> tuple[list[_Block], list[str], str]:
        """
        Walk document pages and split into structural blocks.

        Returns:
            blocks:        ordered list of _Block objects
            sections_found: unique section headers encountered
            strategy:      human-readable description of which strategy fired
        """
        has_lists = self._document_has_lists(document)

        if has_lists:
            blocks = self._extract_list_aware_blocks(document)
            strategy = "criterion_aware_list"
        else:
            blocks = self._extract_paragraph_blocks(document)
            strategy = "criterion_aware_paragraph"

        sections_found = self._collect_sections(document.full_text)
        return blocks, sections_found, strategy

    @staticmethod
    def _document_has_lists(document: ParsedDocument) -> bool:
        sample = document.full_text[:5_000]
        return bool(_NUMBERED_ITEM_RE.search(sample) or _BULLET_ITEM_RE.search(sample))

    def _extract_list_aware_blocks(self, document: ParsedDocument) -> list[_Block]:
        """
        For documents with numbered / bullet lists:
          - Split at each list-item boundary
          - Prose paragraphs between lists become their own blocks
        """
        blocks: list[_Block] = []
        for page in document.pages:
            page_blocks = self._split_page_into_blocks(page.text, page.page_number)
            blocks.extend(page_blocks)
        return blocks

    def _split_page_into_blocks(self, text: str, page_number: int) -> list[_Block]:
        """
        Split one page's text into structural blocks.

        Strategy: scan line-by-line, accumulating into the current block.
        A new block starts when:
          - A numbered list item is detected     → carry marker
          - A bullet item is detected            → carry marker
          - A blank line follows a non-blank run → paragraph boundary
        """
        lines = text.split("\n")
        blocks: list[_Block] = []
        current_lines: list[str] = []
        current_marker: str | None = None

        def _flush() -> None:
            combined = " ".join(current_lines).strip()
            if combined:
                blocks.append(_Block(combined, current_marker, page_number))

        for line in lines:
            stripped = line.strip()

            numbered_match = _NUMBERED_ITEM_RE.match(stripped)
            bullet_match   = _BULLET_ITEM_RE.match(stripped) if not numbered_match else None

            if numbered_match or bullet_match:
                _flush()
                current_lines = [stripped]
                current_marker = (
                    numbered_match.group(1) if numbered_match else bullet_match.group(1)  # type: ignore[union-attr]
                )
            elif not stripped:
                # Blank line → paragraph boundary
                _flush()
                current_lines = []
                current_marker = None
            else:
                current_lines.append(stripped)

        _flush()
        return blocks

    def _extract_paragraph_blocks(self, document: ParsedDocument) -> list[_Block]:
        """
        For documents without list structure:
          Split at double-newline paragraph boundaries.
        """
        blocks: list[_Block] = []
        for page in document.pages:
            paragraphs = re.split(r"\n{2,}", page.text)
            for para in paragraphs:
                para = para.strip()
                if para:
                    blocks.append(_Block(para, None, page.page_number))
        return blocks

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_section_header(text: str) -> bool:
        stripped = text.strip()
        if len(stripped) > 120:
            return False
        return bool(_SECTION_HEADER_RE.match(stripped))

    @staticmethod
    def _classify_criterion(text: str, section_header: str | None) -> CriterionType:
        target = (section_header or "") + " " + text
        for pattern, ctype in _SECTION_TO_TYPE:
            if pattern.search(target):
                return ctype
        return CriterionType.GENERAL

    def _split_if_oversized(self, text: str) -> list[str]:
        """
        If text exceeds MAX_CHUNK_CHARS, split at the last sentence boundary
        within the limit.  Preserves complete sentences in each sub-chunk.
        """
        if len(text) <= self._max:
            return [text]

        parts: list[str] = []
        while len(text) > self._max:
            # Find the last sentence end within the limit
            window = text[: self._max]
            last_period = max(
                window.rfind(". "),
                window.rfind(".\n"),
                window.rfind("? "),
                window.rfind("! "),
            )
            if last_period <= self._min:
                # No sentence boundary found — hard split at MAX
                parts.append(text[: self._max])
                text = text[self._max :].strip()
            else:
                cut = last_period + 1
                parts.append(text[:cut].strip())
                text = text[cut:].strip()
        if text:
            parts.append(text)
        return parts

    @staticmethod
    def _collect_sections(full_text: str) -> list[str]:
        """Return unique section header titles found in the document."""
        seen: list[str] = []
        for line in full_text.split("\n"):
            m = _SECTION_HEADER_RE.match(line.strip())
            if m:
                title = m.group("header").strip().title()
                if title not in seen:
                    seen.append(title)
        return seen
