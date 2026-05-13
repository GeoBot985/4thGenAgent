# Codebase Containment Review

Scope: `src/`, `runtime/`, `tools/`, `bits/`, `optional_tools/`

Method:
- Reviewed module names, import edges, and runtime/UI/report call paths.
- Ran `ruff` on the scoped folders for `F401` and `F811`.
- Applied only import cleanup and package-export cleanup. No runtime behavior changes were intended.

## Inventory Summary

| Folder | Code files | Notes |
|---|---:|---|
| `runtime/` | 144 | Core engine, persistence, validation, tool registry, report builder, and domain tools |
| `src/` | 34 | Tkinter UI, presenters, scenario/demo orchestration, report launchers |
| `tools/` | 29 | CLI utilities, verification, release docs, and external integration helpers |
| `bits/` | 77 | FastAPI/RAG prototype, app services, and RAG utilities |
| `optional_tools/` | 9 | Optional RPA integration surface for Google Messages ABSA |

## Major Module Purposes

### `src/`

- `src/operator_ui.py`
  - Tkinter shell and all view rendering.
  - Owns widget wiring and callback dispatch.
  - Should remain presentation-only.
- `src/operator_presenter.py`
  - Builds the technical demo view model for Operator mode.
  - Converts snapshot/taskframe state into compact UI-facing text.
- `src/demo_story_presenter.py`
  - Builds the business-readable Demo story model.
  - Owns demo-specific story selection, scenario compatibility, and step labels.
- `src/operator_data.py`
  - Normalizes snapshots, manifests, selected-step details, and footer text.
- `src/operator_playback.py`
  - Builds the playback timeline and per-step selected detail payloads.
- `src/operator_demo_runner.py`
  - Runs demo manifests and demo packs.
  - Bridges selected demo configs to runtime execution.
- `src/operator_scenario_runner.py`
  - Runs named scenarios, post-actions, and scenario validation.
- `src/operator_reports.py`
  - Thin UI helper for operator run reports and report-folder access.
- `src/operator_approval_actions.py`
  - Approve/reject/execute actions for staged pending side effects.
- `src/operator_approval_pack.py`
  - Builds the approval pack view used by the UI and reports.
- `src/operator_artifacts.py`
  - Tracks artifact paths and openable artifact state.
- `src/operator_actions.py`
  - Event helpers for UI-driven demo intake.
- `src/operator_customer_inbox_runner.py`
  - Customer inbox processing and demo message intake helpers.
- `src/operator_cross_workflow_demo.py`
  - Cross-workflow demo packs and run summaries.

### `runtime/`

- `runtime/orchestrator.py`
  - Core manifest execution engine.
  - Creates TaskFrames, runs steps, verifies completion, and executes tools.
- `runtime/tool_runner.py`
  - Tool invocation, dry-run/live handling, pending-action staging, and result normalization.
- `runtime/tool_registry.py`
  - Authoritative registry of tools and their metadata.
- `runtime/tool_capability_registry.py`
  - Capability metadata and setup requirements for tools.
- `runtime/tool_health.py`
  - Health probes and setup/availability checks.
- `runtime/tool_setup.py`
  - Setup guidance and safe setup actions.
- `runtime/manifest_loader.py`
  - Manifest parsing, validation, and catalog loading.
- `runtime/manifest_catalog.py`
  - Event-route mapping and manifest lookup helpers.
- `runtime/event_router.py`
  - Routes events to manifests and input mappings.
- `runtime/event_store.py`
  - Event persistence, deduplication, and ingestion.
- `runtime/taskframe.py`
  - TaskFrame model, state transitions, audit events, and output helpers.
- `runtime/persistence.py`
  - Filesystem persistence paths and JSON read/write helpers.
- `runtime/taskframe_reload.py`
  - Reloads persisted TaskFrames back into runtime objects.
- `runtime/run_report.py`
  - Run report builder and HTML/Markdown renderers for operator and demo reports.
