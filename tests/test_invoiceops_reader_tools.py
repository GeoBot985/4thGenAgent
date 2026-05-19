from __future__ import annotations

import os

import pytest

from runtime.invoiceops_reader_tools import invoiceops_read_invoice_file

_FIXTURES = "tests/fixtures/invoiceops"
_TXT = f"{_FIXTURES}/sample_invoice.txt"
_PDF = f"{_FIXTURES}/sample_invoice.pdf"
_BAD_TXT = f"{_FIXTURES}/bad_invoice.txt"
_BLANK_PDF = f"{_FIXTURES}/blank_invoice.pdf"


# ---------------------------------------------------------------------------
# Happy path — text
# ---------------------------------------------------------------------------

def test_read_txt_invoice_ok() -> None:
    r = invoiceops_read_invoice_file(_TXT)
    assert r["ok"] is True
    assert r["error"] == ""


def test_read_txt_result_type() -> None:
    r = invoiceops_read_invoice_file(_TXT)
    assert r["type"] == "invoiceops_raw_invoice_text"


def test_read_txt_data_fields_present() -> None:
    r = invoiceops_read_invoice_file(_TXT)
    data = r["data"]
    assert "source_path" in data
    assert "source_type" in data
    assert "text" in data
    assert "char_count" in data
    assert "line_count" in data


def test_read_txt_source_type_is_text() -> None:
    r = invoiceops_read_invoice_file(_TXT)
    assert r["data"]["source_type"] == "text"


def test_read_txt_source_path_is_absolute() -> None:
    r = invoiceops_read_invoice_file(_TXT)
    assert os.path.isabs(r["data"]["source_path"])


def test_read_txt_text_nonempty() -> None:
    r = invoiceops_read_invoice_file(_TXT)
    assert len(r["data"]["text"]) > 0


def test_read_txt_char_count_matches_text() -> None:
    r = invoiceops_read_invoice_file(_TXT)
    assert r["data"]["char_count"] == len(r["data"]["text"])


def test_read_txt_line_count_matches_text() -> None:
    r = invoiceops_read_invoice_file(_TXT)
    assert r["data"]["line_count"] == len(r["data"]["text"].splitlines())


def test_read_txt_line_count_positive() -> None:
    r = invoiceops_read_invoice_file(_TXT)
    assert r["data"]["line_count"] > 0


def test_read_txt_contains_invoice_content() -> None:
    r = invoiceops_read_invoice_file(_TXT)
    assert "INV-2024-001" in r["data"]["text"]


# ---------------------------------------------------------------------------
# Happy path — PDF
# ---------------------------------------------------------------------------

def test_read_pdf_invoice_ok() -> None:
    r = invoiceops_read_invoice_file(_PDF)
    assert r["ok"] is True
    assert r["error"] == ""


def test_read_pdf_result_type() -> None:
    r = invoiceops_read_invoice_file(_PDF)
    assert r["type"] == "invoiceops_raw_invoice_text"


def test_read_pdf_source_type_is_pdf() -> None:
    r = invoiceops_read_invoice_file(_PDF)
    assert r["data"]["source_type"] == "pdf"


def test_read_pdf_source_path_is_absolute() -> None:
    r = invoiceops_read_invoice_file(_PDF)
    assert os.path.isabs(r["data"]["source_path"])


def test_read_pdf_text_nonempty() -> None:
    r = invoiceops_read_invoice_file(_PDF)
    assert len(r["data"]["text"]) > 0


def test_read_pdf_char_count_matches_text() -> None:
    r = invoiceops_read_invoice_file(_PDF)
    assert r["data"]["char_count"] == len(r["data"]["text"])


def test_read_pdf_line_count_positive() -> None:
    r = invoiceops_read_invoice_file(_PDF)
    assert r["data"]["line_count"] > 0


def test_read_pdf_contains_invoice_content() -> None:
    r = invoiceops_read_invoice_file(_PDF)
    assert "INV-2024-002" in r["data"]["text"]


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

def test_read_txt_evidence_present() -> None:
    r = invoiceops_read_invoice_file(_TXT)
    assert isinstance(r["evidence"], dict)
    assert r["evidence"]


def test_read_txt_evidence_tool() -> None:
    r = invoiceops_read_invoice_file(_TXT)
    assert r["evidence"]["tool"] == "invoiceops/read_invoice_file"


def test_read_txt_evidence_mode_dry_run() -> None:
    r = invoiceops_read_invoice_file(_TXT)
    assert r["evidence"]["mode"] == "dry_run"


def test_read_txt_evidence_operation_read() -> None:
    r = invoiceops_read_invoice_file(_TXT)
    assert r["evidence"]["operation"] == "read"


def test_read_txt_evidence_input_refs_contain_path() -> None:
    r = invoiceops_read_invoice_file(_TXT)
    refs = r["evidence"]["input_refs"]
    assert any("path=" in ref for ref in refs)


def test_read_txt_evidence_output_ref() -> None:
    r = invoiceops_read_invoice_file(_TXT)
    assert r["evidence"]["output_ref"] == "invoiceops_raw_invoice_text"


