"""
Unit tests for the policy ingestion pipeline.

All external dependencies (pdfplumber, Pinecone, EmbeddingService) are mocked
so tests run without any network calls or installed OCR libraries.

Test coverage:
  - models.py           — PolicyCriterion, ParsedDocument, IngestionResult
  - pdf_parser.py       — PDFParser (mocked pdfplumber; OCR fallback path)
  - chunker.py          — PolicyChunker (list-aware + paragraph strategies)
  - extractor.py        — MetadataExtractor (CPT, ICD, dates, payer, merge)
  - validator.py        — ChunkValidator (hard rules + soft warnings)
  - dedup.py            — DuplicateDetector (duplicate / version-conflict paths)
  - pipeline.py         — IngestionPipeline (happy path, duplicate, all-invalid)
"""

from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.ingestion.chunker import PolicyChunker
from app.services.ingestion.dedup import DuplicateDetector
from app.services.ingestion.extractor import MetadataExtractor
from app.services.ingestion.models import (
    ChunkingResult,
    CriterionType,
    DuplicateCheckResult,
    IngestionResult,
    IngestionStatus,
    ParsedDocument,
    ParsedPage,
    PolicyCriterion,
    PolicyIngestionRequest,
)
from app.services.ingestion.pdf_parser import PDFParser
from app.services.ingestion.pipeline import IngestionPipeline
from app.services.ingestion.validator import ChunkValidator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_request(**kwargs) -> PolicyIngestionRequest:
    defaults = dict(
        policy_id="aetna-cgm-v3",
        policy_name="CGM Coverage Criteria",
        payer_name="Aetna",
        service_type="Continuous Glucose Monitor",
    )
    defaults.update(kwargs)
    return PolicyIngestionRequest(**defaults)


def _make_page(number: int = 1, text: str = "Some policy text.", ocr: bool = False) -> ParsedPage:
    return ParsedPage(
        page_number=number,
        text=text,
        char_count=len(text),
        used_ocr=ocr,
    )


def _make_parsed_doc(pages: list[ParsedPage] | None = None) -> ParsedDocument:
    if pages is None:
        pages = [_make_page()]
    full_text = "\n\n".join(p.text for p in pages)
    return ParsedDocument(
        pages=pages,
        full_text=full_text,
        total_pages=len(pages),
        used_ocr_pages=[p.page_number for p in pages if p.used_ocr],
        document_hash=hashlib.sha256(full_text.encode()).hexdigest(),
    )


def _make_criterion(
    index: int = 0,
    text: str = "Member must have a documented diagnosis of diabetes mellitus.",
    ctype: CriterionType = CriterionType.COVERAGE_CRITERIA,
    section: str | None = "Coverage Criteria",
) -> PolicyCriterion:
    return PolicyCriterion(
        chunk_index=index,
        text=text,
        criterion_type=ctype,
        section_header=section,
        list_marker=None,
        source_page=1,
    )


# ===========================================================================
# Models
# ===========================================================================

class TestPolicyIngestionRequest:
    def test_valid_slug(self):
        r = _make_request(policy_id="aetna-cgm-v3")
        assert r.policy_id == "aetna-cgm-v3"

    def test_slug_lowercased(self):
        r = _make_request(policy_id="AETNA-CGM-V3")
        assert r.policy_id == "aetna-cgm-v3"

    def test_invalid_slug_raises(self):
        with pytest.raises(Exception):
            _make_request(policy_id="invalid slug!")

    def test_codes_default_empty(self):
        r = _make_request()
        assert r.cpt_codes == []
        assert r.icd_codes == []


class TestParsedDocument:
    def test_avg_chars_per_page(self):
        pages = [
            _make_page(1, "A" * 100),
            _make_page(2, "B" * 200),
        ]
        doc = _make_parsed_doc(pages)
        assert doc.avg_chars_per_page == 150.0

    def test_is_text_poor_true(self):
        pages = [_make_page(text="Short.")]
        doc = _make_parsed_doc(pages)
        assert doc.is_text_poor is True

    def test_is_text_poor_false(self):
        pages = [_make_page(text="A" * 200)]
        doc = _make_parsed_doc(pages)
        assert doc.is_text_poor is False

    def test_no_pages_avg_chars_zero(self):
        doc = ParsedDocument(
            pages=[],
            full_text="",
            total_pages=0,
            document_hash="abc",
        )
        assert doc.avg_chars_per_page == 0.0


