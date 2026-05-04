from __future__ import annotations

import argparse

from tools.write_sheet_entries import write_sheet_entries


PAYMENTS = [
    ["payment_id", "payment_ref", "order_ref", "customer_id", "amount", "currency", "payment_date", "status", "source"],
    ["PAY-1001", "EFT-9001", "ORD-10042", "CUST-1001", "1250.00", "ZAR", "2026-05-04", "received", "bank"],
    ["PAY-1002", "EFT-9002", "ORD-10043", "CUST-1002", "450.00", "ZAR", "2026-05-04", "received", "bank"],
    ["PAY-1003", "EFT-9003", "ORD-10044", "CUST-1003", "300.00", "ZAR", "2026-05-04", "received", "bank"],
    ["PAY-1004", "EFT-9004", "ORD-10045", "CUST-1004", "500.00", "ZAR", "2026-05-04", "received", "bank"],
    ["PAY-1005", "EFT-9005", "ORD-10046", "CUST-1005", "250.00", "ZAR", "2026-05-04", "received", "bank"],
    ["PAY-1006", "EFT-9005", "ORD-10046", "CUST-1005", "250.00", "ZAR", "2026-05-04", "received", "bank"],
]

ORDERS = [
    ["order_ref", "customer_id", "order_total", "currency", "order_status", "invoice_id"],
    ["ORD-10042", "CUST-1001", "1250.00", "ZAR", "invoiced", "INV-10042"],
    ["ORD-10043", "CUST-1002", "500.00", "ZAR", "invoiced", "INV-10043"],
    ["ORD-10044", "CUST-1003", "300.00", "ZAR", "invoiced", "INV-10044"],
    ["ORD-10045", "CUST-1004", "500.00", "ZAR", "invoiced", "INV-10045"],
    ["ORD-10046", "CUST-1005", "250.00", "ZAR", "invoiced", "INV-10046"],
]

INVOICES = [
    ["invoice_id", "order_ref", "customer_id", "invoice_total", "currency", "invoice_status", "issued_date", "due_date"],
    ["INV-10042", "ORD-10042", "CUST-1001", "1250.00", "ZAR", "issued", "2026-05-01", "2026-05-15"],
    ["INV-10043", "ORD-10043", "CUST-1002", "500.00", "ZAR", "issued", "2026-05-01", "2026-05-15"],
    ["INV-10044", "ORD-10044", "CUST-1003", "300.00", "ZAR", "issued", "2026-05-01", "2026-05-15"],
    ["INV-10045", "ORD-10045", "CUST-1004", "500.00", "ZAR", "issued", "2026-05-01", "2026-05-15"],
    ["INV-10046", "ORD-10046", "CUST-1005", "250.00", "ZAR", "issued", "2026-05-01", "2026-05-15"],
]

LEDGER = [
    ["ledger_entry_id", "source_type", "source_ref", "debit_account", "credit_account", "amount", "currency", "posted_date", "status"],
    ["LED-1001", "payment", "EFT-9001", "bank", "revenue", "1250.00", "ZAR", "2026-05-04", "posted"],
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spreadsheet-id", required=True)
    parser.add_argument("--clear-first", action="store_true")
    args = parser.parse_args()
    for range_name, rows in {
        "Payments!A:I": PAYMENTS,
        "Orders!A:F": ORDERS,
        "CustomerInvoices!A:H": INVOICES,
        "Ledger!A:I": LEDGER,
    }.items():
        write_sheet_entries(args.spreadsheet_id, range_name, rows, mode="update" if args.clear_first else "append")


if __name__ == "__main__":
    main()
