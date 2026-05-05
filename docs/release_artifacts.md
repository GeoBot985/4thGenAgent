# Release Artifacts

This repository uses a deterministic golden demo to produce RC artifacts in `runtime_data/outputs/`.

| Artifact | Path | Created By | Purpose | Required |
|---|---|---|---|---|
| Golden demo summary report | `runtime_data/outputs/reports/golden_demo_report.md` | `scripts/run_golden_demo.py` | Operator-facing release-candidate summary | Yes |
| Golden demo summary HTML | `runtime_data/outputs/reports/golden_demo_report.html` | `scripts/run_golden_demo.py` | Browser-friendly summary view | Yes |
| Golden demo audit JSON | `runtime_data/outputs/audit/golden_demo_audit.json` | `scripts/run_golden_demo.py` | Machine-readable verdict and workflow checks | Yes |
| Customer workflow report | `runtime_data/outputs/reports/customer_workflow_report.md` | `scripts/run_golden_demo.py` | Customer lane evidence | Yes |
| Customer workflow HTML | `runtime_data/outputs/reports/customer_workflow_report.html` | `scripts/run_golden_demo.py` | Browser-friendly customer lane evidence | Yes |
| Customer workflow audit JSON | `runtime_data/outputs/audit/customer_workflow_audit.json` | `scripts/run_golden_demo.py` | Customer lane structured audit trail | Yes |
| Procurement workflow report | `runtime_data/outputs/reports/procurement_workflow_report.md` | `scripts/run_golden_demo.py` | Procurement lane evidence | Yes |
| Procurement workflow HTML | `runtime_data/outputs/reports/procurement_workflow_report.html` | `scripts/run_golden_demo.py` | Browser-friendly procurement lane evidence | Yes |
| Procurement workflow audit JSON | `runtime_data/outputs/audit/procurement_workflow_audit.json` | `scripts/run_golden_demo.py` | Procurement lane structured audit trail | Yes |
| Accounting workflow report | `runtime_data/outputs/reports/accounting_workflow_report.md` | `scripts/run_golden_demo.py` | Accounting lane evidence | Yes |
| Accounting workflow HTML | `runtime_data/outputs/reports/accounting_workflow_report.html` | `scripts/run_golden_demo.py` | Browser-friendly accounting lane evidence | Yes |
| Accounting workflow audit JSON | `runtime_data/outputs/audit/accounting_workflow_audit.json` | `scripts/run_golden_demo.py` | Accounting lane structured audit trail | Yes |