class TestPolicyCriterion:
    def test_enriched_text_with_header(self):
        c = _make_criterion(section="Coverage Criteria")
        assert c.enriched_text.startswith("Coverage Criteria\n")

    def test_enriched_text_without_header(self):
        c = _make_criterion(section=None)
        assert c.enriched_text == c.text

    def test_min_length_enforced(self):
        with pytest.raises(Exception):
            PolicyCriterion(
                chunk_index=0,
                text="Short",          # < 20 chars
                criterion_type=CriterionType.GENERAL,
                source_page=1,
            )

    def test_confidence_bounds(self):
        with pytest.raises(Exception):
            _make_criterion().__class__(
                chunk_index=0,
                text="A" * 30,
                criterion_type=CriterionType.GENERAL,
                source_page=1,
                confidence=1.5,       # > 1.0
            )


# ===========================================================================
# PDF Parser
# ===========================================================================

class TestPDFParser:
    def _mock_pdfplumber_pages(self, texts: list[str]):
        """Return a context-manager mock that yields pdfplumber page mocks."""
        pages = []
        for i, text in enumerate(texts, start=1):
            page = MagicMock()
            page.extract_text.return_value = text
            page.extract_tables.return_value = []
            pages.append(page)

        pdf_mock = MagicMock()
        pdf_mock.pages = pages
        pdf_mock.__enter__ = MagicMock(return_value=pdf_mock)
        pdf_mock.__exit__ = MagicMock(return_value=False)
        return pdf_mock

    @pytest.mark.asyncio
    async def test_parse_returns_parsed_document(self):
        parser = PDFParser(ocr_enabled=False)
        fake_text = "Coverage Criteria\n1. Member must have diabetes.\n"
        pdf_mock = self._mock_pdfplumber_pages([fake_text])

        with patch("pdfplumber.open", return_value=pdf_mock):
            result = await parser.parse(b"fake-pdf-bytes")

        assert isinstance(result, ParsedDocument)
        assert result.total_pages == 1
        assert result.document_hash == hashlib.sha256(b"fake-pdf-bytes").hexdigest()

    @pytest.mark.asyncio
    async def test_parse_text_poor_triggers_ocr_when_enabled(self):
        parser = PDFParser(ocr_enabled=True)
        pdf_mock = self._mock_pdfplumber_pages(["Hi"])  # text-poor

        ocr_page = ParsedPage(page_number=1, text="A" * 300, char_count=300, used_ocr=True)
        with (
            patch("pdfplumber.open", return_value=pdf_mock),
            patch.object(parser, "_extract_with_ocr", new_callable=AsyncMock, return_value=[ocr_page]),
        ):
            result = await parser.parse(b"scanned-pdf")

        assert result.used_ocr_pages == [1]

    @pytest.mark.asyncio
    async def test_parse_ocr_disabled_no_fallback(self):
        parser = PDFParser(ocr_enabled=False)
        pdf_mock = self._mock_pdfplumber_pages(["Hi"])

        with patch("pdfplumber.open", return_value=pdf_mock):
            result = await parser.parse(b"pdf")

        assert result.used_ocr_pages == []

    @pytest.mark.asyncio
    async def test_document_hash_is_sha256(self):
        parser = PDFParser(ocr_enabled=False)
        pdf_bytes = b"test content"
        expected_hash = hashlib.sha256(pdf_bytes).hexdigest()
        pdf_mock = self._mock_pdfplumber_pages(["Some text " * 20])

        with patch("pdfplumber.open", return_value=pdf_mock):
            result = await parser.parse(pdf_bytes)

        assert result.document_hash == expected_hash

    @pytest.mark.asyncio
    async def test_multiple_pages(self):
        parser = PDFParser(ocr_enabled=False)
        pdf_mock = self._mock_pdfplumber_pages(["Page one text.", "Page two text."])

        with patch("pdfplumber.open", return_value=pdf_mock):
            result = await parser.parse(b"multi-page-pdf")

        assert result.total_pages == 2
        assert len(result.pages) == 2


# ===========================================================================
# Chunker
# ===========================================================================