- `runtime/evidence_bundle.py`
  - Evidence bundle generation from persisted run artifacts.
- `runtime/failure_summary.py`
  - Failure summary extraction and presentation data.
- `runtime/run_ledger.py`
  - Run ledger records and summary snapshots.
- `runtime/artifact_index.py`
  - Indexes persisted run artifacts.
- `runtime/artifact_cleanup.py`
  - Safe cleanup policy and cleanup candidate evaluation.
- `runtime/validation.py`
  - Validation rules and manifest validation execution.
- `runtime/conditions.py`
  - Conditional rule evaluation helpers.
- `runtime/completion_gate.py`
  - Completion evaluation and final state transitions.
- `runtime/approval_commands.py`
  - Approval command execution for pending actions.
- `runtime/approval.py`
  - Approval event helpers.
- `runtime/live_execution.py`
  - Live execution guardrails and execution control.
- `runtime/live_guardrails.py`
  - Live-side-effect safety checks.
- `runtime/scenario_validation.py`
  - Scenario result validation and expectations.
- `runtime/retention_policy.py`
  - Retention and cleanup policy rules.
- `runtime/retry_policy.py`
  - Retry classification and backoff policy.
- `runtime/inspection.py`
  - Read-only inspection helpers for persisted runs.
- `runtime/inspection_commands.py`
  - CLI-style wrappers over inspection actions.
- `runtime/memory_store.py`, `runtime/memory_commands.py`
  - In-memory demo/LLM state persistence and command wrappers.
- `runtime/business_data.py`, `runtime/business_store.py`, `runtime/business_context.py`, `runtime/company_store.py`
  - Seed data, business record access, and context assembly.
- `runtime/customer_tools.py`, `runtime/domain_customer_tools.py`, `runtime/order_tools.py`, `runtime/shipment_tools.py`, `runtime/payment_tools.py`, `runtime/procurement_tools.py`, `runtime/reconciliation_tools.py`, `runtime/accounting_tools.py`
  - Domain tool implementations used by the tool registry.
- `runtime/message_tools.py`, `runtime/messages_tools.py`
  - Message validation / read tooling. This is a duplicate-looking surface and should be watched for drift.
- `runtime/llm_tools.py`, `runtime/llm_micro_tools.py`, `runtime/llm_prompts.py`, `runtime/llm_adapter.py`, `runtime/llm_commands.py`, `runtime/llm_config.py`
  - LLM adapter, prompts, micro-tools, and command integration.
- `runtime/test_tools.py`
  - Test tool surface registered in the tool registry.

### `tools/`

- `tools/run_release_candidate_verification.py`
  - Release verification orchestrator and compliance checks.
- `tools/write_current_release_status.py`
  - Generates current release status and evidence-pack docs.
- `tools/workspace_tools.py`
  - Workspace-facing helper CLI surface.
- `tools/google_auth.py`
  - Shared Google auth helpers.
- `tools/gobook_tools.py`
  - GoBook RPA helper surface.
- `tools/whatsapp_*`
  - WhatsApp browser/RPA helpers and message search/send wrappers.
- `tools/*calendar*`, `tools/*sheet*`, `tools/*gmail*`
  - Google Workspace integration helpers.
- `tools/capture_portfolio_screenshots.py`
  - Screenshot capture utility for portfolio evidence.

### `bits/`

- `bits/main.py`
  - Separate FastAPI/RAG prototype application.
  - Not part of the current Tkinter demo/report runtime path.
- `bits/app/services/*`
  - Prompting, ingestion, confidence, response formatting, grounding, and RAG services.
- `bits/rag/*`
  - RAG ingestion/search/OCR/layout utilities and manual experiments.
- `bits/models.py`
  - Pydantic request/response models for the FastAPI prototype.
- `bits/ollama_client.py`
  - Ollama client wrapper for the prototype app.

### `optional_tools/`

- `optional_tools/rpa/google_messages_absa/messages_tools.py`
  - Optional browser-backed Google Messages ABSA integration.
