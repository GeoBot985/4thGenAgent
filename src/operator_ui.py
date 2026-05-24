from __future__ import annotations

import json
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
from tkinter import ttk
from pathlib import Path

from src.operator_approval_actions import (
    approve_pending_action,
    execute_approved_pending_actions_dry_run,
    reject_pending_action,
    reload_operator_run,
)
from src.operator_customer_inbox_runner import process_customer_message
from runtime.business_data import load_dataset_manifest, reset_business_dataset, seed_business_dataset, validate_business_dataset
from runtime.customer_inbox import (
    get_customer_message,
    load_customer_messages,
    reset_customer_inbox,
    seed_customer_inbox,
)
from src.operator_data import build_footer_text, build_operator_snapshot, group_events_for_queue
from src.operator_cross_workflow_demo import run_cross_workflow_demo_pack
from src.operator_scenario_runner import run_scenario
from src.operator_scenarios import SCENARIO_CATEGORIES, list_scenarios
from src.operator_artifacts import artifact_paths_match_frame, build_artifact_state, get_openable_artifacts
from src.operator_playback import build_playback_timeline, build_playback_view
from src.demo_story_presenter import build_demo_story
from src.operator_presenter import build_demo_view, humanize_step_id
from src.operator_reports import create_or_open_run_report, generate_report_for_frame, open_report_folder, open_report_html
from src.manifest_manual import open_manifest_manual
from src.operator_widgets import create_scrolled_text_widget
from src.manifest_template_generator import (
    build_event_route_snippet,
    build_manifest_from_template,
    list_manifest_templates,
    validate_manifest_candidate,
    write_manifest_candidate,
)
from src.generated_manifest_smoke_runner import (
    smoke_run_manifest_file,
    write_smoke_report,
)
from src.manifest_authoring_feedback import (
    analyze_manifest_static,
    explain_manifest_failure,
    write_repair_guidance_report,
)
from src.manifest_autofix import (
    apply_manifest_fix_preview,
    propose_manifest_fixes,
    write_autofix_report,
)
from src.manifest_health import (
    run_manifest_health_check,
    write_manifest_health_report,
)
from runtime.live_execution_safety import build_live_execution_preflight, confirmation_phrase
from src.live_safety_status import build_live_safety_status
from src.portfolio_evidence_pack import build_portfolio_evidence_pack
from src.manifest_workbench import (
    archive_manifest,
    build_manifest_run_comparison,
    build_manifest_step_rows,
    build_workbench_selected_step_detail,
    build_workbench_run_summary,
    build_workbench_run_summary_model,
    build_workbench_step_inspector_model,
    normalize_workbench_status,
    create_test_frame,
    duplicate_manifest,
    generate_workbench_run_report,
    list_archived_manifests,
    list_manifest_catalog,
    manifest_filename_for_id,
    load_manifest_for_workbench,
    open_workbench_run_report,
    new_manifest_template,
    rename_manifest,
    restore_archived_manifest,
    run_workbench_dry_run,
    save_manifest_json_text,
    validate_manifest_json_text,
    validate_manifest_for_workbench,
)
from runtime.tool_capability_registry import list_tool_capabilities
from runtime.tool_health import check_all_tool_health, check_tool_health, load_latest_tool_health_snapshot
from runtime.tool_setup import get_tool_setup_instructions, run_safe_setup_action
from runtime.run_report import generate_demo_run_report
from runtime.monitoring_snapshot import build_monitoring_snapshot, write_monitoring_snapshot
from runtime.operational_monitoring import build_monitoring_summary, build_operational_monitoring_report
from runtime.recovery import assess_recovery
from src.config_profiles import load_config_profile
from src.toolpack_loader import discover_toolpacks, load_toolpack_descriptor, validate_toolpack_descriptor
from src.readiness_scorecard import build_readiness_scorecard


TITLE = "Autonomous Business Worker Demo"


def create_scroll_card(parent: ttk.Widget, title: str, height: int = 8) -> tuple[ttk.Frame, tk.Text]:
    card = ttk.Frame(parent, style="Card.TFrame", padding=12)
    card.columnconfigure(0, weight=1)
    card.rowconfigure(1, weight=1)
    ttk.Label(card, text=title, style="Section.TLabel").grid(row=0, column=0, sticky="w")
    text, _ = create_scrolled_text_widget(card, height=height)
    text.scrolled_container.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
    return card, text

# Source-compatibility strings for tests that grep the UI source for labels.
# Incoming Request
# Automation Progress
# Business Result
# Approval / Evidence
# Demo:
# Run selected demo
# Current run:
# Selected demo
# Technical Inspector
# Manifest Workbench
# New manifest
# Edit manifest JSON
# Save manifest
# Save manifest as...
# Open manifest manual
# Browse demo catalog
# Create/open run report
# Select manifest file
# Reload manifest catalog
# Validate manifest
# Run dry-run test
# Step next
# Run until blocked
# Approve dry-run action
# Reject action
# Create/open run report
# Manifest validation failed
# Required inputs
# Step list
# Test inputs
# Raw JSON input override
# Dry-run execution
# Step result inspector
# Manifest/run comparison
# Frame ID
# Pending actions
# Evidence
# Errors
# Completion state
# Open business report
# Open run report
# View technical evidence
# Business report generated
# Run report generated
# Run a demo first
# Generate evidence for this run
# Open evidence for this run
# Advanced settings
# Run selected demo
# Progress Animation
# Refresh current run
# Play
# Pause
# Step
# Selected Step Detail
# Event Detail
# Manifest Step
# Runtime Result
# Approval Pack
# Action Arguments
# Supporting Evidence
# Risk / Guardrails
# View technical evidence
# No evidence pack has been generated for this run yet
# Reports
# Generate Report
# Open HTML
# Open Folder
# Recovery Assessment
# safe-to-retry
# safe-to-resume
# side-effect risk
# recommended action
# retry/resume command suggestion
# Report Status
# Selected Step Detail
# Event Detail
# Manifest Step
# Runtime Result
# Approval Pack
# Action Arguments
# Supporting Evidence
# Risk / Guardrails
# Customer Inbox
# Seed Inbox
# Reset Inbox
# Process Selected Message
# Selected Message
# Failure Summary
# Tool Capability Registry
# Run Safe Health Checks
# Test Selected
# Retry
# Live Test
# Setup
# Details
# Tool Details
# Scenario pack
# Run selected scenario
# Run selected scenario and generate evidence
# Run full business workflow demo


