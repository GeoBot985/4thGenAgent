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


## Order management workflow pack artifacts

| Artifact | Path | Purpose |
|---|---|---|
| Order management doc | `docs/order_management_workflows.md` | Workflow descriptions, tool table, dataset reference |
| Order validate_new manifest | `manifests/order.validate_new.manifest.json` | Manifest for new order validation |
| Order reserve_stock manifest | `manifests/order.reserve_stock.manifest.json` | Manifest for stock reservation |
| Order release_paid manifest | `manifests/order.release_paid.manifest.json` | Manifest for releasing a paid order |
| Order detect_delayed manifest | `manifests/order.detect_delayed.manifest.json` | Manifest for delayed order detection |
| Order update_shipment_status manifest | `manifests/order.update_shipment_status.manifest.json` | Manifest for shipment status updates |

## Google Workspace tool pack artifacts

The release evidence set includes the Google Workspace read-only tool pack descriptor, safety scan, setup guide, and integration-test documentation.

## Cross-workflow demo story pack artifacts

The portfolio demo v2 now produces a consolidated story pack under `runtime_data/demo_packs/<pack_run_id>/story_pack/`.

| Artifact | Path | Purpose |
|---|---|---|
| Story index Markdown | `runtime_data/demo_packs/<pack_run_id>/story_pack/index.md` | Reviewer-facing narrative summary |
| Story index HTML | `runtime_data/demo_packs/<pack_run_id>/story_pack/index.html` | Browser-friendly evidence pack |
| Story summary JSON | `runtime_data/demo_packs/<pack_run_id>/story_pack/summary.json` | Machine-readable story summary |
| Story evidence manifest | `runtime_data/demo_packs/<pack_run_id>/story_pack/evidence_manifest.json` | Linked artifact inventory |
| Workflow timeline | `runtime_data/demo_packs/<pack_run_id>/story_pack/workflow_timeline.json` | Lane-by-lane execution trace |
| Screenshot checklist | `runtime_data/demo_packs/<pack_run_id>/story_pack/screenshots_checklist.md` | Portfolio capture checklist |

## Readiness scorecard artifacts

| Artifact | Path | Purpose |
|---|---|---|
| Readiness scorecard JSON | `runtime_data/readiness/readiness_scorecard.json` | Machine-readable 90% readiness scorecard |
| Readiness scorecard Markdown | `runtime_data/readiness/readiness_scorecard.md` | Reviewer-facing readiness summary |
| Readiness scorecard HTML | `runtime_data/readiness/readiness_scorecard.html` | Browser-friendly readiness view |
