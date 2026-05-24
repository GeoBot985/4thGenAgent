from __future__ import annotations

"""
Spec 158 — InvoiceOps Showcase Sheet Formatting.

Builds Google Sheets batchUpdate formatting specifications for the showcase
demo workbook.  No direct API calls are made here; the caller is responsible
for submitting the returned request list to the Sheets API.

Tab colour codes and conditional formatting rules follow the InvoiceOps
status vocabulary: matched, exception, blocked, reconciled, unreconciled,
manual_review.
"""

from typing import Any

# ---------------------------------------------------------------------------
# Colour palette (RGB 0–1 floats for Sheets API)
# ---------------------------------------------------------------------------

_GREEN = {"red": 0.204, "green": 0.659, "blue": 0.325}          # matched / reconciled
_AMBER = {"red": 0.953, "green": 0.612, "blue": 0.071}          # exception / warning
_RED = {"red": 0.878, "green": 0.200, "blue": 0.200}            # blocked / error
_BLUE = {"red": 0.267, "green": 0.533, "blue": 0.800}           # headers / dashboard
_LIGHT_BLUE = {"red": 0.827, "green": 0.906, "blue": 0.976}     # header background
_LIGHT_GREEN = {"red": 0.851, "green": 0.953, "blue": 0.875}    # matched rows
_LIGHT_RED = {"red": 0.976, "green": 0.839, "blue": 0.839}      # blocked rows
_LIGHT_AMBER = {"red": 0.996, "green": 0.941, "blue": 0.796}    # exception rows
_LIGHT_GREY = {"red": 0.949, "green": 0.953, "blue": 0.957}     # alternate rows
_WHITE = {"red": 1.0, "green": 1.0, "blue": 1.0}
_DARK_TEXT = {"red": 0.114, "green": 0.161, "blue": 0.220}

# Tab colours
_TAB_COLOURS: dict[str, dict[str, float]] = {
    "Dashboard": {"red": 0.267, "green": 0.533, "blue": 0.800},
    "Invoices": {"red": 0.204, "green": 0.659, "blue": 0.325},
    "PO Register": {"red": 0.416, "green": 0.659, "blue": 0.294},
    "Goods Receipts": {"red": 0.416, "green": 0.659, "blue": 0.294},
    "Supplier Master": {"red": 0.416, "green": 0.659, "blue": 0.294},
    "Match Results": {"red": 0.204, "green": 0.659, "blue": 0.325},
    "Exceptions": {"red": 0.953, "green": 0.612, "blue": 0.071},
    "Ledger": {"red": 0.267, "green": 0.533, "blue": 0.800},
    "Posting Ledger": {"red": 0.267, "green": 0.533, "blue": 0.800},
    "Reconciliation": {"red": 0.204, "green": 0.659, "blue": 0.325},
    "Rollback Plans": {"red": 0.878, "green": 0.200, "blue": 0.200},
    "Evidence Index": {"red": 0.533, "green": 0.267, "blue": 0.800},
    "Demo Run Log": {"red": 0.600, "green": 0.600, "blue": 0.600},
}

# Tab headers per sheet
_TAB_HEADERS: dict[str, list[str]] = {
    "Dashboard": ["Metric", "Value"],
    "Invoices": ["Invoice Number", "Invoice Date", "Supplier", "PO Number", "GR Number", "Subtotal", "VAT", "Total", "Match Status", "Posting Status", "Run ID"],
    "PO Register": ["PO Number", "Supplier ID", "Supplier Name", "Approved Total", "Currency", "Status"],
    "Goods Receipts": ["GR Number", "PO Number", "Supplier Name", "Qty Received", "Qty Ordered", "Status"],
    "Supplier Master": ["Supplier ID", "Name", "VAT Number", "Status"],
    "Match Results": ["Invoice Number", "Supplier", "PO Number", "GR Number", "Invoice Total", "PO Total", "Match Status", "Exception Type", "Scenario"],
    "Exceptions": ["Invoice Number", "Exception Type", "Supplier", "PO Number", "Recommended Action", "Scenario"],
    "Ledger": ["Invoice Number", "Entry Type", "Account", "Debit ZAR", "Credit ZAR", "Description", "Run ID"],
    "Posting Ledger": ["Idempotency Key", "Invoice Number", "Target Register", "Payload Hash", "Execution Status", "Timestamp", "Run ID"],
    "Reconciliation": ["Invoice Number", "Match Status", "Posting Status", "Reconciliation Status", "Exception Type", "Live Write Count"],
    "Rollback Plans": ["Invoice Number", "Rollback Action", "Target Register", "Idempotency Key", "Rollback Status", "Notes"],
    "Evidence Index": ["Invoice Number", "Evidence Type", "Path / Reference", "Exists", "Scenario"],
    "Demo Run Log": ["Timestamp", "Run ID", "Event", "Invoice Number", "Details"],
}