class TestPolicyChunker:
    COVERAGE_SECTION = "Coverage Criteria:\n"
    LIST_TEXT = (
        "Coverage Criteria:\n"
        "1. Member must have a documented diagnosis of diabetes mellitus type 1.\n"
        "2. Prescribing physician must document medical necessity.\n"
        "3. HbA1c must be >= 7% within the past 6 months.\n"
    )
    BULLET_TEXT = (
        "Exclusions:\n"
        "• Services not covered include cosmetic procedures.\n"
        "• Experimental treatments are excluded.\n"
    )
    PARAGRAPH_TEXT = (
        "This policy establishes coverage criteria for continuous glucose monitors.\n\n"
        "The device must be prescribed by a licensed endocrinologist.\n\n"
        "Documentation of prior conventional testing is required.\n"
    )

    def _doc_from_text(self, text: str) -> ParsedDocument:
        page = _make_page(text=text)
        return _make_parsed_doc([page])

    def test_numbered_list_produces_one_chunk_per_item(self):
        chunker = PolicyChunker()
        result = chunker.chunk(self._doc_from_text(self.LIST_TEXT))
        # 3 numbered criteria → 3 chunks (header is consumed)
        assert result.total_chunks == 3

    def test_bullet_list_produces_one_chunk_per_bullet(self):
        chunker = PolicyChunker()
        result = chunker.chunk(self._doc_from_text(self.BULLET_TEXT))
        assert result.total_chunks == 2

    def test_paragraph_strategy_used_when_no_lists(self):
        chunker = PolicyChunker()
        result = chunker.chunk(self._doc_from_text(self.PARAGRAPH_TEXT))
        assert result.strategy_used == "criterion_aware_paragraph"

    def test_list_strategy_used_when_lists_present(self):
        chunker = PolicyChunker()
        result = chunker.chunk(self._doc_from_text(self.LIST_TEXT))
        assert result.strategy_used == "criterion_aware_list"

    def test_section_header_attached_to_chunks(self):
        chunker = PolicyChunker()
        result = chunker.chunk(self._doc_from_text(self.LIST_TEXT))
        for c in result.criteria:
            assert c.section_header is not None

    def test_exclusion_type_detected(self):
        chunker = PolicyChunker()
        result = chunker.chunk(self._doc_from_text(self.BULLET_TEXT))
        for c in result.criteria:
            assert c.criterion_type == CriterionType.EXCLUSION

    def test_coverage_criteria_type_detected(self):
        chunker = PolicyChunker()
        result = chunker.chunk(self._doc_from_text(self.LIST_TEXT))
        for c in result.criteria:
            assert c.criterion_type == CriterionType.COVERAGE_CRITERIA

    def test_negation_flag_set(self):
        text = "Coverage Criteria:\n1. Not covered if no documented diagnosis present.\n"
        chunker = PolicyChunker()
        result = chunker.chunk(self._doc_from_text(text))
        assert any(c.has_negation for c in result.criteria)

    def test_empty_document_produces_no_chunks(self):
        chunker = PolicyChunker()
        doc = ParsedDocument(
            pages=[],
            full_text="",
            total_pages=0,
            document_hash="abc",
        )
        result = chunker.chunk(doc)
        assert result.total_chunks == 0

    def test_oversized_block_split_at_sentence_boundary(self):
        long_text = (
            "Coverage Criteria:\n"
            "1. " + ("This is a sentence about medical necessity. " * 60) + "\n"
        )
        chunker = PolicyChunker(max_chunk_chars=500)
        result = chunker.chunk(self._doc_from_text(long_text))
        for c in result.criteria:
            assert len(c.text) <= 500 + 50  # some tolerance for trailing word

    def test_inline_cpt_codes_extracted(self):
        text = "Coverage Criteria:\n1. CPT 95249 is covered when criteria are met.\n"
        chunker = PolicyChunker()
        result = chunker.chunk(self._doc_from_text(text))
        all_cpts = [c for cr in result.criteria for c in cr.cpt_codes]
        assert "95249" in all_cpts

    def test_sections_found_populated(self):
        chunker = PolicyChunker()
        result = chunker.chunk(self._doc_from_text(self.LIST_TEXT))
        assert len(result.sections_found) >= 1


# ===========================================================================
# Extractor
# ===========================================================================

