from __future__ import annotations

from runtime.invoiceops_showcase_sheet_formatting import (
    build_showcase_formatting_spec,
    get_tab_headers,
    get_all_tab_headers,
    _TAB_HEADERS,
    _TAB_COLOURS,
)
from runtime.invoiceops_showcase_demo import SHOWCASE_TABS


def test_formatting_spec_returns_requests() -> None:
    spec = build_showcase_formatting_spec(spreadsheet_id="TESTSHEET")
    assert spec["spreadsheet_id"] == "TESTSHEET"
    assert isinstance(spec["requests"], list)
    assert len(spec["requests"]) > 0


def test_all_tabs_have_headers() -> None:
    for tab in SHOWCASE_TABS:
        headers = get_tab_headers(tab)
        assert len(headers) >= 2, f"{tab} needs >= 2 headers"


def test_all_tabs_have_colours() -> None:
    for tab in SHOWCASE_TABS:
        assert tab in _TAB_COLOURS, f"{tab} has no tab colour"


def test_header_row_requests_included() -> None:
    spec = build_showcase_formatting_spec(spreadsheet_id="X")
    request_types = {list(r.keys())[0] for r in spec["requests"]}
    assert "updateSheetProperties" in request_types
    assert "repeatCell" in request_types


def test_basic_filter_requests_included() -> None:
    spec = build_showcase_formatting_spec(spreadsheet_id="X")
    request_types = [list(r.keys())[0] for r in spec["requests"]]
    assert "setBasicFilter" in request_types


def test_conditional_format_requests_included() -> None:
    spec = build_showcase_formatting_spec(spreadsheet_id="X")
    request_types = [list(r.keys())[0] for r in spec["requests"]]
    assert "addConditionalFormatRule" in request_types


def test_get_all_tab_headers_returns_all_tabs() -> None:
    all_headers = get_all_tab_headers()
    for tab in SHOWCASE_TABS:
        assert tab in all_headers


def test_frozen_header_requests_included() -> None:
    spec = build_showcase_formatting_spec(spreadsheet_id="X")
    freeze_requests = [
        r for r in spec["requests"]
        if "updateSheetProperties" in r
        and "frozenRowCount" in r.get("updateSheetProperties", {}).get("fields", "")
    ]
    assert len(freeze_requests) >= len(SHOWCASE_TABS)


def test_currency_format_requests_for_invoices_tab() -> None:
    spec = build_showcase_formatting_spec(spreadsheet_id="X")
    currency_requests = [
        r for r in spec["requests"]
        if "repeatCell" in r
        and "CURRENCY" in str(r.get("repeatCell", {}).get("cell", {}))
    ]
    assert len(currency_requests) > 0


def test_tab_colours_are_rgb_fractions() -> None:
    for tab, colour in _TAB_COLOURS.items():
        for channel in ("red", "green", "blue"):
            val = colour[channel]
            assert 0.0 <= val <= 1.0, f"{tab}.{channel}={val} out of range"