# Column widths in pixels per sheet (approximate — Sheets uses "columns" not px in API but we use char widths)
_TAB_COL_WIDTHS: dict[str, list[int]] = {
    "Dashboard": [300, 200],
    "Invoices": [140, 110, 240, 140, 140, 110, 90, 110, 120, 140, 200],
    "PO Register": [140, 110, 240, 120, 90, 100],
    "Goods Receipts": [140, 140, 240, 120, 120, 100],
    "Supplier Master": [110, 280, 140, 100],
    "Match Results": [140, 240, 140, 140, 110, 110, 120, 160, 180],
    "Exceptions": [140, 160, 240, 140, 280, 180],
    "Ledger": [140, 120, 160, 110, 110, 240, 200],
    "Posting Ledger": [280, 140, 160, 280, 140, 180, 200],
    "Reconciliation": [140, 120, 140, 160, 160, 120],
    "Rollback Plans": [140, 160, 160, 280, 120, 280],
    "Evidence Index": [140, 160, 300, 80, 180],
    "Demo Run Log": [180, 200, 160, 140, 400],
}


# ---------------------------------------------------------------------------
# Helper: sheet ID resolver (uses title-based lookup)
# ---------------------------------------------------------------------------

def _sheet_id_placeholder(title: str) -> str:
    """Return a placeholder sheet ID reference (resolved at runtime by caller)."""
    return f"SHEET_ID:{title}"


def _color(rgb: dict[str, float]) -> dict[str, Any]:
    return {"red": rgb["red"], "green": rgb["green"], "blue": rgb["blue"]}


def _cell_format(
    *,
    bold: bool = False,
    bg: dict[str, float] | None = None,
    fg: dict[str, float] | None = None,
    font_size: int = 10,
    horizontal_alignment: str = "LEFT",
    number_format_type: str = "",
    number_format_pattern: str = "",
) -> dict[str, Any]:
    fmt: dict[str, Any] = {
        "textFormat": {
            "bold": bold,
            "fontSize": font_size,
            "foregroundColor": _color(fg or _DARK_TEXT),
        },
        "horizontalAlignment": horizontal_alignment,
        "verticalAlignment": "MIDDLE",
        "wrapStrategy": "CLIP",
    }
    if bg:
        fmt["backgroundColor"] = _color(bg)
    if number_format_type:
        fmt["numberFormat"] = {
            "type": number_format_type,
            "pattern": number_format_pattern,
        }
    return fmt


# ---------------------------------------------------------------------------
# Request builders
# ---------------------------------------------------------------------------

def _freeze_header_row(sheet_id: str) -> dict[str, Any]:
    return {
        "updateSheetProperties": {
            "properties": {
                "sheetId": sheet_id,
                "gridProperties": {"frozenRowCount": 1},
            },
            "fields": "gridProperties.frozenRowCount",
        }
    }


def _tab_colour(sheet_id: str, colour: dict[str, float]) -> dict[str, Any]:
    return {
        "updateSheetProperties": {
            "properties": {
                "sheetId": sheet_id,
                "tabColor": _color(colour),
            },
            "fields": "tabColor",
        }
    }