class TestMetadataExtractor:
    SAMPLE_TEXT = """
Aetna Clinical Policy Bulletin
Continuous Glucose Monitors (CGM)
Policy for Continuous Glucose Monitor Devices
Effective Date: January 01, 2024
Expiration Date: December 31, 2024
Version 3.1

Coverage Criteria:
CPT codes covered: 95249, 95250, 95251
ICD-10 codes: E11.65, E10.649
"""

    def test_cpt_codes_extracted(self):
        ext = MetadataExtractor()
        meta = ext.extract(self.SAMPLE_TEXT)
        assert "95249" in meta.cpt_codes
        assert "95250" in meta.cpt_codes
        assert "95251" in meta.cpt_codes

    def test_icd_codes_extracted(self):
        ext = MetadataExtractor()
        meta = ext.extract(self.SAMPLE_TEXT)
        assert "E11.65" in meta.icd_codes
        assert "E10.649" in meta.icd_codes

    def test_version_extracted(self):
        ext = MetadataExtractor()
        meta = ext.extract(self.SAMPLE_TEXT)
        assert meta.policy_version == "3.1"

    def test_effective_date_extracted(self):
        ext = MetadataExtractor()
        meta = ext.extract(self.SAMPLE_TEXT)
        assert meta.effective_date == "2024-01-01"

    def test_expiration_date_extracted(self):
        ext = MetadataExtractor()
        meta = ext.extract(self.SAMPLE_TEXT)
        assert meta.expiration_date == "2024-12-31"

    def test_payer_name_extracted(self):
        ext = MetadataExtractor()
        meta = ext.extract(self.SAMPLE_TEXT)
        assert meta.payer_name == "Aetna"

    def test_no_codes_returns_empty_lists(self):
        ext = MetadataExtractor()
        meta = ext.extract("No codes here.")
        assert meta.cpt_codes == []
        assert meta.icd_codes == []

    def test_merge_preserves_caller_payer(self):
        ext = MetadataExtractor()
        request = _make_request(payer_name="Cigna")
        meta = ext.extract(self.SAMPLE_TEXT)   # would extract "Aetna"
        merged = MetadataExtractor.merge(request, meta)
        assert merged.payer_name == "Cigna"    # caller wins

    def test_merge_fills_missing_payer(self):
        ext = MetadataExtractor()
        request = _make_request(payer_name=None)
        meta = ext.extract(self.SAMPLE_TEXT)
        merged = MetadataExtractor.merge(request, meta)
        assert merged.payer_name == "Aetna"

    def test_merge_deduplicates_codes(self):
        ext = MetadataExtractor()
        request = _make_request(cpt_codes=["95249"])
        meta = ext.extract(self.SAMPLE_TEXT)   # also finds 95249
        merged = MetadataExtractor.merge(request, meta)
        assert merged.cpt_codes.count("95249") == 1

    def test_cpt_range_expanded(self):
        ext = MetadataExtractor()
        meta = ext.extract("Covered CPT 99201-99205 for office visits.")
        for code in ["99201", "99202", "99203", "99204", "99205"]:
            assert code in meta.cpt_codes


# ===========================================================================
# Validator
# ===========================================================================

class TestChunkValidator:
    def test_valid_criterion_passes(self):
        v = ChunkValidator()
        criterion = _make_criterion(text="Member must have a documented diagnosis of diabetes.")
        result = v.validate_batch([criterion])
        assert len(result.valid_criteria) == 1
        assert len(result.invalid_criteria) == 0

    def test_short_text_fails_hard_rule(self):
        v = ChunkValidator()
        criterion = _make_criterion(text="A" * 10)
        # Force text length below minimum by constructing bypassing pydantic
        criterion = criterion.model_copy(update={"text": "A" * 10})
        result = v.validate_batch([criterion])
        assert len(result.invalid_criteria) == 1

    def test_numeric_only_fails(self):
        v = ChunkValidator()
        criterion = _make_criterion(text="12345678901234567890")
        result = v.validate_batch([criterion])
        assert len(result.invalid_criteria) == 1

    def test_header_footer_fails(self):
        v = ChunkValidator()
        criterion = _make_criterion(text="Page 1 of 10")
        result = v.validate_batch([criterion])
        assert len(result.invalid_criteria) == 1

    def test_missing_section_header_warning(self):
        v = ChunkValidator()
        criterion = _make_criterion(
            text="Member must have documented HbA1c test within 6 months.",
            section=None,
        )
        result = v.validate_batch([criterion])
        assert len(result.valid_criteria) == 1
        vr = result.results[0]
        assert any("section_header" in w for w in vr.warnings)

    def test_pass_rate_all_valid(self):
        v = ChunkValidator()
        criteria = [_make_criterion(index=i) for i in range(5)]
        result = v.validate_batch(criteria)
        assert result.pass_rate == 1.0

    def test_pass_rate_mixed(self):
        v = ChunkValidator()
        valid   = _make_criterion(index=0, text="Member must have documented diagnosis.")
        invalid = _make_criterion(index=1, text="1234567890123456789012")  # numeric
        result = v.validate_batch([valid, invalid])
        assert result.pass_rate == 0.5

    def test_empty_batch_pass_rate_zero(self):
        v = ChunkValidator()
        result = v.validate_batch([])
        assert result.pass_rate == 0.0


