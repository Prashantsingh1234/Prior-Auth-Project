"""
File type detection for healthcare documents.

Detection strategy:
  1. Magic bytes inspection (reliable, format-independent)
  2. MIME type hint from caller (fallback if magic bytes ambiguous)
  3. File extension as last resort

Supports:
  PDF (scanned + native), PNG, JPG, TIFF, JSON, plain text, email (EML)

Native vs. scanned PDF distinction:
  After magic bytes identify a PDF, pdfplumber extracts one page to count
  embedded text characters. < 80 chars/page → SCANNED_PDF, else NATIVE_PDF.
"""

from __future__ import annotations

import io
import json

import structlog

from app.services.document.models import DocumentType

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Magic byte signatures
# ---------------------------------------------------------------------------

_MAGIC: list[tuple[bytes, DocumentType]] = [
    (b"%PDF",         DocumentType.NATIVE_PDF),   # refined to SCANNED_PDF later
    (b"\x89PNG\r\n",  DocumentType.IMAGE_PNG),
    (b"\xff\xd8\xff", DocumentType.IMAGE_JPG),
    (b"II*\x00",      DocumentType.IMAGE_TIFF),   # little-endian TIFF
    (b"MM\x00*",      DocumentType.IMAGE_TIFF),   # big-endian TIFF
    (b"GIF87a",       DocumentType.IMAGE_PNG),    # treat GIF as image
    (b"GIF89a",       DocumentType.IMAGE_PNG),
]

# Minimum characters per page to classify a PDF as native (has embedded text)
_NATIVE_PDF_MIN_CHARS = 80

# MIME type → DocumentType mapping (used when magic bytes are inconclusive)
_MIME_MAP: dict[str, DocumentType] = {
    "application/pdf":   DocumentType.NATIVE_PDF,
    "image/png":         DocumentType.IMAGE_PNG,
    "image/jpeg":        DocumentType.IMAGE_JPG,
    "image/jpg":         DocumentType.IMAGE_JPG,
    "image/tiff":        DocumentType.IMAGE_TIFF,
    "application/json":  DocumentType.JSON_PAYLOAD,
    "text/plain":        DocumentType.TEXT_NOTE,
    "message/rfc822":    DocumentType.EMAIL,
    "text/html":         DocumentType.TEXT_NOTE,
}

# File extension → DocumentType (last resort)
_EXT_MAP: dict[str, DocumentType] = {
    ".pdf":  DocumentType.NATIVE_PDF,
    ".png":  DocumentType.IMAGE_PNG,
    ".jpg":  DocumentType.IMAGE_JPG,
    ".jpeg": DocumentType.IMAGE_JPG,
    ".tiff": DocumentType.IMAGE_TIFF,
    ".tif":  DocumentType.IMAGE_TIFF,
    ".json": DocumentType.JSON_PAYLOAD,
    ".txt":  DocumentType.TEXT_NOTE,
    ".eml":  DocumentType.EMAIL,
    ".msg":  DocumentType.EMAIL,
}


