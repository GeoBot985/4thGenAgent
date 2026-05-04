from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .event_router import EventRouter
from .events import RuntimeEvent
from .llm_adapter import BaseLLMAdapter, FakeLLMAdapter
from .llm_config import build_llm_adapter
from .memory_store import MemoryStore
from .models import TaskFrame
from .persistence import PersistenceManager
from .orchestrator import Orchestrator
from .inspection import RunInspector
from .taskframe import add_audit_event


class RuntimeEngine:
    def __init__(
        self,
        routes_path: str | Path = "manifests/event_routes.json",
        manifest_dir: str | Path = "manifests",
        memory_store: MemoryStore | None = None,
        llm_adapter: BaseLLMAdapter | None = None,
        use_configured_llm: bool = False,
        runtime_data_dir: str | Path = "runtime_data",
        persist_runs: bool = True,
    ):
        self.router = EventRouter(routes_path, manifest_dir)
        self.memory_store = memory_store or MemoryStore()
        self.llm_adapter = llm_adapter or (build_llm_adapter() if use_configured_llm else FakeLLMAdapter())
        self.manifest_dir = Path(manifest_dir)
        self.runtime_data_dir = Path(runtime_data_dir)
        self.persist_runs = persist_runs
        self.inspector = RunInspector(runtime_data_dir=self.runtime_data_dir)
        self.orchestrator = Orchestrator(
            memory_store=self.memory_store,
            llm_adapter=self.llm_adapter,
            inspector=self.inspector,
            runtime_data_dir=self.runtime_data_dir,
            manifest_dir=self.manifest_dir,
        )
        self.persistence = PersistenceManager(self.runtime_data_dir) if persist_runs else None

    def handle_event(
        self,
        event: RuntimeEvent,
        dry_run: bool = True,
    ) -> TaskFrame:
        manifest = self.router.resolve_manifest(event)
        frame: TaskFrame | None = None
        trigger = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "source": event.source,
            **dict(event.payload),
        }
        inputs = dict(event.payload)
        frame = self.orchestrator.create_frame_from_manifest(
            manifest,
            trigger=trigger,
            inputs=inputs,
            raw_input=json.dumps(
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "source": event.source,
                    "payload": event.payload,
                },
                sort_keys=True,
            ),
        )
        add_audit_event(
            frame,
            "EVENT_RECEIVED",
            "Runtime event received.",
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "source": event.source,
            },
        )
        add_audit_event(
            frame,
            "EVENT_ROUTED",
            "Runtime event routed to manifest.",
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "manifest_id": manifest.manifest_id,
            },
        )
        add_audit_event(
            frame,
            "RUNTIME_ENGINE_STARTED",
            "Runtime engine started processing event.",
            {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "manifest_id": manifest.manifest_id,
                "dry_run": dry_run,
            },
        )
        self._save_frame_snapshot(frame)
        try:
            frame = self.orchestrator.prepare_frame(frame)
            frame = self.orchestrator.run_until_blocked(frame, manifest, dry_run=dry_run)
            return frame
        finally:
            if frame is not None:
                add_audit_event(
                    frame,
                    "RUNTIME_ENGINE_COMPLETED",
                    "Runtime engine completed event processing.",
                    {
                        "event_id": event.event_id,
                        "event_type": event.event_type,
                        "manifest_id": manifest.manifest_id,
                        "state": frame.state,
                        "dry_run": dry_run,
                    },
                )
                self._save_frame_snapshot(frame)

    def _save_frame_snapshot(self, frame: TaskFrame) -> None:
        if self.persistence is None:
            return
        self.persistence.save_snapshot(frame)