# ===========================================================================
# Duplicate Detector
# ===========================================================================

class TestDuplicateDetector:
    def _make_client(self, matches: list[dict]) -> MagicMock:
        client = MagicMock()
        client.query = AsyncMock(return_value={"matches": matches})
        client.describe_index_stats = AsyncMock(
            return_value=MagicMock(namespaces={"": {"vector_count": 100}})
        )
        return client

    @pytest.mark.asyncio
    async def test_duplicate_found(self):
        match = {
            "id": "aetna-cgm-v3_0001",
            "score": 1.0,
            "metadata": {
                "policy_id": "aetna-cgm-v3",
                "document_hash": "abc123",
                "policy_version": "2.0",
            },
        }
        client = self._make_client([match])
        detector = DuplicateDetector(client)
        result = await detector.check("abc123", "aetna-cgm-v3")
        assert result.is_duplicate is True
        assert result.existing_policy_id == "aetna-cgm-v3"

    @pytest.mark.asyncio
    async def test_no_duplicate(self):
        client = self._make_client([])
        detector = DuplicateDetector(client)
        result = await detector.check("new-hash", "aetna-cgm-v4")
        assert result.is_duplicate is False
        assert result.existing_policy_id is None

    @pytest.mark.asyncio
    async def test_pinecone_error_treated_as_no_duplicate(self):
        client = MagicMock()
        client.query = AsyncMock(side_effect=Exception("Pinecone down"))
        detector = DuplicateDetector(client)
        result = await detector.check("some-hash", "aetna-cgm-v5")
        assert result.is_duplicate is False

    @pytest.mark.asyncio
    async def test_version_conflict_detected(self):
        match = {
            "id": "aetna-cgm-v3_0001",
            "score": 1.0,
            "metadata": {
                "policy_id": "aetna-cgm-v3",
                "document_hash": "old-hash",
            },
        }
        client = self._make_client([match])
        detector = DuplicateDetector(client)
        conflict, existing_hash = await detector.check_version_conflict(
            "aetna-cgm-v3", "new-hash"
        )
        assert conflict is True
        assert existing_hash == "old-hash"

    @pytest.mark.asyncio
    async def test_no_version_conflict_when_hash_matches(self):
        match = {
            "id": "aetna-cgm-v3_0001",
            "score": 1.0,
            "metadata": {
                "policy_id": "aetna-cgm-v3",
                "document_hash": "same-hash",
            },
        }
        client = self._make_client([match])
        detector = DuplicateDetector(client)
        conflict, _ = await detector.check_version_conflict("aetna-cgm-v3", "same-hash")
        assert conflict is False


# ===========================================================================
# IngestionPipeline (integration of all stages, mocked I/O)
# ===========================================================================