class DocumentDetector:
    """
    Detects the type of a document from its raw bytes.

    Usage:
        detector = DocumentDetector()
        doc_type = detector.detect(pdf_bytes, mime_hint="application/pdf")
    """

    def __init__(self) -> None:
        self._log = structlog.get_logger(self.__class__.__name__)

    def detect(
        self,
        content: bytes,
        mime_hint: str = "",
        filename: str = "",
    ) -> DocumentType:
        """
        Detect document type with magic bytes as primary signal.

        Args:
            content:   Raw file bytes (at least 16 bytes for reliable detection)
            mime_hint: MIME type string provided by the caller / upload form
            filename:  Original filename (used for extension fallback)

        Returns:
            DocumentType enum value.
        """
        if not content:
            return DocumentType.UNKNOWN

        # 1. Magic bytes
        doc_type = self._detect_by_magic(content)

        if doc_type == DocumentType.NATIVE_PDF:
            doc_type = self._classify_pdf(content)
        elif doc_type is not None:
            return doc_type

        # 2. Try JSON / text detection by content sniffing
        if doc_type is None:
            sniff = self._sniff_text(content)
            if sniff:
                return sniff

        # 3. MIME hint
        if doc_type is None and mime_hint:
            doc_type = _MIME_MAP.get(mime_hint.lower().split(";")[0].strip())

        # 4. File extension
        if doc_type is None and filename:
            suffix = ("." + filename.rsplit(".", 1)[-1]).lower() if "." in filename else ""
            doc_type = _EXT_MAP.get(suffix)

        result = doc_type or DocumentType.UNKNOWN
        self._log.debug(
            "detector.result",
            doc_type=result,
            mime_hint=mime_hint,
            filename=filename,
        )
        return result

    # ------------------------------------------------------------------

    @staticmethod
    def _detect_by_magic(content: bytes) -> DocumentType | None:
        for signature, dtype in _MAGIC:
            if content.startswith(signature):
                return dtype
        # EML detection: starts with "From " or "Received:" headers
        try:
            head = content[:200].decode("utf-8", errors="ignore")
            if head.startswith("From ") or head.startswith("Received:"):
                return DocumentType.EMAIL
        except Exception:
            pass
        return None

    def _classify_pdf(self, content: bytes) -> DocumentType:
        """Distinguish native PDFs (embedded text) from scanned PDFs."""
        try:
            import pdfplumber

            with pdfplumber.open(io.BytesIO(content)) as pdf:
                if not pdf.pages:
                    return DocumentType.SCANNED_PDF
                # Sample up to 3 pages
                sample_pages = pdf.pages[:3]
                total_chars = sum(
                    len(p.extract_text() or "") for p in sample_pages
                )
                avg_chars = total_chars / len(sample_pages)
                return (
                    DocumentType.NATIVE_PDF
                    if avg_chars >= _NATIVE_PDF_MIN_CHARS
                    else DocumentType.SCANNED_PDF
                )
        except Exception as err:
            self._log.warning("detector.pdf_classify_failed", error=str(err))
            return DocumentType.SCANNED_PDF

    @staticmethod
    def _sniff_text(content: bytes) -> DocumentType | None:
        """Detect JSON or plain text by attempting to decode."""
        try:
            text = content.decode("utf-8", errors="strict")
            stripped = text.strip()
            if stripped.startswith(("{", "[")):
                json.loads(stripped)
                return DocumentType.JSON_PAYLOAD
            # Plain text: high ratio of printable ASCII
            printable = sum(1 for c in stripped if c.isprintable() or c in "\n\r\t")
            if stripped and printable / len(stripped) > 0.90:
                return DocumentType.TEXT_NOTE
        except (UnicodeDecodeError, json.JSONDecodeError, ZeroDivisionError):
            pass
        return None

    def get_mime_type(self, doc_type: DocumentType) -> str:
        """Return the canonical MIME type for a detected DocumentType."""
        return {
            DocumentType.NATIVE_PDF:           "application/pdf",
            DocumentType.SCANNED_PDF:          "application/pdf",
            DocumentType.IMAGE_PNG:            "image/png",
            DocumentType.IMAGE_JPG:            "image/jpeg",
            DocumentType.IMAGE_TIFF:           "image/tiff",
            DocumentType.JSON_PAYLOAD:         "application/json",
            DocumentType.TEXT_NOTE:            "text/plain",
            DocumentType.EMAIL:                "message/rfc822",
        }.get(doc_type, "application/octet-stream")

    @staticmethod
    def requires_ocr(doc_type: DocumentType) -> bool:
        """Return True if this document type requires OCR to extract text."""
        return doc_type in {
            DocumentType.SCANNED_PDF,
            DocumentType.IMAGE_PNG,
            DocumentType.IMAGE_JPG,
            DocumentType.IMAGE_TIFF,
        }

    @staticmethod
    def is_supported(doc_type: DocumentType) -> bool:
        return doc_type != DocumentType.UNKNOWN