- `optional_tools/rpa/google_messages_absa/health.py`
  - Optional health checks for the ABSA integration.
- `optional_tools/rpa/google_messages_absa/registry.py`
  - Registration metadata for the optional integration.
- `optional_tools/rpa/google_messages_absa/tests/*`
  - Optional integration tests for the ABSA surface.

## Boundary Check

### Runtime boundary

- `runtime/` does not import `tkinter`, `ttk`, or UI widgets.
- Runtime owns execution, persistence, validation, reporting, tool registry, and evidence generation.
- Demo-specific presentation text lives in `src/demo_story_presenter.py`, not in runtime orchestration.
- `runtime/run_report.py` is a report builder only. It renders HTML/Markdown from persisted frame data; it does not drive the UI.

### UI/report boundary

- `src/operator_ui.py` imports `src.demo_story_presenter.build_demo_story` and `runtime.run_report.generate_demo_run_report`.
- The Tkinter file renders widgets and routes button actions.
- Business meaning is derived in presenters/report builders, not inside the widget tree.
- `src/demo_story_presenter.py` is the single place for demo story wording and scenario compatibility checks.
- `runtime/run_report.py` is the single place for run-report model construction and HTML/Markdown rendering.

### Orchestration boundary

- `runtime/orchestrator.py` executes manifests and tool steps.
- It uses manifest metadata and TaskFrame state, not demo-only presentation concepts.
- Scenario selection and user-facing labels are handled above runtime in `src/`.
- Business workflow details remain in manifests and tool registry entries.

## Suspected Dead or Legacy Surfaces

These are not proven dead, but they look legacy, utility-only, or duplication-prone:

- `runtime/message_tools.py`
  - Singular message tool surface that overlaps with `runtime/messages_tools.py`.
  - Keep an eye on this pair for drift or aliasing cleanup.
- `bits/main.py`
  - Separate FastAPI/RAG prototype, not part of the current demo/report flow.
- `bits/rag/manual_test_rag.py`
  - Manual harness only.
- `runtime/test_tools.py`
  - Registry-backed test surface rather than production workflow code.
- `optional_tools/rpa/google_messages_absa/tests/*`
  - Optional integration tests, not core runtime behavior.

## Duplicate Responsibility Areas

- `src/operator_demo_runner.py` and `src/operator_scenario_runner.py`
  - Both turn a selected scenario into a run, but for different entry points.
- `src/operator_presenter.py` and `src/demo_story_presenter.py`
  - Both build view models from runtime state, but one is technical and one is business-readable.
- `runtime/run_report.py` and `src/operator_reports.py`
  - Report generation vs. UI entrypoint for opening reports.
- `runtime/manifest_loader.py` and `runtime/manifest_catalog.py`
  - Closely related manifest loading and routing responsibilities.
- `runtime/message_tools.py` and `runtime/messages_tools.py`
  - Similar naming and adjacent responsibilities; highest drift risk in this review.
- `runtime/tool_registry.py` and `runtime/tool_capability_registry.py`
  - Tool registration and capability metadata should stay aligned.

## Safe Cleanup Performed

- Removed unused imports across the scoped folders.
- Fixed one duplicate import redefinition in `bits/main.py`.
- Kept `runtime/__init__.py` as an explicit re-export surface with `__all__` so the package API stays stable.
- No dead functions were removed because this review did not prove any were unused by tests.

## Verification

Completed successfully after the cleanup:

- `python -m ruff check src runtime tools bits optional_tools --select F401,F811`
- `python -m pytest`
- `python scripts/run_golden_demo.py`
- `python scripts/run_release_verification.py`

## Notes

- The repository has a large surface area, but the runtime/demo/report/UI split is now reasonably contained.
- The highest-risk coupling area remains the message-tool naming overlap and the dual presenter/report path.
- Further simplification should focus on consolidation, not more presentation logic inside `runtime/`.