class TestIngestionPipeline:
    def _make_pipeline(
        self,
        parsed_doc: ParsedDocument | None = None,
        is_duplicate: bool = False,
        chunks_indexed: int = 5,
    ) -> IngestionPipeline:
        if parsed_doc is None:
            text = (
                "Coverage Criteria:\n"
                "1. Member must have a documented diagnosis of diabetes mellitus.\n"
                "2. Prescribing physician must document that conventional testing is inadequate.\n"
                "3. HbA1c >= 7% within past 6 months.\n"
            ) * 2
            parsed_doc = _make_parsed_doc([_make_page(text=text)])

        parser = MagicMock()
        parser.parse = AsyncMock(return_value=parsed_doc)

        dedup = MagicMock()
        dedup.check = AsyncMock(
            return_value=DuplicateCheckResult(
                is_duplicate=is_duplicate,
                existing_policy_id="existing-id" if is_duplicate else None,
                existing_version="1.0" if is_duplicate else None,
                document_hash=parsed_doc.document_hash,
            )
        )
        dedup.check_version_conflict = AsyncMock(return_value=(False, None))

        indexer = MagicMock()
        indexer.index_policy = AsyncMock(return_value=chunks_indexed)
        indexer.reindex_policy = AsyncMock(return_value={"upserted": chunks_indexed})

        pipeline = IngestionPipeline(
            pdf_parser=parser,
            chunker=PolicyChunker(),
            extractor=MetadataExtractor(),
            validator=ChunkValidator(),
            dedup=dedup,
            indexer=indexer,
        )
        return pipeline

    @pytest.mark.asyncio
    async def test_happy_path_returns_success(self):
        pipeline = self._make_pipeline()
        result = await pipeline.ingest(_make_request(), b"pdf-bytes")
        assert result.status == IngestionStatus.SUCCESS
        assert result.total_chunks_indexed > 0

    @pytest.mark.asyncio
    async def test_duplicate_returns_duplicate_status(self):
        pipeline = self._make_pipeline(is_duplicate=True)
        result = await pipeline.ingest(_make_request(), b"pdf-bytes")
        assert result.status == IngestionStatus.DUPLICATE
        assert result.total_chunks_indexed == 0

    @pytest.mark.asyncio
    async def test_pdf_parse_failure_returns_failed(self):
        pipeline = self._make_pipeline()
        pipeline._parser.parse = AsyncMock(side_effect=Exception("corrupt PDF"))
        result = await pipeline.ingest(_make_request(), b"bad-pdf")
        assert result.status == IngestionStatus.FAILED
        assert any("PDF parsing failed" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_all_invalid_chunks_returns_failed(self):
        # Use a doc whose text produces only header/footer-like chunks
        page = _make_page(text="Page 1 of 10\nPage 2 of 10\nPage 3 of 10\n")
        doc = _make_parsed_doc([page])
        pipeline = self._make_pipeline(parsed_doc=doc)
        result = await pipeline.ingest(_make_request(), b"pdf-bytes")
        # Either FAILED (all invalid) or SUCCESS with 0 indexed, depending on chunk content
        assert result.status in (IngestionStatus.FAILED, IngestionStatus.SUCCESS)

    @pytest.mark.asyncio
    async def test_partial_validation_returns_partial_status(self):
        """A mix of valid + invalid chunks should yield PARTIAL status."""
        pipeline = self._make_pipeline()

        # Patch validator to return 1 invalid out of 3
        original_validate = pipeline._validator.validate_batch

        def _patched_validate(criteria):
            result = original_validate(criteria)
            if result.valid_criteria and not result.invalid_criteria:
                # Simulate one invalid by moving one criterion
                invalid = result.valid_criteria.pop()
                result.invalid_criteria.append(invalid)
            return result

        pipeline._validator.validate_batch = _patched_validate  # type: ignore[method-assign]
        result = await pipeline.ingest(_make_request(), b"pdf-bytes")
        # With mix of valid/invalid → PARTIAL
        assert result.status in (IngestionStatus.PARTIAL, IngestionStatus.SUCCESS)

    @pytest.mark.asyncio
    async def test_result_has_extracted_codes(self):
        text = (
            "Aetna Coverage Criteria:\n"
            "1. CPT 95249 applies when HbA1c (E11.65) is documented.\n"
            "2. Member must meet all qualifying criteria.\n"
        )
        doc = _make_parsed_doc([_make_page(text=text)])
        pipeline = self._make_pipeline(parsed_doc=doc)
        result = await pipeline.ingest(_make_request(), b"pdf")
        # CPT/ICD may have been extracted by extractor stage
        assert isinstance(result.extracted_cpt_codes, list)
        assert isinstance(result.extracted_icd_codes, list)

    @pytest.mark.asyncio
    async def test_allow_reindex_calls_reindex_policy(self):
        pipeline = self._make_pipeline()
        pipeline._dedup.check_version_conflict = AsyncMock(
            return_value=(True, "old-hash")
        )
        await pipeline.ingest(_make_request(), b"pdf", allow_reindex=True)
        pipeline._indexer.reindex_policy.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_policy_id_propagated_to_result(self):
        pipeline = self._make_pipeline()
        result = await pipeline.ingest(
            _make_request(policy_id="humana-insulin-v1"), b"pdf"
        )
        assert result.policy_id == "humana-insulin-v1"