def _header_row_format(sheet_id: str, col_count: int) -> dict[str, Any]:
    return {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": 0,
                "endRowIndex": 1,
                "startColumnIndex": 0,
                "endColumnIndex": col_count,
            },
            "cell": {
                "userEnteredFormat": _cell_format(
                    bold=True,
                    bg=_LIGHT_BLUE,
                    fg=_DARK_TEXT,
                    font_size=10,
                    horizontal_alignment="CENTER",
                )
            },
            "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)",
        }
    }


def _column_width(sheet_id: str, col_index: int, width_px: int) -> dict[str, Any]:
    return {
        "updateDimensionProperties": {
            "range": {
                "sheetId": sheet_id,
                "dimension": "COLUMNS",
                "startIndex": col_index,
                "endIndex": col_index + 1,
            },
            "properties": {"pixelSize": width_px},
            "fields": "pixelSize",
        }
    }


def _currency_format(sheet_id: str, col_index: int, start_row: int = 1, end_row: int = 1000) -> dict[str, Any]:
    return {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": start_row,
                "endRowIndex": end_row,
                "startColumnIndex": col_index,
                "endColumnIndex": col_index + 1,
            },
            "cell": {
                "userEnteredFormat": _cell_format(
                    number_format_type="CURRENCY",
                    number_format_pattern='"ZAR "#,##0.00',
                )
            },
            "fields": "userEnteredFormat.numberFormat",
        }
    }


def _date_format(sheet_id: str, col_index: int, start_row: int = 1, end_row: int = 1000) -> dict[str, Any]:
    return {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": start_row,
                "endRowIndex": end_row,
                "startColumnIndex": col_index,
                "endColumnIndex": col_index + 1,
            },
            "cell": {
                "userEnteredFormat": _cell_format(
                    number_format_type="DATE",
                    number_format_pattern="yyyy-mm-dd",
                )
            },
            "fields": "userEnteredFormat.numberFormat",
        }
    }


def _conditional_format_status(
    sheet_id: str,
    col_index: int,
    *,
    value: str,
    bg: dict[str, float],
    start_row: int = 1,
    end_row: int = 1000,
) -> dict[str, Any]:
    return {
        "addConditionalFormatRule": {
            "rule": {
                "ranges": [{
                    "sheetId": sheet_id,
                    "startRowIndex": start_row,
                    "endRowIndex": end_row,
                    "startColumnIndex": col_index,
                    "endColumnIndex": col_index + 1,
                }],
                "booleanRule": {
                    "condition": {
                        "type": "TEXT_EQ",
                        "values": [{"userEnteredValue": value}],
                    },
                    "format": {"backgroundColor": _color(bg)},
                },
            },
            "index": 0,
        }
    }


def _add_basic_filter(sheet_id: str, col_count: int) -> dict[str, Any]:
    return {
        "setBasicFilter": {
            "filter": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": col_count,
                }
            }
        }
    }


# ---------------------------------------------------------------------------
# Public API: build formatting spec
# ---------------------------------------------------------------------------