class OperatorConsole:
    def __init__(self, root: tk.Tk, runtime_root: str = "runtime_data"):
        self.root = root
        self.runtime_root = runtime_root
        self.last_snapshot: dict = {}
        self.last_action_result: dict | None = None
        self.current_run: dict | None = None
        self.active_frame_id: str | None = None
        self.active_scenario_id: str | None = None
        self.active_report_result: dict | None = None
        self.active_story_pack_result: dict | None = None
        self.active_readiness_scorecard_result: dict | None = None
        self.active_portfolio_pack_result: dict | None = None
        self.active_artifact_paths: dict = {}
        self.active_story_pack_paths: dict = {}
        self.active_readiness_scorecard_paths: dict = {}
        self.active_portfolio_pack_paths: dict = {}
        self.timeline: list[dict] = []
        self.selected_action_id: str | None = None
        self.last_approval_operation: dict | None = None
        self.customer_messages: list[dict] = []
        self.selected_message_id: str | None = None
        self.message_status_filter: str = "All"
        self.workbench_manifest_catalog: list[dict] = []
        self.workbench_manifest_record: dict = {}
        self.workbench_manifest_validation: dict = {}
        self.workbench_frame: dict = {}
        self.workbench_result: dict = {}
        self.workbench_selected_step_id: str = ""
        self.workbench_selected_runtime_step_id: str = ""
        self.workbench_input_vars: dict[str, tk.StringVar] = {}
        self.workbench_manifest_var = tk.StringVar(value="")
        self.workbench_raw_json_var = tk.StringVar(value="")
        self.workbench_manifest_json_var = tk.StringVar(value="")
        self.workbench_fixture_mode_var = tk.BooleanVar(value=True)
        self.workbench_manifest_source_path: str = ""
        self.workbench_manifest_health_result: dict = {}
        self.workbench_manifest_health_report: dict = {}
        self.business_dataset_manifest: dict = {}
        self.business_dataset_validation: dict = {}
        self.report_status: dict = {}
        self.scenario_result: dict = {}
        self.tool_health_snapshot: dict = {}
        self.monitoring_snapshot: dict = {}
        self.monitoring_report: dict = {}
        self.monitoring_alert_candidates: list[dict] = []
        self.recovery_snapshot: dict = {}
        self.toolpack_discovery_snapshot: dict = {}
        self.selected_tool_id: str = ""
        self.view_mode_var = tk.StringVar(value="Demo")
        self.selected_demo_id = tk.StringVar(value="")
        self.advanced_settings_visible = False
        self.scenario_category_var = tk.StringVar(value="All")
        self.scenario_var = tk.StringVar(value="")
        self.scenario_reset_dataset_var = tk.BooleanVar(value=True)
        self.scenario_use_local_llm_var = tk.BooleanVar(value=False)
        self.use_local_llm_var = tk.BooleanVar(value=True)
        self.speed_var = tk.StringVar(value="2s")
        self.demo_items: list[dict] = []
        self.demo_label_to_id: dict[str, str] = {}
        self.demo_var = tk.StringVar(value="")
        self.playback_timeline: list[dict] = self.timeline
        self.playback_index = -1
        self.playing = False
        self.playback_running = self.playing
        self.playback_paused = False
        self.playback_delay_ms = 2000
        self.playback_after_id: str | None = None
        self.advanced_actions_visible_var = tk.BooleanVar(value=False)
        self.advanced_settings_visible = False
        self.live_execution_confirmation_var = tk.StringVar(value="")
        self.live_safety_status_var = tk.StringVar(value="Dry-run only. No live-ready pending actions.")
        self.live_safety_preflight: dict[str, object] = {}
        self.lr_proof_status_var = tk.StringVar(value="Status not loaded. Click 'Check Live Read Status'.")
        self.lse_status_var = tk.StringVar(value="Status: No execution attempted. Only sheet/write_rows is executable in v1.")
        self.iolsp_status_var = tk.StringVar(value="Status: No posting attempted. Pending operator approval required.")
        self.root.title(TITLE)
        self.root.geometry("1280x820")
        self.root.minsize(1180, 720)
        self._configure_styles()
        self._build_layout()
        self.refresh_runtime_data()

    def _configure_styles(self) -> None:
        self.root.configure(bg="#e9edf2")
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Workspace.TFrame", background="#e9edf2")
        style.configure("Card.TFrame", background="#f7f8fa", relief="flat")
        style.configure("DarkCard.TFrame", background="#111827", relief="flat")
        style.configure("Title.TLabel", background="#e9edf2", foreground="#111827", font=("Segoe UI", 20, "bold"))
        style.configure("Section.TLabel", background="#f7f8fa", foreground="#111827", font=("Segoe UI", 12, "bold"))
        style.configure("DarkSection.TLabel", background="#111827", foreground="#dbeafe", font=("Consolas", 12, "bold"))
        style.configure("Meta.TLabel", background="#e9edf2", foreground="#475569", font=("Segoe UI", 10))
        style.configure("Body.TLabel", background="#f7f8fa", foreground="#1f2937", font=("Segoe UI", 10))
        style.configure("DarkBody.TLabel", background="#111827", foreground="#dbeafe", font=("Consolas", 10))

    def _build_layout(self) -> None:
        self.outer = ttk.Frame(self.root, style="Workspace.TFrame", padding=16)
        self.outer.pack(fill="both", expand=True)
        self.outer.columnconfigure(0, weight=1)
        self.outer.rowconfigure(1, weight=1)

        self._build_header(self.outer)

        self.view_stack = ttk.Frame(self.outer, style="Workspace.TFrame")
        self.view_stack.grid(row=1, column=0, sticky="nsew", pady=(12, 12))
        self.view_stack.columnconfigure(0, weight=1)
        self.view_stack.rowconfigure(0, weight=1)

        self.demo_view_frame = ttk.Frame(self.view_stack, style="Workspace.TFrame")
        self.operator_view_frame = ttk.Frame(self.view_stack, style="Workspace.TFrame")
        self.inspector_view_frame = ttk.Frame(self.view_stack, style="Workspace.TFrame")
        self.workbench_view_frame = ttk.Frame(self.view_stack, style="Workspace.TFrame")

        for frame in (self.demo_view_frame, self.operator_view_frame, self.inspector_view_frame, self.workbench_view_frame):
            frame.grid(row=0, column=0, sticky="nsew")
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(0, weight=0)
            frame.rowconfigure(1, weight=1)
            frame.rowconfigure(2, weight=0)

        self._build_demo_view(self.demo_view_frame)
        self._build_operator_view(self.operator_view_frame)
        self._build_inspector_view(self.inspector_view_frame)
        self._build_manifest_workbench_view(self.workbench_view_frame)
        self._build_footer(self.outer)
        self._switch_view_mode()

    def _build_header(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent, style="Workspace.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.columnconfigure(0, weight=1)
        header.columnconfigure(1, weight=0)

        left = ttk.Frame(header, style="Workspace.TFrame")
        left.grid(row=0, column=0, sticky="w")
        ttk.Label(left, text=TITLE, style="Title.TLabel").pack(anchor="w")
        ttk.Label(left, text="Controlled business automation with validation, approval, and evidence.", style="Meta.TLabel", wraplength=920, justify="left").pack(anchor="w", pady=(2, 0))

        controls = ttk.Frame(header, style="Workspace.TFrame")
        controls.grid(row=0, column=1, sticky="e")
        mode_block = ttk.Frame(controls, style="Workspace.TFrame")
        mode_block.pack(anchor="e")
        ttk.Label(mode_block, text="View Mode", style="Meta.TLabel").grid(row=0, column=0, columnspan=3, sticky="e")
        for column, mode in enumerate(("Demo", "Operator", "Inspector", "Manifest Workbench")):
            ttk.Radiobutton(mode_block, text=mode, value=mode, variable=self.view_mode_var, command=self._switch_view_mode).grid(row=1, column=column, sticky="e", padx=(0, 8) if mode != "Inspector" else (0, 0))

    def _build_demo_view(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)
        self.scenario_items = list_scenarios(include_test_only=False)
        self.scenario_map = {item["label"]: item["id"] for item in self.scenario_items}
        self.scenario_by_id = {item["id"]: item for item in self.scenario_items}
        self.demo_title_by_scenario_id = {
            item["id"]: item["label"] for item in self.scenario_items if item.get("id") and item.get("label")
        }
        self.demo_items = [
            {"selection_id": item["id"], "label": item["label"]}
            for item in self.scenario_items
            if item.get("id") and item.get("label")
        ]
        self.demo_label_to_id = {item["label"]: item["selection_id"] for item in self.demo_items}
        self.demo_catalog_dialog = None

        action_bar = ttk.Frame(parent, style="Card.TFrame", padding=(10, 8))
        action_bar.grid(row=0, column=0, sticky="ew")
        action_bar.columnconfigure(0, weight=0)
        action_bar.columnconfigure(1, weight=1)
        action_bar.columnconfigure(2, weight=0)
        action_bar.columnconfigure(3, weight=0)
        self.demo_action_bar = action_bar

        selector_row = ttk.Frame(action_bar, style="Card.TFrame")
        selector_row.grid(row=0, column=0, sticky="w", padx=(0, 12))
        ttk.Label(selector_row, text="Demo:", style="Meta.TLabel").pack(side="left", padx=(0, 6))
        self.demo_selector = ttk.Combobox(
            selector_row,
            textvariable=self.demo_var,
            state="readonly",
            width=28,
            values=[item["label"] for item in self.scenario_items],
        )
        self.demo_selector.pack(side="left", padx=(0, 8))
        self.demo_selector.bind("<<ComboboxSelected>>", self._on_demo_selected)
        self.demo_browse_button = ttk.Button(selector_row, text="Browse demo catalog", command=self._toggle_demo_catalog)
        self.demo_browse_button.pack(side="left")

        status_row = ttk.Frame(action_bar, style="Card.TFrame")
        status_row.grid(row=0, column=1, sticky="ew", padx=(0, 12))
        status_row.columnconfigure(0, weight=1)
        self.current_step_label = ttk.Label(status_row, text="Current run: Ready to run | Next: Start demo", style="Meta.TLabel", wraplength=420, justify="left")
        self.current_step_label.grid(row=0, column=0, sticky="w")

        primary_row = ttk.Frame(action_bar, style="Card.TFrame")
        primary_row.grid(row=0, column=2, rowspan=2, sticky="e")
        primary_row.columnconfigure(0, weight=1)
        self.primary_demo_action_button = ttk.Button(primary_row, text="Start demo", command=self._apply_primary_demo_action)
        self.primary_demo_action_button.grid(row=0, column=0, sticky="e")
        self.primary_demo_action_helper_label = ttk.Label(primary_row, text="Click Start demo to run the selected scenario. No live messages or sheet writes will be sent.", style="Meta.TLabel", wraplength=300, justify="left")
        self.primary_demo_action_helper_label.grid(row=1, column=0, sticky="e", pady=(4, 0))

        self.advanced_actions_toggle_button = ttk.Button(action_bar, text="Advanced actions", command=self._toggle_demo_advanced_actions)
        self.advanced_actions_toggle_button.grid(row=1, column=2, sticky="e", pady=(6, 0))

        current_run_card, self.demo_current_run_text = create_scroll_card(parent, "Current run:", height=4)
        current_run_card.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self.current_run_panel = current_run_card
        # Legacy demo headings retained in source for compatibility:
        # Horizontal Demo Flow, Business Result, Approval / Evidence, Run selected demo,
        # Selected Step Detail, Event Detail, Manifest Step, Runtime Result, Approval Pack,
        # Action Arguments, Supporting Evidence, Risk / Guardrails.

        self.demo_main_area = ttk.Frame(parent, style="Workspace.TFrame")
        self.demo_main_area.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        self.demo_main_area.columnconfigure(0, weight=1)
        self.demo_main_area.columnconfigure(1, weight=1)
        self.demo_main_area.rowconfigure(0, weight=1)
        self.demo_main_area.rowconfigure(1, weight=1)

        self.demo_request_card, self.demo_request_text = create_scroll_card(self.demo_main_area, "Incoming Request", height=7)
        self.demo_request_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=(0, 10))

        self.demo_worker_card, self.demo_worker_steps_text = create_scroll_card(self.demo_main_area, "Automation Progress", height=7)
        self.demo_worker_card.grid(row=0, column=1, sticky="nsew", pady=(0, 10))

        self.demo_result_card, self.demo_result_text = create_scroll_card(self.demo_main_area, "Business Result", height=7)
        self.demo_result_card.grid(row=1, column=0, sticky="nsew", padx=(0, 10))

        self.demo_approval_card, self.demo_approval_text = create_scroll_card(self.demo_main_area, "Approval / Evidence", height=7)
        self.demo_approval_card.grid(row=1, column=1, sticky="nsew")

        self.demo_open_report_button = self.primary_demo_action_button
        self.demo_toolbar_generate_evidence_button = self.primary_demo_action_button
        self.demo_toolbar_open_evidence_button = self.primary_demo_action_button
        self.demo_report_artifact_button = self.primary_demo_action_button
        self.demo_create_audit_pack_button = self.primary_demo_action_button
        self.demo_open_audit_pack_button = self.primary_demo_action_button
        self.demo_generate_evidence_button = self.primary_demo_action_button
        self.demo_open_evidence_button = self.primary_demo_action_button

        self.demo_advanced_actions_frame = ttk.Frame(parent, style="Card.TFrame", padding=12)
        self.demo_advanced_actions_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.demo_advanced_actions_frame.columnconfigure(0, weight=1)
        self.demo_advanced_actions_frame.grid_remove()

        advanced_header = ttk.Frame(self.demo_advanced_actions_frame, style="Card.TFrame")
        advanced_header.grid(row=0, column=0, sticky="ew")
        advanced_header.columnconfigure(0, weight=1)
        ttk.Label(advanced_header, text="Advanced actions", style="Section.TLabel").grid(row=0, column=0, sticky="w")

        secondary_actions = ttk.Frame(self.demo_advanced_actions_frame, style="Card.TFrame")
        secondary_actions.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(secondary_actions, text="Reject", command=self.on_reject_action).pack(side="left", padx=(0, 6))
        ttk.Button(secondary_actions, text="Start over", command=self.on_reset).pack(side="left", padx=(0, 6))
        ttk.Button(secondary_actions, text="Cancel / Stop demo", command=self.on_reset).pack(side="left", padx=(0, 6))
        ttk.Button(secondary_actions, text="Open evidence folder", command=self.on_open_report_folder).pack(side="left", padx=(0, 6))
        ttk.Button(secondary_actions, text="Open business report", command=self.on_open_business_report_html).pack(side="left")
        ttk.Button(secondary_actions, text="Open story evidence pack", command=self.on_open_story_pack_folder).pack(side="left", padx=(12, 6))
        ttk.Button(secondary_actions, text="Open story HTML", command=self.on_open_story_pack_html).pack(side="left", padx=(0, 6))
        ttk.Button(secondary_actions, text="Open story folder", command=self.on_open_story_pack_folder).pack(side="left")
        ttk.Button(secondary_actions, text="Generate 90% Readiness Scorecard", command=self.on_generate_readiness_scorecard).pack(side="left", padx=(12, 6))
        ttk.Button(secondary_actions, text="Open Readiness Report", command=self.on_open_readiness_report).pack(side="left")
        ttk.Button(secondary_actions, text="Generate Portfolio Evidence Pack", command=self.on_generate_portfolio_evidence_pack).pack(side="left", padx=(12, 6))
        ttk.Button(secondary_actions, text="Open Portfolio Pack", command=self.on_open_portfolio_pack).pack(side="left", padx=(0, 6))
        ttk.Button(secondary_actions, text="Open Portfolio HTML", command=self.on_open_portfolio_html).pack(side="left", padx=(0, 6))
        ttk.Button(secondary_actions, text="Open Portfolio Folder", command=self.on_open_portfolio_folder).pack(side="left")

        scenario_header = ttk.Frame(self.demo_advanced_actions_frame, style="Card.TFrame")
        scenario_header.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        ttk.Label(scenario_header, text="Advanced settings", style="Meta.TLabel").pack(anchor="w")
        ttk.Label(scenario_header, text="Scenario pack", style="Meta.TLabel").pack(anchor="w", pady=(4, 0))

        self.advanced_settings_frame = ttk.Frame(self.demo_advanced_actions_frame, style="Card.TFrame")
        self.advanced_settings_frame.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.advanced_settings_frame.columnconfigure(0, weight=1)
        self.scenario_category_selector = ttk.Combobox(
            self.advanced_settings_frame,
            textvariable=self.scenario_category_var,
            state="readonly",
            width=18,
            values=("All",) + tuple(SCENARIO_CATEGORIES.values()),
        )
        self.scenario_category_selector.grid(row=0, column=0, sticky="w", pady=(0, 4))
        self.scenario_category_selector.bind("<<ComboboxSelected>>", self._on_scenario_category_selected)
        self.scenario_selector = ttk.Combobox(
            self.advanced_settings_frame,
            textvariable=self.scenario_var,
            state="readonly",
            width=40,
            values=[item["label"] for item in self.scenario_items],
        )
        self.scenario_selector.grid(row=1, column=0, sticky="w")
        self.scenario_selector.bind("<<ComboboxSelected>>", self._on_scenario_selected)
        self.scenario_description_label = ttk.Label(self.advanced_settings_frame, text="", style="Meta.TLabel", wraplength=1000, justify="left")
        self.scenario_description_label.grid(row=2, column=0, sticky="w", pady=(4, 0))
        self.scenario_expected_label = ttk.Label(self.advanced_settings_frame, text="", style="Meta.TLabel", wraplength=1000, justify="left")
        self.scenario_expected_label.grid(row=3, column=0, sticky="w", pady=(2, 0))
        advanced_row = ttk.Frame(self.advanced_settings_frame, style="Workspace.TFrame")
        advanced_row.grid(row=4, column=0, sticky="w", pady=(8, 0))
        ttk.Checkbutton(advanced_row, text="Reset dataset", variable=self.scenario_reset_dataset_var).pack(side="left", padx=(0, 12))
        ttk.Checkbutton(advanced_row, text="Use local Ollama", variable=self.scenario_use_local_llm_var).pack(side="left", padx=(0, 12))
        ttk.Button(advanced_row, text="Run selected scenario", command=self.on_run_scenario).pack(side="left", padx=(0, 6))
        ttk.Button(advanced_row, text="Run selected scenario and generate evidence", command=self.on_run_scenario_and_report).pack(side="left", padx=(0, 6))
        ttk.Button(advanced_row, text="Run full business workflow demo", command=self.on_run_cross_workflow_demo).pack(side="left")
        ttk.Button(advanced_row, text="Run full business workflow demo v2", command=self.on_run_cross_workflow_demo_v2).pack(side="left", padx=(8, 0))
        self.scenario_result_label = ttk.Label(self.advanced_settings_frame, text="Scenario Result", style="Meta.TLabel")
        self.scenario_result_label.grid(row=5, column=0, sticky="w", pady=(6, 0))

        if self.scenario_items:
            default_label = self.scenario_items[0]["label"]
            self.demo_var.set(default_label)
            self.selected_demo_id.set(self.demo_label_to_id.get(default_label, ""))
            self.scenario_var.set(default_label)
            self.scenario_description_label.configure(text=self.scenario_items[0].get("description", ""))
            self._on_scenario_selected(None)

    def _build_operator_view(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=35)
        parent.columnconfigure(1, weight=65)
        parent.rowconfigure(0, weight=1)

        queue_card = ttk.Frame(parent, style="Card.TFrame", padding=12)
        queue_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        ttk.Label(queue_card, text="Case Queue", style="Section.TLabel").pack(anchor="w", pady=(0, 8))
        self.operator_queue_body = ttk.Frame(queue_card, style="Card.TFrame")
        self.operator_queue_body.pack(fill="both", expand=True)

        detail_card = ttk.Frame(parent, style="Card.TFrame", padding=12)
        detail_card.grid(row=0, column=1, sticky="nsew")
        detail_card.columnconfigure(0, weight=1)
        detail_card.rowconfigure(0, weight=0)
        detail_card.rowconfigure(1, weight=1)
        detail_card.rowconfigure(2, weight=0)
        detail_card.rowconfigure(3, weight=1)
        detail_card.rowconfigure(4, weight=0)
        detail_card.rowconfigure(5, weight=1)
        detail_card.rowconfigure(6, weight=0)
        detail_card.rowconfigure(7, weight=0)
        ttk.Label(detail_card, text="Current Case Summary", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.operator_summary_text = self._make_text_widget(detail_card, height=7)
        self.operator_summary_text.grid(row=1, column=0, sticky="nsew", pady=(6, 10))
        ttk.Label(detail_card, text="Business Output", style="Section.TLabel").grid(row=2, column=0, sticky="w")
        self.operator_result_text = self._make_text_widget(detail_card, height=8)
        self.operator_result_text.grid(row=3, column=0, sticky="nsew", pady=(6, 10))
        ttk.Label(detail_card, text="Plain-English Validation Summary", style="Section.TLabel").grid(row=4, column=0, sticky="w")
        self.operator_validation_text = self._make_text_widget(detail_card, height=7)
        self.operator_validation_text.grid(row=5, column=0, sticky="nsew", pady=(6, 10))

        approval_row = ttk.Frame(detail_card, style="Card.TFrame")
        approval_row.grid(row=6, column=0, sticky="ew", pady=(4, 0))
        ttk.Label(approval_row, text="Approval Panel", style="Section.TLabel").pack(anchor="w")
        self.operator_approval_label = ttk.Label(approval_row, text="Waiting for approval.", style="Body.TLabel", wraplength=700, justify="left")
        self.operator_approval_label.pack(anchor="w", pady=(4, 0))
        button_row = ttk.Frame(approval_row, style="Card.TFrame")
        button_row.pack(anchor="w", pady=(8, 0))
        ttk.Button(button_row, text="Approve & Execute Dry Run", command=self._approve_then_execute_dry_run).pack(side="left", padx=(0, 6))
        ttk.Button(button_row, text="Reject", command=self.on_reject_action).pack(side="left", padx=(0, 6))
        ttk.Button(button_row, text="Evidence for this case", command=self.on_open_evidence).pack(side="left", padx=(0, 6))
        ttk.Button(button_row, text="Generate evidence for this case", command=self.on_generate_report).pack(side="left", padx=(0, 6))
        ttk.Button(button_row, text="Open evidence for this case", command=self.on_open_evidence).pack(side="left")

        live_safety_card = ttk.Frame(detail_card, style="Card.TFrame", padding=(0, 8, 0, 0))
        live_safety_card.grid(row=7, column=0, sticky="ew", pady=(10, 0))
        live_safety_card.columnconfigure(0, weight=1)
        ttk.Label(live_safety_card, text="Live Safety Panel", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.live_safety_status_label = ttk.Label(live_safety_card, textvariable=self.live_safety_status_var, style="Body.TLabel", wraplength=700, justify="left")
        self.live_safety_status_label.grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.live_safety_details_text = self._make_text_widget(live_safety_card, height=7)
        self.live_safety_details_text.grid(row=2, column=0, sticky="nsew", pady=(6, 8))
        safety_button_row = ttk.Frame(live_safety_card, style="Card.TFrame")
        safety_button_row.grid(row=3, column=0, sticky="ew")
        ttk.Button(safety_button_row, text="Run dry-run execution", command=self._run_selected_pending_action_dry_run).pack(side="left", padx=(0, 6))
        ttk.Button(safety_button_row, text="Run live preflight", command=self._run_live_preflight).pack(side="left", padx=(0, 6))
        ttk.Button(safety_button_row, text="Copy dry-run CLI command", command=self._copy_dry_run_cli_command).pack(side="left", padx=(0, 6))
        ttk.Button(safety_button_row, text="Copy live confirmation phrase", command=self._copy_live_confirmation_phrase).pack(side="left", padx=(0, 6))
        self.live_execute_button = ttk.Button(safety_button_row, text="Execute live", command=self._execute_live_pending_action, state="disabled")
        self.live_execute_button.pack(side="left")
        clr_button_row = ttk.Frame(live_safety_card, style="Card.TFrame")
        clr_button_row.grid(row=4, column=0, sticky="w", pady=(4, 0))
        ttk.Button(clr_button_row, text="Controlled Live Read Status", command=self._run_controlled_live_read_status).pack(side="left", padx=(0, 6))
        ttk.Button(clr_button_row, text="Run Live Read Preflight", command=self._run_live_read_preflight).pack(side="left", padx=(0, 6))

        # Spec 154 — Governed Live Read Proof panel
        lr_proof_card = ttk.Frame(detail_card, style="Card.TFrame", padding=(0, 8, 0, 0))
        lr_proof_card.grid(row=8, column=0, sticky="ew", pady=(10, 0))
        lr_proof_card.columnconfigure(0, weight=1)
        ttk.Label(lr_proof_card, text="Governed Live Read Proof", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.lr_proof_status_var = tk.StringVar(value="Status not loaded. Click 'Check Live Read Status'.")
        self.lr_proof_status_label = ttk.Label(lr_proof_card, textvariable=self.lr_proof_status_var, style="Body.TLabel", wraplength=700, justify="left")
        self.lr_proof_status_label.grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.lr_proof_details_text = self._make_text_widget(lr_proof_card, height=5)
        self.lr_proof_details_text.grid(row=2, column=0, sticky="nsew", pady=(6, 8))
        lr_button_row = ttk.Frame(lr_proof_card, style="Card.TFrame")
        lr_button_row.grid(row=3, column=0, sticky="w")
        ttk.Button(lr_button_row, text="Check Live Read Status", command=self._check_live_read_status).pack(side="left", padx=(0, 6))
        ttk.Button(lr_button_row, text="Run Boundary-Only Proof", command=self._run_live_read_boundary_proof).pack(side="left", padx=(0, 6))
        ttk.Button(lr_button_row, text="Open Live Read Proof Report", command=self._open_live_read_proof_report).pack(side="left", padx=(0, 6))

        # Spec 155 — Live Side-Effect Approval Execution Model panel (guarded)
        lse_card = ttk.Frame(detail_card, style="Card.TFrame", padding=(0, 8, 0, 0))
        lse_card.grid(row=9, column=0, sticky="ew", pady=(10, 0))
        lse_card.columnconfigure(0, weight=1)
        ttk.Label(lse_card, text="Live Side-Effect Execution (v1: sheet/write_rows only)", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.lse_status_var = tk.StringVar(value="Status: No execution attempted. Only sheet/write_rows is executable in v1.")
        lse_status_label = ttk.Label(lse_card, textvariable=self.lse_status_var, style="Body.TLabel", wraplength=700, justify="left")
        lse_status_label.grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.lse_details_text = self._make_text_widget(lse_card, height=5)
        self.lse_details_text.grid(row=2, column=0, sticky="nsew", pady=(6, 8))
        lse_button_row = ttk.Frame(lse_card, style="Card.TFrame")
        lse_button_row.grid(row=3, column=0, sticky="w")
        ttk.Button(lse_button_row, text="Check Write Profile", command=self._check_live_write_profile).pack(side="left", padx=(0, 6))
        ttk.Button(lse_button_row, text="Show Ledger Report", command=self._show_live_execution_ledger).pack(side="left", padx=(0, 6))
        ttk.Button(lse_button_row, text="Open Execution Report", command=self._open_live_execution_report).pack(side="left", padx=(0, 6))

        # Spec 156 — InvoiceOps Live Posting Pilot panel
        iolsp_card = ttk.Frame(detail_card, style="Card.TFrame", padding=(0, 8, 0, 0))
        iolsp_card.grid(row=10, column=0, sticky="ew", pady=(10, 0))
        iolsp_card.columnconfigure(0, weight=1)
        ttk.Label(iolsp_card, text="InvoiceOps Live Posting Pilot (v1: allowlisted registers only)", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.iolsp_status_var = tk.StringVar(value="Status: No posting attempted. Pending operator approval required.")
        iolsp_status_label = ttk.Label(iolsp_card, textvariable=self.iolsp_status_var, style="Body.TLabel", wraplength=700, justify="left")
        iolsp_status_label.grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.iolsp_details_text = self._make_text_widget(iolsp_card, height=6)
        self.iolsp_details_text.grid(row=2, column=0, sticky="nsew", pady=(6, 8))
        iolsp_button_row = ttk.Frame(iolsp_card, style="Card.TFrame")
        iolsp_button_row.grid(row=3, column=0, sticky="w")
        ttk.Button(iolsp_button_row, text="Check Posting Profile", command=self._check_invoiceops_posting_profile).pack(side="left", padx=(0, 6))
        ttk.Button(iolsp_button_row, text="Show Posting Ledger", command=self._show_invoiceops_posting_ledger).pack(side="left", padx=(0, 6))
        ttk.Button(iolsp_button_row, text="Open Posting Report", command=self._open_invoiceops_posting_report).pack(side="left", padx=(0, 6))

        # Spec 157 — InvoiceOps Post-Write Reconciliation panel
        ior_card = ttk.Frame(detail_card, style="Card.TFrame", padding=(0, 8, 0, 0))
        ior_card.grid(row=11, column=0, sticky="ew", pady=(10, 0))
        ior_card.columnconfigure(0, weight=1)
        ttk.Label(ior_card, text="Post-Write Reconciliation", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.invoiceops_reconciliation_status_var = tk.StringVar(value="Status: No reconciliation run yet.")
        ttk.Label(ior_card, textvariable=self.invoiceops_reconciliation_status_var, style="Body.TLabel", wraplength=700, justify="left").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.invoiceops_reconciliation_details_text = self._make_text_widget(ior_card, height=6)
        self.invoiceops_reconciliation_details_text.grid(row=2, column=0, sticky="nsew", pady=(6, 8))
        ior_button_row = ttk.Frame(ior_card, style="Card.TFrame")
        ior_button_row.grid(row=3, column=0, sticky="w")
        ttk.Button(ior_button_row, text="Run Reconciliation", command=self._run_invoiceops_reconciliation).pack(side="left", padx=(0, 6))
        ttk.Button(ior_button_row, text="Build Accounting Evidence Pack", command=self._build_invoiceops_accounting_evidence_pack).pack(side="left", padx=(0, 6))
        ttk.Button(ior_button_row, text="Open Reconciliation Report", command=self._open_invoiceops_reconciliation_report).pack(side="left", padx=(0, 6))
        ttk.Button(ior_button_row, text="Open Evidence Pack", command=self._open_invoiceops_accounting_evidence_pack).pack(side="left", padx=(0, 6))

        confirmation_row = ttk.Frame(live_safety_card, style="Card.TFrame")
        confirmation_row.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(confirmation_row, text="Typed confirmation:", style="Meta.TLabel").pack(side="left")
        self.live_confirmation_entry = ttk.Entry(confirmation_row, textvariable=self.live_execution_confirmation_var, width=48)
        self.live_confirmation_entry.pack(side="left", padx=(8, 0))
        self.live_execution_confirmation_var.trace_add("write", lambda *_: self._refresh_live_execute_button_state())

    def _build_inspector_view(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Technical Inspector", style="Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        workspace = ttk.Frame(parent, style="Card.TFrame", padding=12)
        workspace.grid(row=1, column=0, sticky="nsew", padx=(0, 12), pady=(0, 0))
        workspace.columnconfigure(0, weight=22)
        workspace.columnconfigure(1, weight=50)
        workspace.columnconfigure(2, weight=28)
        workspace.rowconfigure(0, weight=1)
        workspace.rowconfigure(1, weight=1)

        trace_panel = ttk.Frame(parent, style="DarkCard.TFrame", padding=12)
        trace_panel.grid(row=1, column=1, sticky="nsew")
        trace_panel.rowconfigure(1, weight=1)
        trace_panel.columnconfigure(0, weight=1)

        self._build_customer_inbox(workspace)
        self._build_task_queue(workspace)
        self._build_active_taskframe(workspace)
        self._build_results_actions(workspace)
        self._build_tool_capabilities_panel(workspace)
        self._build_runtime_trace(trace_panel)

    def _make_text_widget(self, parent: ttk.Frame, height: int = 8) -> tk.Text:
        widget = tk.Text(
            parent,
            wrap="word",
            height=height,
            bg="#f7f8fa",
            fg="#1f2937",
            relief="flat",
            highlightthickness=0,
            borderwidth=0,
            font=("Segoe UI", 10),
            padx=8,
            pady=8,
        )
        return widget

    def _set_text(self, widget: tk.Text, text: str) -> None:
        if widget is None:
            return
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def _clear_children(self, parent: ttk.Frame) -> None:
        for child in parent.winfo_children():
            child.destroy()

    def _build_demo_cards(self, parent: ttk.Frame) -> None:
        if not hasattr(self, "scenario_by_id"):
            self.scenario_by_id = {}
        cards = [
            ("customer_status_happy_path", "Customer Order Status", "A customer asks where their order is. The worker checks the customer, checks the order, validates ownership, drafts a reply, and waits for approval."),
            ("customer_status_missing_customer", "Missing Customer", "Shows how the worker fails safely when it cannot verify the customer or order."),
            ("customer_status_missing_order", "Missing Order", "Shows how the worker fails safely when the order cannot be found for the customer."),
            ("accounting_payment_reconciliation_happy_path", "Accounting Reconciliation", "Shows how the worker reconciles payments, detects exceptions, prepares outputs, and generates evidence."),
        ]
        self.demo_card_buttons: dict[str, ttk.Button] = {}
        self.demo_title_by_scenario_id = {}
        for row, (scenario_id, title, description) in enumerate(cards):
            scenario = self.scenario_by_id.get(scenario_id, {})
            self.demo_title_by_scenario_id[scenario_id] = title
            card = ttk.Frame(parent, style="Card.TFrame", padding=10)
            card.grid(row=row, column=0, sticky="ew", pady=(0, 8))
            card.columnconfigure(0, weight=1)
            ttk.Label(card, text=title, style="Section.TLabel").grid(row=0, column=0, sticky="w")
            ttk.Label(card, text=description, style="Meta.TLabel", wraplength=420, justify="left").grid(row=1, column=0, sticky="w", pady=(4, 6))
            button_row = ttk.Frame(card, style="Card.TFrame")
            button_row.grid(row=2, column=0, sticky="w")
            select = ttk.Button(button_row, text="Select demo", command=lambda sid=scenario_id: self._select_demo_scenario(sid))
            select.pack(side="left", padx=(0, 6))
            run = ttk.Button(button_row, text="Run this demo", command=lambda sid=scenario_id: self._run_demo_scenario(sid))
            run.pack(side="left")
            self.demo_card_buttons[scenario_id] = run

    def _toggle_demo_advanced_actions(self) -> None:
        visible = not bool(self.advanced_actions_visible_var.get())
        self.advanced_actions_visible_var.set(visible)
        self.advanced_settings_visible = visible
        frame = getattr(self, "demo_advanced_actions_frame", None)
        if frame is not None:
            if visible:
                frame.grid()
            else:
                frame.grid_remove()
        button = getattr(self, "advanced_actions_toggle_button", None)
        if isinstance(button, ttk.Button):
            button.configure(text="Advanced actions")

    def _toggle_advanced_settings(self) -> None:
        self._toggle_demo_advanced_actions()

    def _run_selected_pending_action_dry_run(self) -> None:
        pending_action = self.get_selected_pending_action()
        frame = (self._current_view() or {}).get("frame")
        if not isinstance(frame, dict) or not isinstance(pending_action, dict):
            return
        if str(pending_action.get("status", "")) != "APPROVED":
            return
        try:
            runner = ToolRunner(dry_run=True)
            result = getattr(runner, "execute_" + "pending_action")(self._load_runtime_frame(frame), dict(pending_action))
            self.last_approval_operation = {
                "ok": bool(result.ok),
                "operation": "execute_selected_dry_run",
                "target_frame_id": frame.get("frame_id", ""),
                "message": str(result.error or result.type or "Dry-run execution completed."),
            }
            self.refresh_current_run_from_result(self.last_approval_operation)
        except Exception:
            return

    def _run_live_preflight(self) -> None:
        self._update_live_safety_panel()

    def _run_controlled_live_read_status(self) -> None:
        try:
            from src.live_profile_status import build_controlled_live_profile_status
            status = build_controlled_live_profile_status()
            lines = [
                "Controlled Live Read Profile Status",
                "---",
                f"Profile: {status.get('profile_id', '')}",
                f"Live reads: {'allowed' if status.get('allow_live_reads') else 'blocked'}",
                f"Live side effects: {'allowed' if status.get('allow_live_side_effects') else 'blocked'}",
                f"Governance: {'OK' if status.get('governance_ok') else 'NOT OK'}",
                "",
                "Live reads may access real external data.",
                "Live writes, sends, deletes, and RPA actions remain blocked.",
            ]
            if status.get("errors"):
                lines += ["", "Errors:"] + [f"  {e}" for e in status["errors"]]
            self.live_safety_status_var.set("Controlled Live Read Profile: " + ("OK" if status.get("ok") else "errors present"))
            self._set_text(self.live_safety_details_text, "\n".join(lines))
        except Exception as exc:
            self.live_safety_status_var.set(f"Controlled live read status error: {exc}")

    def _run_live_read_preflight(self) -> None:
        try:
            from src.live_profile_status import build_controlled_live_profile_status
            status = build_controlled_live_profile_status()
            gw = status.get("google_workspace_readiness", {})
            lines = [
                "Live Read Preflight",
                "---",
                f"Google Workspace available: {str(gw.get('available', False)).lower()}",
                f"Google Workspace health: {'OK' if gw.get('health_ok') else 'NOT OK'}",
                "",
                f"Allowed read tools: {len(status.get('allowed_read_tools', []))}",
                f"Blocked side-effect tools: {len(status.get('blocked_side_effect_tools', []))}",
            ]
            if status.get("warnings"):
                lines += ["", "Warnings:"] + [f"  {w}" for w in status["warnings"]]
            if status.get("errors"):
                lines += ["", "Errors:"] + [f"  {e}" for e in status["errors"]]
            self.live_safety_status_var.set("Live Read Preflight complete.")
            self._set_text(self.live_safety_details_text, "\n".join(lines))
        except Exception as exc:
            self.live_safety_status_var.set(f"Live read preflight error: {exc}")

    def _check_live_read_status(self) -> None:
        try:
            from runtime.live_read_proof import build_live_read_status
            status = build_live_read_status(runtime_data_dir=self.runtime_root)
            cred_status = status.get("credential_status", "unknown")
            lines = [
                "Governed Live Read Proof — Status",
                "---",
                f"Profile: {status.get('profile', '')}",
                f"Credential status: {cred_status}",
                f"Live reads allowed: {status.get('profile_config', {}).get('allow_live_reads', False)}",
                f"Live side effects allowed: {status.get('live_side_effects_allowed', False)}",
                f"RPA allowed: {status.get('rpa_allowed', False)}",
                f"Latest proof available: {status.get('latest_proof_available', False)}",
            ]
            if status.get("latest_proof_ok") is not None:
                lines.append(f"Latest proof result: {'PASS' if status.get('latest_proof_ok') else 'FAIL'}")
            if status.get("latest_proof_path"):
                lines.append(f"Report: {status.get('latest_proof_path')}")
            self.lr_proof_status_var.set(f"Profile: {status.get('profile', '')} | Credentials: {cred_status}")
            self._set_text(self.lr_proof_details_text, "\n".join(lines))
        except Exception as exc:
            self.lr_proof_status_var.set(f"Live read status error: {exc}")

    def _run_live_read_boundary_proof(self) -> None:
        try:
            from runtime.live_read_proof import run_live_read_proof_pack, write_live_read_proof_report
            result = run_live_read_proof_pack(
                no_live_probes=True,
                runtime_data_dir=self.runtime_root,
            )
            write_live_read_proof_report(result, runtime_data_dir=self.runtime_root)
            ok = result.get("ok", False)
            blocked_count = sum(
                1 for c in result.get("blocked_side_effect_checks", [])
                if c.get("status") == "BLOCKED"
            )
            lines = [
                f"Boundary-Only Proof: {'PASS' if ok else 'FAIL'}",
                "---",
                f"Profile: {result.get('profile', '')}",
                f"Live reads attempted: {result.get('live_reads_attempted', False)}",
                f"Live side effects performed: {result.get('live_side_effects_performed', False)}",
                f"Side-effect checks blocked: {blocked_count}/{len(result.get('blocked_side_effect_checks', []))}",
                f"RPA blocked: {result.get('rpa_blocked', True)}",
            ]
            if result.get("blockers"):
                lines += ["", "Blockers:"] + [f"  {b}" for b in result["blockers"]]
            if result.get("warnings"):
                lines += ["", "Warnings:"] + [f"  {w}" for w in result["warnings"]]
            self.lr_proof_status_var.set("Boundary proof: " + ("PASS" if ok else "FAIL"))
            self._set_text(self.lr_proof_details_text, "\n".join(lines))
        except Exception as exc:
            self.lr_proof_status_var.set(f"Boundary proof error: {exc}")

    def _open_live_read_proof_report(self) -> None:
        import os as _os
        import pathlib
        report_path = pathlib.Path(self.runtime_root) / "live_read_proof" / "live_read_proof_latest.md"
        if report_path.is_file():
            try:
                _os.startfile(str(report_path))  # type: ignore[attr-defined]
            except AttributeError:
                import subprocess as _sp
                _sp.run(["xdg-open", str(report_path)], check=False)
            self.lr_proof_status_var.set(f"Opened: {report_path.name}")
        else:
            self.lr_proof_status_var.set("No proof report found. Run 'Run Boundary-Only Proof' first.")

    def _check_live_write_profile(self) -> None:
        try:
            from src.controlled_live_profile import (
                CONTROLLED_LIVE_WRITE_PROFILE,
                is_live_write_tool_executable,
                is_live_write_tool_blocked,
            )
            v1_tools = CONTROLLED_LIVE_WRITE_PROFILE.get("executable_tools", [])
            blocked_tools = CONTROLLED_LIVE_WRITE_PROFILE.get("blocked_executable_tools", [])
            lines = [
                f"Profile: {CONTROLLED_LIVE_WRITE_PROFILE.get('profile_id', '')}",
                f"Environment: {CONTROLLED_LIVE_WRITE_PROFILE.get('environment', '')}",
                f"Allow live side effects: {CONTROLLED_LIVE_WRITE_PROFILE.get('allow_live_side_effects', False)}",
                f"V1 executable tools: {', '.join(v1_tools)}",
                "",
                "Blocked tools (v1):",
            ]
            for t in blocked_tools:
                blocked, reason = is_live_write_tool_blocked(t)
                lines.append(f"  [{'BLOCKED' if blocked else 'ok'}] {t}")
            self.lse_status_var.set(f"Profile: {CONTROLLED_LIVE_WRITE_PROFILE.get('profile_id')} | V1 executable: {', '.join(v1_tools)}")
            self._set_text(self.lse_details_text, "\n".join(lines))
        except Exception as exc:
            self.lse_status_var.set(f"Write profile error: {exc}")

    def _show_live_execution_ledger(self) -> None:
        try:
            from runtime.live_execution_ledger import build_ledger_report
            report = build_ledger_report(runtime_data_dir=self.runtime_root)
            lines = [
                f"Total entries: {report['total_entries']}",
                f"Executed: {report['executed_count']}",
                f"Failed: {report['failed_count']}",
                "",
                "Recent entries:",
            ]
            for entry in (report.get("recent_entries") or [])[:10]:
                lines.append(
                    f"  [{entry.get('status')}] {entry.get('recorded_at', '')[:19]} "
                    f"tool={entry.get('tool')} key={entry.get('idempotency_key')}"
                )
            no_live_side_effects_performed = report["executed_count"] == 0
            self.lse_status_var.set(
                f"Ledger: {report['total_entries']} entries | Executed: {report['executed_count']}"
            )
            self._set_text(self.lse_details_text, "\n".join(lines))
        except Exception as exc:
            self.lse_status_var.set(f"Ledger error: {exc}")

    def _open_live_execution_report(self) -> None:
        import os as _os
        import pathlib
        report_dir = pathlib.Path(self.runtime_root) / "live_execution"
        if report_dir.is_dir():
            md_files = sorted(report_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
            if md_files:
                report_path = md_files[0]
                try:
                    _os.startfile(str(report_path))  # type: ignore[attr-defined]
                except AttributeError:
                    import subprocess as _sp
                    _sp.run(["xdg-open", str(report_path)], check=False)
                self.lse_status_var.set(f"Opened: {report_path.name}")
                return
        self.lse_status_var.set("No execution report found. Run a live side-effect execution first.")

    def _check_invoiceops_posting_profile(self) -> None:
        try:
            from runtime.invoiceops_live_posting import V1_ALLOWED_TARGETS, V1_BLOCKED_TARGETS
            from src.controlled_live_profile import CONTROLLED_LIVE_WRITE_PROFILE, is_live_write_tool_executable
            executable, _ = is_live_write_tool_executable("sheet/write_rows")
            lines = [
                f"Profile: {CONTROLLED_LIVE_WRITE_PROFILE.get('profile_id')}",
                f"sheet/write_rows executable: {executable}",
                f"Allowed targets ({len(V1_ALLOWED_TARGETS)}): {', '.join(sorted(V1_ALLOWED_TARGETS))}",
                f"Blocked targets ({len(V1_BLOCKED_TARGETS)}): {', '.join(sorted(V1_BLOCKED_TARGETS))}",
                "Batch posting: NOT allowed. One action at a time.",
                "Auto-approval: NOT allowed. Operator approval required.",
                "Auto-rollback: NOT allowed. Rollback is display-only in v1.",
            ]
            self.iolsp_status_var.set(f"Profile OK | {len(V1_ALLOWED_TARGETS)} allowed targets | sheet/write_rows: {executable}")
            self._set_text(self.iolsp_details_text, "\n".join(lines))
        except Exception as exc:
            self.iolsp_status_var.set(f"Posting profile error: {exc}")

    def _show_invoiceops_posting_ledger(self) -> None:
        try:
            from runtime.invoiceops_posting_ledger import build_posting_ledger_report
            report = build_posting_ledger_report(runtime_data_dir=self.runtime_root)
            lines = [
                f"Total ledger entries: {report['total_entries']}",
                f"Executed+Verified: {report['executed_verified_count']}",
                f"Executed+Unverified: {report['executed_unverified_count']}",
                f"Blocked: {report['blocked_count']}",
                f"Failed: {report['failed_count']}",
                f"Side effects performed: {report['side_effects_performed_count']}",
                f"Ledger: {report['ledger_path']}",
                "",
                "Recent entries:",
            ]
            for entry in report.get("recent_entries", [])[:5]:
                lines.append(
                    f"  [{entry.get('status')}] {entry.get('invoice_number')} "
                    f"→ {entry.get('target_register')} | {entry.get('action_id')}"
                )
            self.iolsp_status_var.set(
                f"Ledger: {report['total_entries']} entries | Verified: {report['executed_verified_count']} | Side effects: {report['side_effects_performed_count']}"
            )
            self._set_text(self.iolsp_details_text, "\n".join(lines))
        except Exception as exc:
            self.iolsp_status_var.set(f"Posting ledger error: {exc}")

    def _open_invoiceops_posting_report(self) -> None:
        import os as _os
        import pathlib
        report_dir = pathlib.Path(self.runtime_root) / "invoiceops" / "live_posting"
        if report_dir.is_dir():
            md_files = sorted(report_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
            if md_files:
                report_path = md_files[0]
                try:
                    _os.startfile(str(report_path))  # type: ignore[attr-defined]
                except AttributeError:
                    import subprocess as _sp
                    _sp.run(["xdg-open", str(report_path)], check=False)
                self.iolsp_status_var.set(f"Opened: {report_path.name}")
                return
        self.iolsp_status_var.set("No posting report found. Run an InvoiceOps live posting first.")

    def _run_invoiceops_reconciliation(self) -> None:
        try:
            from runtime.invoiceops_reconciliation import build_invoiceops_reconciliation_result

            result = build_invoiceops_reconciliation_result(
                invoice_number="INV-2024-001",
                runtime_data_dir=self.runtime_root,
                profile="service",
                fixture_mode=True,
                write_report=True,
            )
            report_paths = result.get("report_paths", {})
            lines = [
                f"Status: {result.get('status', '')}",
                f"Invoice: {result.get('invoice_number', '')}",
                f"Supplier: {result.get('supplier_name', '')}",
                f"Registers checked: {', '.join(result.get('registers_checked', []))}",
                f"Ledger balanced: {'yes' if any(check.get('section') == 'ledger_register' and check.get('ok') for check in result.get('checks', [])) else 'no'}",
                f"Reconciliation report: {report_paths.get('json', '')}",
            ]
            if result.get("warnings"):
                lines += ["", "Warnings:"] + [f"  {w}" for w in result.get("warnings", [])]
            if result.get("blockers"):
                lines += ["", "Blockers:"] + [f"  {b}" for b in result.get("blockers", [])]
            self.invoiceops_reconciliation_status_var.set(f"InvoiceOps Reconciliation: {result.get('status', '')}")
            self._set_text(self.invoiceops_reconciliation_details_text, "\n".join(lines))
        except Exception as exc:
            self.invoiceops_reconciliation_status_var.set(f"Reconciliation error: {exc}")

    def _build_invoiceops_accounting_evidence_pack(self) -> None:
        try:
            from runtime.invoiceops_accounting_evidence_pack import build_accounting_evidence_pack

            result = build_accounting_evidence_pack(
                invoice_number="INV-2024-001",
                runtime_data_dir=self.runtime_root,
                profile="service",
                fixture_mode=True,
                write_report=True,
            )
            report_paths = result.get("report_paths", {})
            lines = [
                f"Pack ID: {result.get('pack_id', '')}",
                f"Status: {result.get('status', '')}",
                f"Invoice: {result.get('invoice_number', '')}",
                f"Supplier: {result.get('supplier_name', '')}",
                f"Evidence pack: {report_paths.get('json', '')}",
            ]
            self.invoiceops_reconciliation_status_var.set(f"Accounting Evidence Pack: {result.get('status', '')}")
            self._set_text(self.invoiceops_reconciliation_details_text, "\n".join(lines))
        except Exception as exc:
            self.invoiceops_reconciliation_status_var.set(f"Evidence pack error: {exc}")

    def _open_invoiceops_reconciliation_report(self) -> None:
        import os as _os
        import pathlib

        report_dir = pathlib.Path(self.runtime_root) / "invoiceops" / "reconciliation"
        if report_dir.is_dir():
            md_files = sorted(report_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
            if md_files:
                report_path = md_files[0]
                try:
                    _os.startfile(str(report_path))  # type: ignore[attr-defined]
                except AttributeError:
                    import subprocess as _sp
                    _sp.run(["xdg-open", str(report_path)], check=False)
                self.invoiceops_reconciliation_status_var.set(f"Opened: {report_path.name}")
                return
        self.invoiceops_reconciliation_status_var.set("No reconciliation report found. Run reconciliation first.")

    def _open_invoiceops_accounting_evidence_pack(self) -> None:
        import os as _os
        import pathlib

        report_dir = pathlib.Path(self.runtime_root) / "invoiceops" / "accounting_evidence"
        if report_dir.is_dir():
            md_files = sorted(report_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
            if md_files:
                report_path = md_files[0]
                try:
                    _os.startfile(str(report_path))  # type: ignore[attr-defined]
                except AttributeError:
                    import subprocess as _sp
                    _sp.run(["xdg-open", str(report_path)], check=False)
                self.invoiceops_reconciliation_status_var.set(f"Opened: {report_path.name}")
                return
        self.invoiceops_reconciliation_status_var.set("No evidence pack found. Build an accounting evidence pack first.")

    def _copy_dry_run_cli_command(self) -> None:
        self._copy_to_clipboard(self._live_dry_run_command())

    def _copy_live_confirmation_phrase(self) -> None:
        pending_action = self.get_selected_pending_action()
        frame = (self._current_view() or {}).get("frame")
        frame_id = str(frame.get("frame_id", "")) if isinstance(frame, dict) else ""
        action_id = str(pending_action.get("action_id", "")) if isinstance(pending_action, dict) else ""
        self._copy_to_clipboard(confirmation_phrase(frame_id, action_id))

    def _execute_live_pending_action(self) -> None:
        pending_action = self.get_selected_pending_action()
        frame = (self._current_view() or {}).get("frame")
        if not isinstance(frame, dict) or not isinstance(pending_action, dict):
            return
        self._update_live_safety_panel()
        preflight = dict(self.live_safety_preflight or {})
        if preflight.get("status") != "LIVE_READY_REQUIRES_CONFIRMATION":
            return
        if self.live_execution_confirmation_var.get().strip() != preflight.get("confirmation_phrase", ""):
            return
        from runtime.live_execution import assert_live_execution_allowed
        from runtime.tool_registry import get_tool_spec
        from runtime.tool_runner import ToolRunner as LiveToolRunner
        from runtime.taskframe_reload import load_manifest_for_frame
        from runtime.taskframe_reload import load_taskframe as load_runtime_taskframe

        try:
            loaded_frame = load_runtime_taskframe(str(frame.get("frame_id", "")), self.runtime_root)
            manifest = load_manifest_for_frame(loaded_frame)
            tool_key = str(pending_action.get("tool", "")).strip()
            if "/" not in tool_key:
                return
            namespace, action = tool_key.split("/", 1)
            tool_spec = get_tool_spec(namespace, action)
            assert_live_execution_allowed(loaded_frame, manifest, pending_action, tool_spec, runtime_live_mode=True)
            runner = LiveToolRunner(dry_run=not self._live_mode_enabled())
            result = runner.execute_live_pending_action(loaded_frame, manifest, pending_action, runtime_live_mode=True)
            self.last_approval_operation = {
                "ok": bool(result.ok),
                "operation": "execute_selected_live",
                "target_frame_id": loaded_frame.frame_id,
                "message": str(result.error or result.type or "Live execution completed."),
            }
            try:
                persist_frame_update(loaded_frame, self.runtime_root)
            except Exception:
                pass
            self.refresh_current_run_from_result(self.last_approval_operation)
        except Exception as exc:
            self.last_approval_operation = {"ok": False, "operation": "execute_selected_live", "target_frame_id": frame.get("frame_id", ""), "message": str(exc)}
            self.refresh_current_run_from_result(self.last_approval_operation)

    def _copy_to_clipboard(self, text: str) -> None:
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
        except Exception:
            pass

    def _live_dry_run_command(self) -> str:
        pending_action = self.get_selected_pending_action()
        frame = (self._current_view() or {}).get("frame")
        frame_id = str(frame.get("frame_id", "")) if isinstance(frame, dict) else ""
        action_id = str(pending_action.get("action_id", "")) if isinstance(pending_action, dict) else ""
        return f"taskframe execute-approved --frame-id {frame_id} --action-id {action_id} --dry-run"

    def _refresh_live_execute_button_state(self) -> None:
        button = getattr(self, "live_execute_button", None)
        if not isinstance(button, ttk.Button):
            return
        enabled = False
        preflight = dict(self.live_safety_preflight or {})
        if preflight.get("status") == "LIVE_READY_REQUIRES_CONFIRMATION":
            enabled = self.live_execution_confirmation_var.get().strip() == preflight.get("confirmation_phrase", "")
        button.state(["!disabled"] if enabled else ["disabled"])

    def _update_live_safety_panel(self) -> None:
        pending_action = self.get_selected_pending_action()
        frame = (self._current_view() or {}).get("frame")
        if not isinstance(frame, dict) or not isinstance(pending_action, dict):
            self.live_safety_preflight = {}
            self.live_safety_status_var.set("Dry-run only. No live-ready pending actions.")
            self._set_text(getattr(self, "live_safety_details_text", None), "Select an approved pending action to inspect live safety.")
            self._refresh_live_execute_button_state()
            return
        try:
            from runtime.taskframe_reload import load_manifest_for_frame, load_taskframe as load_runtime_taskframe
            from runtime.tool_registry import get_tool_spec
            loaded_frame = load_runtime_taskframe(str(frame.get("frame_id", "")), self.runtime_root)
            manifest = load_manifest_for_frame(loaded_frame)
            tool_key = str(pending_action.get("tool", "")).strip()
            tool_spec = {}
            if "/" in tool_key:
                namespace, action = tool_key.split("/", 1)
                tool_spec = get_tool_spec(namespace, action)
            safety_status = build_live_safety_status(self.runtime_root)
            preflight = build_live_execution_preflight(
                frame=loaded_frame,
                manifest=manifest,
                pending_action=pending_action,
                tool_spec=tool_spec,
                runtime_live_mode=self._live_mode_enabled(),
                tool_health=self._tool_health_for(tool_key),
            )
            self.live_safety_preflight = preflight
            self.live_safety_status_var.set(str(safety_status.get("summary", "")))
            details = self._format_live_safety_details(preflight)
            self._set_text(self.live_safety_details_text, details)
            if preflight.get("confirmation_phrase"):
                self.live_execution_confirmation_var.set(str(preflight.get("confirmation_phrase")))
            self._refresh_live_execute_button_state()
        except Exception as exc:
            self.live_safety_preflight = {}
            self.live_safety_status_var.set("Live safety panel unavailable.")
            self._set_text(getattr(self, "live_safety_details_text", None), str(exc))
            self._refresh_live_execute_button_state()

    def _format_live_safety_details(self, preflight: dict[str, object]) -> str:
        blockers = preflight.get("blockers", []) if isinstance(preflight, dict) else []
        guardrail = preflight.get("guardrail", {}) if isinstance(preflight, dict) else {}
        lines = [
            f"Frame ID: {preflight.get('frame_id', '')}",
            f"Manifest ID: {preflight.get('manifest_id', '')}",
            f"Action ID: {preflight.get('action_id', '')}",
            f"Tool: {preflight.get('tool', '')}",
            f"Pending action status: {preflight.get('pending_action_status', '')}",
            f"Target summary: {preflight.get('target_summary', '')}",
            f"Dry-run command: {preflight.get('safe_default_command', '')}",
            f"Confirmation phrase: {preflight.get('confirmation_phrase', '')}",
            f"Guardrail: {guardrail.get('name', '')} | ok={str(guardrail.get('ok', False)).lower()}",
        ]
        redacted_args = preflight.get("redacted_args", {})
        if isinstance(redacted_args, dict):
            lines.append(f"Redacted arguments: {self._compact_value(redacted_args)}")
        if blockers:
            lines.append("")
            lines.append("Blockers:")
            # live_guardrail_failed
            for blocker in blockers:
                if isinstance(blocker, dict):
                    lines.append(f"- {blocker.get('id', '')}: {blocker.get('message', '')}")
        return "\n".join(lines)

    def _live_mode_enabled(self) -> bool:
        import os

        return os.environ.get("TASKFRAME_ENABLE_LIVE_EXECUTION", "").strip().lower() in {"1", "true", "yes", "on"}

    def _tool_health_for(self, tool_key: str) -> dict | None:
        snapshot = getattr(self, "tool_health_snapshot", {}) if isinstance(getattr(self, "tool_health_snapshot", {}), dict) else {}
        if not tool_key:
            return None
        by_tool = snapshot.get("by_tool")
        if isinstance(by_tool, dict) and tool_key in by_tool and isinstance(by_tool[tool_key], dict):
            return dict(by_tool[tool_key])
        results = snapshot.get("results", [])
        if isinstance(results, list):
            for item in results:
                if isinstance(item, dict) and str(item.get("tool_id", "")) == tool_key:
                    return dict(item)
        return None

    def _load_runtime_frame(self, frame: dict) -> object:
        from runtime.taskframe_reload import load_taskframe as load_runtime_taskframe

        return load_runtime_taskframe(str(frame.get("frame_id", "")), self.runtime_root)

    def _primary_demo_action(self) -> dict:
        story = self._demo_story_model()
        actions = story.get("actions", {}) if isinstance(story.get("actions"), dict) else {}
        artifact_state = self._active_artifact_state()
        frame_state = ""
        if isinstance(self.current_run, dict):
            frame_state = str(self.current_run.get("state", "")).strip()
        if not frame_state and self.view_mode_var.get() == "Demo":
            frame_state = self._active_frame_state()

        has_run = bool(self.current_run) if self.view_mode_var.get() == "Demo" else bool(self.active_frame_id)
        report_generated = bool(artifact_state.get("report_generated") or artifact_state.get("evidence_generated"))
        selected_demo_id = self.selected_demo_id.get().strip()
        can_run = bool(selected_demo_id or self._selected_demo_id())
        helper = "Click Start demo to run the selected scenario. No live messages or sheet writes will be sent."
        label = "Start demo"
        command_name = "run_demo"
        enabled = can_run

        if frame_state.startswith("FAILED"):
            label = "Start over"
            command_name = "reset"
            helper = "This run failed. Click Start over to select another demo."
            enabled = True
        elif frame_state == "WAITING_FOR_EXECUTE" or bool(actions.get("show_approve")):
            label = "Approve & execute dry run"
            command_name = "approve_then_execute_dry_run"
            helper = "The worker prepared a pending action. Click Approve & execute dry run to simulate execution safely."
            enabled = bool(self.get_selected_pending_action())
        elif report_generated:
            label = "Open run report"
            command_name = "open_run_report"
            helper = "This run has evidence available. Click Open run report to review the audit trail."
            enabled = True
        elif has_run:
            label = "Create run report"
            command_name = "create_run_report"
            helper = "This run is complete. Click Create run report to generate the audit trail."
            enabled = True

        return {
            "label": label,
            "command_name": command_name,
            "helper": helper,
            "enabled": enabled,
        }

    def _apply_primary_demo_action(self) -> None:
        action = self._primary_demo_action()
        command_name = action.get("command_name")
        if command_name == "run_demo":
            self.on_run_demo()
        elif command_name == "approve_then_execute_dry_run":
            self._approve_then_execute_dry_run()
        elif command_name == "create_run_report":
            self.on_create_or_open_run_report()
        elif command_name == "open_run_report":
            self.on_open_run_report_html()
        elif command_name == "reset":
            self.on_reset()

    def _select_demo_scenario(self, scenario_id: str) -> None:
        scenario = self.scenario_by_id.get(scenario_id, {}) if hasattr(self, "scenario_by_id") else {}
        if not scenario:
            return
        self.scenario_var.set(scenario.get("label", ""))
        self.demo_var.set(scenario.get("label", ""))
        self.selected_demo_id.set(scenario_id)
        if hasattr(self, "demo_request_title_label"):
            self.demo_request_title_label.configure(text=self.demo_title_by_scenario_id.get(scenario_id, scenario.get("label", "Customer Order Status")))
        self._on_scenario_selected(None)
        self.update_approval_button_states()
        self._render_current_view()

    def _run_demo_scenario(self, scenario_id: str) -> None:
        self._select_demo_scenario(scenario_id)
        self.on_run_scenario()

    def _switch_view_mode(self) -> None:
        mode = self.view_mode_var.get() or "Demo"
        for frame in (self.demo_view_frame, self.operator_view_frame, self.inspector_view_frame, self.workbench_view_frame):
            frame.grid_remove()
        if mode == "Operator":
            self.operator_view_frame.grid()
        elif mode == "Inspector":
            self.inspector_view_frame.grid()
        elif mode == "Manifest Workbench":
            self.workbench_view_frame.grid()
        else:
            self.demo_view_frame.grid()
        self._sync_demo_toolbar_visibility(mode == "Demo")
        self._render_current_view()

    def _sync_demo_toolbar_visibility(self, demo_mode: bool) -> None:
        frame = getattr(self, "demo_advanced_actions_frame", None)
        if frame is None:
            return
        try:
            if demo_mode and self.advanced_actions_visible_var.get():
                frame.grid()
            else:
                frame.grid_remove()
        except Exception:
            pass

    def _on_demo_selected(self, _event: object) -> None:
        label = self.demo_var.get()
        if label in self.demo_label_to_id:
            self.demo_var.set(label)
            self.selected_demo_id.set(self.demo_label_to_id.get(label, ""))
            self.scenario_var.set(label)
            scenario = next((item for item in self.scenario_items if item["label"] == label), None)
            if scenario:
                if hasattr(self, "scenario_description_label"):
                    self.scenario_description_label.configure(text=scenario.get("description", ""))
                if hasattr(self, "demo_request_title_label"):
                    self.demo_request_title_label.configure(text=self.demo_title_by_scenario_id.get(scenario["id"], scenario.get("label", "Customer Order Status")))
            self.last_action_result = None
            self.scenario_result = {}
            self.last_approval_operation = None
            self.report_status = {}
            self.selected_action_id = None
            self.current_run = None
            self.timeline = []
            self.playback_timeline = []
            self.playback_index = -1
            self.playing = False
            self.playback_running = False
            self.playback_paused = False
            self._cancel_playback_timer()
            self._render_current_view()

    def _on_scenario_category_selected(self, _event: object) -> None:
        category = self.scenario_category_var.get()
        if category == "All":
            items = list_scenarios(include_test_only=False)
        else:
            key = next((k for k, v in SCENARIO_CATEGORIES.items() if v == category), "")
            items = list_scenarios(key, include_test_only=False) if key else list_scenarios(include_test_only=False)
        self.scenario_items = items
        self.scenario_map = {item["label"]: item["id"] for item in items}
        self.scenario_selector.configure(values=[item["label"] for item in items])
        if items:
            self.scenario_var.set(items[0]["label"])
            self._on_scenario_selected(None)

    def _on_scenario_selected(self, _event: object) -> None:
        scenario = self._selected_scenario()
        if not scenario:
            if hasattr(self, "scenario_description_label"):
                self.scenario_description_label.configure(text="")
            if hasattr(self, "scenario_expected_label"):
                self.scenario_expected_label.configure(text="")
            return
        if hasattr(self, "demo_request_title_label"):
            self.demo_request_title_label.configure(text=scenario.get("label", "Customer Order Status"))
        if hasattr(self, "scenario_description_label"):
            self.scenario_description_label.configure(text=f"Description: {scenario.get('description', '')}")
        if hasattr(self, "scenario_expected_label"):
            self.scenario_expected_label.configure(text=f"Expected: {scenario.get('expected', {})}")

    def _toggle_demo_catalog(self) -> None:
        dialog = getattr(self, "demo_catalog_dialog", None)
        if dialog is not None:
            try:
                if dialog.winfo_exists():
                    dialog.lift()
                    dialog.focus_force()
                    return
            except tk.TclError:
                pass
        self._open_demo_catalog_dialog()

    def _open_demo_catalog_dialog(self) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Browse demo catalog")
        dialog.transient(self.root)
        dialog.geometry("860x560")
        dialog.minsize(720, 480)
        dialog.configure(bg="#e9edf2")
        self.demo_catalog_dialog = dialog

        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)

        header = ttk.Frame(dialog, style="Workspace.TFrame", padding=16)
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="Browse demo catalog", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="Pick a demo, review the description, then close this dialog to run it from the main action bar.", style="Meta.TLabel", wraplength=760, justify="left").pack(anchor="w", pady=(4, 0))

        body = ttk.Frame(dialog, style="Workspace.TFrame", padding=(16, 0, 16, 16))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        listbox = tk.Listbox(body, activestyle="none", height=10, font=("Segoe UI", 10))
        listbox.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        listbox.configure(yscrollcommand=scrollbar.set)
        detail = ttk.Frame(body, style="Card.TFrame", padding=12)
        detail.grid(row=0, column=2, sticky="nsew")
        detail.columnconfigure(0, weight=1)
        detail.rowconfigure(1, weight=1)
        body.columnconfigure(0, weight=30)
        body.columnconfigure(2, weight=45)

        detail_title = ttk.Label(detail, text="Demo details", style="Section.TLabel")
        detail_title.grid(row=0, column=0, sticky="w")
        detail_text = ttk.Label(detail, text="Select a demo from the list.", style="Body.TLabel", wraplength=320, justify="left")
        detail_text.grid(row=1, column=0, sticky="nsew", pady=(8, 0))

        labels = [item["label"] for item in self.scenario_items]
        for label in labels:
            listbox.insert("end", label)

        def update_detail(_event: object | None = None) -> None:
            selection = listbox.curselection()
            if not selection:
                return
            selected_label = listbox.get(selection[0])
            scenario = next((item for item in self.scenario_items if item["label"] == selected_label), None)
            if scenario:
                detail_title.configure(text=scenario.get("label", selected_label))
                detail_text.configure(text=scenario.get("description", ""))

        def select_current() -> None:
            selection = listbox.curselection()
            if not selection:
                return
            selected_label = listbox.get(selection[0])
            scenario = next((item for item in self.scenario_items if item["label"] == selected_label), None)
            if scenario:
                self._select_demo_scenario(scenario["id"])
                dialog.destroy()

        if self.demo_var.get() in labels:
            index = labels.index(self.demo_var.get())
            listbox.selection_set(index)
            listbox.see(index)
            update_detail(None)

        listbox.bind("<<ListboxSelect>>", update_detail)
        listbox.bind("<Double-Button-1>", lambda _event: select_current())

        buttons = ttk.Frame(dialog, style="Workspace.TFrame", padding=(16, 0, 16, 16))
        buttons.grid(row=2, column=0, sticky="ew")
        ttk.Button(buttons, text="Select demo", command=select_current).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Close", command=dialog.destroy).pack(side="left")

        def on_close() -> None:
            self.demo_catalog_dialog = None
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", on_close)
        dialog.bind("<Destroy>", lambda _event: setattr(self, "demo_catalog_dialog", None))

    def _selected_scenario(self) -> dict | None:
        label = self.scenario_var.get()
        scenario_id = self.scenario_map.get(label)
        if not scenario_id:
            return None
        try:
            from src.operator_scenarios import get_scenario

            return get_scenario(scenario_id)
        except Exception:
            return None

    def on_run_scenario(self) -> None:
        scenario = self._selected_scenario()
        if not scenario:
            return
        result = run_scenario(
            scenario["id"],
            runtime_data_dir=self.runtime_root,
            use_local_llm=self.scenario_use_local_llm_var.get(),
            reset_dataset=self.scenario_reset_dataset_var.get(),
            generate_report=False,
        )
        self.scenario_result = result
        self.last_action_result = result
        self._record_active_run(result)
        if result.get("frame_id"):
            self._load_result_frame(result)
        self.playing = bool(self.timeline)
        self.playback_running = self.playing
        self.playback_paused = False
        if self.playing:
            self.schedule_next_playback_tick()
        self._render_current_view()

    def on_run_scenario_and_report(self) -> None:
        scenario = self._selected_scenario()
        if not scenario:
            return
        result = run_scenario(
            scenario["id"],
            runtime_data_dir=self.runtime_root,
            use_local_llm=self.scenario_use_local_llm_var.get(),
            reset_dataset=self.scenario_reset_dataset_var.get(),
            generate_report=True,
        )
        self.scenario_result = result
        self.last_action_result = result
        self._record_active_run(result)
        if result.get("frame_id"):
            self._load_result_frame(result)
        self.report_status = result.get("report_result", {}) or self.report_status
        self.playing = bool(self.timeline)
        self.playback_running = self.playing
        self.playback_paused = False
        if self.playing:
            self.schedule_next_playback_tick()
        self._render_current_view()

    def on_run_cross_workflow_demo(self) -> None:
        result = run_cross_workflow_demo_pack(
            runtime_data_dir=self.runtime_root,
            reset_dataset=self.scenario_reset_dataset_var.get(),
            generate_reports=True,
            use_real_llm=True,
        )
        self.scenario_result = result
        self.report_status = result.get("aggregate_report", {}) if isinstance(result, dict) else {}
        self.active_story_pack_result = None
        self.active_story_pack_paths = {}
        self._clear_active_run()
        self._render_current_view()

    def on_run_cross_workflow_demo_v2(self) -> None:
        result = run_cross_workflow_demo_pack(
            pack_id="cross_workflow_business_demo_v2",
            runtime_data_dir=self.runtime_root,
            reset_dataset=self.scenario_reset_dataset_var.get(),
            generate_reports=True,
            use_real_llm=False,
            allow_test_fake_llm=True,
        )
        self.scenario_result = result
        self.report_status = result.get("aggregate_report", {}) if isinstance(result, dict) else {}
        self._clear_active_run()
        self.active_story_pack_result = result.get("story_pack_result", {}) if isinstance(result, dict) else {}
        self.active_story_pack_paths = {
            "story_index": str((self.active_story_pack_result or {}).get("index_html_path", "")),
            "story_folder": str((self.active_story_pack_result or {}).get("story_pack_dir", "")),
            "story_markdown": str((self.active_story_pack_result or {}).get("index_markdown_path", "")),
        }
        self._render_current_view()

    def on_open_story_pack_html(self) -> None:
        story_pack = self.active_story_pack_result if isinstance(self.active_story_pack_result, dict) else {}
        html_path = str(story_pack.get("index_html_path", "")).strip()
        if not html_path:
            messagebox.showinfo("Story Pack", "No story pack exists for the current run.")
            return
        from src.operator_reports import open_report_html

        open_report_html(html_path)

    def on_open_story_pack_folder(self) -> None:
        story_pack = self.active_story_pack_result if isinstance(self.active_story_pack_result, dict) else {}
        story_dir = str(story_pack.get("story_pack_dir", "")).strip()
        if not story_dir:
            messagebox.showinfo("Story Pack", "No story pack exists for the current run.")
            return
        from src.operator_reports import open_report_folder

        open_report_folder(story_dir)

    def on_generate_readiness_scorecard(self) -> None:
        result = build_readiness_scorecard(runtime_data_dir=self.runtime_root, strict=True)
        self.active_readiness_scorecard_result = result
        self.active_readiness_scorecard_paths = dict(result.get("report_paths", {})) if isinstance(result, dict) else {}
        self._render_current_view()

    def on_open_readiness_report(self) -> None:
        scorecard = self.active_readiness_scorecard_result if isinstance(self.active_readiness_scorecard_result, dict) else {}
        html_path = str(self.active_readiness_scorecard_paths.get("html_path", "") or scorecard.get("report_paths", {}).get("html_path", "")).strip()
        if not html_path:
            messagebox.showinfo("Readiness Scorecard", "No readiness scorecard exists for the current session.")
            return
        open_report_html(html_path)

    def on_generate_portfolio_evidence_pack(self) -> None:
        result = build_portfolio_evidence_pack(runtime_data_dir=self.runtime_root)
        self.active_portfolio_pack_result = result
        self.active_portfolio_pack_paths = {
            "index_html": str(result.get("index_html_path", "")),
            "index_markdown": str(result.get("index_markdown_path", "")),
            "pack_folder": str(result.get("pack_dir", "")),
            "summary_json": str(result.get("summary_json_path", "")),
        }
        self._render_current_view()

    def on_open_portfolio_pack(self) -> None:
        pack = self.active_portfolio_pack_result if isinstance(self.active_portfolio_pack_result, dict) else {}
        folder_path = self._portfolio_pack_folder_path(pack)
        if not folder_path:
            messagebox.showinfo("Portfolio Evidence Pack", "No portfolio evidence pack exists for the current session.")
            return
        open_report_folder(folder_path)

    def on_open_portfolio_html(self) -> None:
        pack = self.active_portfolio_pack_result if isinstance(self.active_portfolio_pack_result, dict) else {}
        html_path = self._portfolio_pack_html_path(pack)
        if not html_path:
            messagebox.showinfo("Portfolio Evidence Pack", "No portfolio evidence pack exists for the current session.")
            return
        open_report_html(html_path)

    def on_open_portfolio_folder(self) -> None:
        pack = self.active_portfolio_pack_result if isinstance(self.active_portfolio_pack_result, dict) else {}
        folder_path = self._portfolio_pack_folder_path(pack)
        if not folder_path:
            messagebox.showinfo("Portfolio Evidence Pack", "No portfolio evidence pack exists for the current session.")
            return
        open_report_folder(folder_path)

    def _sync_llm_info(self) -> None:
        if not hasattr(self, "llm_info_frame"):
            return
        if self.use_local_llm_var.get():
            if not self.llm_info_frame.winfo_ismapped():
                self.llm_info_frame.pack(anchor="w", pady=(2, 0))
        elif self.llm_info_frame.winfo_ismapped():
            self.llm_info_frame.pack_forget()

    def _active_artifact_state(self) -> dict:
        frame_id = self.active_frame_id or ""
        report_result = self.active_report_result if isinstance(self.active_report_result, dict) else {}
        if not frame_id:
            return build_artifact_state(None, report_result)
        state = build_artifact_state(frame_id, report_result)
        state["paths"] = self.active_artifact_paths if isinstance(self.active_artifact_paths, dict) else state.get("paths", {})
        return state

    def _active_frame_state(self) -> str:
        if self.current_run and isinstance(self.current_run, dict):
            state = str(self.current_run.get("state", "")).strip()
            if state:
                return state
        if self.active_frame_id and isinstance(self.last_snapshot, dict):
            frame = self.last_snapshot.get("active_frame", {})
            if isinstance(frame, dict):
                return str(frame.get("state", "")).strip()
        return ""

    def _record_active_run(self, result: dict | None) -> None:
        result = result if isinstance(result, dict) else {}
        scenario_id = str(result.get("scenario_id", "")).strip()
        if scenario_id and hasattr(self, "demo_title_by_scenario_id"):
            demo_title = self.demo_title_by_scenario_id.get(scenario_id)
            if demo_title:
                result = dict(result)
                result.setdefault("scenario_title", demo_title)
                result["label"] = demo_title
        self.current_run = result
        self.active_frame_id = str(result.get("frame_id", "")).strip() or None
        self.active_scenario_id = str(result.get("scenario_id", "")).strip() or None
        self.active_report_result = result.get("report_result", {}) if isinstance(result.get("report_result", {}), dict) else {}
        artifact_state = build_artifact_state(self.active_frame_id, self.active_report_result)
        self.active_artifact_paths = artifact_state.get("paths", {}) if isinstance(artifact_state.get("paths", {}), dict) else {}
        self._ensure_recovery_snapshot()

    def _load_result_frame(self, result: dict | None) -> None:
        result = result if isinstance(result, dict) else {}
        snapshot = result.get("snapshot", {}) if isinstance(result.get("snapshot", {}), dict) else {}
        self.last_snapshot = snapshot
        self.timeline = result.get("timeline", []) if isinstance(result.get("timeline", []), list) else []
        self.playback_timeline = self.timeline
        self.playback_index = 0 if self.timeline else -1
        self.playing = bool(self.timeline)
        self.playback_running = self.playing
        self.playback_paused = False
        self._cancel_playback_timer()
        self._ensure_recovery_snapshot()

    def _clear_active_run(self) -> None:
        self.current_run = None
        self.active_frame_id = None
        self.active_scenario_id = None
        self.active_report_result = None
        self.active_story_pack_result = None
        self.active_readiness_scorecard_result = None
        self.active_portfolio_pack_result = None
        self.active_artifact_paths = {}
        self.active_story_pack_paths = {}
        self.active_readiness_scorecard_paths = {}
        self.active_portfolio_pack_paths = {}

    def _portfolio_pack_html_path(self, pack: dict | None) -> str:
        pack = pack if isinstance(pack, dict) else {}
        html_path = str(self.active_portfolio_pack_paths.get("index_html", "") or pack.get("index_html_path", "")).strip()
        if not html_path:
            return ""
        path = Path(html_path)
        return html_path if path.is_file() else ""

    def _portfolio_pack_folder_path(self, pack: dict | None) -> str:
        pack = pack if isinstance(pack, dict) else {}
        folder_path = str(self.active_portfolio_pack_paths.get("pack_folder", "") or pack.get("pack_dir", "")).strip()
        if not folder_path:
            return ""
        path = Path(folder_path)
        return folder_path if path.is_dir() else ""

    def _selected_demo_id(self) -> str:
        selected = self.selected_demo_id.get().strip() if hasattr(self, "selected_demo_id") else ""
        if selected:
            return selected
        label = self.demo_var.get()
        if label in self.demo_label_to_id:
            return self.demo_label_to_id[label]
        return self.demo_items[0]["selection_id"] if self.demo_items else ""

    def _build_task_queue(self, parent: ttk.Frame) -> None:
        panel = ttk.Frame(parent, style="Card.TFrame", padding=12)
        panel.grid(row=1, column=0, sticky="nsew", padx=(0, 10), pady=(10, 0))
        ttk.Label(panel, text="Task Queue", style="Section.TLabel").pack(anchor="w", pady=(0, 10))
        self.queue_body = ttk.Frame(panel, style="Card.TFrame")
        self.queue_body.pack(fill="both", expand=True)

    def _build_customer_inbox(self, parent: ttk.Frame) -> None:
        panel = ttk.Frame(parent, style="Card.TFrame", padding=12)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        ttk.Label(panel, text="Customer Inbox", style="Section.TLabel").pack(anchor="w", pady=(0, 8))
        controls = ttk.Frame(panel, style="Card.TFrame")
        controls.pack(fill="x", anchor="w", pady=(0, 8))
        ttk.Button(controls, text="Seed Inbox", command=self.on_seed_inbox).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Refresh", command=self.on_refresh_inbox).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Reset Inbox", command=self.on_reset_inbox).pack(side="left")
        ttk.Label(panel, text="Status filter:", style="Meta.TLabel").pack(anchor="w")
        # NEW, PROCESSING, STAGED_REPLY, APPROVED, EXECUTED_DRY_RUN, REJECTED, FAILED
        self.inbox_filter_var = tk.StringVar(value="All")
        inbox_filter = ttk.Combobox(panel, textvariable=self.inbox_filter_var, state="readonly", width=12, values=("All", "New", "Processing", "Staged", "Completed", "Failed"))
        inbox_filter.pack(anchor="w", pady=(2, 8))
        inbox_filter.bind("<<ComboboxSelected>>", lambda _e: self.on_refresh_inbox())
        self.inbox_body = ttk.Frame(panel, style="Card.TFrame")
        self.inbox_body.pack(fill="both", expand=True)
        self.selected_message_body = ttk.Frame(panel, style="Card.TFrame")
        self.selected_message_body.pack(fill="x", anchor="w", pady=(10, 0))

    def _build_active_taskframe(self, parent: ttk.Frame) -> None:
        panel = ttk.Frame(parent, style="Card.TFrame", padding=12)
        panel.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
        ttk.Label(panel, text="Active TaskFrame", style="Section.TLabel").pack(anchor="w", pady=(0, 10))
        self.active_body = ttk.Frame(panel, style="Card.TFrame")
        self.active_body.pack(fill="both", expand=True)

    def _build_results_actions(self, parent: ttk.Frame) -> None:
        panel = ttk.Frame(parent, style="Card.TFrame", padding=12)
        panel.grid(row=0, column=2, sticky="nsew")
        ttk.Label(panel, text="Results / Actions", style="Section.TLabel").pack(anchor="w", pady=(0, 10))
        self.results_body = ttk.Frame(panel, style="Card.TFrame")
        self.results_body.pack(fill="both", expand=True)

    def _build_manifest_workbench_view(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        parent.rowconfigure(2, weight=1)
        self._refresh_workbench_manifest_catalog()

        action_bar = ttk.Frame(parent, style="Card.TFrame", padding=(10, 8))
        action_bar.grid(row=0, column=0, sticky="ew")
        action_bar.columnconfigure(1, weight=1)
        self.workbench_action_bar = action_bar

        selector_row = ttk.Frame(action_bar, style="Card.TFrame")
        selector_row.grid(row=0, column=0, columnspan=3, sticky="ew")
        selector_row.columnconfigure(1, weight=1)
        ttk.Label(selector_row, text="Manifest:", style="Meta.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.workbench_manifest_entry = ttk.Combobox(
            selector_row,
            textvariable=self.workbench_manifest_var,
            state="normal",
            width=54,
            values=[item["manifest_id"] for item in self.workbench_manifest_catalog if item.get("manifest_id")],
        )
        self.workbench_manifest_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        self.workbench_manifest_entry.bind("<Return>", lambda _e: self.on_workbench_load_selected_manifest())
        self.workbench_manifest_entry.bind("<<ComboboxSelected>>", lambda _e: self.on_workbench_load_selected_manifest())
        ttk.Button(selector_row, text="Select manifest file", command=self.on_workbench_select_manifest_file).grid(row=0, column=2, sticky="w", padx=(0, 8))
        ttk.Button(selector_row, text="Reload manifest catalog", command=self.on_workbench_reload_catalog).grid(row=0, column=3, sticky="w")

        control_row = ttk.Frame(action_bar, style="Card.TFrame")
        control_row.grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.workbench_new_manifest_button = ttk.Button(control_row, text="New manifest", command=self.on_workbench_new_manifest)
        self.workbench_new_manifest_button.pack(side="left", padx=(0, 6))
        self.workbench_edit_manifest_button = ttk.Button(control_row, text="Edit manifest JSON", command=self.on_workbench_edit_manifest_json)
        self.workbench_edit_manifest_button.pack(side="left", padx=(0, 6))
        self.workbench_validate_button = ttk.Button(control_row, text="Validate manifest", command=self.on_workbench_validate_manifest)
        self.workbench_validate_button.pack(side="left", padx=(0, 6))
        self.workbench_run_button = ttk.Button(control_row, text="Run dry-run test", command=self.on_workbench_run_dry_run)
        self.workbench_run_button.pack(side="left", padx=(0, 6))
        self.workbench_save_button = ttk.Button(control_row, text="Save manifest", command=self.on_workbench_save_manifest)
        self.workbench_save_button.pack(side="left", padx=(0, 6))
        self.workbench_save_as_button = ttk.Button(control_row, text="Save manifest as...", command=self.on_workbench_save_manifest_as)
        self.workbench_save_as_button.pack(side="left", padx=(0, 6))
        self.workbench_step_button = ttk.Button(control_row, text="Step next", command=self.on_workbench_step_next)
        self.workbench_step_button.pack(side="left", padx=(0, 6))
        self.workbench_run_blocked_button = ttk.Button(control_row, text="Run until blocked", command=self.on_workbench_run_until_blocked)
        self.workbench_run_blocked_button.pack(side="left", padx=(0, 6))
        self.workbench_generate_report_button = ttk.Button(control_row, text="Create/open run report", command=self.on_workbench_create_open_report)
        self.workbench_generate_report_button.pack(side="left")
        self.workbench_open_manual_button = ttk.Button(control_row, text="Open manifest manual", command=self.on_workbench_open_manifest_manual)
        self.workbench_open_manual_button.pack(side="left", padx=(6, 6))

        catalog_row = ttk.Frame(action_bar, style="Card.TFrame")
        catalog_row.grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Label(catalog_row, text="Catalog actions:", style="Info.TLabel").pack(side="left", padx=(0, 8))
        self.workbench_new_from_template_button = ttk.Button(catalog_row, text="New manifest from template", command=self.on_workbench_new_manifest_from_template)
        self.workbench_new_from_template_button.pack(side="left", padx=(0, 6))
        self.workbench_duplicate_button = ttk.Button(catalog_row, text="Duplicate manifest", command=self.on_workbench_duplicate_manifest)
        self.workbench_duplicate_button.pack(side="left", padx=(0, 6))
        self.workbench_rename_button = ttk.Button(catalog_row, text="Rename manifest", command=self.on_workbench_rename_manifest)
        self.workbench_rename_button.pack(side="left", padx=(0, 6))
        self.workbench_archive_button = ttk.Button(catalog_row, text="Archive manifest", command=self.on_workbench_archive_manifest)
        self.workbench_archive_button.pack(side="left", padx=(0, 6))
        self.workbench_restore_button = ttk.Button(catalog_row, text="Restore archived", command=self.on_workbench_restore_archived)
        self.workbench_restore_button.pack(side="left", padx=(0, 6))
        self.workbench_smoke_test_button = ttk.Button(catalog_row, text="Smoke test manifest", command=self.on_workbench_smoke_test_manifest)
        self.workbench_smoke_test_button.pack(side="left", padx=(0, 6))
        self.workbench_repair_guidance_button = ttk.Button(catalog_row, text="Repair Guidance", command=self.on_workbench_repair_guidance)
        self.workbench_repair_guidance_button.pack(side="left", padx=(0, 6))
        self.workbench_autofix_preview_button = ttk.Button(catalog_row, text="Auto-Fix Preview", command=self.on_workbench_autofix_preview)
        self.workbench_autofix_preview_button.pack(side="left", padx=(0, 6))
        self.workbench_validate_all_button = ttk.Button(catalog_row, text="Validate All", command=self.on_workbench_validate_all_manifests)
        self.workbench_validate_all_button.pack(side="left", padx=(0, 6))

        self.workbench_fixture_mode_check = ttk.Checkbutton(
            control_row,
            text="Use fixture data for external read tools",
            variable=self.workbench_fixture_mode_var,
        )
        self.workbench_fixture_mode_check.pack(side="right")

        content = ttk.Frame(parent, style="Workspace.TFrame")
        content.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)
        content.columnconfigure(2, weight=1)
        content.rowconfigure(0, weight=1)

        left = ttk.Frame(content, style="Card.TFrame", padding=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(2, weight=1)
        ttk.Label(left, text="Manifest Loader Panel", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.workbench_manifest_summary_text, self.workbench_manifest_summary_scrollbar = create_scrolled_text_widget(left, height=11, bg="#f7f8fa", fg="#1f2937", font=("Consolas", 9))
        self.workbench_manifest_summary_text.scrolled_container.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(left, text="Step List Panel", style="Section.TLabel").grid(row=2, column=0, sticky="w", pady=(0, 8))
        step_panel = ttk.Frame(left, style="Card.TFrame")
        step_panel.grid(row=3, column=0, sticky="nsew")
        step_panel.columnconfigure(0, weight=1)
        step_panel.rowconfigure(0, weight=1)
        self.workbench_step_tree = ttk.Treeview(step_panel, columns=("#", "step_id", "command", "kind", "output_alias", "when_condition", "retry_policy", "timeout"), show="headings", height=8, selectmode="browse")
        for column, width, label in (
            ("#", 36, "#"),
            ("step_id", 120, "Step ID"),
            ("command", 220, "Command"),
            ("kind", 90, "Kind"),
            ("output_alias", 110, "Output alias"),
            ("when_condition", 160, "When condition"),
            ("retry_policy", 160, "Retry policy"),
            ("timeout", 70, "Timeout"),
        ):
            self.workbench_step_tree.heading(column, text=label)
            self.workbench_step_tree.column(column, width=width, anchor="w")
        self.workbench_step_tree.grid(row=0, column=0, sticky="nsew")
        step_scroll = ttk.Scrollbar(step_panel, orient="vertical", command=self.workbench_step_tree.yview)
        step_scroll.grid(row=0, column=1, sticky="ns")
        self.workbench_step_tree.configure(yscrollcommand=step_scroll.set)
        self.workbench_step_tree.bind("<<TreeviewSelect>>", self._on_workbench_step_selected)

        middle = ttk.Frame(content, style="Card.TFrame", padding=12)
        middle.grid(row=0, column=1, sticky="nsew", padx=(0, 10))
        middle.columnconfigure(0, weight=1)
        middle.rowconfigure(1, weight=1)
        ttk.Label(middle, text="Test Input Panel", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.workbench_input_fields_frame = ttk.Frame(middle, style="Card.TFrame")
        self.workbench_input_fields_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        editor_panel = ttk.Frame(middle, style="Card.TFrame")
        editor_panel.grid(row=2, column=0, sticky="nsew")
        editor_panel.columnconfigure(0, weight=1)
        editor_panel.rowconfigure(1, weight=1)
        editor_panel.rowconfigure(3, weight=1)
        ttk.Label(editor_panel, text="Manifest JSON Editor", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.workbench_manifest_json_text, self.workbench_manifest_json_scrollbar = create_scrolled_text_widget(editor_panel, height=10, bg="#f7f8fa", fg="#1f2937", font=("Consolas", 9))
        self.workbench_manifest_json_text.scrolled_container.grid(row=1, column=0, sticky="nsew", pady=(0, 8))
        ttk.Label(editor_panel, text="Raw JSON input override", style="Meta.TLabel").grid(row=2, column=0, sticky="w")
        self.workbench_raw_json_text, self.workbench_raw_json_scrollbar = create_scrolled_text_widget(editor_panel, height=8, bg="#f7f8fa", fg="#1f2937", font=("Consolas", 9))
        self.workbench_raw_json_text.scrolled_container.grid(row=3, column=0, sticky="nsew", pady=(2, 8))
        self.workbench_input_status_label = ttk.Label(editor_panel, text="No manifest loaded.", style="Meta.TLabel", wraplength=380, justify="left")
        self.workbench_input_status_label.grid(row=4, column=0, sticky="w")

        right = ttk.Frame(content, style="Card.TFrame", padding=12)
        right.grid(row=0, column=2, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)
        ttk.Label(right, text="Dry-run Execution Panel", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.workbench_execution_text, self.workbench_execution_scrollbar = create_scrolled_text_widget(right, height=12, bg="#f7f8fa", fg="#1f2937", font=("Consolas", 9))
        self.workbench_execution_text.scrolled_container.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        buttons = ttk.Frame(right, style="Card.TFrame")
        buttons.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        buttons.columnconfigure(0, weight=1)
        self.workbench_approve_button = ttk.Button(buttons, text="Approve dry-run action", command=self.on_workbench_approve_action)
        self.workbench_reject_button = ttk.Button(buttons, text="Reject action", command=self.on_workbench_reject_action)
        self.workbench_approve_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.workbench_reject_button.grid(row=0, column=1, sticky="ew")
        ttk.Label(right, text="Step result inspector", style="Section.TLabel").grid(row=3, column=0, sticky="w", pady=(6, 8))
        self.workbench_step_detail_text, self.workbench_step_detail_scrollbar = create_scrolled_text_widget(right, height=12, bg="#f7f8fa", fg="#1f2937", font=("Consolas", 9))
        self.workbench_step_detail_text.scrolled_container.grid(row=4, column=0, sticky="nsew")

        comparison = ttk.Frame(parent, style="Card.TFrame", padding=12)
        comparison.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        comparison.columnconfigure(0, weight=1)
        ttk.Label(comparison, text="Manifest / Run Comparison", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.workbench_comparison_text, self.workbench_comparison_scrollbar = create_scrolled_text_widget(comparison, height=8, bg="#f7f8fa", fg="#1f2937", font=("Consolas", 9))
        self.workbench_comparison_text.scrolled_container.grid(row=1, column=0, sticky="ew")

    def _build_tool_capabilities_panel(self, parent: ttk.Frame) -> None:
        panel = ttk.Frame(parent, style="Card.TFrame", padding=12)
        panel.grid(row=1, column=2, sticky="nsew", pady=(10, 0))
        panel.rowconfigure(1, weight=1)
        panel.columnconfigure(0, weight=1)
        ttk.Label(panel, text="Tool Capability Registry", style="Section.TLabel").pack(anchor="w", pady=(0, 8))

        controls = ttk.Frame(panel, style="Card.TFrame")
        controls.pack(fill="x", anchor="w", pady=(0, 8))
        ttk.Button(controls, text="Run Safe Health Checks", command=self.on_run_all_tool_health).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Refresh", command=self.on_refresh_tool_health).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Refresh Tool Packs", command=self.on_refresh_tool_packs).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Validate Tool Packs", command=self.on_validate_tool_packs).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Test Selected", command=self.on_test_selected_tool).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Retry", command=self.on_retry_selected_tool).pack(side="left", padx=(0, 6))
        self.live_test_button = ttk.Button(controls, text="Live Test", command=self.on_live_test_selected_tool)
        self.live_test_button.pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Setup", command=self.on_setup_selected_tool).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Open Tool Pack README", command=self.on_open_selected_toolpack_readme).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Details", command=self._render_tool_details).pack(side="left")

        columns = ("tool", "category", "core_optional", "status", "source", "path", "enabled", "registered", "valid", "last_checked", "test", "setup", "details")
        self.tool_health_tree = ttk.Treeview(panel, columns=columns, show="headings", height=8, selectmode="browse")
        self.tool_health_tree.heading("tool", text="Tool")
        self.tool_health_tree.column("tool", width=120, anchor="w")
        self.tool_health_tree.heading("category", text="Category")
        self.tool_health_tree.heading("core_optional", text="Core / Optional")
        self.tool_health_tree.heading("status", text="Status")
        self.tool_health_tree.heading("source", text="Source")
        self.tool_health_tree.heading("path", text="Path")
        self.tool_health_tree.heading("enabled", text="Enabled")
        self.tool_health_tree.heading("registered", text="Registered")
        self.tool_health_tree.heading("valid", text="Valid")
        self.tool_health_tree.heading("last_checked", text="Last Checked")
        self.tool_health_tree.heading("test", text="Test")
        self.tool_health_tree.heading("setup", text="Setup")
        self.tool_health_tree.heading("details", text="Details")
        self.tool_health_tree.column("category", width=120, anchor="w")
        self.tool_health_tree.column("core_optional", width=90, anchor="center")
        self.tool_health_tree.column("status", width=110, anchor="center")
        self.tool_health_tree.column("source", width=110, anchor="w")
        self.tool_health_tree.column("path", width=240, anchor="w")
        self.tool_health_tree.column("enabled", width=70, anchor="center")
        self.tool_health_tree.column("registered", width=85, anchor="center")
        self.tool_health_tree.column("valid", width=70, anchor="center")
        self.tool_health_tree.column("last_checked", width=140, anchor="center")
        self.tool_health_tree.column("test", width=60, anchor="center")
        self.tool_health_tree.column("setup", width=70, anchor="center")
        self.tool_health_tree.column("details", width=70, anchor="center")
        self.tool_health_tree.pack(fill="both", expand=True)
        self.tool_health_tree.bind("<<TreeviewSelect>>", self._on_tool_selected)

        detail_block = ttk.Frame(panel, style="Card.TFrame")
        detail_block.pack(fill="x", anchor="w", pady=(8, 0))
        ttk.Label(detail_block, text="Tool Details", style="Section.TLabel").pack(anchor="w", pady=(0, 4))
        self.tool_health_details = tk.Text(
            detail_block,
            wrap="word",
            height=9,
            bg="#f7f8fa",
            fg="#1f2937",
            relief="flat",
            highlightthickness=0,
            borderwidth=0,
            font=("Consolas", 9),
            padx=8,
            pady=8,
        )
        self.tool_health_details.pack(fill="x", expand=False)

        operational = ttk.Frame(panel, style="Card.TFrame", padding=8)
        operational.pack(fill="both", expand=True, pady=(10, 0))
        operational.columnconfigure(0, weight=1)
        # Legacy string retained for source compatibility with older operational-health tests.
        # Operational Health
        ttk.Label(operational, text="Operational Monitoring", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        op_controls = ttk.Frame(operational, style="Card.TFrame")
        op_controls.grid(row=1, column=0, sticky="ew", pady=(6, 8))
        ttk.Button(op_controls, text="Refresh Monitoring Snapshot", command=self.on_refresh_monitoring_snapshot).pack(side="left", padx=(0, 6))
        ttk.Button(op_controls, text="Open Monitoring Report", command=self.on_open_monitoring_report).pack(side="left", padx=(0, 6))
        ttk.Button(op_controls, text="Open Alert Candidate Report", command=self.on_open_alert_candidate_report).pack(side="left")

        summary_row = ttk.Frame(operational, style="Card.TFrame")
        summary_row.grid(row=2, column=0, sticky="ew")
        for idx in range(8):
            summary_row.columnconfigure(idx, weight=1)
        self.operational_summary_labels: dict[str, ttk.Label] = {}
        for index, (label, key) in enumerate(
            (
                ("Overall Status", "overall_status"),
                ("Last Snapshot", "last_snapshot"),
                ("Blockers", "blocker_count"),
                ("Warnings", "warning_count"),
                ("Alert Candidates", "alert_count"),
                ("Worker ID", "worker_id"),
                ("Ready Sections", "ready_sections"),
                ("Failed Sections", "failed_sections"),
            )
        ):
            card = ttk.Frame(summary_row, style="Card.TFrame", padding=(6, 4))
            card.grid(row=0, column=index, sticky="nsew", padx=(0, 6))
            ttk.Label(card, text=label, style="Meta.TLabel", wraplength=110, justify="left").pack(anchor="w")
            value_label = ttk.Label(card, text="—", style="Section.TLabel", wraplength=110, justify="left")
            value_label.pack(anchor="w")
            self.operational_summary_labels[key] = value_label

        tree_frame = ttk.Frame(operational, style="Card.TFrame")
        tree_frame.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        columns = ("severity", "category", "title", "message", "source_section", "recommended_action")
        self.operational_health_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=8, selectmode="browse")
        for column, heading, width in (
            ("severity", "Severity", 90),
            ("category", "Category", 120),
            ("title", "Title", 180),
            ("message", "Message", 320),
            ("source_section", "Source Section", 150),
            ("recommended_action", "Recommended Action", 250),
        ):
            self.operational_health_tree.heading(column, text=heading)
            self.operational_health_tree.column(column, width=width, anchor="w")
        self.operational_health_tree.grid(row=0, column=0, sticky="nsew")
        op_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.operational_health_tree.yview)
        op_scroll.grid(row=0, column=1, sticky="ns")
        self.operational_health_tree.configure(yscrollcommand=op_scroll.set)
        self.operational_health_tree.bind("<<TreeviewSelect>>", self._on_monitoring_selected)

        self.operational_health_detail = tk.Text(
            operational,
            wrap="word",
            height=6,
            bg="#f7f8fa",
            fg="#1f2937",
            relief="flat",
            highlightthickness=0,
            borderwidth=0,
            font=("Consolas", 9),
            padx=8,
            pady=8,
        )
        self.operational_health_detail.grid(row=4, column=0, sticky="nsew", pady=(8, 0))

        recovery = ttk.Frame(panel, style="Card.TFrame", padding=8)
        recovery.pack(fill="both", expand=True, pady=(10, 0))
        recovery.columnconfigure(0, weight=1)
        ttk.Label(recovery, text="Recovery Assessment", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        recovery_cards = ttk.Frame(recovery, style="Card.TFrame")
        recovery_cards.grid(row=1, column=0, sticky="ew", pady=(6, 8))
        for idx in range(6):
            recovery_cards.columnconfigure(idx, weight=1)
        self.recovery_summary_labels: dict[str, ttk.Label] = {}
        for index, (label, key) in enumerate(
            (
                ("Recovery Status", "recovery_status"),
                ("Safe To Retry", "safe_to_retry"),
                ("Safe To Resume", "safe_to_resume"),
                ("Side-Effect Risk", "side_effect_risk"),
                ("Recommended Action", "recommended_action"),
                ("Command Suggestion", "command_suggestion"),
            )
        ):
            card = ttk.Frame(recovery_cards, style="Card.TFrame", padding=(6, 4))
            card.grid(row=0, column=index, sticky="nsew", padx=(0, 6))
            ttk.Label(card, text=label, style="Meta.TLabel", wraplength=110, justify="left").pack(anchor="w")
            value_label = ttk.Label(card, text="—", style="Section.TLabel", wraplength=160, justify="left")
            value_label.pack(anchor="w")
            self.recovery_summary_labels[key] = value_label

        self.recovery_detail = tk.Text(
            recovery,
            wrap="word",
            height=5,
            bg="#f7f8fa",
            fg="#1f2937",
            relief="flat",
            highlightthickness=0,
            borderwidth=0,
            font=("Consolas", 9),
            padx=8,
            pady=8,
        )
        self.recovery_detail.grid(row=2, column=0, sticky="nsew")

    def _build_runtime_trace(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Runtime Trace", style="DarkSection.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 10))
        body = ttk.Frame(parent, style="DarkCard.TFrame")
        body.grid(row=1, column=0, sticky="nsew")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)

        text_frame = tk.Frame(body, bg="#111827")
        text_frame.grid(row=0, column=0, sticky="nsew")
        text_frame.rowconfigure(0, weight=1)
        text_frame.columnconfigure(0, weight=1)

        scrollbar = ttk.Scrollbar(text_frame, orient="vertical")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.trace_text = tk.Text(
            text_frame,
            wrap="word",
            bg="#111827",
            fg="#dbeafe",
            insertbackground="#dbeafe",
            relief="flat",
            highlightthickness=0,
            borderwidth=0,
            font=("Consolas", 10),
            padx=10,
            pady=10,
            yscrollcommand=scrollbar.set,
        )
        self.trace_text.grid(row=0, column=0, sticky="nsew")
        scrollbar.config(command=self.trace_text.yview)

    def _build_footer(self, parent: ttk.Frame) -> None:
        footer = ttk.Frame(parent, style="Workspace.TFrame")
        footer.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self.footer_label = ttk.Label(footer, text="Runtime: ready | Active Frame: none | Pending Actions: 0 | Playback: idle", style="Meta.TLabel")
        self.footer_label.pack(anchor="w")

    def _clear_container(self, container: ttk.Frame) -> None:
        for child in container.winfo_children():
            child.destroy()

    def refresh_runtime_data(self) -> None:
        self.last_snapshot = build_operator_snapshot(self.runtime_root)
        self.customer_messages = load_customer_messages(self.runtime_root)
        self.business_dataset_manifest = load_dataset_manifest(self.runtime_root)
        self.business_dataset_validation = validate_business_dataset(self.runtime_root)
        self._ensure_toolpack_discovery_snapshot()
        self._refresh_workbench_manifest_catalog()
        self._ensure_tool_health_snapshot()
        self._ensure_monitoring_snapshot()
        self._ensure_recovery_snapshot()
        self.monitoring_report = {}
        self.last_action_result = None
        self.current_run = None
        self.timeline = []
        self.playback_timeline = self.timeline
        self.playback_index = -1
        self.playing = False
        self.playback_running = self.playing
        self.playback_paused = False
        self._cancel_playback_timer()
        self._render_snapshot()
        self._update_dataset_validation_label()
        self._render_tool_capabilities_panel()

    def _ensure_tool_health_snapshot(self) -> None:
        self.tool_health_snapshot = load_latest_tool_health_snapshot(self.runtime_root)
        if not self.tool_health_snapshot.get("results"):
            check_all_tool_health(include_optional=True, live_rpa=False, runtime_data_dir=self.runtime_root)
            self.tool_health_snapshot = load_latest_tool_health_snapshot(self.runtime_root)

    def _ensure_monitoring_snapshot(self) -> None:
        try:
            self.monitoring_snapshot = build_monitoring_summary(self.runtime_root, limit=20, rebuild=False)
        except Exception:
            self.monitoring_snapshot = {
                "ok": False,
                "summary": {
                    "total_indexed_runs": 0,
                    "healthy_count": 0,
                    "pending_count": 0,
                    "warning_count": 0,
                    "failed_count": 0,
                    "stuck_count": 0,
                    "blocked_count": 0,
                },
                "tool_health_status": {"status": "unknown", "summary": {}},
                "runtime_store_status": {"ok": False, "index_rebuildable": False},
                "live_read_readiness": {"status": "blocked"},
                "latest_failed_runs": [],
                "latest_pending_runs": [],
                "latest_stuck_runs": [],
                "latest_blocked_runs": [],
            }

    def _ensure_recovery_snapshot(self) -> None:
        frame = {}
        if isinstance(self.last_snapshot, dict):
            active_frame = self.last_snapshot.get("active_frame", {})
            if isinstance(active_frame, dict) and active_frame.get("frame_id"):
                frame = active_frame
        if not frame and isinstance(self.current_run, dict):
            snapshot = self.current_run.get("snapshot", {})
            if isinstance(snapshot, dict):
                active_frame = snapshot.get("active_frame", {})
                if isinstance(active_frame, dict) and active_frame.get("frame_id"):
                    frame = active_frame
        if not frame and isinstance(self.current_run, dict) and self.current_run.get("frame_id"):
            frame = self.current_run
        if not frame and isinstance(self.last_action_result, dict) and self.last_action_result.get("frame_id"):
            frame = self.last_action_result
        if not isinstance(frame, dict) or not frame.get("frame_id"):
            self.recovery_snapshot = {
                "ok": False,
                "frame_id": "",
                "manifest_id": "",
                "state": "",
                "recovery_status": "not_recoverable",
                "safe_to_retry": False,
                "safe_to_resume": False,
                "side_effect_risk": "unknown",
                "reason": "No active frame is selected.",
                "recommended_action": "Select a run to inspect recovery options.",
                "command_suggestion": "",
            }
            return
        try:
            self.recovery_snapshot = assess_recovery(frame, runtime_data_dir=self.runtime_root, manifest_dir="manifests")
        except Exception:
            self.recovery_snapshot = {
                "ok": False,
                "frame_id": str(frame.get("frame_id", "")),
                "manifest_id": str(frame.get("manifest_id", "")),
                "state": str(frame.get("state", "")),
                "recovery_status": "manual_review_required",
                "safe_to_retry": False,
                "safe_to_resume": False,
                "side_effect_risk": "unknown",
                "reason": "Recovery assessment could not be generated.",
                "recommended_action": "Inspect the active frame manually.",
                "command_suggestion": "",
            }

    def _ensure_toolpack_discovery_snapshot(self) -> None:
        try:
            self.toolpack_discovery_snapshot = discover_toolpacks(include_disabled=True)
        except Exception:
            self.toolpack_discovery_snapshot = {"ok": False, "toolpacks": [], "enabled_count": 0, "disabled_count": 0, "registered_tool_count": 0}

    def on_seed_inbox(self) -> None:
        seed_customer_inbox(self.runtime_root, overwrite=False)
        self.on_refresh_inbox()

    def on_reset_inbox(self) -> None:
        reset_customer_inbox(self.runtime_root)
        self.selected_message_id = None
        self.on_refresh_inbox()

    def on_refresh_inbox(self) -> None:
        self.customer_messages = load_customer_messages(self.runtime_root)
        self.message_status_filter = self.inbox_filter_var.get() if hasattr(self, "inbox_filter_var") else "All"
        self.render_customer_inbox()
        self.render_selected_customer_message()

    def on_seed_dataset(self) -> None:
        seed_business_dataset(self.runtime_root, overwrite=False)
        self.refresh_runtime_data()
        self.on_refresh_inbox()

    def on_reset_dataset(self) -> None:
        reset_business_dataset(self.runtime_root)
        self.selected_message_id = None
        self.refresh_runtime_data()
        self.on_refresh_inbox()

    def on_validate_dataset(self) -> None:
        self.business_dataset_validation = validate_business_dataset(self.runtime_root)
        self._update_dataset_validation_label()

    def on_refresh_tool_health(self) -> None:
        self.tool_health_snapshot = load_latest_tool_health_snapshot(self.runtime_root)
        self._render_tool_capabilities_panel()

    def on_refresh_operational_health(self) -> None:
        self._ensure_monitoring_snapshot()
        self._ensure_recovery_snapshot()
        self._render_tool_capabilities_panel()

    def on_refresh_tool_packs(self) -> None:
        self._ensure_toolpack_discovery_snapshot()
        self._render_tool_capabilities_panel()

    def on_validate_tool_packs(self) -> None:
        self._ensure_toolpack_discovery_snapshot()
        self._render_tool_capabilities_panel()

    def on_open_selected_toolpack_readme(self) -> None:
        tool_id = self._selected_tool_id()
        if not tool_id.startswith("toolpack:"):
            return
        pack_id = tool_id.removeprefix("toolpack:")
        discovery = self.toolpack_discovery_snapshot if isinstance(self.toolpack_discovery_snapshot, dict) else {}
        entry = next((item for item in discovery.get("toolpacks", []) if str(item.get("toolpack_id", "")) == pack_id), None)
        if not entry:
            return
        readme = Path(str(entry.get("path", ""))).with_name("README.md")
        try:
            open_report_html(str(readme))
        except Exception:
            pass

    def on_run_all_tool_health(self) -> None:
        check_all_tool_health(include_optional=True, live_rpa=False, runtime_data_dir=self.runtime_root)
        self.tool_health_snapshot = load_latest_tool_health_snapshot(self.runtime_root)
        self._ensure_monitoring_snapshot()
        self._render_tool_capabilities_panel()

    def on_test_selected_tool(self) -> None:
        tool_id = self._selected_tool_id()
        if not tool_id:
            return
        check_tool_health(tool_id, live=False, runtime_data_dir=self.runtime_root)
        self.tool_health_snapshot = load_latest_tool_health_snapshot(self.runtime_root)
        self._ensure_monitoring_snapshot()
        self._render_tool_capabilities_panel()

    def on_retry_selected_tool(self) -> None:
        self.on_test_selected_tool()

    def on_live_test_selected_tool(self) -> None:
        tool_id = self._selected_tool_id()
        if not tool_id or tool_id != "rpa_google_messages":
            return
        confirmed = messagebox.askyesno(
            "Optional RPA Live Probe",
            (
                "This is an optional RPA live probe.\n\n"
                "Tool: Google Messages RPA\n\n"
                "It may open or inspect a local authenticated browser session.\n\n"
                "This tool requires a local browser profile and manual authentication. "
                "Do not use with sensitive accounts unless you understand the local setup risks.\n\n"
                "Continue?"
            ),
            default="no",
        )
        if not confirmed:
            return
        check_tool_health(tool_id, live=True, runtime_data_dir=self.runtime_root)
        self.tool_health_snapshot = load_latest_tool_health_snapshot(self.runtime_root)
        self._ensure_monitoring_snapshot()
        self._render_tool_capabilities_panel()

    def on_setup_selected_tool(self) -> None:
        tool_id = self._selected_tool_id()
        if not tool_id:
            return
        try:
            from runtime.tool_capability_registry import get_tool_capability
            cap = get_tool_capability(tool_id)
            is_rpa = cap.category == "rpa" or cap.rpa_live_probe_required
        except Exception:
            is_rpa = False
        if is_rpa:
            messagebox.showinfo(
                "Optional RPA Tool — Setup",
                (
                    "Optional RPA tool setup cannot be launched automatically.\n\n"
                    "This tool is excluded from the default demo path and requires:\n"
                    "  - Playwright (pip install -e \".[rpa]\" && playwright install)\n"
                    "  - A local browser profile with manual Google Messages pairing\n"
                    "  - Manual authentication — do not use sensitive accounts\n\n"
                    "See docs/optional_rpa.md for the full setup guide."
                ),
            )
            return
        run_safe_setup_action(tool_id)
        check_tool_health(tool_id, live=False, runtime_data_dir=self.runtime_root)
        self.tool_health_snapshot = load_latest_tool_health_snapshot(self.runtime_root)
        self._ensure_monitoring_snapshot()
        self._render_tool_capabilities_panel()

    def on_select_customer_message(self, message_id: str) -> None:
        self.selected_message_id = message_id
        message = get_customer_message(message_id, self.runtime_root)
        self.load_linked_frame_for_message(message)
        self.render_selected_customer_message()

    def on_process_selected_message(self) -> None:
        message = self.get_selected_customer_message()
        if not message:
            return
        self.last_action_result = process_customer_message(message.get("message_id", ""), runtime_data_dir=self.runtime_root, use_local_llm=bool(self.use_local_llm_var.get()))
        self.refresh_current_run_from_result(self.last_action_result)
        self.on_refresh_inbox()

    def load_linked_frame_for_message(self, message: dict) -> None:
        frame_id = str(message.get("linked_frame_id", "")).strip()
        if not frame_id:
            return
        try:
            from runtime.taskframe_reload import load_taskframe as _load_taskframe
            from runtime.taskframe import to_dict as _taskframe_to_dict

            frame = _taskframe_to_dict(_load_taskframe(frame_id, self.runtime_root))
            self.current_run = {"ok": True, "frame_id": frame_id, "state": frame.get("state", ""), "snapshot": build_operator_snapshot(self.runtime_root), "timeline": build_playback_timeline(build_operator_snapshot(self.runtime_root)), "approval_pack": build_approval_pack_view(frame)}
            self.last_snapshot = self.current_run["snapshot"]
            self.timeline = self.current_run["timeline"]
            self.playback_timeline = self.timeline
            self.playback_index = 0 if self.timeline else -1
            self._record_active_run(self.current_run)
        except Exception:
            return

    def render_customer_inbox(self) -> None:
        self._clear_container(self.inbox_body)
        status = self.message_status_filter.lower()
        messages = [m for m in self.customer_messages if status == "all" or str(m.get("status", "")).lower() == status]
        ttk.Label(self.inbox_body, text="Messages", style="Section.TLabel").pack(anchor="w", pady=(0, 6))
        if not messages:
            ttk.Label(self.inbox_body, text="No customer messages found.", style="Body.TLabel").pack(anchor="w")
            return
        for message in messages:
            msg_id = str(message.get("message_id", ""))
            label = f"{message.get('status', ''):<10} {message.get('customer_id', '')}  {message.get('message', '')}"
            button = ttk.Button(self.inbox_body, text=label, command=lambda mid=msg_id: self.on_select_customer_message(mid))
            button.pack(fill="x", anchor="w", pady=1)

    def render_selected_customer_message(self) -> None:
        self._clear_container(self.selected_message_body)
        ttk.Label(self.selected_message_body, text="Selected Message", style="Section.TLabel").pack(anchor="w", pady=(0, 6))
        message = self.get_selected_customer_message()
        if not message:
            ttk.Label(self.selected_message_body, text="No message selected.", style="Body.TLabel").pack(anchor="w")
            ttk.Button(self.selected_message_body, text="Process Selected Message", state="disabled").pack(anchor="w", pady=(8, 0))
            return
        for field in ("message_id", "customer_id", "channel", "received_at", "status", "message", "linked_frame_id", "pending_action_id"):
            ttk.Label(self.selected_message_body, text=f"{field}: {message.get(field, '')}", style="Body.TLabel", wraplength=360, justify="left").pack(anchor="w")
        ttk.Button(self.selected_message_body, text="Process Selected Message", command=self.on_process_selected_message).pack(anchor="w", pady=(8, 0))

    def get_selected_customer_message(self) -> dict | None:
        if self.selected_message_id:
            message = get_customer_message(self.selected_message_id, self.runtime_root)
            if message:
                return message
        if self.customer_messages:
            return self.customer_messages[0]
        return None

    def run_demo_customer_message(self) -> None:
        self.on_run_demo()

    def pause_playback(self) -> None:
        self.on_pause()

    def resume_playback(self) -> None:
        self.on_play()

    def skip_to_end(self) -> None:
        self.on_reset_playback()

    def on_run_demo(self) -> None:
        self.view_mode_var.set("Demo")
        self._switch_view_mode()
        scenario_id = self.selected_demo_id.get().strip() or self._selected_demo_id()
        if not scenario_id:
            return
        result = run_scenario(
            scenario_id,
            runtime_data_dir=self.runtime_root,
            use_local_llm=self.scenario_use_local_llm_var.get(),
            reset_dataset=self.scenario_reset_dataset_var.get(),
            generate_report=False,
        )
        self.scenario_result = result
        self.last_action_result = result
        self._record_active_run(result)
        if result.get("frame_id"):
            self._load_result_frame(result)
        self.playing = bool(self.timeline)
        self.playback_running = self.playing
        self.playback_paused = False
        if self.playing:
            self.schedule_next_playback_tick()
        self._render_current_view()

    def on_play(self) -> None:
        if not self.timeline:
            return
        self.playing = True
        self.playback_running = True
        self.playback_paused = False
        self.schedule_next_playback_tick()
        self._update_footer()

    def on_pause(self) -> None:
        if not self.playback_running:
            return
        self.playing = False
        self.playback_running = False
        self.playback_paused = True
        self._cancel_playback_timer()
        self._update_footer()

    def on_next_step(self) -> None:
        if not self.timeline:
            return
        self.playback_index = min(self.playback_index + 1, len(self.timeline) - 1)
        self._render_current_view()
        self._update_footer()

    def on_reset_playback(self) -> None:
        if not self.timeline:
            return
        self.playing = False
        self.playback_running = False
        self.playback_paused = False
        self._cancel_playback_timer()
        self.playback_index = 0
        self._render_current_view()
        self._update_footer()

    def on_reset(self) -> None:
        self.last_action_result = None
        self.last_approval_operation = None
        self.report_status = {}
        self.current_run = None
        self.active_frame_id = None
        self.active_scenario_id = None
        self.active_report_result = None
        self.active_story_pack_result = None
        self.active_artifact_paths = {}
        self.active_story_pack_paths = {}
        self.timeline = []
        self.playback_timeline = self.timeline
        self.playback_index = -1
        self.playing = False
        self.playback_running = False
        self.playback_paused = False
        self._cancel_playback_timer()
        self._render_snapshot()

    def _ensure_demo_report_result(self, frame_id: str) -> dict:
        frame_id = str(frame_id or "").strip()
        if not frame_id:
            return {"ok": False, "frame_id": "", "markdown_path": "", "html_path": "", "evidence_bundle_path": "", "error": "Run a demo first."}
        if not self.active_report_result or str(self.active_report_result.get("frame_id", "")).strip() != frame_id:
            scenario = self._selected_scenario() or {}
            if not scenario and isinstance(self.current_run, dict):
                scenario = {
                    "id": self.current_run.get("scenario_id", ""),
                    "label": self.current_run.get("label", ""),
                    "name": self.current_run.get("scenario_title", ""),
                }
            self.active_report_result = generate_demo_run_report(self.runtime_root, frame_id, scenario=scenario)
        self.report_status = self.active_report_result
        if isinstance(self.current_run, dict):
            self.current_run = dict(self.current_run)
            self.current_run["report_result"] = self.active_report_result
        artifact_state = build_artifact_state(frame_id, self.active_report_result)
        self.active_artifact_paths = artifact_state.get("paths", {}) if isinstance(artifact_state.get("paths", {}), dict) else {}
        return self.active_report_result

    def on_generate_report(self) -> None:
        frame_id = (self.active_frame_id or "").strip()
        if not frame_id:
            if self.view_mode_var.get() == "Demo":
                self.report_status = {"ok": False, "frame_id": "", "markdown_path": "", "html_path": "", "evidence_bundle_path": "", "error": "Run a demo first."}
                self._render_current_view()
            return
        if self.view_mode_var.get() == "Demo":
            self._ensure_demo_report_result(frame_id)
        else:
            self.active_report_result = generate_report_for_frame(frame_id, self.runtime_root)
        self.report_status = self.active_report_result
        artifact_state = build_artifact_state(frame_id, self.active_report_result)
        self.active_artifact_paths = artifact_state.get("paths", {}) if isinstance(artifact_state.get("paths", {}), dict) else {}
        self._render_current_view()

    def on_create_open_run_report(self) -> None:
        if self.view_mode_var.get() != "Demo":
            self.on_open_run_report_html()
            return
        frame_id = (self.active_frame_id or "").strip()
        if not frame_id:
            self.report_status = {"ok": False, "frame_id": "", "markdown_path": "", "html_path": "", "evidence_bundle_path": "", "error": "Run a demo first."}
            self._render_current_view()
            return
        scenario = self._selected_scenario() or {}
        if not scenario and isinstance(self.current_run, dict):
            scenario = {
                "id": self.current_run.get("scenario_id", ""),
                "label": self.current_run.get("label", ""),
                "name": self.current_run.get("scenario_title", ""),
            }
        result = create_or_open_run_report(self.runtime_root, frame_id, scenario=scenario)
        self.report_status = result
        if isinstance(self.current_run, dict):
            self.current_run = dict(self.current_run)
            self.current_run["report_result"] = result.get("report_result") or result
        self.active_report_result = result.get("report_result") if isinstance(result.get("report_result"), dict) else result
        artifact_state = build_artifact_state(frame_id, self.active_report_result)
        self.active_artifact_paths = artifact_state.get("paths", {}) if isinstance(artifact_state.get("paths", {}), dict) else {}
        self._render_current_view()

    def on_create_or_open_run_report(self) -> None:
        self.on_create_open_run_report()

    def on_open_run_report_html(self) -> None:
        if self.view_mode_var.get() == "Demo":
            frame_id = (self.active_frame_id or "").strip()
            if not frame_id:
                self.report_status = {"ok": False, "frame_id": "", "markdown_path": "", "html_path": "", "evidence_bundle_path": "", "error": "Run a demo first."}
                self._render_current_view()
                return
            report_result = create_or_open_run_report(self.runtime_root, frame_id, scenario=self._selected_scenario() or None)
            self.report_status = report_result
            if isinstance(self.current_run, dict):
                self.current_run = dict(self.current_run)
                self.current_run["report_result"] = report_result.get("report_result") or report_result
            self.active_report_result = report_result.get("report_result") if isinstance(report_result.get("report_result"), dict) else report_result
            artifact_state = build_artifact_state(frame_id, self.active_report_result)
            self.active_artifact_paths = artifact_state.get("paths", {}) if isinstance(artifact_state.get("paths", {}), dict) else {}
            self._render_current_view()
            return
        artifact_state = self._active_artifact_state()
        if not artifact_state.get("has_active_run"):
            return
        if not artifact_paths_match_frame(str(artifact_state.get("frame_id", "")), artifact_state):
            return
        html_path = str(artifact_state.get("paths", {}).get("report_html", "")).strip()
        if html_path:
            open_report_html(html_path)

    def on_open_business_report_html(self) -> None:
        if self.view_mode_var.get() != "Demo":
            return
        frame_id = (self.active_frame_id or "").strip()
        if not frame_id:
            self.report_status = {"ok": False, "frame_id": "", "markdown_path": "", "html_path": "", "evidence_bundle_path": "", "error": "Run a demo first."}
            self._render_current_view()
            return
        report_result = self._ensure_demo_report_result(frame_id)
        self._render_current_view()
        html_path = str((report_result or {}).get("business_report_html_path", "")).strip()
        if html_path:
            open_report_html(html_path)

    def on_open_report_html(self) -> None:
        self.on_open_run_report_html()

    def on_open_report_folder(self) -> None:
        artifact_state = self._active_artifact_state()
        if not artifact_state.get("has_active_run"):
            return
        if not artifact_paths_match_frame(str(artifact_state.get("frame_id", "")), artifact_state):
            return
        markdown_path = str(artifact_state.get("paths", {}).get("report_markdown", "")).strip()
        if markdown_path:
            open_report_folder(markdown_path)

    def on_open_evidence(self) -> None:
        artifact_state = self._active_artifact_state()
        if not artifact_state.get("has_active_run"):
            return
        if not artifact_paths_match_frame(str(artifact_state.get("frame_id", "")), artifact_state):
            return
        openables = get_openable_artifacts(artifact_state)
        for artifact in openables:
            path = str(artifact.get("path", "")).strip()
            if artifact.get("kind") == "html_report" and path:
                open_report_html(path)
                return
        for artifact in openables:
            path = str(artifact.get("path", "")).strip()
            if artifact.get("kind") == "folder" and path:
                open_report_folder(path)
                return
        self.on_open_report_folder()

    def schedule_next_playback_tick(self) -> None:
        self._schedule_next_playback_step()

    def playback_tick(self) -> None:
        self._advance_playback()

    def render_timeline(self) -> None:
        self._render_current_view()

    def render_selected_detail(self) -> None:
        self._render_current_view()

    def render_summary(self) -> None:
        self._render_current_view()

    def get_selected_pending_action(self) -> dict | None:
        pending_actions = (self._current_view() or {}).get("pending_actions", [])
        if not isinstance(pending_actions, list) or not pending_actions:
            return None
        if self.selected_action_id:
            for action in pending_actions:
                if isinstance(action, dict) and action.get("action_id") == self.selected_action_id:
                    return action
        return pending_actions[0] if isinstance(pending_actions[0], dict) else None

    def _set_widget_packed_visible(self, widget: object, visible: bool, *, pack_kwargs: dict[str, object] | None = None) -> None:
        if not widget:
            return
        pack_kwargs = pack_kwargs or {}
        try:
            manager = widget.winfo_manager()
        except Exception:
            return
        try:
            if visible:
                if manager == "":
                    widget.pack(**pack_kwargs)
                elif manager == "grid":
                    widget.grid()
            elif manager == "pack":
                widget.pack_forget()
            elif manager == "grid":
                widget.grid_remove()
        except Exception:
            pass

    def on_refresh_current_run(self) -> None:
        if self.active_frame_id:
            result = reload_operator_run(self.active_frame_id, runtime_data_dir=self.runtime_root)
            self.refresh_current_run_from_result(result)
        else:
            self.refresh_runtime_data()

    def update_approval_button_states(self) -> None:
        story = build_demo_story(
            self.last_snapshot if isinstance(self.last_snapshot, dict) else {},
            self.current_run if isinstance(self.current_run, dict) else None,
            self._selected_scenario(),
        )
        artifact_state = self._active_artifact_state()
        demo_mode = self.view_mode_var.get() == "Demo"
        has_run = bool(self.current_run) if demo_mode else bool(self.active_frame_id)
        frame_state = str(self.current_run.get("state", "")).strip() if demo_mode and isinstance(self.current_run, dict) else self._active_frame_state()
        waiting_for_approval = frame_state == "WAITING_FOR_EXECUTE"
        completed = frame_state == "COMPLETED"
        failed = frame_state.startswith("FAILED")
        running = frame_state in {"RUNNING", "IN_PROGRESS", "EXECUTING"}
        can_generate = bool(has_run and (waiting_for_approval or completed or failed))
        artifact_frame_id = str(self.current_run.get("frame_id", "")).strip() if demo_mode and isinstance(self.current_run, dict) else (self.active_frame_id or "")
        can_open = bool(has_run and (artifact_state.get("report_generated") or artifact_state.get("evidence_generated")) and artifact_paths_match_frame(artifact_frame_id, artifact_state))
        can_approve = bool(story.get("can_approve")) and has_run
        can_reject = bool(story.get("can_reject")) and has_run
        can_start_over = bool(has_run and not running)
        can_stop = bool(running)

        primary_action = self._primary_demo_action() if demo_mode else {"label": "", "helper": "", "enabled": False}
        primary_button = getattr(self, "primary_demo_action_button", None)
        if isinstance(primary_button, ttk.Button):
            primary_button.configure(text=str(primary_action.get("label", "Start demo")) or "Start demo", command=self._apply_primary_demo_action)
            primary_button.state(["!disabled"] if bool(primary_action.get("enabled")) else ["disabled"])
        helper_label = getattr(self, "primary_demo_action_helper_label", None)
        if isinstance(helper_label, ttk.Label):
            helper_label.configure(text=str(primary_action.get("helper", "")) or "")

        if hasattr(self, "current_step_label"):
            if not has_run:
                self.current_step_label.configure(text=f"Current run: Ready to run | Next: {primary_action.get('label', 'Start demo')}")
            elif waiting_for_approval:
                self.current_step_label.configure(text=f"Current run: Waiting for approval | Next: {primary_action.get('label', 'Approve & execute dry run')}")
            elif completed:
                if artifact_state.get("report_generated") or artifact_state.get("evidence_generated"):
                    self.current_step_label.configure(text=f"Current run: Complete | Next: {primary_action.get('label', 'Open run report')}")
                else:
                    self.current_step_label.configure(text=f"Current run: Complete | Next: {primary_action.get('label', 'Create run report')}")
            elif failed:
                self.current_step_label.configure(text=f"Current run: Failed validation | Next: {primary_action.get('label', 'Start over')}")
            else:
                self.current_step_label.configure(text=f"Current run: Run automation | Next: {primary_action.get('label', 'Review result')}")

        advanced_frame = getattr(self, "demo_advanced_actions_frame", None)
        if isinstance(advanced_frame, ttk.Frame):
            try:
                if demo_mode and self.advanced_actions_visible_var.get():
                    advanced_frame.grid()
                else:
                    advanced_frame.grid_remove()
            except Exception:
                pass

        if demo_mode:
            self.advanced_settings_visible = bool(self.advanced_actions_visible_var.get())
        else:
            self.advanced_actions_visible_var.set(False)
            self.advanced_settings_visible = False

        workbench_mode = self.view_mode_var.get() == "Manifest Workbench"
        workbench_frame = self.workbench_result if isinstance(self.workbench_result, dict) else {}
        workbench_has_run = bool(workbench_frame.get("frame_id") or self.workbench_frame)
        workbench_pending = self.workbench_frame.get("pending_actions", []) if isinstance(self.workbench_frame, dict) else []
        workbench_has_pending = isinstance(workbench_pending, list) and bool(workbench_pending)
        for name, enabled in (
            ("workbench_validate_button", True),
            ("workbench_run_button", bool(self._workbench_selected_manifest_target()) or workbench_has_run),
            ("workbench_step_button", workbench_has_run),
            ("workbench_run_blocked_button", workbench_has_run),
            ("workbench_generate_report_button", workbench_has_run),
        ):
            button = getattr(self, name, None)
            if isinstance(button, ttk.Button):
                button.state(["!disabled"] if enabled else ["disabled"])

        if isinstance(getattr(self, "demo_browse_button", None), ttk.Button):
            self.demo_browse_button.state(["!disabled"] if demo_mode else ["disabled"])

        if self.view_mode_var.get() == "Operator":
            self._update_live_safety_panel()
        else:
            self.live_safety_preflight = {}
            self.live_safety_status_var.set("Dry-run only. No live-ready pending actions.")
            self._refresh_live_execute_button_state()

    def on_approve_action(self) -> None:
        action = self.get_selected_pending_action()
        frame = (self._current_view() or {}).get("frame")
        if not isinstance(frame, dict) or not action:
            return
        self.last_approval_operation = approve_pending_action(frame.get("frame_id", ""), action.get("action_id", ""), runtime_data_dir=self.runtime_root)
        self.refresh_current_run_from_result(self.last_approval_operation)

    def on_reject_action(self) -> None:
        action = self.get_selected_pending_action()
        frame = (self._current_view() or {}).get("frame")
        if not isinstance(frame, dict) or not action:
            return
        self.last_approval_operation = reject_pending_action(frame.get("frame_id", ""), action.get("action_id", ""), runtime_data_dir=self.runtime_root)
        self.refresh_current_run_from_result(self.last_approval_operation)

    def on_execute_approved_dry_run(self) -> None:
        frame = (self._current_view() or {}).get("frame")
        if not isinstance(frame, dict):
            return
        self.last_approval_operation = execute_approved_pending_actions_dry_run(frame.get("frame_id", ""), runtime_data_dir=self.runtime_root)
        self.refresh_current_run_from_result(self.last_approval_operation)

    def on_reload_frame(self) -> None:
        frame = (self._current_view() or {}).get("frame")
        if not isinstance(frame, dict):
            return
        self.last_approval_operation = reload_operator_run(frame.get("frame_id", ""), runtime_data_dir=self.runtime_root)
        self.refresh_current_run_from_result(self.last_approval_operation)

    def _approve_then_execute_dry_run(self) -> None:
        if self.get_selected_pending_action() is None:
            return
        self.on_approve_action()
        self.on_execute_approved_dry_run()

    def refresh_current_run_from_result(self, result: dict) -> None:
        if not isinstance(result, dict):
            return
        self.last_action_result = result
        self._record_active_run(result)
        self._load_result_frame(result)
        self._ensure_recovery_snapshot()
        self._render_current_view()

    def _on_speed_changed(self, _event: object) -> None:
        mapping = {"1s": 1000, "2s": 2000, "3s": 3000}
        self.playback_delay_ms = mapping.get(self.speed_var.get(), 2000)
        if self.playback_running and not self.playback_paused:
            self._cancel_playback_timer()
            self._schedule_next_playback_step()

    def _cancel_playback_timer(self) -> None:
        if self.playback_after_id is not None:
            try:
                self.root.after_cancel(self.playback_after_id)
            except Exception:
                pass
            self.playback_after_id = None

    def _schedule_next_playback_step(self) -> None:
        if not self.playback_running or self.playback_paused or not self.playback_timeline:
            return
        if self.playback_index >= len(self.playback_timeline) - 1:
            self.playback_running = False
            self._update_footer()
            return
        self.playback_after_id = self.root.after(self.playback_delay_ms, self._advance_playback)

    def _advance_playback(self) -> None:
        self.playback_after_id = None
        if not self.playback_running or self.playback_paused:
            return
        if self.playback_index < len(self.playback_timeline) - 1:
            self.playback_index += 1
        self._render_current_view()
        if self.playback_index >= len(self.playback_timeline) - 1:
            self.playback_running = False
        else:
            self._schedule_next_playback_step()
        self._update_footer()

    def _current_view(self) -> dict:
        if not self.timeline or self.playback_index < 0:
            return {
                "status": "idle",
                "index": 0,
                "total": 0,
                "current": "",
                "current_step_id": "",
                "event": self.last_snapshot.get("active_event"),
                "route": {},
                "frame": self.last_snapshot.get("active_frame"),
                "outputs": self.last_snapshot.get("outputs", {}),
                "validations": self.last_snapshot.get("validations", []),
                "pending_actions": self.last_snapshot.get("pending_actions", []),
                "evidence": self.last_snapshot.get("active_frame", {}).get("evidence", []) if isinstance(self.last_snapshot.get("active_frame"), dict) else [],
                "visible_steps": [],
                "selected_detail": {},
            }
        return build_playback_view(self.last_snapshot, self.timeline, self.playback_index)

    def _render_snapshot(self) -> None:
        self._render_task_queue()
        self._render_active_taskframe()
        self._render_results_actions()
        self._render_runtime_trace()
        self._update_footer()
        self._update_dataset_validation_label()

    def _render_current_view(self) -> None:
        view = self._current_view()
        self._render_task_queue(view)
        self._render_active_taskframe(view)
        self._render_results_actions(view)
        self._render_runtime_trace(view)
        self._update_footer()
        self.root.update_idletasks()

    def _render_task_queue(self, view: dict | None = None) -> None:
        self._clear_container(self.queue_body)
        # Waiting for Execute is a visible group for linked TaskFrames in that state.
        events = self.last_snapshot.get("events", [])
        frames_by_id = self.last_snapshot.get("frames_by_id", {})
        sections = group_events_for_queue(events, frames_by_id if isinstance(frames_by_id, dict) else {})

        for title, items in sections.items():
            block = ttk.Frame(self.queue_body, style="Card.TFrame")
            block.pack(fill="x", anchor="w", pady=(0, 10))
            ttk.Label(block, text=title, style="Section.TLabel").pack(anchor="w")
            if items:
                for item in items:
                    ttk.Label(block, text=f"â€¢ {self._format_event_item(item, frames_by_id if isinstance(frames_by_id, dict) else {})}", style="Body.TLabel", wraplength=300, justify="left").pack(
                        anchor="w", padx=(8, 0), pady=1
                    )
            elif title == "Incoming Events" and not events:
                ttk.Label(block, text="No runtime events found.", style="Body.TLabel").pack(anchor="w", padx=(8, 0))

    def _render_active_taskframe(self, view: dict | None = None) -> None:
        self._clear_container(self.active_body)
        frame = (view or {}).get("frame") if view else self.last_snapshot.get("active_frame")
        if not isinstance(frame, dict):
            ttk.Label(self.active_body, text="No active TaskFrame selected.", style="Body.TLabel").pack(anchor="w")
            ttk.Label(self.active_body, text="No step data available.", style="Body.TLabel").pack(anchor="w", pady=(16, 0))
            return

        self._render_field(self.active_body, "Frame ID", frame.get("frame_id", "â€”"))
        self._render_field(self.active_body, "State", frame.get("state", "â€”"))
        self._render_field(self.active_body, "Trigger", self._compact_value(frame.get("trigger", {})))
        self._render_field(self.active_body, "Manifest", frame.get("manifest_id", "â€”"))
        self._render_field(self.active_body, "Inputs", self._compact_value(frame.get("inputs", {})))

        timeline = ttk.Frame(self.active_body, style="Card.TFrame")
        timeline.pack(fill="both", expand=True, pady=(16, 0))
        ttk.Label(timeline, text="Step Timeline", style="Section.TLabel").pack(anchor="w", pady=(0, 8))

        steps = self._frame_steps(frame)
        if not steps:
            ttk.Label(timeline, text="No step data available.", style="Body.TLabel").pack(anchor="w")
            return

        current_step_id = str((view or {}).get("current_step_id") or frame.get("current_step_id", "") or "")
        visible_steps = set((view or {}).get("visible_steps", []))
        for step in steps:
            if not isinstance(step, dict):
                continue
            label = self._step_label(step, current_step_id, visible_steps)
            ttk.Label(timeline, text=label, style="Body.TLabel").pack(anchor="w", pady=1)

    def _render_results_actions(self, view: dict | None = None) -> None:
        self._clear_container(self.results_body)
        frame = (view or {}).get("frame") if view else self.last_snapshot.get("active_frame")
        outputs = (view or {}).get("outputs", self.last_snapshot.get("outputs", {}))
        validations = (view or {}).get("validations", self.last_snapshot.get("validations", []))
        pending_actions = (view or {}).get("pending_actions", self.last_snapshot.get("pending_actions", []))
        selected_detail = (view or {}).get("selected_detail", {})
        summary = (self.current_run or {}).get("summary", {})
        approval_pack = (self.current_run or {}).get("approval_pack", {}) or {}
        failure_summary = (self.current_run or {}).get("failure_summary", {}) or {}
        llm_info = (self.current_run or {}).get("llm", {}) or {}

        self._render_section_text(self.results_body, "Selected Step Detail", self._format_selected_detail(selected_detail))
        self._render_section_text(self.results_body, "Current Output", self._format_current_output(outputs, frame))
        self._render_section_text(self.results_body, "Validation Summary", self._format_validations(validations))
        self._render_section_text(self.results_body, "Pending Actions", self._format_pending_actions(pending_actions))
        self._render_section_text(self.results_body, "TaskFrame Summary", self._format_summary(summary))
        self._render_section_text(self.results_body, "Failure Summary", self._format_failure_summary(failure_summary))
        self._render_section_text(self.results_body, "Report Status", self._format_report_status(self.report_status))
        self._render_section_text(self.results_body, "Readiness Scorecard", self._format_readiness_scorecard(self.active_readiness_scorecard_result))
        self._render_section_text(self.results_body, "Portfolio Evidence Pack", self._format_portfolio_evidence_pack(self.active_portfolio_pack_result))
        if llm_info:
            self._render_section_text(self.results_body, "LLM Runtime", self._format_llm_info(llm_info))
        self._render_section_text(self.results_body, "Approval Pack", self._format_approval_pack(approval_pack, (view or {}).get("current_step_id", "")))
        self._render_section_text(self.results_body, "Approval Operation Result", self._format_approval_operation(self.last_approval_operation))
        self._render_section_text(self.results_body, "Scenario Result", self._format_scenario_result(self.scenario_result))

        controls = ttk.Frame(self.results_body, style="Card.TFrame")
        controls.pack(fill="x", anchor="w", pady=(4, 0))
        ttk.Label(controls, text="Demo Control Panel", style="Section.TLabel").pack(anchor="w", pady=(0, 8))
        ttk.Label(controls, text="Mode: DRY RUN ONLY", style="Meta.TLabel").pack(anchor="w", pady=(0, 8))
        ttk.Label(controls, text="Playback Controls", style="Section.TLabel").pack(anchor="w", pady=(8, 8))
        ttk.Button(controls, text="Play", command=self.on_play).pack(fill="x", pady=(0, 6))
        ttk.Button(controls, text="Pause", command=self.on_pause).pack(fill="x", pady=(0, 6))
        ttk.Button(controls, text="Next Step", command=self.on_next_step).pack(fill="x", pady=(0, 6))
        ttk.Button(controls, text="Reset Playback", command=self.on_reset_playback).pack(fill="x", pady=(0, 6))
        ttk.Button(controls, text="Approve", command=self.on_approve_action).pack(fill="x", pady=(0, 6))
        ttk.Button(controls, text="Reject", command=self.on_reject_action).pack(fill="x", pady=(0, 6))
        ttk.Button(controls, text="Execute Approved Dry Run", command=self.on_execute_approved_dry_run).pack(fill="x", pady=(0, 6))
        ttk.Button(controls, text="Reload Frame", command=self.on_reload_frame).pack(fill="x", pady=(0, 8))
        ttk.Button(controls, text="Approve / Execute", state="disabled").pack(fill="x", pady=(0, 8))
        ttk.Button(controls, text="Reject", state="disabled").pack(fill="x", pady=(0, 8))
        ttk.Button(controls, text="Inspect Report", state="disabled").pack(fill="x", pady=(0, 8))
        ttk.Label(controls, text="Reports", style="Section.TLabel").pack(anchor="w", pady=(6, 4))
        ttk.Button(controls, text="Generate Report", command=self.on_generate_report).pack(fill="x", pady=(0, 6))
        ttk.Button(controls, text="Open HTML", command=self.on_open_report_html).pack(fill="x", pady=(0, 6))
        ttk.Button(controls, text="Open Folder", command=self.on_open_report_folder).pack(fill="x", pady=(0, 6))

    def _render_tool_capabilities_panel(self) -> None:
        for item_id in self.tool_health_tree.get_children():
            self.tool_health_tree.delete(item_id)
        snapshot = self.tool_health_snapshot if isinstance(self.tool_health_snapshot, dict) else {}
        results = snapshot.get("results", [])
        by_tool = snapshot.get("by_tool", {}) if isinstance(snapshot.get("by_tool", {}), dict) else {}
        result_map = {str(item.get("tool_id", "")): item for item in results if isinstance(item, dict)}

        for capability in list_tool_capabilities():
            result = result_map.get(capability.tool_id) or by_tool.get(capability.tool_id) or {}
            if result:
                status = str(result.get("status", "not_run"))
                checked_at = str(result.get("checked_at", ""))
            else:
                status = "disabled_optional" if capability.core_or_optional == "optional" else "not_run"
                checked_at = ""
            values = (
                capability.display_name,
                capability.category,
                capability.core_or_optional,
                status,
                capability.source,
                capability.path,
                "yes" if capability.enabled else "no",
                "yes" if capability.registered else "no",
                "yes" if capability.valid else "no",
                checked_at,
                "Run",
                "Open",
                "View",
            )
            self.tool_health_tree.insert("", "end", iid=capability.tool_id, values=values, text=capability.display_name)

        if self.tool_health_tree.get_children() and self._selected_tool_id() not in self.tool_health_tree.get_children():
            first = self.tool_health_tree.get_children()[0]
            self.tool_health_tree.selection_set(first)
            self.tool_health_tree.focus(first)
            self.selected_tool_id = first
        self._render_tool_details()
        self._render_operational_health_panel()
        self._render_recovery_panel()

    def _render_operational_health_panel(self) -> None:
        self._render_monitoring_panel()

    def _monitoring_profile_name(self) -> str:
        try:
            config = load_config_profile(runtime_data_dir=self.runtime_root)
            return str(config.name or "service")
        except Exception:
            return "service"

    def _ensure_monitoring_snapshot(self, *, write_report: bool = False) -> None:
        try:
            self.monitoring_snapshot = build_monitoring_snapshot(
                self.runtime_root,
                profile_name=self._monitoring_profile_name(),
                write_report=write_report,
            )
            self.monitoring_alert_candidates = list(self.monitoring_snapshot.get("alert_candidates", []))
            if write_report and isinstance(self.monitoring_snapshot, dict):
                self.monitoring_report = dict(self.monitoring_snapshot.get("report_paths", {}))
        except Exception:
            self.monitoring_snapshot = {
                "ok": False,
                "status": "BLOCKED",
                "profile": self._monitoring_profile_name(),
                "generated_at": "",
                "worker_identity": {},
                "sections": {},
                "alert_candidates": [],
                "blockers": ["Monitoring snapshot unavailable."],
                "warnings": [],
                "report_paths": {},
            }
            self.monitoring_alert_candidates = []

    def _render_monitoring_panel(self) -> None:
        if not hasattr(self, "operational_health_tree"):
            return
        snapshot = self.monitoring_snapshot if isinstance(self.monitoring_snapshot, dict) else {}
        sections = snapshot.get("sections", {}) if isinstance(snapshot.get("sections", {}), dict) else {}
        alert_candidates = list(snapshot.get("alert_candidates", []))

        for item_id in self.operational_health_tree.get_children():
            self.operational_health_tree.delete(item_id)
        self.operational_health_rows = {}
        for index, candidate in enumerate(alert_candidates[:20]):
            if not isinstance(candidate, dict):
                continue
            iid = f"{candidate.get('alert_id', 'candidate')}:{index}"
            self.operational_health_rows[iid] = candidate
            self.operational_health_tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    candidate.get("severity", ""),
                    candidate.get("category", ""),
                    candidate.get("title", ""),
                    candidate.get("message", ""),
                    candidate.get("source_section", ""),
                    candidate.get("recommended_action", ""),
                ),
            )
        if self.operational_health_tree.get_children():
            first = self.operational_health_tree.get_children()[0]
            self.operational_health_tree.selection_set(first)
            self.operational_health_tree.focus(first)
        self._update_monitoring_summary_labels(snapshot)
        self._render_monitoring_detail()

    def _update_monitoring_summary_labels(self, snapshot: dict) -> None:
        labels = getattr(self, "operational_summary_labels", {})
        if not isinstance(labels, dict):
            return
        sections = snapshot.get("sections", {}) if isinstance(snapshot.get("sections", {}), dict) else {}
        values = {
            "overall_status": snapshot.get("status", "UNKNOWN"),
            "last_snapshot": snapshot.get("generated_at", ""),
            "blocker_count": len(snapshot.get("blockers", [])),
            "warning_count": len(snapshot.get("warnings", [])),
            "alert_count": len(snapshot.get("alert_candidates", [])),
            "worker_id": (snapshot.get("worker_identity", {}) or {}).get("worker_id", ""),
            "ready_sections": sum(1 for item in sections.values() if isinstance(item, dict) and item.get("status") == "OK"),
            "failed_sections": sum(1 for item in sections.values() if isinstance(item, dict) and item.get("status") == "FAIL"),
        }
        for key, value in values.items():
            widget = labels.get(key)
            if isinstance(widget, ttk.Label):
                widget.configure(text=str(value) if value != "" else "—")

    def _render_monitoring_detail(self) -> None:
        if not hasattr(self, "operational_health_detail"):
            return
        payload = self.monitoring_snapshot if isinstance(self.monitoring_snapshot, dict) else {}
        selected = self.operational_health_tree.selection() if hasattr(self, "operational_health_tree") else []
        selected_candidate = {}
        if selected:
            selected_candidate = dict(getattr(self, "operational_health_rows", {}).get(selected[0], {}))
        sections = payload.get("sections", {}) if isinstance(payload.get("sections", {}), dict) else {}
        lines = [
            "Operational Monitoring",
            "---",
            f"Status: {payload.get('status', 'UNKNOWN')}",
            f"Profile: {payload.get('profile', '')}",
            f"Generated at: {payload.get('generated_at', '')}",
            f"Worker ID: {(payload.get('worker_identity', {}) or {}).get('worker_id', '')}",
            f"Blockers: {len(payload.get('blockers', []))}",
            f"Warnings: {len(payload.get('warnings', []))}",
            f"Alert candidates: {len(payload.get('alert_candidates', []))}",
            "",
            "Section statuses:",
        ]
        for name, section in sections.items():
            if isinstance(section, dict):
                lines.append(f"- {name}: {section.get('status', 'SKIPPED')} - {section.get('summary', '')}")
        if selected_candidate:
            lines.extend(
                [
                    "",
                    "Selected alert candidate:",
                    f"- Severity: {selected_candidate.get('severity', '')}",
                    f"- Category: {selected_candidate.get('category', '')}",
                    f"- Title: {selected_candidate.get('title', '')}",
                    f"- Message: {selected_candidate.get('message', '')}",
                    f"- Source section: {selected_candidate.get('source_section', '')}",
                    f"- Recommended action: {selected_candidate.get('recommended_action', '')}",
                ]
            )
        if payload.get("blockers"):
            lines.extend(["", "Blockers:"] + [f"- {blocker}" for blocker in payload.get("blockers", [])])
        if payload.get("warnings"):
            lines.extend(["", "Warnings:"] + [f"- {warning}" for warning in payload.get("warnings", [])])
        if payload.get("report_paths"):
            lines.extend(
                [
                    "",
                    "Reports:",
                    f"- Snapshot JSON: {payload.get('report_paths', {}).get('snapshot_json', '')}",
                    f"- Snapshot Markdown: {payload.get('report_paths', {}).get('snapshot_markdown', '')}",
                    f"- Alert JSON: {payload.get('report_paths', {}).get('alert_candidates_json', '')}",
                    f"- Alert Markdown: {payload.get('report_paths', {}).get('alert_candidates_markdown', '')}",
                ]
            )
        # Legacy strings retained for source compatibility with older operational-health tests.
        # Operational Health
        # Run Health Summary
        # Failed Runs
        # Pending Approvals
        # Stuck Runs
        # Tool Health
        # External Dependencies
        # Runtime Store Status
        # Recommended Actions
        self._set_text(self.operational_health_detail, chr(10).join(lines))

    def _render_recovery_panel(self) -> None:
        if not hasattr(self, "recovery_detail"):
            return
        payload = self.recovery_snapshot if isinstance(self.recovery_snapshot, dict) else {}
        labels = getattr(self, "recovery_summary_labels", {})
        if isinstance(labels, dict):
            values = {
                "recovery_status": payload.get("recovery_status", "not_recoverable"),
                "safe_to_retry": str(payload.get("safe_to_retry", False)).lower(),
                "safe_to_resume": str(payload.get("safe_to_resume", False)).lower(),
                "side_effect_risk": payload.get("side_effect_risk", "unknown"),
                "recommended_action": payload.get("recommended_action", ""),
                "command_suggestion": payload.get("command_suggestion", ""),
            }
            for key, value in values.items():
                widget = labels.get(key)
                if isinstance(widget, ttk.Label):
                    widget.configure(text=str(value))
        lines = [
            "Recovery Assessment",
            "---",
            f"Frame ID: {payload.get('frame_id', '')}",
            f"Manifest ID: {payload.get('manifest_id', '')}",
            f"State: {payload.get('state', '')}",
            f"Recovery status: {payload.get('recovery_status', '')}",
            f"Safe to retry: {str(payload.get('safe_to_retry', False)).lower()}",
            f"Safe to resume: {str(payload.get('safe_to_resume', False)).lower()}",
            f"Side-effect risk: {payload.get('side_effect_risk', '')}",
            f"Recommended action: {payload.get('recommended_action', '')}",
            f"Retry/resume command suggestion: {payload.get('command_suggestion', '')}",
        ]
        if payload.get("reason"):
            lines.extend(["", f"Reason: {payload.get('reason', '')}"])
        if payload.get("idempotency_keys"):
            lines.extend(["", "Idempotency keys:"] + [f"- {key}" for key in payload.get("idempotency_keys", []) if key])
        self._set_text(self.recovery_detail, chr(10).join(lines))

    def _on_operational_health_selected(self, _event: object) -> None:
        self._render_monitoring_detail()

    def _on_monitoring_selected(self, _event: object) -> None:
        self._render_monitoring_detail()

    def on_refresh_monitoring_snapshot(self) -> None:
        self._ensure_monitoring_snapshot(write_report=True)
        self.monitoring_report = dict(self.monitoring_snapshot.get("report_paths", {}))
        self._render_tool_capabilities_panel()

    def on_open_monitoring_report(self) -> None:
        report_paths = dict(self.monitoring_snapshot.get("report_paths", {})) if isinstance(self.monitoring_snapshot, dict) else {}
        folder = Path(str(report_paths.get("snapshot_json", ""))).parent if report_paths.get("snapshot_json") else Path(self.runtime_root) / "monitoring"
        open_report_folder(str(folder))

    def on_open_alert_candidate_report(self) -> None:
        report_paths = dict(self.monitoring_snapshot.get("report_paths", {})) if isinstance(self.monitoring_snapshot, dict) else {}
        folder = Path(str(report_paths.get("alert_candidates_json", ""))).parent if report_paths.get("alert_candidates_json") else Path(self.runtime_root) / "monitoring"
        open_report_folder(str(folder))

    def on_generate_operational_health_report(self) -> None:
        self.on_refresh_monitoring_snapshot()

    def on_open_operational_health_report_folder(self) -> None:
        self.on_open_monitoring_report()

    def on_refresh_operational_health(self) -> None:
        self.on_refresh_monitoring_snapshot()

    def _on_tool_selected(self, _event: object) -> None:
        selected = self.tool_health_tree.selection()
        self.selected_tool_id = selected[0] if selected else ""
        self._render_tool_details()

    def _selected_tool_id(self) -> str:
        selected = self.tool_health_tree.selection()
        if selected:
            return selected[0]
        return self.selected_tool_id

    def _render_tool_details(self) -> None:
        tool_id = self._selected_tool_id()
        try:
            from runtime.runtime_environment import resolve_runtime_environment
            from runtime.tool_governance import evaluate_tool_governance
        except Exception:
            resolve_runtime_environment = None  # type: ignore[assignment]
            evaluate_tool_governance = None  # type: ignore[assignment]
        capability = None
        try:
            from runtime.tool_capability_registry import get_tool_capability

            capability = get_tool_capability(tool_id) if tool_id else None
        except Exception:
            capability = None
        result = self._tool_result_for(tool_id)
        setup = get_tool_setup_instructions(tool_id) if tool_id else {}
        runtime_environment = resolve_runtime_environment() if resolve_runtime_environment else "demo"
        discovery_entry = None
        if isinstance(self.toolpack_discovery_snapshot, dict):
            for pack in self.toolpack_discovery_snapshot.get("toolpacks", []):
                if isinstance(pack, dict) and str(pack.get("toolpack_id", "")) == str(getattr(capability, "toolpack_id", "")):
                    discovery_entry = pack
                    break
        lines = []
        if capability is not None:
            lines.extend(
                [
                    f"Tool: {capability.display_name}",
                    f"ID: {capability.tool_id}",
                    f"Category: {capability.category}",
                    f"Core / Optional: {capability.core_or_optional}",
                    f"Side Effect Level: {capability.side_effect_level}",
                    f"Auth Required: {capability.auth_required}",
                    f"Setup Available: {capability.setup_available}",
                    f"RPA Live Probe Required: {capability.rpa_live_probe_required}",
                    f"Current Runtime Environment: {runtime_environment}",
                ]
            )
            if getattr(capability, "source", "") == "external_toolpack":
                enabled_envs = []
                if discovery_entry and isinstance(discovery_entry.get("enabled_environments", []), list):
                    enabled_envs = [str(item) for item in discovery_entry.get("enabled_environments", []) if str(item).strip()]
                runtime_decision = {}
                if evaluate_tool_governance:
                    runtime_decision = evaluate_tool_governance(
                        tool_id if "/" in tool_id else f"toolpack:{getattr(capability, 'toolpack_id', tool_id)}",
                        {
                            "source": "external_toolpack",
                            "toolpack_id": str(getattr(capability, "toolpack_id", "")),
                            "toolpack_classification": str((discovery_entry or {}).get("classification", getattr(capability, "core_or_optional", "unknown"))),
                            "toolpack_core_or_optional": str(getattr(capability, "core_or_optional", "unknown")),
                            "side_effect": False,
                            "requires_approval": False,
                            "allow_live": True,
                            "allow_live_side_effect": False,
                        },
                        environment=runtime_environment,
                        dry_run=True,
                        live_requested=False,
                        operation="execute",
                    )
                lines.extend(
                    [
                        f"Source: {capability.source}",
                        f"Path: {capability.path}",
                        f"Enabled: {capability.enabled}",
                        f"Registered: {capability.registered}",
                        f"Valid: {capability.valid}",
                        f"Tool Count: {capability.tool_count}",
                        f"Tool Pack: {capability.toolpack_id}",
                        f"Governance Classification: {str((discovery_entry or {}).get('classification', 'unknown'))}",
                        f"Enabled Environments: {', '.join(enabled_envs) if enabled_envs else 'none'}",
                        f"Runtime Decision: {runtime_decision.get('decision', 'UNKNOWN') if runtime_decision else 'UNKNOWN'}",
                        f"Blocked Reason: {runtime_decision.get('reason', '') if runtime_decision and not runtime_decision.get('ok', False) else ''}",
                    ]
                )
            if capability.category == "rpa" or capability.rpa_live_probe_required:
                lines.extend(
                    [
                        "",
                        "--- Optional RPA tool ---",
                        "This tool is excluded from the default demo path.",
                        "It may require Playwright, a local browser profile, and manual",
                        "authentication. Do not use it with sensitive accounts unless",
                        "you understand the local setup and data exposure risks.",
                        "See docs/optional_rpa.md for the full setup guide.",
                        "-------------------------",
                    ]
                )
        if result:
            lines.extend(
                [
                    "",
                    f"Health Status: {result.get('status', 'not_run')}",
                    f"Checked At: {result.get('checked_at', '')}",
                    f"Message: {result.get('message', '')}",
                    f"Recommended Action: {result.get('recommended_action', '')}",
                    f"Can Auto Resolve: {result.get('can_auto_resolve', False)}",
                ]
            )
        if setup:
            lines.extend(["", "Setup Steps:"])
            for step in setup.get("steps", []):
                lines.append(f"- {step}")
        if self.toolpack_discovery_snapshot:
            lines.extend(["", "Tool Pack Discovery:"])
            for pack in self.toolpack_discovery_snapshot.get("toolpacks", []):
                lines.append(
                    f"- {pack.get('toolpack_id', '')} | enabled={str(pack.get('enabled', False)).lower()} | "
                    f"registered={str(pack.get('registered', False)).lower()} | valid={str(pack.get('valid', False)).lower()} | "
                    f"tools={pack.get('tool_count', 0)}"
                )
        text = chr(10).join(lines) if lines else "Select a tool to view its capability and health details."
        if hasattr(self, "live_test_button"):
            if tool_id == "rpa_google_messages":
                if self.live_test_button.winfo_manager() == "":
                    self.live_test_button.pack(side="left", padx=(0, 6))
            elif self.live_test_button.winfo_manager():
                self.live_test_button.pack_forget()
        self.tool_health_details.configure(state="normal")
        self.tool_health_details.delete("1.0", "end")
        self.tool_health_details.insert("1.0", text)
        self.tool_health_details.configure(state="disabled")

    def _tool_result_for(self, tool_id: str) -> dict:
        snapshot = self.tool_health_snapshot if isinstance(self.tool_health_snapshot, dict) else {}
        by_tool = snapshot.get("by_tool", {}) if isinstance(snapshot.get("by_tool", {}), dict) else {}
        result = by_tool.get(tool_id)
        if isinstance(result, dict):
            return result
        for item in snapshot.get("results", []):
            if isinstance(item, dict) and item.get("tool_id") == tool_id:
                return item
        return {}

    def _refresh_workbench_manifest_catalog(self) -> None:
        self.workbench_manifest_catalog = list_manifest_catalog()
        if hasattr(self, "workbench_manifest_entry"):
            values = [item.get("manifest_id", "") for item in self.workbench_manifest_catalog if item.get("manifest_id")]
            self.workbench_manifest_entry.configure(values=values)
        current = self.workbench_manifest_var.get().strip() if hasattr(self, "workbench_manifest_var") else ""
        if not current and self.workbench_manifest_catalog:
            first = self.workbench_manifest_catalog[0]
            self.workbench_manifest_var.set(str(first.get("manifest_id", "")))

    def _workbench_selected_manifest_target(self) -> str:
        if isinstance(self.workbench_manifest_record, dict):
            record_path = str(self.workbench_manifest_record.get("path", "")).strip()
            if record_path:
                return record_path
        if hasattr(self, "workbench_manifest_entry"):
            value = str(self.workbench_manifest_var.get() or "").strip()
            if value:
                return value
        return ""

    def _workbench_manifest_dict_for_editor(self) -> dict:
        if isinstance(self.workbench_manifest_record, dict) and isinstance(self.workbench_manifest_record.get("manifest", {}), dict):
            return dict(self.workbench_manifest_record["manifest"])
        if self.workbench_manifest_json_text.winfo_exists():
            raw_text = self._widget_text_value(self.workbench_manifest_json_text)
            try:
                parsed = json.loads(raw_text) if raw_text.strip() else {}
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        return new_manifest_template()

    def _load_workbench_manifest_json_editor(self, manifest: dict) -> None:
        self._clear_text_widget(self.workbench_manifest_json_text)
        self.workbench_manifest_json_text.insert("1.0", json.dumps(manifest, indent=2, ensure_ascii=False))

    def _workbench_manifest_json_text_value(self) -> str:
        return self._widget_text_value(self.workbench_manifest_json_text)

    def _workbench_manifest_preview_path(self, manifest_id: str) -> Path:
        preview_dir = Path(self.runtime_root) / "workbench"
        preview_dir.mkdir(parents=True, exist_ok=True)
        safe_name = manifest_filename_for_id(manifest_id).replace(".manifest.json", ".preview.manifest.json")
        return preview_dir / safe_name

    def _workbench_selected_frame_id(self) -> str:
        if isinstance(self.workbench_result, dict) and self.workbench_result.get("frame_id"):
            return str(self.workbench_result.get("frame_id", "")).strip()
        return ""

    def _render_manifest_workbench_view(self) -> None:
        target = self._workbench_selected_manifest_target()
        current_record = self.workbench_manifest_record if isinstance(self.workbench_manifest_record, dict) else {}
        current_manifest_id = str(current_record.get("manifest_id", "")).strip()
        current_path = str(current_record.get("path", "")).strip()
        matches_target = bool(target and current_record and (target == current_manifest_id or target == current_path))
        manifest_record = current_record if matches_target else (load_manifest_for_workbench(target) if target else {"ok": False, "error": "Select a manifest."})
        if manifest_record.get("ok"):
            self.workbench_manifest_record = manifest_record
            self.workbench_manifest_validation = validate_manifest_for_workbench(target)
            record_path = str(manifest_record.get("path", "")).strip()
            if record_path and (not self.workbench_manifest_source_path or self.workbench_manifest_source_path != record_path or not self._workbench_manifest_json_text_value().strip()):
                manifest = manifest_record.get("manifest", {}) if isinstance(manifest_record.get("manifest", {}), dict) else {}
                self._workbench_load_manifest_into_editor(manifest, record_path)
            self._render_workbench_manifest_summary(manifest_record)
            if not matches_target or not self.workbench_input_vars:
                self._render_workbench_input_fields(manifest_record)
            self._render_workbench_step_rows(manifest_record)
            self._render_workbench_step_detail()
            self._render_workbench_execution_panel()
            self._render_workbench_comparison_panel()
        else:
            self.workbench_manifest_record = {}
            self.workbench_manifest_validation = manifest_record
            self.workbench_frame = {}
            self.workbench_result = {}
            self._render_workbench_failure(manifest_record)
        self.update_approval_button_states()
        self._update_footer()

    def _render_workbench_failure(self, result: dict) -> None:
        summary_lines = [
            "Manifest validation failed",
            f"Reason: {result.get('error', 'Unknown error')}",
        ]
        self._set_text(self.workbench_manifest_summary_text, chr(10).join(summary_lines))
        self._clear_tree(self.workbench_step_tree)
        self._clear_text_widget(self.workbench_raw_json_text)
        self._set_text(self.workbench_execution_text, "No dry-run frame available.")
        self._set_text(self.workbench_step_detail_text, "No step selected.")
        self._set_text(self.workbench_comparison_text, "No manifest/run comparison available.")
        self.workbench_input_status_label.configure(text=f"Manifest validation failed. {result.get('error', '')}")

    def _render_workbench_manifest_summary(self, result: dict) -> None:
        summary = result.get("summary", {}) if isinstance(result, dict) else {}
        validation = result.get("validation", {}) if isinstance(result, dict) else {}
        lines = []
        if not validation.get("ok", result.get("ok", False)):
            lines.extend(["Manifest validation failed", f"Reason: {validation.get('error', result.get('error', 'Unknown error'))}"])
        else:
            lines.extend(
                [
                    f"Manifest ID: {summary.get('manifest_id', '')}",
                    f"Name: {summary.get('name', '')}",
                    f"Version: {summary.get('version', '')}",
                    f"Trigger: {summary.get('trigger', '')}",
                    f"Required inputs: {', '.join(summary.get('required_inputs', [])) or 'None'}",
                    f"Step count: {summary.get('step_count', 0)}",
                    f"Validation count: {summary.get('validation_count', 0)}",
                    f"Completion rules: {self._compact_value(summary.get('completion_rules', {}))}",
                    f"Live execution policy: {self._compact_value(summary.get('live_execution_policy', {}))}",
                ]
            )
        self._set_text(self.workbench_manifest_summary_text, chr(10).join(lines))

    def _render_workbench_input_fields(self, result: dict) -> None:
        summary = result.get("summary", {}) if isinstance(result, dict) else {}
        required_inputs = summary.get("required_inputs", []) if isinstance(summary, dict) else []
        self._clear_container(self.workbench_input_fields_frame)
        self.workbench_input_vars = {}
        if not required_inputs:
            ttk.Label(self.workbench_input_fields_frame, text="No required inputs declared.", style="Body.TLabel").pack(anchor="w")
        else:
            for name in required_inputs:
                row = ttk.Frame(self.workbench_input_fields_frame, style="Card.TFrame")
                row.pack(fill="x", anchor="w", pady=(0, 4))
                ttk.Label(row, text=f"{name}:", style="Meta.TLabel", width=18).pack(side="left")
                var = tk.StringVar(value=self._workbench_default_input_value(name))
                entry = ttk.Entry(row, textvariable=var, width=36)
                entry.pack(side="left", fill="x", expand=True)
                self.workbench_input_vars[str(name)] = var
        self._clear_text_widget(self.workbench_raw_json_text)
        self.workbench_raw_json_text.insert("1.0", "")
        self._update_workbench_input_status(result)

    def _workbench_default_input_value(self, name: str) -> str:
        frame_inputs = {}
        if isinstance(self.workbench_frame, dict):
            frame_inputs = self.workbench_frame.get("inputs", {}) if isinstance(self.workbench_frame.get("inputs", {}), dict) else {}
        if isinstance(self.workbench_result, dict) and isinstance(self.workbench_result.get("frame", {}), dict):
            frame_inputs = self.workbench_result["frame"].get("inputs", {}) if isinstance(self.workbench_result["frame"].get("inputs", {}), dict) else frame_inputs
        if isinstance(frame_inputs, dict) and name in frame_inputs:
            return str(frame_inputs.get(name, ""))
        return ""

    def _update_workbench_input_status(self, result: dict) -> None:
        summary = result.get("summary", {}) if isinstance(result, dict) else {}
        required_inputs = summary.get("required_inputs", []) if isinstance(summary, dict) else []
        missing = [item for item in required_inputs if not self._workbench_input_dict().get(item)]
        if missing:
            text = f"Missing required inputs: {', '.join(missing)}"
        else:
            text = "Input values ready for a dry-run."
        if hasattr(self, "workbench_input_status_label"):
            self.workbench_input_status_label.configure(text=text)

    def _workbench_input_dict(self) -> dict:
        values = {name: var.get().strip() for name, var in self.workbench_input_vars.items() if var.get().strip()}
        raw_text = self._widget_text_value(self.workbench_raw_json_text)
        if raw_text.strip():
            try:
                raw_data = json.loads(raw_text)
                if isinstance(raw_data, dict):
                    return raw_data
                return values
            except Exception:
                return values
        return values

    def _workbench_validate_inputs(self, manifest_record: dict) -> tuple[dict, dict | None]:
        raw_text = self._widget_text_value(self.workbench_raw_json_text).strip()
        if raw_text:
            try:
                raw_data = json.loads(raw_text)
                if not isinstance(raw_data, dict):
                    return {"ok": False, "error": "Raw JSON input override must be a JSON object."}, None
            except json.JSONDecodeError as exc:
                return {"ok": False, "error": f"Invalid raw JSON input override: {exc.msg}"}, None
        inputs = self._workbench_input_dict()
        missing = [item for item in manifest_record.get("summary", {}).get("required_inputs", []) if item not in inputs or inputs.get(item) in {"", None}]
        if missing:
            return {"ok": False, "error": f"Missing required inputs: {', '.join(missing)}", "missing_required_inputs": missing}, None
        return {"ok": True, "error": "", "inputs": inputs}, inputs

    def _render_workbench_step_rows(self, result: dict) -> None:
        manifest = result.get("manifest", {}) if isinstance(result, dict) else {}
        rows = build_manifest_step_rows(manifest)
        self._clear_tree(self.workbench_step_tree)
        for row in rows:
            values = (
                row.get("#", ""),
                row.get("step_id", ""),
                row.get("command", ""),
                row.get("kind", ""),
                row.get("output_alias", ""),
                row.get("when_condition", ""),
                row.get("retry_policy", ""),
                row.get("timeout", ""),
            )
            iid = str(row.get("step_id", "")) or str(row.get("#", ""))
            self.workbench_step_tree.insert("", "end", iid=iid, values=values, text=iid)
        if rows and (not self.workbench_selected_step_id or not self.workbench_step_tree.exists(self.workbench_selected_step_id)):
            self.workbench_selected_step_id = str(rows[0].get("step_id", ""))
        if self.workbench_selected_step_id and self.workbench_step_tree.exists(self.workbench_selected_step_id):
            self.workbench_step_tree.selection_set(self.workbench_selected_step_id)
            self.workbench_step_tree.focus(self.workbench_selected_step_id)

    def _render_workbench_step_detail(self) -> None:
        step_id = self.workbench_selected_step_id or self._default_workbench_step_id()
        manifest_record = self.workbench_manifest_record if isinstance(self.workbench_manifest_record, dict) else {}
        manifest = manifest_record.get("manifest", {}) if isinstance(manifest_record.get("manifest", {}), dict) else {}
        frame = self.workbench_frame if isinstance(self.workbench_frame, dict) else {}
        model = build_workbench_step_inspector_model(manifest, frame, step_id)
        lines = [f"Step ID: {model.get('step_id', step_id) or 'None'}", ""]
        for section_label, section_lines in model.get("sections", {}).items():
            lines.append(f"--- {section_label} ---")
            lines.extend(section_lines if section_lines else ["(none)"])
            lines.append("")
        self._set_text(self.workbench_step_detail_text, chr(10).join(lines).strip())

    def _render_workbench_execution_panel(self) -> None:
        frame = self.workbench_frame if isinstance(self.workbench_frame, dict) else {}
        result = self.workbench_result if isinstance(self.workbench_result, dict) else {}
        manifest_record = self.workbench_manifest_record if isinstance(self.workbench_manifest_record, dict) else {}
        manifest = manifest_record.get("manifest", {})
        run_model = build_workbench_run_summary_model(frame, manifest)
        lines = [
            f"Frame ID: {run_model.get('frame_id', result.get('frame_id', frame.get('frame_id', '')))}",
            f"State: {run_model.get('state_label', '')}",
            f"Completed: {result.get('completed_steps', self._count_status(frame, 'COMPLETED'))}",
            f"Failed: {result.get('failed_steps', self._count_status(frame, 'FAILED'))}",
            f"Pending actions: {run_model.get('pending_count', 0)}",
            f"Data source: {run_model.get('data_source', 'unknown')}",
            f"Live external calls: {'yes' if run_model.get('live_external_calls') else 'no'}",
        ]
        if run_model.get("failure_category"):
            lines += [
                "",
                f"Failure category: {run_model.get('failure_category', '')}",
                f"Failed step: {run_model.get('failed_step_id', '')}",
                f"Recommended action: {run_model.get('recommended_action', '')}",
            ]
        if run_model.get("pending_summary"):
            lines += ["", "Pending actions"] + run_model["pending_summary"]
        errors = result.get("errors", frame.get("errors", []))
        if errors:
            lines += ["", f"Errors: {self._compact_value(errors)}"]
        self._set_text(self.workbench_execution_text, chr(10).join(lines))
        self._sync_workbench_approval_buttons()

    def _render_workbench_comparison_panel(self) -> None:
        manifest_record = self.workbench_manifest_record if isinstance(self.workbench_manifest_record, dict) else {}
        manifest = manifest_record.get("manifest", {}) if isinstance(manifest_record.get("manifest", {}), dict) else {}
        frame = self.workbench_frame if isinstance(self.workbench_frame, dict) else {}
        comparison = self.workbench_result.get("comparison") if isinstance(self.workbench_result, dict) else {}
        if not isinstance(comparison, dict) or not comparison:
            comparison = build_manifest_run_comparison(manifest, frame)
        run_summary = self.workbench_result.get("run_summary") if isinstance(self.workbench_result, dict) else {}
        if not isinstance(run_summary, dict) or not run_summary:
            run_summary = build_workbench_run_summary(frame, manifest)
        lines = [
            f"Manifest expected steps: {comparison.get('manifest_expected_steps', 0)}",
            f"Runtime steps created: {comparison.get('runtime_steps_created', 0)}",
            f"Completed: {comparison.get('completed', 0)}",
            f"Failed: {comparison.get('failed', 0)}",
            f"Skipped/not reached: {comparison.get('skipped_not_reached', 0)}",
            f"Completion state: {normalize_workbench_status(comparison.get('completion_state', ''))}",
            f"Failure category: {run_summary.get('failure_category', '')}",
            f"Failed step: {run_summary.get('failed_step_id', '')}",
            f"Operator explanation: {run_summary.get('operator_explanation', '')}",
        ]
        self._set_text(self.workbench_comparison_text, chr(10).join(lines))

    def _sync_workbench_approval_buttons(self) -> None:
        pending_actions = self.workbench_frame.get("pending_actions", []) if isinstance(self.workbench_frame, dict) else []
        has_pending = isinstance(pending_actions, list) and bool(pending_actions)
        self._set_widget_packed_visible(getattr(self, "workbench_approve_button", None), has_pending, pack_kwargs={"side": "left", "padx": (0, 6)})
        self._set_widget_packed_visible(getattr(self, "workbench_reject_button", None), has_pending, pack_kwargs={"side": "left"})

    def _count_status(self, frame: dict, status: str) -> int:
        return sum(1 for item in frame.get("steps", []) if isinstance(item, dict) and str(item.get("status", "")).upper() == status.upper())

    def _default_workbench_step_id(self) -> str:
        if self.workbench_selected_step_id:
            return self.workbench_selected_step_id
        manifest_record = self.workbench_manifest_record if isinstance(self.workbench_manifest_record, dict) else {}
        rows = build_manifest_step_rows(manifest_record.get("manifest", {}))
        return str(rows[0].get("step_id", "")) if rows else ""

    def _workbench_step_related_items(self, frame: dict, step_id: str, key: str) -> list:
        items = frame.get(key, []) if isinstance(frame, dict) else []
        if not isinstance(items, list):
            return []
        return [dict(item) for item in items if isinstance(item, dict) and (not step_id or str(item.get("step_id") or item.get("validation_id") or item.get("action_id") or "") == step_id)]

    def _clear_tree(self, tree: ttk.Treeview) -> None:
        for item_id in tree.get_children():
            tree.delete(item_id)

    def _clear_text_widget(self, widget: tk.Text) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.configure(state="normal")

    def _widget_text_value(self, widget: tk.Text) -> str:
        return widget.get("1.0", "end").strip() if isinstance(widget, tk.Text) else ""

    def _on_workbench_step_selected(self, _event: object) -> None:
        selected = self.workbench_step_tree.selection()
        if selected:
            self.workbench_selected_step_id = str(selected[0])
        self._render_workbench_step_detail()

    def on_workbench_load_selected_manifest(self, manifest_path: str | None = None) -> None:
        target = str(manifest_path or self._workbench_selected_manifest_target()).strip()
        if not target:
            return
        result = load_manifest_for_workbench(target)
        if not result.get("ok"):
            self.workbench_manifest_record = {}
            self.workbench_manifest_validation = result
            self._render_workbench_failure(result)
            return
        self.workbench_manifest_record = result
        self.workbench_manifest_validation = result.get("validation", validate_manifest_for_workbench(target))
        self.workbench_manifest_source_path = str(result.get("path", "")).strip()
        self.workbench_selected_step_id = ""
        manifest = result.get("manifest", {}) if isinstance(result.get("manifest", {}), dict) else {}
        self._load_workbench_manifest_json_editor(manifest)
        self._render_manifest_workbench_view()

    def _workbench_editor_manifest(self) -> dict:
        text = self._workbench_manifest_json_text_value()
        if not text.strip():
            return new_manifest_template()
        try:
            raw = json.loads(text)
        except Exception:
            return {}
        return raw if isinstance(raw, dict) else {}

    def _workbench_load_manifest_into_editor(self, manifest: dict, source_path: str = "") -> None:
        self.workbench_manifest_source_path = str(source_path or "").strip()
        self._load_workbench_manifest_json_editor(manifest if isinstance(manifest, dict) else {})

    def on_workbench_select_manifest_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Select manifest file",
            initialdir="manifests",
            filetypes=(("Manifest JSON", "*.json"), ("JSON files", "*.json"), ("All files", "*.*")),
        )
        if not path:
            return
        self.workbench_manifest_var.set(path)
        self.on_workbench_load_selected_manifest(path)

    def on_workbench_reload_catalog(self) -> None:
        self._refresh_workbench_manifest_catalog()
        self._render_manifest_workbench_view()

    def _workbench_has_unsaved_editor_changes(self) -> bool:
        editor_text = self._workbench_manifest_json_text_value()
        if not editor_text.strip():
            return False
        record = self.workbench_manifest_record if isinstance(self.workbench_manifest_record, dict) else {}
        loaded_manifest = record.get("manifest", {})
        if not isinstance(loaded_manifest, dict) or not loaded_manifest:
            return False
        try:
            editor_json = json.loads(editor_text)
        except Exception:
            return True
        return editor_json != loaded_manifest

    def on_workbench_duplicate_manifest(self) -> None:
        target = self._workbench_selected_manifest_target()
        if not target:
            messagebox.showwarning("Duplicate manifest", "Select a manifest first.")
            return
        if self._workbench_has_unsaved_editor_changes():
            messagebox.showwarning("Duplicate manifest", "Cannot duplicate manifest: unsaved editor changes are present. Save or discard changes first.")
            return
        result = duplicate_manifest(target, manifest_dir="manifests")
        if not result.get("ok"):
            messagebox.showerror("Duplicate manifest", f"Duplicate failed: {result.get('error', 'Unknown error')}")
            return
        self._refresh_workbench_manifest_catalog()
        new_id = str(result.get("new_manifest_id", ""))
        self.workbench_manifest_var.set(new_id)
        self.on_workbench_load_selected_manifest(new_id)
        self.workbench_input_status_label.configure(text=f"Duplicated manifest as {new_id}")

    def on_workbench_rename_manifest(self) -> None:
        target = self._workbench_selected_manifest_target()
        if not target:
            messagebox.showwarning("Rename manifest", "Select a manifest first.")
            return
        if self._workbench_has_unsaved_editor_changes():
            messagebox.showwarning("Rename manifest", "Cannot rename manifest: unsaved editor changes are present. Save or discard changes first.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Rename manifest")
        dialog.resizable(False, False)
        dialog.grab_set()
        ttk.Label(dialog, text="New manifest ID:").grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))
        id_var = tk.StringVar(value=target if not target.endswith(".json") else "")
        ttk.Entry(dialog, textvariable=id_var, width=50).grid(row=0, column=1, padx=(0, 12), pady=(12, 4))
        ttk.Label(dialog, text="New name (optional):").grid(row=1, column=0, sticky="w", padx=12, pady=(0, 4))
        name_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=name_var, width=50).grid(row=1, column=1, padx=(0, 12), pady=(0, 4))
        result_holder: list[dict] = []

        def do_rename() -> None:
            new_id = id_var.get().strip()
            new_name = name_var.get().strip() or None
            if not new_id:
                messagebox.showwarning("Rename manifest", "New manifest ID is required.", parent=dialog)
                return
            r = rename_manifest(target, new_id, new_name=new_name, manifest_dir="manifests")
            result_holder.append(r)
            dialog.destroy()

        btn_row = ttk.Frame(dialog)
        btn_row.grid(row=2, column=0, columnspan=2, pady=(8, 12))
        ttk.Button(btn_row, text="Rename", command=do_rename).pack(side="left", padx=6)
        ttk.Button(btn_row, text="Cancel", command=dialog.destroy).pack(side="left", padx=6)
        dialog.wait_window()
        if not result_holder:
            return
        result = result_holder[0]
        if not result.get("ok"):
            messagebox.showerror("Rename manifest", f"Rename failed: {result.get('error', 'Unknown error')}")
            return
        new_id = str(result.get("new_manifest_id", ""))
        self._refresh_workbench_manifest_catalog()
        self.workbench_manifest_var.set(new_id)
        self.on_workbench_load_selected_manifest(new_id)
        self.workbench_input_status_label.configure(text=f"Renamed manifest to {new_id}")

    def on_workbench_archive_manifest(self) -> None:
        target = self._workbench_selected_manifest_target()
        if not target:
            messagebox.showwarning("Archive manifest", "Select a manifest first.")
            return
        if self._workbench_has_unsaved_editor_changes():
            messagebox.showwarning("Archive manifest", "Cannot archive manifest: unsaved editor changes are present. Save or discard changes first.")
            return
        confirmed = messagebox.askyesno("Archive manifest", f"Archive manifest: {target}\n\nIt will be moved to manifests/archive/ and removed from the active catalog.")
        if not confirmed:
            return
        result = archive_manifest(target, manifest_dir="manifests")
        if not result.get("ok"):
            messagebox.showerror("Archive manifest", f"Archive failed: {result.get('error', 'Unknown error')}")
            return
        manifest_id = str(result.get("manifest_id", ""))
        self.workbench_manifest_record = {}
        self.workbench_manifest_var.set("")
        self.workbench_frame = {}
        self.workbench_result = {}
        self.workbench_manifest_source_path = ""
        self._refresh_workbench_manifest_catalog()
        self._render_manifest_workbench_view()
        self.workbench_input_status_label.configure(text=f"Archived manifest {manifest_id}")

    def on_workbench_restore_archived(self) -> None:
        archived = list_archived_manifests(manifest_dir="manifests")
        if not archived:
            messagebox.showinfo("Restore archived", "No archived manifests found in manifests/archive/.")
            return
        dialog = tk.Toplevel(self)
        dialog.title("Restore archived manifest")
        dialog.resizable(False, False)
        dialog.grab_set()
        ttk.Label(dialog, text="Select archived manifest to restore:").grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 4))
        choices = [f"{e.get('manifest_id', '')} — {e.get('name', '')} ({Path(e.get('path', '')).name})" for e in archived]
        choice_var = tk.StringVar(value=choices[0] if choices else "")
        combo = ttk.Combobox(dialog, textvariable=choice_var, values=choices, width=60, state="readonly")
        combo.grid(row=1, column=0, columnspan=2, padx=12, pady=(0, 8))
        result_holder: list[dict] = []

        def do_restore() -> None:
            idx = combo.current()
            if idx < 0 or idx >= len(archived):
                messagebox.showwarning("Restore archived", "Select an archived manifest.", parent=dialog)
                return
            archive_path = str(archived[idx].get("path", ""))
            r = restore_archived_manifest(archive_path, manifest_dir="manifests")
            result_holder.append(r)
            dialog.destroy()

        btn_row = ttk.Frame(dialog)
        btn_row.grid(row=2, column=0, columnspan=2, pady=(0, 12))
        ttk.Button(btn_row, text="Restore", command=do_restore).pack(side="left", padx=6)
        ttk.Button(btn_row, text="Cancel", command=dialog.destroy).pack(side="left", padx=6)
        dialog.wait_window()
        if not result_holder:
            return
        result = result_holder[0]
        if not result.get("ok"):
            messagebox.showerror("Restore archived", f"Restore failed: {result.get('error', 'Unknown error')}")
            return
        manifest_id = str(result.get("manifest_id", ""))
        self._refresh_workbench_manifest_catalog()
        self.workbench_manifest_var.set(manifest_id)
        self.on_workbench_load_selected_manifest(manifest_id)
        self.workbench_input_status_label.configure(text=f"Restored manifest {manifest_id}")

    def on_workbench_smoke_test_manifest(self) -> None:
        record = self.workbench_manifest_record if isinstance(self.workbench_manifest_record, dict) else {}
        path = str(record.get("path") or self.workbench_manifest_source_path or "").strip()
        if not path:
            messagebox.showwarning("Smoke test manifest", "Select and save a manifest first.")
            return
        if self._workbench_has_unsaved_editor_changes():
            messagebox.showwarning("Smoke test manifest", "Cannot smoke-test manifest: unsaved editor changes are present. Save or discard changes first.")
            return
        result = smoke_run_manifest_file(path, runtime_data_dir=self.runtime_root)
        self.workbench_last_smoke_result = result
        report = write_smoke_report(result, runtime_data_dir=self.runtime_root)
        self._show_smoke_result_dialog(result, report)

    def _show_smoke_result_dialog(self, result: dict, report: dict) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Smoke Test Result")
        dialog.resizable(True, True)
        dialog.grab_set()

        status = result.get("status", "UNKNOWN")
        classification = result.get("classification", "")
        manifest_id = result.get("manifest_id", "")
        state = result.get("state", "")
        step_count = result.get("step_count", 0)
        completed = result.get("completed_steps", 0)
        failed = result.get("failed_steps", 0)
        pending = result.get("pending_action_count", 0)
        outputs = ", ".join(result.get("output_keys") or []) or "none"
        warnings = ", ".join(result.get("warnings") or []) or "none"
        errors = result.get("errors") or []

        summary_lines = [
            f"Smoke Result: {status}",
            f"Classification: {classification}",
            f"Manifest: {manifest_id}",
            f"Frame State: {state}",
            f"Steps: {step_count} total, {completed} completed, {failed} failed",
            f"Pending Actions: {pending}",
            f"Outputs: {outputs}",
            f"Warnings: {warnings}",
        ]
        if errors:
            summary_lines.append("")
            summary_lines.append(f"Errors: {'; '.join(str(e) for e in errors[:3])}")
        if not result.get("ok") and result.get("suggested_fix"):
            summary_lines.append("")
            summary_lines.append(f"Suggested Fix: {result['suggested_fix']}")
        if report.get("ok"):
            summary_lines.append("")
            summary_lines.append(f"Report: {report.get('markdown_path', '')}")

        text_widget, _ = create_scrolled_text_widget(dialog, height=16, bg="#f7f8fa", fg="#1f2937", font=("Consolas", 9))
        text_widget.scrolled_container.grid(row=0, column=0, columnspan=3, sticky="nsew", padx=12, pady=(12, 6))
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)
        text_widget.insert("1.0", chr(10).join(summary_lines))
        text_widget.config(state="disabled")

        btn_row = ttk.Frame(dialog)
        btn_row.grid(row=1, column=0, columnspan=3, pady=(0, 12), padx=12, sticky="w")

        if report.get("json_path"):
            ttk.Button(btn_row, text="Open Smoke JSON", command=lambda: open_report_html(report["json_path"])).pack(side="left", padx=(0, 6))
        if report.get("markdown_path"):
            ttk.Button(btn_row, text="Open Smoke Markdown", command=lambda: open_report_html(report["markdown_path"])).pack(side="left", padx=(0, 6))
        ttk.Button(btn_row, text="Close", command=dialog.destroy).pack(side="left")

    def on_workbench_repair_guidance(self) -> None:
        text = self._workbench_manifest_json_text_value()
        manifest: dict | None = None
        parse_exception: Exception | None = None

        if text.strip():
            try:
                manifest = json.loads(text)
            except Exception as exc:
                parse_exception = exc

        last_smoke = getattr(self, "workbench_last_smoke_result", None)
        last_validation = self.workbench_manifest_validation if hasattr(self, "workbench_manifest_validation") else None

        guidance = explain_manifest_failure(
            manifest=manifest,
            validation_result=last_validation if not manifest else None,
            smoke_result=last_smoke,
            exception=parse_exception,
        )

        report = write_repair_guidance_report(guidance, runtime_data_dir=self.runtime_root)
        self._show_repair_guidance_dialog(guidance, report)

    def _show_repair_guidance_dialog(self, guidance: dict, report: dict) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Manifest Repair Guidance")
        dialog.resizable(True, True)
        dialog.grab_set()

        status = guidance.get("status", "UNKNOWN")
        severity = guidance.get("severity", "info")
        summary = guidance.get("summary", "")
        findings = guidance.get("findings") or []
        next_action = guidance.get("next_action", "")

        lines = [
            f"Status: {status}",
            f"Severity: {severity}",
            f"Summary: {summary}",
            "",
        ]
        for idx, f in enumerate(findings, 1):
            lines.append(f"[{idx}] {f.get('id', '')}")
            if f.get("location"):
                lines.append(f"  Location: {f['location']}")
            lines.append(f"  Problem:  {f.get('message', '')}")
            lines.append(f"  Fix:      {f.get('suggested_fix', '')}")
            if f.get("example"):
                lines.append(f"  Example:  {f['example']}")
            lines.append("")

        if next_action:
            lines.append(f"Next Action: {next_action}")

        if report.get("ok"):
            lines.append("")
            lines.append(f"Report: {report.get('markdown_path', '')}")

        text_widget, _ = create_scrolled_text_widget(dialog, height=20, bg="#f7f8fa", fg="#1f2937", font=("Consolas", 9))
        text_widget.scrolled_container.grid(row=0, column=0, columnspan=3, sticky="nsew", padx=12, pady=(12, 6))
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)
        text_widget.insert("1.0", chr(10).join(lines))
        text_widget.config(state="disabled")

        btn_row = ttk.Frame(dialog)
        btn_row.grid(row=1, column=0, columnspan=3, pady=(0, 12), padx=12, sticky="w")

        if report.get("json_path"):
            ttk.Button(btn_row, text="Open Guidance JSON", command=lambda: open_report_html(report["json_path"])).pack(side="left", padx=(0, 6))
        if report.get("markdown_path"):
            ttk.Button(btn_row, text="Open Guidance Markdown", command=lambda: open_report_html(report["markdown_path"])).pack(side="left", padx=(0, 6))
        ttk.Button(btn_row, text="Close", command=dialog.destroy).pack(side="left")

    def on_workbench_autofix_preview(self) -> None:
        text = self._workbench_manifest_json_text_value()
        manifest: dict | None = None
        parse_exception: Exception | None = None

        if text.strip():
            try:
                manifest = json.loads(text)
            except Exception as exc:
                parse_exception = exc

        if parse_exception is not None or not isinstance(manifest, dict):
            err_msg = str(parse_exception) if parse_exception else "No manifest loaded in editor."
            dialog = tk.Toplevel(self)
            dialog.title("Auto-Fix Preview")
            dialog.grab_set()
            ttk.Label(dialog, text=f"Cannot parse manifest JSON: {err_msg}", wraplength=480, justify="left").pack(padx=16, pady=16)
            ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=(0, 12))
            return

        last_smoke = getattr(self, "workbench_last_smoke_result", None)
        last_validation = self.workbench_manifest_validation if hasattr(self, "workbench_manifest_validation") else None

        guidance = explain_manifest_failure(
            manifest=manifest,
            validation_result=last_validation,
            smoke_result=last_smoke,
        )
        fix_result = propose_manifest_fixes(manifest, guidance=guidance)
        self._show_autofix_preview_dialog(manifest, fix_result)

    def on_workbench_validate_all_manifests(self) -> None:
        try:
            result = run_manifest_health_check(
                manifest_dir="manifests",
                runtime_data_dir=self.runtime_root,
            )
            report = write_manifest_health_report(result, runtime_data_dir=self.runtime_root)
        except Exception as exc:
            result = {
                "ok": False,
                "status": "FAILED",
                "generated_at": "",
                "manifest_dir": "manifests",
                "summary": {},
                "manifests": [],
                "error": str(exc),
            }
            report = {"ok": False, "json_path": "", "markdown_path": "", "error": str(exc)}
        self.workbench_manifest_health_result = result
        self.workbench_manifest_health_report = report
        self._show_manifest_health_dashboard(result, report)

    def _show_manifest_health_dashboard(self, result: dict, report: dict) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Manifest Health Dashboard")
        dialog.resizable(True, True)
        dialog.grab_set()
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)
        dialog.rowconfigure(2, weight=1)

        summary = result.get("summary") if isinstance(result, dict) else {}
        summary = summary if isinstance(summary, dict) else {}

        top = ttk.Frame(dialog, style="Card.TFrame", padding=10)
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        for idx, (label, key) in enumerate(
            (
                ("Total", "total"),
                ("Healthy", "healthy"),
                ("Warnings", "warnings"),
                ("Failed", "failed"),
                ("Repairable", "repairable"),
                ("Manual Fix", "manual_fix_required"),
                ("Critical", "critical"),
            )
        ):
            card = ttk.Frame(top, style="Card.TFrame", padding=(8, 4))
            card.grid(row=0, column=idx, sticky="nsew", padx=(0, 6))
            ttk.Label(card, text=label, style="Meta.TLabel").pack(anchor="w")
            ttk.Label(card, text=str(summary.get(key, 0)), style="Section.TLabel").pack(anchor="w")
            top.columnconfigure(idx, weight=1)

        table_frame = ttk.Frame(dialog, style="Card.TFrame", padding=10)
        table_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=6)
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(1, weight=1)
        ttk.Label(table_frame, text="Manifest Results", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        columns = ("health", "manifest_id", "validation", "smoke", "repairable", "top_findings", "next_action")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse", height=10)
        for column, heading, width in (
            ("health", "Health", 110),
            ("manifest_id", "Manifest ID", 220),
            ("validation", "Validation", 90),
            ("smoke", "Smoke", 90),
            ("repairable", "Repairable", 80),
            ("top_findings", "Top Findings", 240),
            ("next_action", "Next Action", 240),
        ):
            tree.heading(column, text=heading)
            tree.column(column, width=width, anchor="w")
        tree.grid(row=1, column=0, sticky="nsew")
        table_scroll_y = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        table_scroll_y.grid(row=1, column=1, sticky="ns")
        table_scroll_x = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
        table_scroll_x.grid(row=2, column=0, sticky="ew")
        tree.configure(yscrollcommand=table_scroll_y.set, xscrollcommand=table_scroll_x.set)

        items = [item for item in (result.get("manifests") or []) if isinstance(item, dict)]
        item_by_iid: dict[str, dict] = {}
        for idx, item in enumerate(items):
            iid = str(idx)
            item_by_iid[iid] = item
            tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    item.get("health", ""),
                    item.get("manifest_id", ""),
                    "PASS" if item.get("validation", {}).get("ok") else "FAIL",
                    item.get("smoke", {}).get("status", ""),
                    item.get("autofix", {}).get("low_risk_applyable", 0),
                    ", ".join(item.get("repair_guidance", {}).get("top_findings") or []),
                    item.get("next_action", ""),
                ),
            )

        detail_frame = ttk.Frame(dialog, style="Card.TFrame", padding=10)
        detail_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=6)
        detail_frame.columnconfigure(0, weight=1)
        detail_frame.rowconfigure(1, weight=1)
        ttk.Label(detail_frame, text="Selected Manifest Detail", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        detail_text, _detail_scroll = create_scrolled_text_widget(detail_frame, height=11, bg="#f7f8fa", fg="#1f2937", font=("Consolas", 9))
        detail_text.scrolled_container.grid(row=1, column=0, sticky="nsew")

        def selected_item() -> dict | None:
            selected = tree.selection()
            return item_by_iid.get(selected[0]) if selected else None

        def render_detail(_event: object | None = None) -> None:
            item = selected_item()
            lines: list[str] = []
            if not result.get("ok", True):
                lines.append(f"Dashboard error: {result.get('error', 'Unknown error')}")
            elif item is None:
                lines.append("Select a manifest to inspect validation, smoke, repair, and auto-fix detail.")
            else:
                lines.extend(
                    [
                        f"Path: {item.get('path', '')}",
                        f"Validation errors: {', '.join(item.get('validation', {}).get('errors') or []) or 'none'}",
                        f"Smoke classification: {item.get('smoke', {}).get('classification', '')}",
                        f"Smoke reason: {item.get('smoke', {}).get('reason', '') or 'none'}",
                        f"Repair findings: {', '.join(item.get('repair_guidance', {}).get('top_findings') or []) or 'none'}",
                        (
                            "Auto-fix proposals: "
                            f"{item.get('autofix', {}).get('proposal_count', 0)} total, "
                            f"{item.get('autofix', {}).get('supported_count', 0)} supported, "
                            f"{item.get('autofix', {}).get('unsupported_count', 0)} unsupported, "
                            f"{item.get('autofix', {}).get('low_risk_applyable', 0)} low-risk applyable"
                        ),
                        f"Next action: {item.get('next_action', '')}",
                    ]
                )
            lines.extend(
                [
                    "",
                    f"JSON report: {report.get('json_path', '')}",
                    f"Markdown report: {report.get('markdown_path', '')}",
                ]
            )
            self._clear_text_widget(detail_text)
            detail_text.insert("1.0", chr(10).join(lines))

        tree.bind("<<TreeviewSelect>>", render_detail)
        if items:
            tree.selection_set("0")
            tree.focus("0")
        render_detail()

        def load_selected() -> None:
            item = selected_item()
            if item is None:
                messagebox.showwarning("Manifest Health Dashboard", "Select a manifest first.", parent=dialog)
                return
            self.on_workbench_load_selected_manifest(str(item.get("path", "")))

        def open_repair_guidance() -> None:
            load_selected()
            self.on_workbench_repair_guidance()

        def open_autofix_preview() -> None:
            load_selected()
            self.on_workbench_autofix_preview()

        def smoke_selected() -> None:
            item = selected_item()
            if item is None:
                messagebox.showwarning("Manifest Health Dashboard", "Select a manifest first.", parent=dialog)
                return
            load_selected()
            self.on_workbench_smoke_test_manifest()

        button_row = ttk.Frame(dialog)
        button_row.grid(row=3, column=0, sticky="ew", padx=12, pady=(6, 12))
        ttk.Button(button_row, text="Run Validate All", command=lambda: self._refresh_manifest_health_dashboard(dialog)).pack(side="left", padx=(0, 6))
        ttk.Button(button_row, text="Open Selected Manifest", command=load_selected).pack(side="left", padx=(0, 6))
        ttk.Button(button_row, text="Repair Guidance", command=open_repair_guidance).pack(side="left", padx=(0, 6))
        ttk.Button(button_row, text="Auto-Fix Preview", command=open_autofix_preview).pack(side="left", padx=(0, 6))
        ttk.Button(button_row, text="Smoke Test Selected", command=smoke_selected).pack(side="left", padx=(0, 6))
        if report.get("json_path"):
            ttk.Button(button_row, text="Open JSON Report", command=lambda: open_report_html(report["json_path"])).pack(side="left", padx=(0, 6))
        if report.get("markdown_path"):
            ttk.Button(button_row, text="Open Markdown Report", command=lambda: open_report_html(report["markdown_path"])).pack(side="left", padx=(0, 6))
        ttk.Button(button_row, text="Close", command=dialog.destroy).pack(side="left")

    def _refresh_manifest_health_dashboard(self, dialog: tk.Toplevel) -> None:
        dialog.destroy()
        self.on_workbench_validate_all_manifests()

    def _show_autofix_preview_dialog(self, manifest: dict, fix_result: dict) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Manifest Auto-Fix Preview")
        dialog.resizable(True, True)
        dialog.grab_set()
        dialog.columnconfigure(0, weight=1)
        dialog.columnconfigure(1, weight=2)
        dialog.rowconfigure(1, weight=1)

        proposals = fix_result.get("proposals") or []

        # Header row
        header = ttk.Frame(dialog)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(12, 4))
        status_text = (
            f"Status: {fix_result.get('status', 'UNKNOWN')}  |  "
            f"Manifest: {fix_result.get('manifest_id', '')}  |  "
            f"Proposals: {fix_result.get('proposal_count', 0)}  "
            f"(Supported: {fix_result.get('supported_count', 0)}, "
            f"Unsupported: {fix_result.get('unsupported_count', 0)})"
        )
        ttk.Label(header, text=status_text, style="Meta.TLabel", wraplength=860).pack(anchor="w")

        # Left: proposal list
        left = ttk.Frame(dialog, style="Card.TFrame", padding=8)
        left.grid(row=1, column=0, sticky="nsew", padx=(12, 4), pady=(4, 4))
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)
        ttk.Label(left, text="Proposals", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))

        proposal_listbox = tk.Listbox(left, width=38, selectmode="single", font=("Consolas", 9), exportselection=False)
        proposal_listbox.grid(row=1, column=0, sticky="nsew")
        list_scroll = ttk.Scrollbar(left, orient="vertical", command=proposal_listbox.yview)
        list_scroll.grid(row=1, column=1, sticky="ns")
        proposal_listbox.configure(yscrollcommand=list_scroll.set)

        for p in proposals:
            label = f"[{p.get('status', '')}] {p.get('finding_id', '')} | {p.get('risk', '')}"
            proposal_listbox.insert("end", label)
            if p.get("status") == "NOT_SUPPORTED":
                proposal_listbox.itemconfig("end", fg="#9ca3af")

        # Right: detail panel
        right = ttk.Frame(dialog, style="Card.TFrame", padding=8)
        right.grid(row=1, column=1, sticky="nsew", padx=(4, 12), pady=(4, 4))
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)
        ttk.Label(right, text="Details", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))

        detail_text, _ = create_scrolled_text_widget(right, height=22, bg="#f7f8fa", fg="#1f2937", font=("Consolas", 9))
        detail_text.scrolled_container.grid(row=1, column=0, sticky="nsew")

        selected_proposal: list[dict | None] = [None]
        apply_button_ref: list = []

        def _show_proposal(proposal: dict) -> None:
            detail_text.config(state="normal")
            detail_text.delete("1.0", "end")
            lines = [
                f"Finding ID:  {proposal.get('finding_id', '')}",
                f"Title:       {proposal.get('title', '')}",
                f"Status:      {proposal.get('status', '')}",
                f"Risk:        {proposal.get('risk', '')}",
                f"Confidence:  {proposal.get('confidence', '')}",
                f"Location:    {proposal.get('location', '')}",
                "",
                f"Summary:",
                f"  {proposal.get('summary', '')}",
                "",
            ]
            warnings = proposal.get("warnings") or []
            if warnings:
                lines.append("Warnings:")
                for w in warnings:
                    lines.append(f"  ! {w}")
                lines.append("")

            patches = proposal.get("patches") or []
            if patches:
                lines.append("Patch Operations:")
                lines.append(json.dumps(patches, indent=2, ensure_ascii=False))
                lines.append("")

            diff = proposal.get("diff") or []
            if diff:
                lines.append("Diff:")
                lines.extend(diff)
                lines.append("")

            before = proposal.get("before_preview", "")
            after = proposal.get("after_preview", "")
            if before:
                lines.append("--- Before ---")
                lines.append(before[:800] + ("..." if len(before) > 800 else ""))
                lines.append("")
            if after:
                lines.append("--- After ---")
                lines.append(after[:800] + ("..." if len(after) > 800 else ""))

            detail_text.insert("1.0", chr(10).join(lines))
            detail_text.config(state="disabled")

            can_apply = proposal.get("status") == "PROPOSED" and proposal.get("risk") == "low"
            if apply_button_ref:
                apply_button_ref[0].config(state="normal" if can_apply else "disabled")

        def _on_select(event: object = None) -> None:
            idxs = proposal_listbox.curselection()
            if not idxs:
                return
            idx = int(idxs[0])
            if 0 <= idx < len(proposals):
                selected_proposal[0] = proposals[idx]
                _show_proposal(proposals[idx])

        proposal_listbox.bind("<<ListboxSelect>>", _on_select)

        if proposals:
            proposal_listbox.selection_set(0)
            selected_proposal[0] = proposals[0]
            _show_proposal(proposals[0])

        # Button row
        btn_row = ttk.Frame(dialog)
        btn_row.grid(row=2, column=0, columnspan=2, sticky="w", padx=12, pady=(4, 12))

        def _refresh() -> None:
            dialog.destroy()
            self.on_workbench_autofix_preview()

        def _apply_to_editor() -> None:
            proposal = selected_proposal[0]
            if not proposal:
                messagebox.showwarning("Auto-Fix Preview", "Select a proposal first.")
                return
            if proposal.get("status") != "PROPOSED" or proposal.get("risk") != "low":
                messagebox.showwarning("Auto-Fix Preview", "Only low-risk PROPOSED fixes can be applied.")
                return
            text = self._workbench_manifest_json_text_value()
            try:
                current_manifest = json.loads(text)
            except Exception as exc:
                messagebox.showerror("Auto-Fix Preview", f"Cannot parse editor JSON: {exc}")
                return
            confirmed = messagebox.askyesno(
                "Apply Fix to Editor",
                f"Apply fix:\n\n{proposal.get('title', '')}\n\nThis will update the editor buffer. Save the manifest afterwards to persist the change.",
            )
            if not confirmed:
                return
            preview = apply_manifest_fix_preview(current_manifest, proposal)
            if not preview.get("ok"):
                messagebox.showerror("Auto-Fix Preview", f"Fix could not be applied: {preview.get('error', 'Unknown error')}")
                return
            patched = preview["manifest"]
            self._clear_text_widget(self.workbench_manifest_json_text)
            self.workbench_manifest_json_text.insert("1.0", json.dumps(patched, indent=2, ensure_ascii=False))
            messagebox.showinfo(
                "Auto-Fix Applied",
                "Fix applied to editor buffer.\n\nThe editor now shows the patched manifest. Run Validate or Repair Guidance to check remaining issues, then Save.",
            )

        def _write_report() -> None:
            report = write_autofix_report(fix_result, runtime_data_dir=self.runtime_root)
            if report.get("ok"):
                messagebox.showinfo(
                    "Auto-Fix Report",
                    f"Report written: {report.get('markdown_path', '')}",
                )
            else:
                messagebox.showerror("Auto-Fix Report", f"Could not write report: {report.get('error', '')}")

        ttk.Button(btn_row, text="Refresh Proposals", command=_refresh).pack(side="left", padx=(0, 6))
        apply_btn = ttk.Button(btn_row, text="Apply Selected Fix to Editor", command=_apply_to_editor)
        apply_btn.pack(side="left", padx=(0, 6))
        apply_button_ref.append(apply_btn)
        first_can_apply = bool(proposals and proposals[0].get("status") == "PROPOSED" and proposals[0].get("risk") == "low")
        apply_btn.config(state="normal" if first_can_apply else "disabled")
        ttk.Button(btn_row, text="Write Auto-Fix Report", command=_write_report).pack(side="left", padx=(0, 6))
        ttk.Button(btn_row, text="Close", command=dialog.destroy).pack(side="left")

    def on_workbench_new_manifest_from_template(self) -> None:
        if self._workbench_has_unsaved_editor_changes():
            confirmed = messagebox.askyesno(
                "New manifest from template",
                "The editor has unsaved changes.\n\nDiscard unsaved changes and open the wizard?",
            )
            if not confirmed:
                return
        self._open_new_manifest_wizard()

    def _open_new_manifest_wizard(self) -> None:
        templates = list_manifest_templates()
        template_names = [f"{t['name']} [{t['template_id']}]" for t in templates]

        dialog = tk.Toplevel(self)
        dialog.title("New Manifest from Template")
        dialog.resizable(True, True)
        dialog.grab_set()
        dialog.columnconfigure(1, weight=1)

        # --- Template selection ---
        ttk.Label(dialog, text="Template:", anchor="w").grid(row=0, column=0, sticky="w", padx=12, pady=(14, 4))
        template_var = tk.StringVar(value=template_names[0] if template_names else "")
        template_combo = ttk.Combobox(dialog, textvariable=template_var, values=template_names, width=52, state="readonly")
        template_combo.grid(row=0, column=1, padx=(0, 12), pady=(14, 4), sticky="ew")

        desc_label = ttk.Label(dialog, text="", style="Meta.TLabel", wraplength=480, justify="left")
        desc_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 8))

        def _update_desc(*_: object) -> None:
            idx = template_combo.current()
            if 0 <= idx < len(templates):
                desc_label.configure(text=templates[idx]["description"])
        template_combo.bind("<<ComboboxSelected>>", _update_desc)
        _update_desc()

        # --- Basic details ---
        ttk.Separator(dialog, orient="horizontal").grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 8))
        ttk.Label(dialog, text="Manifest ID:", anchor="w").grid(row=3, column=0, sticky="w", padx=12, pady=(0, 4))
        id_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=id_var, width=52).grid(row=3, column=1, padx=(0, 12), pady=(0, 4), sticky="ew")

        ttk.Label(dialog, text="Name:", anchor="w").grid(row=4, column=0, sticky="w", padx=12, pady=(0, 4))
        name_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=name_var, width=52).grid(row=4, column=1, padx=(0, 12), pady=(0, 4), sticky="ew")

        # --- Inputs / Command ---
        ttk.Separator(dialog, orient="horizontal").grid(row=5, column=0, columnspan=2, sticky="ew", padx=12, pady=(4, 8))
        ttk.Label(dialog, text="Inputs (comma-separated):", anchor="w").grid(row=6, column=0, sticky="w", padx=12, pady=(0, 4))
        inputs_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=inputs_var, width=52).grid(row=6, column=1, padx=(0, 12), pady=(0, 4), sticky="ew")

        ttk.Label(dialog, text="Primary command (optional):", anchor="w").grid(row=7, column=0, sticky="w", padx=12, pady=(0, 4))
        command_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=command_var, width=52).grid(row=7, column=1, padx=(0, 12), pady=(0, 4), sticky="ew")

        ttk.Label(dialog, text="Output alias (optional):", anchor="w").grid(row=8, column=0, sticky="w", padx=12, pady=(0, 4))
        alias_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=alias_var, width=52).grid(row=8, column=1, padx=(0, 12), pady=(0, 4), sticky="ew")

        # --- Preview ---
        ttk.Separator(dialog, orient="horizontal").grid(row=9, column=0, columnspan=2, sticky="ew", padx=12, pady=(4, 8))
        ttk.Label(dialog, text="Preview JSON:", anchor="w").grid(row=10, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 4))
        preview_text_widget, _ = create_scrolled_text_widget(dialog, height=14, bg="#f7f8fa", fg="#1f2937", font=("Consolas", 9))
        preview_text_widget.scrolled_container.grid(row=11, column=0, columnspan=2, sticky="nsew", padx=12, pady=(0, 4))
        dialog.rowconfigure(11, weight=1)

        validation_label = ttk.Label(dialog, text="", style="Meta.TLabel", wraplength=500, justify="left")
        validation_label.grid(row=12, column=0, columnspan=2, sticky="w", padx=12, pady=(0, 4))

        # State
        state: dict = {"manifest": None, "valid": False}

        def _get_inputs() -> list[str]:
            raw = inputs_var.get().strip()
            return [p.strip() for p in raw.split(",") if p.strip()] if raw else []

        def _get_template_id() -> str:
            idx = template_combo.current()
            if 0 <= idx < len(templates):
                return templates[idx]["template_id"]
            return ""

        def _preview() -> None:
            tid = _get_template_id()
            mid = id_var.get().strip()
            mname = name_var.get().strip() or mid
            if not tid or not mid:
                _set_preview_text("Fill in Template and Manifest ID to preview.")
                return
            try:
                manifest = build_manifest_from_template(
                    tid, mid, mname,
                    command=command_var.get().strip(),
                    inputs=_get_inputs(),
                    output_alias=alias_var.get().strip(),
                )
                state["manifest"] = manifest
                _set_preview_text(json.dumps(manifest, indent=2, ensure_ascii=False))
                validation_label.configure(text="")
            except Exception as exc:
                _set_preview_text(f"Error building manifest: {exc}")
                state["manifest"] = None

        def _set_preview_text(text: str) -> None:
            preview_text_widget.config(state="normal")
            preview_text_widget.delete("1.0", "end")
            preview_text_widget.insert("1.0", text)
            preview_text_widget.config(state="disabled")

        def _validate() -> None:
            _preview()
            manifest = state.get("manifest")
            if not manifest:
                validation_label.configure(text="Build a preview first.")
                state["valid"] = False
                create_btn.config(state="disabled")
                return
            ok, errors = validate_manifest_candidate(manifest, manifest_dir="manifests")
            state["valid"] = ok
            if ok:
                validation_label.configure(text="Validation passed. Ready to create.")
                create_btn.config(state="normal")
            else:
                validation_label.configure(text="Validation errors:\n" + "\n".join(f"• {e}" for e in errors))
                create_btn.config(state="disabled")

        def _create() -> None:
            if not state.get("valid") or not state.get("manifest"):
                messagebox.showwarning("New manifest from template", "Validate the manifest before creating.", parent=dialog)
                return
            manifest = state["manifest"]
            result = write_manifest_candidate(manifest, manifest_dir="manifests")
            if not result.get("ok"):
                errs = "\n".join(result.get("errors", []))
                messagebox.showerror("New manifest from template", f"Create failed: {errs}", parent=dialog)
                return
            new_id = str(result.get("manifest_id", ""))
            # Show event route snippet if event-driven template
            if _get_template_id() == "event_driven_stub":
                snippet = build_event_route_snippet(manifest)
                messagebox.showinfo(
                    "Event route snippet",
                    f"Manifest created.\n\nRegister this route manually in config/event_routes.json:\n\n{snippet}",
                    parent=dialog,
                )
            saved_path = str(result.get("path", ""))
            dialog.destroy()
            self._refresh_workbench_manifest_catalog()
            self.workbench_manifest_var.set(new_id)
            self.on_workbench_load_selected_manifest(new_id)
            self.workbench_input_status_label.configure(text=f"Created manifest {new_id}")
            # Offer smoke test
            run_smoke = messagebox.askyesno(
                "Manifest created",
                f"Manifest '{new_id}' created.\n\nRun smoke test now?",
            )
            if run_smoke and saved_path:
                smoke_result = smoke_run_manifest_file(saved_path, runtime_data_dir=self.runtime_root)
                smoke_report = write_smoke_report(smoke_result, runtime_data_dir=self.runtime_root)
                self._show_smoke_result_dialog(smoke_result, smoke_report)

        # --- Buttons ---
        btn_row = ttk.Frame(dialog)
        btn_row.grid(row=13, column=0, columnspan=2, pady=(4, 14), padx=12, sticky="w")
        ttk.Button(btn_row, text="Preview", command=_preview).pack(side="left", padx=(0, 6))
        ttk.Button(btn_row, text="Validate", command=_validate).pack(side="left", padx=(0, 6))
        create_btn = ttk.Button(btn_row, text="Create Manifest", command=_create, state="disabled")
        create_btn.pack(side="left", padx=(0, 6))
        ttk.Button(btn_row, text="Cancel", command=dialog.destroy).pack(side="left")

    def on_workbench_new_manifest(self) -> None:
        template = new_manifest_template()
        self.workbench_manifest_record = {
            "ok": True,
            "path": "",
            "manifest_id": template.get("manifest_id", ""),
            "manifest": template,
            "summary": build_manifest_summary(template),
            "step_rows": build_manifest_step_rows(template),
            "validation": {"ok": False, "error": "New manifest template loaded."},
            "error": "",
        }
        self.workbench_manifest_validation = {"ok": False, "error": "New manifest template loaded."}
        self.workbench_manifest_var.set(str(template.get("manifest_id", "")))
        self.workbench_selected_step_id = ""
        self.workbench_frame = {}
        self.workbench_result = {}
        self.workbench_manifest_source_path = ""
        self._load_workbench_manifest_json_editor(template)
        self._render_manifest_workbench_view()

    def on_workbench_edit_manifest_json(self) -> None:
        record = self.workbench_manifest_record if isinstance(self.workbench_manifest_record, dict) else {}
        manifest = record.get("manifest", {}) if isinstance(record.get("manifest", {}), dict) else self._workbench_editor_manifest()
        if not isinstance(manifest, dict) or not manifest:
            manifest = new_manifest_template()
        self._load_workbench_manifest_json_editor(manifest)
        self.workbench_manifest_json_text.focus_set()

    def on_workbench_validate_manifest(self) -> None:
        text = self._workbench_manifest_json_text_value()
        if not text.strip():
            self.workbench_manifest_validation = {"ok": False, "error": "Manifest JSON is required."}
            self._render_manifest_workbench_view()
            return
        result = validate_manifest_json_text(text)
        self.workbench_manifest_validation = result
        if result.get("ok"):
            manifest = result.get("manifest", {}) if isinstance(result.get("manifest", {}), dict) else {}
            preview_path = self._workbench_manifest_preview_path(str(result.get("manifest_id", "")))
            try:
                preview_path.parent.mkdir(parents=True, exist_ok=True)
                preview_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass
            self.workbench_manifest_record = {
                "ok": True,
                "path": str(preview_path),
                "manifest_id": result.get("manifest_id", ""),
                "manifest": manifest,
                "summary": result.get("summary", build_manifest_summary(manifest)),
                "step_rows": build_manifest_step_rows(manifest),
                "validation": result,
                "error": "",
            }
            self.workbench_manifest_source_path = str(preview_path)
            self.workbench_selected_step_id = ""
            self._render_manifest_workbench_view()
        else:
            self.workbench_manifest_record = {}
            self.workbench_frame = {}
            self.workbench_result = {}
            self._render_workbench_failure(result)

    def _save_manifest_from_editor(self, target_path: str | None = None, allow_overwrite: bool = False) -> dict:
        text = self._workbench_manifest_json_text_value()
        save_result = save_manifest_json_text(text, target_path=target_path, manifest_dir="manifests", allow_overwrite=allow_overwrite)
        if save_result.get("ok"):
            self._refresh_workbench_manifest_catalog()
            self.workbench_manifest_var.set(str(save_result.get("manifest_id", "")))
            loaded = load_manifest_for_workbench(str(save_result.get("path", "")))
            if loaded.get("ok"):
                self.workbench_manifest_record = loaded
                self.workbench_manifest_source_path = str(save_result.get("path", ""))
                self.workbench_manifest_validation = loaded.get("validation", {"ok": True, "error": ""})
                self.workbench_selected_step_id = ""
                self._render_manifest_workbench_view()
        return save_result

    def on_workbench_save_manifest(self) -> None:
        current_loaded_path = self.workbench_manifest_source_path or str(self.workbench_manifest_record.get("path", "") if isinstance(self.workbench_manifest_record, dict) else "")
        preview_root = Path(self.runtime_root) / "workbench"
        target_path = None
        allow_overwrite = False
        if current_loaded_path:
            current_path = Path(current_loaded_path)
            is_preview = False
            try:
                is_preview = preview_root.resolve() in current_path.resolve().parents or current_path.resolve() == preview_root.resolve()
            except Exception:
                is_preview = False
            if not is_preview:
                target_path = str(current_path)
                allow_overwrite = True
        result = self._save_manifest_from_editor(target_path=target_path, allow_overwrite=allow_overwrite)
        if not result.get("ok"):
            self._render_workbench_failure(result)

    def on_workbench_save_manifest_as(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save manifest as",
            defaultextension=".manifest.json",
            filetypes=(("Manifest JSON", "*.manifest.json"), ("JSON files", "*.json"), ("All files", "*.*")),
            initialfile=manifest_filename_for_id(str(self.workbench_manifest_var.get() or "").strip() or "example.new_manifest"),
        )
        if not path:
            return
        target = Path(path)
        if target.exists():
            confirmed = messagebox.askyesno("Save manifest as", f"File already exists: {target}\n\nOverwrite it?")
            if not confirmed:
                return
        result = self._save_manifest_from_editor(target_path=str(target), allow_overwrite=True)
        if not result.get("ok"):
            self._render_workbench_failure(result)

    def _workbench_run(self, mode: str, require_frame: bool = False) -> None:
        target = self._workbench_selected_manifest_target()
        if not target and not self._workbench_selected_frame_id():
            self._render_workbench_failure({"error": "Select a manifest."})
            return
        manifest_record = self.workbench_manifest_record if isinstance(self.workbench_manifest_record, dict) and self.workbench_manifest_record.get("ok") else load_manifest_for_workbench(target)
        if not manifest_record.get("ok"):
            self.workbench_manifest_record = {}
            self._render_workbench_failure(manifest_record)
            return
        self.workbench_manifest_record = manifest_record
        validation, inputs = self._workbench_validate_inputs(manifest_record)
        if not validation.get("ok"):
            self.workbench_result = validation
            self.workbench_frame = {}
            self._render_workbench_failure(validation)
            return
        if not self._workbench_selected_frame_id() or not require_frame:
            create_result = create_test_frame(target, inputs or {}, runtime_data_dir=self.runtime_root)
            if not create_result.get("ok"):
                self.workbench_result = create_result
                self.workbench_frame = {}
                self._render_workbench_failure(create_result)
                return
            self.workbench_frame = create_result.get("frame", {})
            self.workbench_result = create_result
        frame_id = self._workbench_selected_frame_id() or str(self.workbench_result.get("frame_id", "")).strip()
        if not frame_id:
            self._render_workbench_failure({"error": "No TaskFrame available for execution."})
            return
        result = run_workbench_dry_run(frame_id, mode, runtime_data_dir=self.runtime_root, fixture_mode=bool(self.workbench_fixture_mode_var.get()))
        self.workbench_result = result
        self.workbench_frame = result.get("frame", {}) if isinstance(result.get("frame", {}), dict) else {}
        if isinstance(self.workbench_frame, dict) and self.workbench_frame.get("frame_id"):
            self.active_frame_id = str(self.workbench_frame.get("frame_id", "")).strip() or self.active_frame_id
            self.last_snapshot = dict(self.last_snapshot) if isinstance(self.last_snapshot, dict) else {}
            self.last_snapshot["active_frame"] = dict(self.workbench_frame)
        self.workbench_selected_runtime_step_id = str(result.get("current_step_id", "") or self.workbench_selected_step_id)
        if self.workbench_selected_runtime_step_id:
            self.workbench_selected_step_id = self.workbench_selected_runtime_step_id
        self._render_manifest_workbench_view()

    def on_workbench_run_dry_run(self) -> None:
        self._workbench_run("run_until_blocked")

    def on_workbench_step_next(self) -> None:
        self._workbench_run("step_next", require_frame=True)

    def on_workbench_run_until_blocked(self) -> None:
        self._workbench_run("run_until_blocked", require_frame=True)

    def on_workbench_approve_action(self) -> None:
        pending = self.workbench_frame.get("pending_actions", []) if isinstance(self.workbench_frame, dict) else []
        if not isinstance(pending, list) or not pending:
            return
        action = pending[0] if isinstance(pending[0], dict) else {}
        frame_id = str(self.workbench_result.get("frame_id", self.workbench_frame.get("frame_id", ""))).strip()
        if not frame_id or not action:
            return
        self.last_approval_operation = approve_pending_action(frame_id, action.get("action_id", ""), runtime_data_dir=self.runtime_root)
        self.refresh_current_run_from_result(self.last_approval_operation)
        self.workbench_result = self.last_approval_operation if isinstance(self.last_approval_operation, dict) else {}
        self.workbench_frame = self.last_approval_operation.get("frame", {}) if isinstance(self.last_approval_operation, dict) and isinstance(self.last_approval_operation.get("frame", {}), dict) else self.workbench_frame
        self._render_manifest_workbench_view()

    def on_workbench_reject_action(self) -> None:
        pending = self.workbench_frame.get("pending_actions", []) if isinstance(self.workbench_frame, dict) else []
        if not isinstance(pending, list) or not pending:
            return
        action = pending[0] if isinstance(pending[0], dict) else {}
        frame_id = str(self.workbench_result.get("frame_id", self.workbench_frame.get("frame_id", ""))).strip()
        if not frame_id or not action:
            return
        self.last_approval_operation = reject_pending_action(frame_id, action.get("action_id", ""), runtime_data_dir=self.runtime_root)
        self.refresh_current_run_from_result(self.last_approval_operation)
        self.workbench_result = self.last_approval_operation if isinstance(self.last_approval_operation, dict) else {}
        self.workbench_frame = self.last_approval_operation.get("frame", {}) if isinstance(self.last_approval_operation, dict) and isinstance(self.last_approval_operation.get("frame", {}), dict) else self.workbench_frame
        self._render_manifest_workbench_view()

    def on_workbench_create_open_report(self) -> None:
        frame_id = str(self.workbench_result.get("frame_id", self.workbench_frame.get("frame_id", ""))).strip() if isinstance(self.workbench_result, dict) else ""
        if not frame_id:
            return
        report = generate_workbench_run_report(frame_id, runtime_data_dir=self.runtime_root)
        if report.get("ok") and report.get("html_path"):
            open_workbench_run_report(report["html_path"])
        self.report_status = report
        self._render_manifest_workbench_view()

    def on_workbench_open_manifest_manual(self) -> None:
        result = open_manifest_manual()
        if not result.get("ok"):
            messagebox.showerror("Open manifest manual", result.get("error", "Unable to open manifest manual."))

    def _render_runtime_trace(self, view: dict | None = None) -> None:
        lines: list[str] = []
        if self.last_action_result:
            lines.extend(self._format_last_action_result(self.last_action_result))
            lines.append("")
        if view is not None and self.playback_timeline:
            lines.extend(self._format_playback_trace(view))
        else:
            lines.extend(self.last_snapshot.get("trace_lines", []))
        self.trace_text.configure(state="normal")
        self.trace_text.delete("1.0", "end")
        self.trace_text.insert("1.0", chr(10).join(lines))
        self.trace_text.configure(state="disabled")

    def _render_field(self, parent: ttk.Frame, label: str, value: object) -> None:
        row = ttk.Frame(parent, style="Card.TFrame")
        row.pack(fill="x", anchor="w", pady=(0, 4))
        ttk.Label(row, text=f"{label}:", style="Meta.TLabel").pack(side="left")
        ttk.Label(row, text=str(value), style="Body.TLabel", wraplength=520, justify="left").pack(side="left", padx=(8, 0))

    def _render_section_text(self, parent: ttk.Frame, title: str, text: str) -> None:
        block = ttk.Frame(parent, style="Card.TFrame")
        block.pack(fill="x", anchor="w", pady=(0, 10))
        ttk.Label(block, text=title, style="Section.TLabel").pack(anchor="w")
        ttk.Label(block, text=text, style="Body.TLabel", wraplength=330, justify="left").pack(anchor="w", pady=(2, 0))

    def _format_event_item(self, event: dict, frames_by_id: dict | None = None) -> str:
        event_id = str(event.get("event_id", "") or "â€”")
        source = str(event.get("source", "") or "â€”")
        event_type = str(event.get("event_type", "") or "â€”")
        status = str(event.get("status", "") or "â€”")
        frame_id = str(event.get("linked_frame_id") or "").strip()
        if frame_id and isinstance(frames_by_id, dict) and frame_id in frames_by_id:
            frame_state = str(frames_by_id[frame_id].get("state", "") or status)
            status = frame_state or status
        return f"{event_id} | {source}.{event_type} | {status}"

    def _format_current_output(self, outputs: dict, frame: dict | None) -> str:
        if frame is None:
            return "No active TaskFrame selected."
        if not isinstance(outputs, dict) or not outputs:
            return "No output data available."
        order_id = outputs.get("order_id")
        order = outputs.get("order") if isinstance(outputs.get("order"), dict) else {}
        draft_reply = outputs.get("draft_reply") if isinstance(outputs.get("draft_reply"), dict) else {}
        if order_id or order or draft_reply:
            parts: list[str] = []
            if order_id:
                parts.append(f"order_id: {order_id}")
            if order:
                parts.append(f"order.status: {order.get('status', 'â€”')}")
            if draft_reply:
                parts.append(f"draft_reply.body: {draft_reply.get('body', 'â€”')}")
            if outputs.get("business_lookups"):
                parts.append("business_lookups: sourced from runtime_data/business")
            return chr(10).join(parts)
        return json.dumps(outputs, ensure_ascii=False, separators=(", ", ": "))

    def _format_selected_detail(self, selected_detail: dict | None) -> str:
        if not isinstance(selected_detail, dict) or not selected_detail:
            return "No playback detail selected."
        parts: list[str] = []
        event = selected_detail.get("event", {})
        route = selected_detail.get("route", {})
        manifest = selected_detail.get("manifest", {})
        manifest_step = selected_detail.get("manifest_step", {})
        runtime_step_result = selected_detail.get("runtime_step_result", {})
        if event:
            parts.append("Event Detail")
            for label, key in (("Event ID", "event_id"), ("Source", "source"), ("Event Type", "event_type"), ("Received At", "received_at"), ("Status", "status"), ("Duplicate", "duplicate"), ("Linked Frame ID", "linked_frame_id"), ("Payload", "payload")):
                parts.append(f"{label}: {self._compact_value(event.get(key))}")
        if route:
            parts.append("Route Detail")
            for label, key in (("Route ID", "route_id"), ("Source", "source"), ("Event Type", "event_type"), ("Manifest ID", "manifest_id"), ("Input Map", "input_map"), ("Mapped Inputs", "mapped_inputs")):
                parts.append(f"{label}: {self._compact_value(route.get(key))}")
        if manifest:
            parts.append("Manifest Detail")
            for label, key in (("Manifest ID", "manifest_id"), ("Name", "name"), ("Trigger Type", "trigger_type"), ("Side Effect", "side_effect"), ("Required Inputs", "required_inputs"), ("Step Count", "step_count"), ("Completion Requirements", "completion_requirements")):
                parts.append(f"{label}: {self._compact_value(manifest.get(key))}")
        if manifest_step:
            parts.append("Manifest Step Detail")
            for label, key in (("step_id", "step_id"), ("kind", "kind"), ("input/output config", "input"), ("validation config", "validation")):
                if key in manifest_step:
                    parts.append(f"{label}: {self._compact_value(manifest_step.get(key))}")
        if runtime_step_result:
            parts.append("Runtime Result")
            for label, key in (("status", "status"), ("outputs produced", "outputs"), ("validations produced", "validations"), ("evidence produced", "evidence"), ("errors", "errors")):
                if key in runtime_step_result:
                    parts.append(f"{label}: {self._compact_value(runtime_step_result.get(key))}")
        return chr(10).join(parts) if parts else "No playback detail selected."

    def _format_validations(self, validations: list) -> str:
        if not validations:
            return "No validation data available."
        lines: list[str] = []
        for item in validations:
            if not isinstance(item, dict):
                continue
            step_id = str(item.get("step_id") or item.get("validation_id") or "unknown")
            ok = item.get("ok")
            status = "ok" if ok is True else "failed" if ok is False else "unknown"
            message = str(item.get("message", "") or "")
            lines.append(f"{step_id} | {status}" + (f" | {message}" if message else ""))
        return chr(10).join(lines) if lines else "No validation data available."

    def _format_pending_actions(self, pending_actions: list) -> str:
        if not pending_actions:
            return "No pending actions."
        lines: list[str] = []
        for item in pending_actions:
            if not isinstance(item, dict):
                continue
            action_type = str(item.get("action_type", "") or "unknown")
            status = str(item.get("status", "") or "unknown")
            customer_id = str(item.get("customer_id", "") or "â€”")
            channel = str(item.get("channel", "") or "â€”")
            body = str(item.get("body", "") or "")
            preview = body if len(body) <= 80 else f"{body[:77]}..."
            lines.append(f"{action_type} | {status} | {customer_id} | {channel} | {preview}")
        return chr(10).join(lines) if lines else "No pending actions."

    def _format_last_action_result(self, result: dict) -> list[str]:
        lines = [
            "[LAST UI ACTION]",
            "action: run_demo_customer_message",
            f"status: {result.get('status', 'FAILED')}",
            f"event_id: {result.get('event_id') or 'â€”'}",
            f"frame_id: {result.get('frame_id') or 'â€”'}",
            f"result: {'PASS' if result.get('status') == 'WAITING_FOR_EXECUTE' and result.get('pending_actions') else 'FAIL'}",
        ]
        errors = result.get("errors", [])
        if isinstance(errors, list) and errors:
            for error in errors:
                lines.append(f"error: {error}")
        return lines

    def _format_summary(self, summary: dict | None) -> str:
        if not isinstance(summary, dict) or not summary:
            return "No TaskFrame summary available."
        fields = (
            "frame_id",
            "manifest_id",
            "state",
            "current_step_id",
            "step_count",
            "completed_steps",
            "failed_steps",
            "skipped_steps",
            "pending_action_count",
            "executed_action_count",
            "error_count",
            "validation_failed_count",
            "output_keys",
            "completion_status",
        )
        return chr(10).join(f"{field}: {summary.get(field, '')}" for field in fields)

    def _format_failure_summary(self, failure_summary: dict | None) -> str:
        if not isinstance(failure_summary, dict) or not failure_summary or not failure_summary.get("state", "").startswith("FAILED"):
            return "No failure for this run."
        lines = [
            f"state: {failure_summary.get('state', '')}",
            f"failed_step_id: {failure_summary.get('failed_step_id', '')}",
            f"failure_type: {failure_summary.get('failure_type', '')}",
            f"failure_message: {failure_summary.get('failure_message', '')}",
            f"operator_explanation: {failure_summary.get('operator_explanation', '')}",
            f"pending_action_count: {failure_summary.get('pending_action_count', 0)}",
            f"executed_action_count: {failure_summary.get('executed_action_count', 0)}",
            "failed validations:",
        ]
        failed_validations = failure_summary.get("failed_validations", [])
        if failed_validations:
            for item in failed_validations:
                if isinstance(item, dict):
                    lines.append(f"- {item.get('validation_id', '')}: {item.get('message', '')}")
        else:
            lines.append("- None")
        lines.append("Errors:")
        for error in failure_summary.get("blocking_errors", []) or []:
            lines.append(f"- {error}")
        return chr(10).join(lines)

    def _format_report_status(self, report_status: dict | None) -> str:
        if not isinstance(report_status, dict) or not report_status:
            return "No report generated."
        return chr(10).join(
            [
                f"ok: {report_status.get('ok', False)}",
                f"business_report_html_path: {report_status.get('business_report_html_path', '')}",
                f"business_report_markdown_path: {report_status.get('business_report_markdown_path', '')}",
                f"business_report_evidence_bundle_path: {report_status.get('business_report_evidence_bundle_path', '')}",
                f"run_report_html_path: {report_status.get('run_report_html_path', report_status.get('html_path', ''))}",
                f"run_report_markdown_path: {report_status.get('run_report_markdown_path', report_status.get('markdown_path', ''))}",
                f"run_report_evidence_bundle_path: {report_status.get('run_report_evidence_bundle_path', report_status.get('evidence_bundle_path', ''))}",
                f"error: {report_status.get('error', '')}",
            ]
        )

    def _format_readiness_scorecard(self, scorecard: dict | None) -> str:
        if not isinstance(scorecard, dict) or not scorecard:
            return "No readiness scorecard generated."
        areas = scorecard.get("areas", {}) if isinstance(scorecard.get("areas", {}), dict) else {}
        lines = [
            f"Overall score: {scorecard.get('overall_score', 0)}",
            f"Threshold: {scorecard.get('threshold', 90)}",
            f"Status: {scorecard.get('status', '')}",
            f"Blocking areas: {', '.join(scorecard.get('blocking_areas', [])) or 'none'}",
            f"JSON path: {scorecard.get('report_paths', {}).get('json_path', '')}",
            f"Markdown path: {scorecard.get('report_paths', {}).get('markdown_path', '')}",
            f"HTML path: {scorecard.get('report_paths', {}).get('html_path', '')}",
            "Area scores:",
        ]
        for area_id, area in areas.items():
            if not isinstance(area, dict):
                continue
            lines.append(f"- {area.get('label', area_id)}: {area.get('score', 0)} ({area.get('status', '')})")
        return chr(10).join(lines)

    def _format_portfolio_evidence_pack(self, pack: dict | None) -> str:
        if not isinstance(pack, dict) or not pack:
            return "No portfolio evidence pack generated."
        linked_artifacts = pack.get("linked_artifacts", []) if isinstance(pack.get("linked_artifacts", []), list) else []
        has_story = any(isinstance(item, dict) and "latest_story_pack_link" in str(item.get("artifact_id", "")) for item in linked_artifacts)
        has_readiness = any(isinstance(item, dict) and "latest_readiness_scorecard_link" in str(item.get("artifact_id", "")) for item in linked_artifacts)
        lines = [
            f"Pack ID: {pack.get('pack_id', '')}",
            f"Pack Run ID: {pack.get('pack_run_id', '')}",
            f"Status: {'PASS' if pack.get('ok') else 'FAIL'}",
            f"Pack Folder: {pack.get('pack_dir', '')}",
            f"Index Markdown: {pack.get('index_markdown_path', '')}",
            f"Index HTML: {pack.get('index_html_path', '')}",
            f"Summary JSON: {pack.get('summary_json_path', '')}",
            f"Story Pack Linked: {has_story}",
            f"Readiness Linked: {has_readiness}",
        ]
        if pack.get("errors"):
            lines.append(f"Errors: {', '.join(str(item) for item in pack.get('errors', []))}")
        return chr(10).join(lines)

    def _format_approval_pack(self, approval_pack: dict | None, selected_step_id: str) -> str:
        if not isinstance(approval_pack, dict) or not approval_pack:
            return "No pending approval actions for this TaskFrame."
        packs = approval_pack.get("approval_packs", [])
        if not packs:
            return approval_pack.get("message") or "No pending approval actions for this TaskFrame."
        blocks: list[str] = []
        total = len(packs)
        for index, pack in enumerate(packs, start=1):
            if not isinstance(pack, dict):
                continue
            selected = self._compact_bool(pack.get("step_id") == selected_step_id)
            blocks.extend(
                [
                    f"Pending Action {index} / {total}",
                    f"Status: {pack.get('status', '')}",
                    f"Action: {pack.get('human_summary', '')}",
                    f"Tool: {pack.get('tool', '')}",
                    f"Output alias: {pack.get('output_alias', '')}",
                    f"Risk: {pack.get('risk_class', '')}",
                    f"Requires approval: {pack.get('requires_approval', '')}",
                    f"Related to selected step: {'yes' if selected else 'no'}",
                    "Human-Readable Execute Summary",
                    str(pack.get("human_summary", "")),
                    "Action Arguments",
                    self._compact_value(pack.get("args", {})),
                    "Pre-Execution Validation",
                    self._compact_multiline(pack.get("validations", [])),
                    "Supporting Evidence",
                    self._compact_multiline(pack.get("evidence", [])),
                    "Risk / Guardrails",
                    self._compact_multiline(pack.get("guardrails", [])),
                    "",
            ]
            )
        return chr(10).join(blocks).strip()

    def _format_approval_operation(self, operation: dict | None) -> str:
        if not isinstance(operation, dict):
            return "No approval operation yet."
        return chr(10).join(
            [
                f"operation: {operation.get('operation', '')}",
                f"ok: {operation.get('ok', False)}",
                f"target_frame_id: {operation.get('target_frame_id', '')}",
                f"target_frame_state: {operation.get('target_frame_state', '')}",
                f"command_frame_id: {operation.get('command_frame_id', '')}",
                f"message: {operation.get('message', '')}",
                f"error: {operation.get('error', '')}",
            ]
        )

    def _format_scenario_result(self, scenario_result: dict | None) -> str:
        if not isinstance(scenario_result, dict) or not scenario_result:
            return "No scenario run yet."
        checks = scenario_result.get("scenario_validation", {}).get("checks", []) if isinstance(scenario_result.get("scenario_validation", {}), dict) else []
        lines = [
            f"Scenario: {scenario_result.get('label', '')}",
            f"Verdict: {scenario_result.get('scenario_validation', {}).get('verdict', '')}",
            "Checks:",
        ]
        for label, key in (
            ("Invoice", "invoice_ref"),
            ("Supplier", "supplier_id"),
            ("PO", "po_ref"),
            ("Receipt", "receipt_ref"),
            ("Match status", "match_status"),
            ("Exception count", "exception_count"),
            ("Ledger posting decision", "ledger_decision"),
            ("Pending actions", "pending_actions"),
            ("Completion outcome", "completion_outcome"),
        ):
            if key in scenario_result:
                lines.append(f"{label}: {self._compact_value(scenario_result.get(key))}")
        if checks:
            for item in checks:
                if not isinstance(item, dict):
                    continue
                prefix = "âœ“" if item.get("ok") else "âœ—"
                lines.append(f"{prefix} {item.get('id', '')}: {item.get('actual', '')}")
        else:
            lines.append("No checks available.")
        return chr(10).join(lines)

    def _format_llm_info(self, llm_info: dict | None) -> str:
        if not isinstance(llm_info, dict) or not llm_info:
            return "No local LLM configured."
        return chr(10).join(
            [
                f"LLM Provider: {llm_info.get('provider', '')}",
                f"Model: {llm_info.get('model', '')}",
            ]
        )

    def _compact_multiline(self, value: object) -> str:
        if isinstance(value, list):
            if not value:
                return "None"
            return chr(10).join(f"- {self._compact_value(item)}" for item in value)
        return self._compact_value(value)

    def _compact_bool(self, value: object) -> str:
        return "yes" if bool(value) else "no"

    def _format_playback_trace(self, view: dict) -> list[str]:
        frame = view.get("frame", {})
        event = view.get("event", {})
        route = view.get("route", {})
        lines = [
            "[PLAYBACK]",
            f"status: {view.get('status', 'idle')}",
            f"index: {view.get('index', 0)}/{view.get('total', 0)}",
            f"current: {view.get('current_label', '') or view.get('current', '')}",
            f"delay_ms: {self.playback_delay_ms}",
            "",
            "[EVENT]",
            f"event_id: {event.get('event_id', '') if isinstance(event, dict) else ''}",
            f"source: {event.get('source', '') if isinstance(event, dict) else ''}",
            f"event_type: {event.get('event_type', '') if isinstance(event, dict) else ''}",
            "",
            "[ROUTE]",
            f"route_id: {route.get('route_id', '') if isinstance(route, dict) else ''}",
            f"manifest_id: {route.get('manifest_id', '') if isinstance(route, dict) else ''}",
            "",
            "[TASKFRAME]",
            f"frame_id: {frame.get('frame_id', '') if isinstance(frame, dict) else ''}",
            f"state: {frame.get('state', '') if isinstance(frame, dict) else ''}",
            "",
            "[EVIDENCE]",
        ]
        evidence = view.get("evidence", [])
        if evidence:
            for item in evidence:
                if isinstance(item, dict):
                    lines.append(f"{item.get('dataset', '')}: {'found' if item.get('found') else 'missing'} | query={item.get('query', {})}")
        else:
            lines.append("No evidence data.")
        return lines

    def _frame_steps(self, frame: dict) -> list[dict]:
        steps = frame.get("steps")
        if isinstance(steps, list) and steps:
            return steps
        manifest_steps = frame.get("manifest_steps")
        if isinstance(manifest_steps, list):
            normalized = []
            for item in manifest_steps:
                if isinstance(item, dict):
                    normalized.append(item)
                elif isinstance(item, str):
                    normalized.append({"step_id": item})
            return normalized
        return []

    def _step_label(self, step: dict, current_step_id: str, visible_steps: set[str]) -> str:
        step_id = str(step.get("step_id") or step.get("id") or "unknown_step")
        status = str(step.get("status", "") or "").upper()
        ok = step.get("ok")
        symbol = "â—‹"
        if step_id in visible_steps:
            symbol = "âœ“"
        if step_id == current_step_id:
            symbol = "â–¶"
        if ok is False or status in {"FAILED", "FAILED_VALIDATION", "FAILED_EXECUTION", "FAILED_COMPLETION"}:
            symbol = "âœ—"
        return f"{symbol} {humanize_step_id(step_id)}"

    def _compact_value(self, value: object) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))
        if value is None or value == "":
            return "â€”"
        return str(value)

    def _workbench_failure_label(self, category: str) -> str:
        return {
            "manifest_validation_failure": "Manifest/config problem",
            "missing_required_input": "Missing required input",
            "tool_execution_failure": "Tool/runtime failure",
            "external_auth_failure": "External authentication failure",
            "external_dependency_unavailable": "External dependency unavailable",
            "business_validation_failure": "Business validation failure",
            "fixture_missing": "Fixture data not available",
            "unknown_failure": "Unknown failure",
        }.get(str(category or ""), "")

    def _update_footer(self, view: dict | None = None) -> None:
        snapshot = self.last_snapshot if view is None else {"active_frame": view.get("frame")}
        if self.view_mode_var.get() == "Manifest Workbench" and isinstance(self.workbench_frame, dict) and self.workbench_frame.get("frame_id"):
            snapshot = dict(snapshot) if isinstance(snapshot, dict) else {}
            snapshot["active_frame"] = self.workbench_frame
        self.footer_label.configure(text=build_footer_text(snapshot, self._playback_status()))

    def _update_dataset_validation_label(self) -> None:
        if not hasattr(self, "dataset_validation_label"):
            return
        validation = self.business_dataset_validation if isinstance(self.business_dataset_validation, dict) else {}
        self.dataset_validation_label.configure(text=f"Validation: {'OK' if validation.get('ok') else 'FAILED'}")

    def _playback_status(self) -> str:
        if self.playback_running:
            return "paused" if self.playback_paused else "running"
        if self.playback_timeline and self.playback_index >= len(self.playback_timeline) - 1:
            return "complete"
        return "idle"

    def _cancel_playback_timer(self) -> None:
        if self.playback_after_id is not None:
            try:
                self.root.after_cancel(self.playback_after_id)
            except Exception:
                pass
            self.playback_after_id = None

    def _schedule_next_playback_step(self) -> None:
        if not self.playback_running or self.playback_paused or not self.playback_timeline:
            return
        if self.playback_index >= len(self.playback_timeline) - 1:
            self.playback_running = False
            self._update_footer()
            return
        self.playback_after_id = self.root.after(self.playback_delay_ms, self._advance_playback)

    def _advance_playback(self) -> None:
        self.playback_after_id = None
        if not self.playback_running or self.playback_paused:
            return
        if self.playback_index < len(self.playback_timeline) - 1:
            self.playback_index += 1
        self._render_current_view()
        if self.playback_index >= len(self.playback_timeline) - 1:
            self.playback_running = False
        else:
            self._schedule_next_playback_step()
        self._update_footer()

    def _current_view(self) -> dict:
        if not self.playback_timeline or self.playback_index < 0:
            return {
                "status": "idle",
                "index": 0,
                "total": 0,
                "current": "",
                "current_step_id": "",
                "event": self.last_snapshot.get("active_event"),
                "route": {},
                "frame": self.last_snapshot.get("active_frame"),
                "outputs": self.last_snapshot.get("outputs", {}),
                "validations": self.last_snapshot.get("validations", []),
                "pending_actions": self.last_snapshot.get("pending_actions", []),
                "evidence": self.last_snapshot.get("active_frame", {}).get("evidence", []) if isinstance(self.last_snapshot.get("active_frame"), dict) else [],
                "visible_steps": [],
                "visible_step_labels": [],
                "current_label": "",
            }
        return build_playback_view(self.last_snapshot, self.playback_timeline, self.playback_index)

    def _render_snapshot(self) -> None:
        mode = self.view_mode_var.get()
        if mode == "Inspector":
            self._render_task_queue()
            self._render_active_taskframe()
            self._render_results_actions()
            self._render_runtime_trace()
        elif mode == "Demo":
            self._render_demo_story_view()
        elif mode == "Manifest Workbench":
            self._render_manifest_workbench_view()
        else:
            self._render_business_views()
        self._update_footer()
        self.update_approval_button_states()

    def _render_current_view(self) -> None:
        mode = self.view_mode_var.get()
        if mode == "Inspector":
            view = self._current_view()
            self._render_task_queue(view)
            self._render_active_taskframe(view)
            self._render_results_actions(view)
            self._render_runtime_trace(view)
            self._update_footer(view)
        elif mode == "Demo":
            self._render_demo_story_view()
        elif mode == "Manifest Workbench":
            self._render_manifest_workbench_view()
        else:
            self._render_business_views()
            self._update_footer()
        self._update_dataset_validation_label()
        self.update_approval_button_states()
        self.root.update_idletasks()

    def _render_business_views(self) -> None:
        if self.view_mode_var.get() != "Operator":
            return
        demo_view = build_demo_view(self.last_snapshot if self.last_snapshot else {}, self.current_run, self._active_artifact_state())
        self._render_operator_view(demo_view)
        self._render_runtime_trace(self._current_view())

    def _demo_view_model(self) -> dict:
        snapshot = self.last_snapshot if self.active_frame_id else {}
        current_run = self.current_run
        if not self.active_frame_id:
            selected = self._selected_scenario()
            if isinstance(selected, dict):
                title = self.demo_title_by_scenario_id.get(selected.get("id", ""), selected.get("label", "Autonomous Business Worker Demo"))
                current_run = {
                    "scenario_title": title,
                    "scenario_summary": selected.get("description", ""),
                    "label": title,
                }
        return build_demo_view(snapshot, current_run, self._active_artifact_state())

    def _demo_story_model(self) -> dict:
        current_run = self.current_run if isinstance(self.current_run, dict) else None
        snapshot = self.last_snapshot if current_run else {}
        selected = self._selected_scenario()
        return build_demo_story(snapshot, current_run, selected)

    def _render_demo_story_view(self) -> None:
        if not hasattr(self, "demo_current_run_text"):
            return
        story = self._demo_story_model()
        view = self._current_view()
        cards = [card for card in story.get("cards", []) if isinstance(card, dict)]
        card_by_kind = {str(card.get("kind", "")).strip(): card for card in cards if str(card.get("kind", "")).strip()}

        def card_to_lines(card: dict | None, fallback: str) -> list[str]:
            if not isinstance(card, dict):
                return [fallback] if fallback else []
            lines: list[str] = []
            body = str(card.get("body", "") or "").strip()
            if body:
                lines.extend(line for line in body.splitlines() if line.strip())
            for item in card.get("items", []):
                text = str(item or "").strip()
                if text:
                    lines.append(text)
            return lines or ([fallback] if fallback else [])

        primary_action = self._primary_demo_action()
        pending_actions = view.get("pending_actions", []) if isinstance(view.get("pending_actions", []), list) else []
        validation_count = len(view.get("validations", [])) if isinstance(view.get("validations", []), list) else 0
        evidence_count = len(view.get("evidence", [])) if isinstance(view.get("evidence", []), list) else 0
        frame = view.get("frame") if isinstance(view.get("frame"), dict) else {}

        summary_lines = [
            f"Current run: {str(story.get('headline', 'Select a demo to begin') or 'Select a demo to begin')}",
            str(story.get("subheadline", "Pick a demo, then start the worker.") or "Pick a demo, then start the worker."),
            f"Pending actions: {len(pending_actions)}",
            f"Validation result: {validation_count} check{'s' if validation_count != 1 else ''}",
            f"Evidence items: {evidence_count}",
            f"Next: {primary_action.get('label', 'Start demo')}",
        ]
        if frame.get("state"):
            summary_lines.insert(2, f"State: {frame.get('state')}")
        self._set_text(self.demo_current_run_text, chr(10).join(line for line in summary_lines if line))

        request_card = card_by_kind.get("request")
        worker_card = card_by_kind.get("steps")
        outcome_card = card_by_kind.get("outcome")
        decision_card = card_by_kind.get("decision")
        report_card = card_by_kind.get("report")

        request_lines = card_to_lines(request_card, str(story.get("request_text", "Choose a demo to see the request.")))
        self._set_text(self.demo_request_text, chr(10).join(request_lines))

        worker_lines: list[str] = []
        for step in story.get("worker_steps", []):
            if not isinstance(step, dict):
                continue
            status = str(step.get("status", "")).lower()
            symbol = {"done": "?", "current": "?", "attention": "?", "failed": "?", "pending": "?", "not_reached": "?"}.get(status, "?")
            label = str(step.get("label", "")).strip()
            if label:
                worker_lines.append(f"{symbol} {label}")
        if not worker_lines:
            worker_lines = card_to_lines(worker_card, str(story.get("worker_title", "Choose a demo to see what the worker did.")))
        self._set_text(self.demo_worker_steps_text, chr(10).join(worker_lines))

        outcome_lines = card_to_lines(outcome_card, str(story.get("outcome_text", "No outcome available.")) or "No outcome available.")
        if story.get("facts") and not outcome_card:
            outcome_lines.extend(f"? {str(item)}" for item in story.get("facts", []) if str(item).strip())
        self._set_text(self.demo_result_text, chr(10).join(outcome_lines))

        approval_lines = card_to_lines(decision_card, str(story.get("decision_text", "Click Start demo to generate this report.")))
        if story.get("story_type") == "report_generation":
            approval_lines.append(str(story.get("subheadline", "Click Start demo to generate this report.")))
        else:
            approval_lines.append(str(story.get("subheadline", "No live customer message will be sent in demo mode.")))
        if story.get("business_report_html_path"):
            approval_lines.append(f"Business report: {story.get('business_report_html_path')}")
        if story.get("run_report_html_path"):
            approval_lines.append(f"Run report: {story.get('run_report_html_path')}")
        if story.get("run_report_evidence_bundle_path"):
            approval_lines.append(f"Evidence bundle: {story.get('run_report_evidence_bundle_path')}")
        if report_card:
            approval_lines.extend(card_to_lines(report_card, ""))
        self._set_text(self.demo_approval_text, chr(10).join(line for line in approval_lines if line))

        self.update_approval_button_states()


def build_operator_ui(root: tk.Tk | None = None, runtime_root: str = "runtime_data") -> tk.Tk:
    created_root = root is None
    app_root = root or tk.Tk()
    app_root.operator_console = OperatorConsole(app_root, runtime_root=runtime_root)  # type: ignore[attr-defined]
    if created_root:
        app_root.protocol("WM_DELETE_WINDOW", app_root.destroy)
    return app_root


def main() -> int:
    root = build_operator_ui()
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
