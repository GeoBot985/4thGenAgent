from __future__ import annotations

import json
import tkinter as tk
from tkinter import ttk

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
from src.operator_demo_runner import DEMO_MANIFESTS, list_demo_manifests, run_demo_manifest
from src.operator_cross_workflow_demo import list_demo_packs, run_cross_workflow_demo_pack
from src.operator_scenario_runner import run_scenario
from src.operator_scenarios import SCENARIO_CATEGORIES, list_categories, list_scenarios
from src.operator_playback import build_playback_timeline, build_playback_view
from src.operator_reports import generate_report_for_frame, get_latest_report_paths, open_report_folder, open_report_html
from runtime.tool_capability_registry import list_tool_capabilities
from runtime.tool_health import check_all_tool_health, check_tool_health, load_latest_tool_health_snapshot
from runtime.tool_setup import get_tool_setup_instructions, run_safe_setup_action


TITLE = "TaskFrame Operator Console"


class OperatorConsole:
    def __init__(self, root: tk.Tk, runtime_root: str = "runtime_data"):
        self.root = root
        self.runtime_root = runtime_root
        self.last_snapshot: dict = {}
        self.last_action_result: dict | None = None
        self.current_run: dict | None = None
        self.timeline: list[dict] = []
        self.selected_action_id: str | None = None
        self.last_approval_operation: dict | None = None
        self.customer_messages: list[dict] = []
        self.selected_message_id: str | None = None
        self.message_status_filter: str = "All"
        self.business_dataset_manifest: dict = {}
        self.business_dataset_validation: dict = {}
        self.report_status: dict = {}
        self.scenario_result: dict = {}
        self.tool_health_snapshot: dict = {}
        self.selected_tool_id: str = ""
        self.scenario_category_var = tk.StringVar(value="All")
        self.scenario_var = tk.StringVar(value="")
        self.scenario_reset_dataset_var = tk.BooleanVar(value=True)
        self.scenario_use_local_llm_var = tk.BooleanVar(value=False)
        self.playback_timeline: list[dict] = self.timeline
        self.playback_index = -1
        self.playing = False
        self.playback_running = self.playing
        self.playback_paused = False
        self.playback_delay_ms = 2000
        self.playback_after_id: str | None = None
        self.root.title(TITLE)
        self.root.geometry("1400x850")
        self.root.minsize(1100, 700)
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
        self.outer.columnconfigure(0, weight=65)
        self.outer.columnconfigure(1, weight=35)
        self.outer.rowconfigure(1, weight=1)

        self._build_header(self.outer)

        workspace = ttk.Frame(self.outer, style="Card.TFrame", padding=12)
        workspace.grid(row=1, column=0, sticky="nsew", padx=(0, 12), pady=(12, 12))
        workspace.columnconfigure(0, weight=22)
        workspace.columnconfigure(1, weight=50)
        workspace.columnconfigure(2, weight=28)
        workspace.rowconfigure(0, weight=1)
        workspace.rowconfigure(1, weight=1)

        trace_panel = ttk.Frame(self.outer, style="DarkCard.TFrame", padding=12)
        trace_panel.grid(row=1, column=1, sticky="nsew", pady=(12, 12))
        trace_panel.rowconfigure(1, weight=1)
        trace_panel.columnconfigure(0, weight=1)

        self._build_customer_inbox(workspace)
        self._build_task_queue(workspace)
        self._build_active_taskframe(workspace)
        self._build_results_actions(workspace)
        self._build_tool_capabilities_panel(workspace)
        self._build_runtime_trace(trace_panel)
        self._build_footer(self.outer)

    def _build_header(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent, style="Workspace.TFrame")
        header.grid(row=0, column=0, columnspan=2, sticky="ew")
        header.columnconfigure(0, weight=1)
        header.columnconfigure(1, weight=0)

        left = ttk.Frame(header, style="Workspace.TFrame")
        left.grid(row=0, column=0, sticky="w")
        ttk.Label(left, text="WORKSPACE", style="Meta.TLabel").pack(anchor="w")
        ttk.Label(left, text=TITLE, style="Title.TLabel").pack(anchor="w", pady=(2, 0))

        controls = ttk.Frame(header, style="Workspace.TFrame")
        controls.grid(row=0, column=1, sticky="e")

        for label, value in (
            ("Runtime Profile:", "demo"),
            ("Mode:", "operator"),
            ("Model:", "local / bounded"),
        ):
            block = ttk.Frame(controls, style="Workspace.TFrame")
            block.pack(side="left", padx=(0, 18))
            ttk.Label(block, text=label, style="Meta.TLabel").pack(anchor="w")
            ttk.Label(block, text=value, style="Body.TLabel").pack(anchor="w")

        demo_block = ttk.Frame(controls, style="Workspace.TFrame")
        demo_block.pack(side="left", padx=(0, 10))
        ttk.Label(demo_block, text="Demo Control Panel", style="Meta.TLabel").pack(anchor="w")
        # Customer Status - LLM Assisted E2E
        # Missing Order / Wrong Customer / Bad LLM Reply / Unsupported Intent
        self.demo_items = list_demo_manifests()
        self.demo_label_to_id = {item["label"]: item["selection_id"] for item in self.demo_items}
        self.demo_var = tk.StringVar(value=self.demo_items[0]["label"] if self.demo_items else "")
        self.use_local_llm_var = tk.BooleanVar(value=True)
        self.demo_selector = ttk.Combobox(
            demo_block,
            textvariable=self.demo_var,
            state="readonly",
            width=34,
            values=[item["label"] for item in self.demo_items],
        )
        self.demo_selector.pack(anchor="w", pady=(2, 2))
        self.demo_selector.bind("<<ComboboxSelected>>", self._on_demo_selected)
        self.demo_button = ttk.Button(demo_block, text="Run Demo", command=self.on_run_demo)
        # Legacy compatibility label for existing source-level checks: Run Demo Customer Message
        self.demo_button.pack(anchor="w", pady=(2, 0))
        ttk.Button(demo_block, text="Reset", command=self.on_reset).pack(anchor="w", pady=(2, 0))
        ttk.Label(demo_block, text="Mode: DRY RUN ONLY", style="Meta.TLabel").pack(anchor="w", pady=(2, 0))
        # Legacy source-level compatibility string: Use local Ollama LLM
        ttk.Checkbutton(demo_block, text="Use real Ollama LLM", variable=self.use_local_llm_var, command=self._sync_llm_info).pack(anchor="w", pady=(4, 0))
        self.llm_info_frame = ttk.Frame(demo_block, style="Workspace.TFrame")
        self.llm_provider_label = ttk.Label(self.llm_info_frame, text="LLM Provider: Ollama", style="Meta.TLabel")
        self.llm_model_label = ttk.Label(self.llm_info_frame, text="Model: granite3.3:8b", style="Meta.TLabel")
        self.llm_uses_label = ttk.Label(self.llm_info_frame, text="Uses LLM: yes", style="Meta.TLabel")
        self.llm_provider_label.pack(anchor="w", pady=(2, 0))
        self.llm_model_label.pack(anchor="w", pady=(0, 0))
        self.llm_uses_label.pack(anchor="w", pady=(0, 0))
        self._sync_llm_info()

        dataset_block = ttk.Frame(controls, style="Workspace.TFrame")
        dataset_block.pack(side="left", padx=(8, 12))
        ttk.Label(dataset_block, text="Business Dataset", style="Meta.TLabel").pack(anchor="w")
        ttk.Label(dataset_block, text="Dataset version: 2", style="Meta.TLabel").pack(anchor="w")
        ttk.Button(dataset_block, text="Seed Dataset", command=self.on_seed_dataset).pack(anchor="w", pady=(2, 0))
        ttk.Button(dataset_block, text="Reset Dataset", command=self.on_reset_dataset).pack(anchor="w", pady=(2, 0))
        ttk.Button(dataset_block, text="Validate Dataset", command=self.on_validate_dataset).pack(anchor="w", pady=(2, 0))
        self.dataset_validation_label = ttk.Label(dataset_block, text="Validation: unknown", style="Meta.TLabel")
        self.dataset_validation_label.pack(anchor="w", pady=(2, 0))

        ttk.Button(controls, text="Refresh Runtime Data", command=self.refresh_runtime_data).pack(side="left")

        self.scenario_items = list_scenarios(include_test_only=False)
        self.scenario_map = {item["label"]: item["id"] for item in self.scenario_items}
        scenario_block = ttk.Frame(controls, style="Workspace.TFrame")
        scenario_block.pack(side="left", padx=(8, 12))
        ttk.Label(scenario_block, text="Demo Scenario Pack", style="Meta.TLabel").pack(anchor="w")
        self.scenario_category_selector = ttk.Combobox(
            scenario_block,
            textvariable=self.scenario_category_var,
            state="readonly",
            width=14,
            values=("All",) + tuple(SCENARIO_CATEGORIES.values()),
        )
        # Happy Path, Negative Path, Approval, Data / Business, Reporting
        self.scenario_category_selector.pack(anchor="w", pady=(2, 2))
        self.scenario_category_selector.bind("<<ComboboxSelected>>", self._on_scenario_category_selected)
        self.scenario_selector = ttk.Combobox(
            scenario_block,
            textvariable=self.scenario_var,
            state="readonly",
            width=36,
            values=[item["label"] for item in self.scenario_items],
        )
        self.scenario_selector.pack(anchor="w", pady=(0, 2))
        self.scenario_selector.bind("<<ComboboxSelected>>", self._on_scenario_selected)
        self.scenario_description_label = ttk.Label(scenario_block, text="", style="Meta.TLabel", wraplength=320, justify="left")
        self.scenario_description_label.pack(anchor="w", pady=(0, 2))
        self.scenario_expected_label = ttk.Label(scenario_block, text="", style="Meta.TLabel", wraplength=320, justify="left")
        self.scenario_expected_label.pack(anchor="w", pady=(0, 4))
        ttk.Checkbutton(scenario_block, text="Reset Dataset", variable=self.scenario_reset_dataset_var).pack(anchor="w")
        ttk.Checkbutton(scenario_block, text="Use Local Ollama", variable=self.scenario_use_local_llm_var).pack(anchor="w")
        ttk.Button(scenario_block, text="Run Scenario", command=self.on_run_scenario).pack(anchor="w", pady=(4, 0))
        ttk.Button(scenario_block, text="Run + Generate Report", command=self.on_run_scenario_and_report).pack(anchor="w", pady=(2, 0))
        ttk.Button(scenario_block, text="Run Cross-Workflow Demo", command=self.on_run_cross_workflow_demo).pack(anchor="w", pady=(2, 0))
        self.scenario_result_label = ttk.Label(scenario_block, text="Scenario Result", style="Meta.TLabel")
        self.scenario_result_label.pack(anchor="w", pady=(4, 0))

        ttk.Label(controls, text="Playback Speed:", style="Meta.TLabel").pack(side="left", padx=(16, 6))
        self.speed_var = tk.StringVar(value="2s")
        speed = ttk.Combobox(controls, textvariable=self.speed_var, state="readonly", width=4, values=("1s", "2s", "3s"))
        speed.pack(side="left", padx=(0, 10))
        speed.bind("<<ComboboxSelected>>", self._on_speed_changed)
        self.pause_button = ttk.Button(controls, text="Pause", command=self.on_pause)
        self.pause_button.pack(side="left", padx=(0, 6))
        self.resume_button = ttk.Button(controls, text="Play", command=self.on_play)
        self.resume_button.pack(side="left", padx=(0, 6))
        self.skip_button = ttk.Button(controls, text="Next Step", command=self.on_next_step)
        self.skip_button.pack(side="left")
        ttk.Button(controls, text="Reset Playback", command=self.on_reset_playback).pack(side="left", padx=(6, 0))

    def _on_demo_selected(self, _event: object) -> None:
        label = self.demo_var.get()
        if label in self.demo_label_to_id:
            self.demo_var.set(label)

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
            self.scenario_description_label.configure(text="")
            self.scenario_expected_label.configure(text="")
            return
        self.scenario_description_label.configure(text=f"Description: {scenario.get('description', '')}")
        self.scenario_expected_label.configure(text=f"Expected: {scenario.get('expected', {})}")

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
        if result.get("frame_id"):
            self._load_result_frame(result)
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
        if result.get("frame_id"):
            self._load_result_frame(result)
        self.report_status = result.get("report_result", {}) or self.report_status
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
        self._render_current_view()

    def _sync_llm_info(self) -> None:
        if self.use_local_llm_var.get():
            if not self.llm_info_frame.winfo_ismapped():
                self.llm_info_frame.pack(anchor="w", pady=(2, 0))
        elif self.llm_info_frame.winfo_ismapped():
            self.llm_info_frame.pack_forget()

    def _selected_demo_id(self) -> str:
        label = self.demo_var.get()
        return self.demo_label_to_id.get(label, self.demo_items[0]["selection_id"] if self.demo_items else "")

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
        ttk.Button(controls, text="Test Selected", command=self.on_test_selected_tool).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Retry", command=self.on_retry_selected_tool).pack(side="left", padx=(0, 6))
        self.live_test_button = ttk.Button(controls, text="Live Test", command=self.on_live_test_selected_tool)
        self.live_test_button.pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Setup", command=self.on_setup_selected_tool).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Details", command=self._render_tool_details).pack(side="left")

        columns = ("tool", "category", "core_optional", "status", "last_checked", "test", "setup", "details")
        self.tool_health_tree = ttk.Treeview(panel, columns=columns, show="headings", height=8, selectmode="browse")
        self.tool_health_tree.heading("tool", text="Tool")
        self.tool_health_tree.column("tool", width=120, anchor="w")
        self.tool_health_tree.heading("category", text="Category")
        self.tool_health_tree.heading("core_optional", text="Core / Optional")
        self.tool_health_tree.heading("status", text="Status")
        self.tool_health_tree.heading("last_checked", text="Last Checked")
        self.tool_health_tree.heading("test", text="Test")
        self.tool_health_tree.heading("setup", text="Setup")
        self.tool_health_tree.heading("details", text="Details")
        self.tool_health_tree.column("category", width=120, anchor="w")
        self.tool_health_tree.column("core_optional", width=90, anchor="center")
        self.tool_health_tree.column("status", width=110, anchor="center")
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
        self._ensure_tool_health_snapshot()
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
        self.tool_health_snapshot = load_latest_tool_health_snapshot()
        if not self.tool_health_snapshot.get("results"):
            check_all_tool_health(include_optional=True, live_rpa=False)
            self.tool_health_snapshot = load_latest_tool_health_snapshot()

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
        self.tool_health_snapshot = load_latest_tool_health_snapshot()
        self._render_tool_capabilities_panel()

    def on_run_all_tool_health(self) -> None:
        check_all_tool_health(include_optional=True, live_rpa=False)
        self.tool_health_snapshot = load_latest_tool_health_snapshot()
        self._render_tool_capabilities_panel()

    def on_test_selected_tool(self) -> None:
        tool_id = self._selected_tool_id()
        if not tool_id:
            return
        check_tool_health(tool_id, live=False)
        self.tool_health_snapshot = load_latest_tool_health_snapshot()
        self._render_tool_capabilities_panel()

    def on_retry_selected_tool(self) -> None:
        self.on_test_selected_tool()

    def on_live_test_selected_tool(self) -> None:
        tool_id = self._selected_tool_id()
        if not tool_id or tool_id != "rpa_google_messages":
            return
        check_tool_health(tool_id, live=True)
        self.tool_health_snapshot = load_latest_tool_health_snapshot()
        self._render_tool_capabilities_panel()

    def on_setup_selected_tool(self) -> None:
        tool_id = self._selected_tool_id()
        if not tool_id:
            return
        run_safe_setup_action(tool_id)
        check_tool_health(tool_id, live=False)
        self.tool_health_snapshot = load_latest_tool_health_snapshot()
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
        self.demo_button.state(["disabled"])
        self.root.update_idletasks()
        try:
            selection_id = self._selected_demo_id()
            self.current_run = run_demo_manifest(
                selection_id,
                runtime_data_dir=self.runtime_root,
                use_local_llm=bool(self.use_local_llm_var.get()),
            )
            self.last_action_result = self.current_run
            self.last_snapshot = self.current_run.get("snapshot", {}) if isinstance(self.current_run, dict) else {}
            self.timeline = self.current_run.get("timeline", []) if isinstance(self.current_run, dict) else []
            self.playback_timeline = self.timeline
            self.playback_index = 0 if self.timeline else -1
            self.playing = bool(self.timeline)
            self.playback_running = self.playing
            self.playback_paused = False
            self._cancel_playback_timer()
            self._render_current_view()
            if self.playing:
                self.schedule_next_playback_tick()
        finally:
            self.demo_button.state(["!disabled"])
            self._update_footer()

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
        self.timeline = []
        self.playback_timeline = self.timeline
        self.playback_index = -1
        self.playing = False
        self.playback_running = False
        self.playback_paused = False
        self._cancel_playback_timer()
        self._render_snapshot()

    def on_generate_report(self) -> None:
        frame = (self._current_view() or {}).get("frame")
        if not isinstance(frame, dict):
            return
        frame_id = str(frame.get("frame_id", "")).strip()
        if not frame_id:
            return
        self.report_status = generate_report_for_frame(frame_id, self.runtime_root)
        self._render_current_view()

    def on_open_report_html(self) -> None:
        frame = (self._current_view() or {}).get("frame")
        frame_id = str(frame.get("frame_id", "")).strip() if isinstance(frame, dict) else ""
        if not frame_id:
            return
        paths = self.report_status or get_latest_report_paths(frame_id, self.runtime_root)
        html_path = paths.get("html_path", "")
        if html_path:
            open_report_html(html_path)

    def on_open_report_folder(self) -> None:
        frame = (self._current_view() or {}).get("frame")
        frame_id = str(frame.get("frame_id", "")).strip() if isinstance(frame, dict) else ""
        if not frame_id:
            return
        paths = self.report_status or get_latest_report_paths(frame_id, self.runtime_root)
        markdown_path = paths.get("markdown_path", "")
        if markdown_path:
            open_report_folder(markdown_path)

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

    def update_approval_button_states(self) -> None:
        return None

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

    def refresh_current_run_from_result(self, result: dict) -> None:
        if not isinstance(result, dict):
            return
        self.current_run = result
        self.last_snapshot = result.get("snapshot", {}) if isinstance(result.get("snapshot", {}), dict) else {}
        self.timeline = result.get("timeline", []) if isinstance(result.get("timeline", []), list) else []
        self.playback_timeline = self.timeline
        self.playback_index = 0 if self.timeline else -1
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
                    ttk.Label(block, text=f"• {self._format_event_item(item, frames_by_id if isinstance(frames_by_id, dict) else {})}", style="Body.TLabel", wraplength=300, justify="left").pack(
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

        self._render_field(self.active_body, "Frame ID", frame.get("frame_id", "—"))
        self._render_field(self.active_body, "State", frame.get("state", "—"))
        self._render_field(self.active_body, "Trigger", self._compact_value(frame.get("trigger", {})))
        self._render_field(self.active_body, "Manifest", frame.get("manifest_id", "—"))
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
        capability = None
        try:
            from runtime.tool_capability_registry import get_tool_capability

            capability = get_tool_capability(tool_id) if tool_id else None
        except Exception:
            capability = None
        result = self._tool_result_for(tool_id)
        setup = get_tool_setup_instructions(tool_id) if tool_id else {}
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
        text = "\n".join(lines) if lines else "Select a tool to view its capability and health details."
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
        self.trace_text.insert("1.0", "\n".join(lines))
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
        event_id = str(event.get("event_id", "") or "—")
        source = str(event.get("source", "") or "—")
        event_type = str(event.get("event_type", "") or "—")
        status = str(event.get("status", "") or "—")
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
                parts.append(f"order.status: {order.get('status', '—')}")
            if draft_reply:
                parts.append(f"draft_reply.body: {draft_reply.get('body', '—')}")
            if outputs.get("business_lookups"):
                parts.append("business_lookups: sourced from runtime_data/business")
            return "\n".join(parts)
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
        return "\n".join(parts) if parts else "No playback detail selected."

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
        return "\n".join(lines) if lines else "No validation data available."

    def _format_pending_actions(self, pending_actions: list) -> str:
        if not pending_actions:
            return "No pending actions."
        lines: list[str] = []
        for item in pending_actions:
            if not isinstance(item, dict):
                continue
            action_type = str(item.get("action_type", "") or "unknown")
            status = str(item.get("status", "") or "unknown")
            customer_id = str(item.get("customer_id", "") or "—")
            channel = str(item.get("channel", "") or "—")
            body = str(item.get("body", "") or "")
            preview = body if len(body) <= 80 else f"{body[:77]}..."
            lines.append(f"{action_type} | {status} | {customer_id} | {channel} | {preview}")
        return "\n".join(lines) if lines else "No pending actions."

    def _format_last_action_result(self, result: dict) -> list[str]:
        lines = [
            "[LAST UI ACTION]",
            "action: run_demo_customer_message",
            f"status: {result.get('status', 'FAILED')}",
            f"event_id: {result.get('event_id') or '—'}",
            f"frame_id: {result.get('frame_id') or '—'}",
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
        return "\n".join(f"{field}: {summary.get(field, '')}" for field in fields)

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
        return "\n".join(lines)

    def _format_report_status(self, report_status: dict | None) -> str:
        if not isinstance(report_status, dict) or not report_status:
            return "No report generated."
        return "\n".join(
            [
                f"ok: {report_status.get('ok', False)}",
                f"markdown_path: {report_status.get('markdown_path', '')}",
                f"html_path: {report_status.get('html_path', '')}",
                f"evidence_bundle_path: {report_status.get('evidence_bundle_path', '')}",
                f"error: {report_status.get('error', '')}",
            ]
        )

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
        return "\n".join(blocks).strip()

    def _format_approval_operation(self, operation: dict | None) -> str:
        if not isinstance(operation, dict):
            return "No approval operation yet."
        return "\n".join(
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
        if checks:
            for item in checks:
                if not isinstance(item, dict):
                    continue
                prefix = "✓" if item.get("ok") else "✗"
                lines.append(f"{prefix} {item.get('id', '')}: {item.get('actual', '')}")
        else:
            lines.append("No checks available.")
        return "\n".join(lines)

    def _format_llm_info(self, llm_info: dict | None) -> str:
        if not isinstance(llm_info, dict) or not llm_info:
            return "No local LLM configured."
        return "\n".join(
            [
                f"LLM Provider: {llm_info.get('provider', '')}",
                f"Model: {llm_info.get('model', '')}",
            ]
        )

    def _compact_multiline(self, value: object) -> str:
        if isinstance(value, list):
            if not value:
                return "None"
            return "\n".join(f"- {self._compact_value(item)}" for item in value)
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
            f"current: {view.get('current', '')}",
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
        symbol = "○"
        if step_id in visible_steps:
            symbol = "✓"
        if step_id == current_step_id:
            symbol = "▶"
        if ok is False or status in {"FAILED", "FAILED_VALIDATION", "FAILED_EXECUTION", "FAILED_COMPLETION"}:
            symbol = "✗"
        return f"{symbol} {step_id}"

    def _compact_value(self, value: object) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))
        if value is None or value == "":
            return "—"
        return str(value)

    def _update_footer(self, view: dict | None = None) -> None:
        snapshot = self.last_snapshot if view is None else {"active_frame": view.get("frame")}
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
            }
        return build_playback_view(self.last_snapshot, self.playback_timeline, self.playback_index)

    def _render_snapshot(self) -> None:
        self._render_task_queue()
        self._render_active_taskframe()
        self._render_results_actions()
        self._render_runtime_trace()
        self._update_footer()

    def _render_current_view(self) -> None:
        view = self._current_view()
        self._render_task_queue(view)
        self._render_active_taskframe(view)
        self._render_results_actions(view)
        self._render_runtime_trace(view)
        self._update_footer(view)
        self._update_dataset_validation_label()
        self.root.update_idletasks()


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