def build_showcase_formatting_spec(
    *,
    spreadsheet_id: str,
) -> dict[str, Any]:
    """
    Return the complete batchUpdate request list for all showcase tabs.
    Sheet IDs are placeholders; caller must resolve them from the real
    spreadsheet before submitting.

    Returns:
        {
            "spreadsheet_id": str,
            "requests": [list of batchUpdate request objects],
            "tab_headers": {tab_title: [header_cols]},
            "tab_col_widths": {tab_title: [widths]},
        }
    """
    requests: list[dict[str, Any]] = []

    from runtime.invoiceops_showcase_demo import SHOWCASE_TABS

    for tab_title in SHOWCASE_TABS:
        sid = _sheet_id_placeholder(tab_title)
        tab_colour = _TAB_COLOURS.get(tab_title, {"red": 0.6, "green": 0.6, "blue": 0.6})
        headers = _TAB_HEADERS.get(tab_title, [])
        col_widths = _TAB_COL_WIDTHS.get(tab_title, [])
        col_count = max(len(headers), 2)

        # Freeze header row
        requests.append(_freeze_header_row(sid))
        # Tab colour
        requests.append(_tab_colour(sid, tab_colour))
        # Bold header row
        requests.append(_header_row_format(sid, col_count))
        # Column widths
        for i, width in enumerate(col_widths):
            requests.append(_column_width(sid, i, width))
        # Basic filter
        requests.append(_add_basic_filter(sid, col_count))

        # Tab-specific formatting
        if tab_title == "Invoices":
            requests.append(_date_format(sid, 1))        # Invoice Date col
            requests.append(_currency_format(sid, 5))    # Subtotal
            requests.append(_currency_format(sid, 6))    # VAT
            requests.append(_currency_format(sid, 7))    # Total
            # Status conditional formatting (Match Status = col 8)
            for val, bg in [("matched", _LIGHT_GREEN), ("exception", _LIGHT_AMBER), ("blocked", _LIGHT_RED)]:
                requests.append(_conditional_format_status(sid, 8, value=val, bg=bg))

        elif tab_title == "Match Results":
            requests.append(_currency_format(sid, 4))    # Invoice Total
            requests.append(_currency_format(sid, 5))    # PO Total
            for val, bg in [("matched", _LIGHT_GREEN), ("exception", _LIGHT_AMBER), ("blocked", _LIGHT_RED)]:
                requests.append(_conditional_format_status(sid, 6, value=val, bg=bg))

        elif tab_title == "Exceptions":
            requests.append(_conditional_format_status(sid, 1, value="DUPLICATE_INVOICE", bg=_LIGHT_RED))
            requests.append(_conditional_format_status(sid, 1, value="PO_NOT_FOUND", bg=_LIGHT_RED))
            requests.append(_conditional_format_status(sid, 1, value="GOODS_RECEIPT_NOT_FOUND", bg=_LIGHT_RED))
            requests.append(_conditional_format_status(sid, 1, value="SUPPLIER_MISMATCH", bg=_LIGHT_AMBER))
            requests.append(_conditional_format_status(sid, 1, value="PRICE_MISMATCH", bg=_LIGHT_AMBER))
            requests.append(_conditional_format_status(sid, 1, value="QUANTITY_MISMATCH", bg=_LIGHT_AMBER))
            requests.append(_conditional_format_status(sid, 1, value="TAX_TOTAL_MISMATCH", bg=_LIGHT_AMBER))

        elif tab_title == "Ledger":
            requests.append(_currency_format(sid, 3))    # Debit ZAR
            requests.append(_currency_format(sid, 4))    # Credit ZAR

        elif tab_title == "Posting Ledger":
            requests.append(_date_format(sid, 5))        # Timestamp
            for val, bg in [("EXECUTED_VERIFIED", _LIGHT_GREEN), ("BLOCKED", _LIGHT_RED), ("PENDING", _LIGHT_AMBER)]:
                requests.append(_conditional_format_status(sid, 4, value=val, bg=bg))

        elif tab_title == "Reconciliation":
            for val, bg in [("RECONCILED", _LIGHT_GREEN), ("UNRECONCILED", _LIGHT_RED), ("MANUAL_REVIEW_REQUIRED", _LIGHT_AMBER)]:
                requests.append(_conditional_format_status(sid, 3, value=val, bg=bg))

        elif tab_title == "PO Register":
            requests.append(_currency_format(sid, 3))    # Approved Total

    return {
        "spreadsheet_id": spreadsheet_id,
        "requests": requests,
        "tab_headers": _TAB_HEADERS,
        "tab_col_widths": _TAB_COL_WIDTHS,
        "tab_colours": {k: v for k, v in _TAB_COLOURS.items()},
        "notes": (
            "Sheet IDs in requests are placeholders in the form 'SHEET_ID:<tab_title>'. "
            "Caller must resolve real sheet IDs from the spreadsheet before submitting to batchUpdate."
        ),
    }


def get_tab_headers(tab_title: str) -> list[str]:
    """Return the header row for a given tab."""
    return list(_TAB_HEADERS.get(tab_title, []))


def get_all_tab_headers() -> dict[str, list[str]]:
    """Return headers for all showcase tabs."""
    return {k: list(v) for k, v in _TAB_HEADERS.items()}