def test_read_pdf_evidence_present() -> None:
    r = invoiceops_read_invoice_file(_PDF)
    assert r["evidence"]


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

def test_read_txt_metadata_fixture_mode_true() -> None:
    r = invoiceops_read_invoice_file(_TXT)
    assert r["metadata"]["fixture_mode"] is True


def test_read_pdf_metadata_fixture_mode_true() -> None:
    r = invoiceops_read_invoice_file(_PDF)
    assert r["metadata"]["fixture_mode"] is True


# ---------------------------------------------------------------------------
# Failure — missing file
# ---------------------------------------------------------------------------

def test_missing_file_fails() -> None:
    r = invoiceops_read_invoice_file("tests/fixtures/invoiceops/does_not_exist.txt")
    assert r["ok"] is False


def test_missing_file_error_code() -> None:
    r = invoiceops_read_invoice_file("tests/fixtures/invoiceops/does_not_exist.txt")
    assert r["error"] == "INVOICE_FILE_NOT_FOUND"


def test_missing_file_data_empty() -> None:
    r = invoiceops_read_invoice_file("tests/fixtures/invoiceops/does_not_exist.txt")
    assert r["data"] == {}


def test_missing_pdf_fails() -> None:
    r = invoiceops_read_invoice_file("tests/fixtures/invoiceops/does_not_exist.pdf")
    assert r["ok"] is False
    assert r["error"] == "INVOICE_FILE_NOT_FOUND"


# ---------------------------------------------------------------------------
# Failure — unsupported extension
# ---------------------------------------------------------------------------

def test_unsupported_docx_fails() -> None:
    r = invoiceops_read_invoice_file("tests/fixtures/invoiceops/invoice.docx")
    assert r["ok"] is False
    assert r["error"] == "UNSUPPORTED_INVOICE_FILE_TYPE"


def test_unsupported_xlsx_fails() -> None:
    r = invoiceops_read_invoice_file("tests/fixtures/invoiceops/invoice.xlsx")
    assert r["ok"] is False
    assert r["error"] == "UNSUPPORTED_INVOICE_FILE_TYPE"


def test_unsupported_csv_fails() -> None:
    r = invoiceops_read_invoice_file("tests/fixtures/invoiceops/invoice.csv")
    assert r["ok"] is False
    assert r["error"] == "UNSUPPORTED_INVOICE_FILE_TYPE"


def test_unsupported_extension_fails() -> None:
    r = invoiceops_read_invoice_file("tests/fixtures/invoiceops/invoice.unknown")
    assert r["ok"] is False
    assert r["error"] == "UNSUPPORTED_INVOICE_FILE_TYPE"


def test_unsupported_extension_data_empty() -> None:
    r = invoiceops_read_invoice_file("tests/fixtures/invoiceops/invoice.docx")
    assert r["data"] == {}


# ---------------------------------------------------------------------------
# Failure — empty text
# ---------------------------------------------------------------------------

def test_empty_txt_invoice_fails() -> None:
    r = invoiceops_read_invoice_file(_BAD_TXT)
    assert r["ok"] is False
    assert r["error"] == "INVOICE_TEXT_EMPTY"


def test_empty_txt_data_empty() -> None:
    r = invoiceops_read_invoice_file(_BAD_TXT)
    assert r["data"] == {}


def test_blank_pdf_invoice_fails() -> None:
    r = invoiceops_read_invoice_file(_BLANK_PDF)
    assert r["ok"] is False
    assert r["error"] == "INVOICE_TEXT_EMPTY"


# ---------------------------------------------------------------------------
# Result structure contract
# ---------------------------------------------------------------------------

def test_ok_result_has_all_required_keys() -> None:
    r = invoiceops_read_invoice_file(_TXT)
    for key in ("ok", "type", "data", "evidence", "error", "metadata"):
        assert key in r, f"Missing key: {key}"


def test_error_result_has_all_required_keys() -> None:
    r = invoiceops_read_invoice_file("missing.txt")
    for key in ("ok", "type", "data", "evidence", "error", "metadata"):
        assert key in r, f"Missing key: {key}"


def test_ok_result_error_field_empty() -> None:
    r = invoiceops_read_invoice_file(_TXT)
    assert r["error"] == ""


def test_error_result_ok_is_false() -> None:
    r = invoiceops_read_invoice_file("missing.txt")
    assert r["ok"] is False


# ---------------------------------------------------------------------------
# No live side effects
# ---------------------------------------------------------------------------

def test_read_does_not_modify_fixture_file(tmp_path) -> None:
    source = tmp_path / "invoice.txt"
    source.write_text("Invoice No: TEST-001\nTotal: 100.00\n", encoding="utf-8")
    original_mtime = source.stat().st_mtime
    invoiceops_read_invoice_file(str(source))
    assert source.stat().st_mtime == original_mtime


def test_read_does_not_create_side_effect_files(tmp_path) -> None:
    source = tmp_path / "invoice.txt"
    source.write_text("Invoice No: TEST-002\nTotal: 200.00\n", encoding="utf-8")
    before = set(os.listdir(tmp_path))
    invoiceops_read_invoice_file(str(source))
    after = set(os.listdir(tmp_path))
    assert before == after
