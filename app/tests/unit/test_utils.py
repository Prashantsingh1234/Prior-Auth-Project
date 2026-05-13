"""Unit tests for common utility functions."""

from __future__ import annotations

import pytest

from app.utils.common import (
    chunk_list,
    extract_cpt_codes,
    extract_icd_codes,
    flatten_dict,
    hash_content,
    mask_pii,
    normalize_text,
    safe_truncate,
)


class TestTextNormalization:

    def test_collapses_multiple_spaces(self) -> None:
        assert normalize_text("hello   world") == "hello world"

    def test_strips_leading_trailing_whitespace(self) -> None:
        assert normalize_text("  hello  ") == "hello"

    def test_handles_newlines(self) -> None:
        assert normalize_text("hello\n\nworld") == "hello world"


class TestCPTExtraction:

    def test_extracts_single_cpt_code(self) -> None:
        codes = extract_cpt_codes("The procedure code is 95249.")
        assert "95249" in codes

    def test_extracts_multiple_cpt_codes(self) -> None:
        codes = extract_cpt_codes("Codes 95249 and 99213 were billed.")
        assert "95249" in codes
        assert "99213" in codes

    def test_deduplicates_cpt_codes(self) -> None:
        codes = extract_cpt_codes("95249 and 95249 again")
        assert codes.count("95249") == 1

    def test_ignores_non_cpt_numbers(self) -> None:
        codes = extract_cpt_codes("Patient is 42 years old with SSN 123.")
        assert len(codes) == 0


class TestICDExtraction:

    def test_extracts_icd_with_decimal(self) -> None:
        codes = extract_icd_codes("Diagnosis: E11.9 (Type 2 Diabetes)")
        assert "E11.9" in codes

    def test_extracts_icd_without_decimal(self) -> None:
        codes = extract_icd_codes("Code E11 confirmed")
        assert "E11" in codes

    def test_case_insensitive_extraction(self) -> None:
        codes = extract_icd_codes("diagnosis e11.9")
        assert "E11.9" in codes

    def test_deduplicates_icd_codes(self) -> None:
        codes = extract_icd_codes("E11.9 and E11.9")
        assert codes.count("E11.9") == 1


class TestHashContent:

    def test_sha256_produces_64_char_hex(self) -> None:
        h = hash_content("test content")
        assert len(h) == 64

    def test_same_input_same_hash(self) -> None:
        assert hash_content("abc") == hash_content("abc")

    def test_different_input_different_hash(self) -> None:
        assert hash_content("abc") != hash_content("xyz")

    def test_bytes_input(self) -> None:
        h = hash_content(b"bytes content")
        assert len(h) == 64


class TestSafeTruncate:

    def test_short_string_unchanged(self) -> None:
        assert safe_truncate("short", 100) == "short"

    def test_long_string_truncated(self) -> None:
        result = safe_truncate("a" * 200, 50)
        assert len(result) == 50
        assert result.endswith("...")

    def test_exact_length_unchanged(self) -> None:
        s = "a" * 10
        assert safe_truncate(s, 10) == s


class TestChunkList:

    def test_even_split(self) -> None:
        chunks = chunk_list([1, 2, 3, 4], 2)
        assert chunks == [[1, 2], [3, 4]]

    def test_uneven_split(self) -> None:
        chunks = chunk_list([1, 2, 3, 4, 5], 2)
        assert chunks == [[1, 2], [3, 4], [5]]

    def test_empty_list(self) -> None:
        assert chunk_list([], 5) == []

    def test_chunk_larger_than_list(self) -> None:
        chunks = chunk_list([1, 2], 10)
        assert chunks == [[1, 2]]


class TestMaskPII:

    def test_masks_ssn(self) -> None:
        result = mask_pii("SSN: 123-45-6789")
        assert "123-45-6789" not in result
        assert "[SSN REDACTED]" in result

    def test_masks_email(self) -> None:
        result = mask_pii("Email: patient@hospital.org")
        assert "patient@hospital.org" not in result
        assert "[EMAIL REDACTED]" in result

    def test_non_pii_text_unchanged(self) -> None:
        text = "Patient has Type 2 Diabetes (E11.9)"
        result = mask_pii(text)
        assert "Type 2 Diabetes" in result
        assert "E11.9" in result


class TestFlattenDict:

    def test_flat_dict_unchanged(self) -> None:
        d = {"a": 1, "b": 2}
        assert flatten_dict(d) == {"a": 1, "b": 2}

    def test_nested_dict_flattened(self) -> None:
        d = {"a": {"b": {"c": 1}}}
        assert flatten_dict(d) == {"a.b.c": 1}

    def test_mixed_depth(self) -> None:
        d = {"a": 1, "b": {"c": 2}}
        assert flatten_dict(d) == {"a": 1, "b.c": 2}
