from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path


EXAMPLES = Path("tool_packs/google_workspace/examples")
TOOLPACK = Path("tool_packs/google_workspace/toolpack.json")


class _FakeExecute:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class _FakeGoogleService:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def users(self):
        service = self

        class _Users:
            def messages(self):
                class _Messages:
                    def list(self, **kwargs):
                        service.calls.append(("gmail.list", kwargs))
                        return _FakeExecute({"messages": [{"id": "msg-1"}]})

                    def get(self, **kwargs):
                        service.calls.append(("gmail.get", kwargs))
                        return _FakeExecute(
                            {
                                "id": kwargs.get("id", ""),
                                "threadId": "thread-1",
                                "snippet": "Hello",
                                "payload": {
                                    "headers": [
                                        {"name": "From", "value": "sender@example.com"},
                                        {"name": "Subject", "value": "Unread mail"},
                                        {"name": "Date", "value": "Mon, 01 Jan 2026 10:00:00 +0200"},
                                    ]
                                },
                            }
                        )

                return _Messages()

            def getProfile(self, **kwargs):
                service.calls.append(("gmail.profile", kwargs))
                return _FakeExecute({"emailAddress": "user@example.com"})

        return _Users()

    def calendarList(self):
        service = self

        class _CalendarList:
            def list(self, **kwargs):
                service.calls.append(("calendar.list", kwargs))
                return _FakeExecute({"items": [{"id": "primary", "primary": True}]})

        return _CalendarList()

    def events(self):
        service = self

        class _Events:
            def list(self, **kwargs):
                service.calls.append(("calendar.events", kwargs))
                return _FakeExecute(
                    {
                        "items": [
                            {
                                "id": "evt-1",
                                "summary": "Planning",
                                "description": "Discuss work",
                                "location": "Room 1",
                                "start": {"dateTime": "2026-05-01T09:00:00+02:00"},
                                "end": {"dateTime": "2026-05-01T10:00:00+02:00"},
                                "htmlLink": "https://example.test",
                                "status": "confirmed",
                            }
                        ]
                    }
                )

        return _Events()

    def spreadsheets(self):
        service = self

        class _Values:
            def get(self, **kwargs):
                service.calls.append(("sheets.values", kwargs))
                return _FakeExecute({"values": [["A", "B"], ["1", "2"]]})

        class _Spreadsheets:
            def values(self):
                return _Values()

        return _Spreadsheets()


@contextmanager
def _temporary_external_tools(config_path: Path):
    import runtime.tool_registry as tool_registry
    import runtime.tool_runner as tool_runner

    saved_registry = dict(tool_registry.TOOL_REGISTRY)
    saved_get_tool_spec = tool_runner.get_tool_spec
    external = tool_registry.build_tool_registry(include_external=True, config_path=config_path)
    tool_registry.TOOL_REGISTRY.clear()
    tool_registry.TOOL_REGISTRY.update(external)
    tool_runner.get_tool_spec = lambda namespace, action: external[f"{namespace}/{action}"]
    try:
        yield
    finally:
        tool_registry.TOOL_REGISTRY.clear()
        tool_registry.TOOL_REGISTRY.update(saved_registry)
        tool_runner.get_tool_spec = saved_get_tool_spec


def _write_config(tmp_path: Path) -> Path:
    payload = {
        "enabled_toolpacks": [str(TOOLPACK)],
        "disabled_toolpacks": [],
        "allow_optional_toolpacks": True,
    }
    path = tmp_path / "enabled_toolpacks.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _patch_service(monkeypatch, service: _FakeGoogleService) -> None:
    from tool_packs.google_workspace import auth

    monkeypatch.setattr(auth, "build_google_service", lambda service_name, version: service)
    monkeypatch.setattr(auth, "google_dependency_state", lambda: {"ok": True, "missing": []})
    monkeypatch.setattr(
        auth,
        "google_auth_files",
        lambda: {
            "credentials_file_present": True,
            "token_file_present": True,
            "configured_services": ["gmail", "calendar", "sheets"],
            "profile": "default",
            "config_dir": ".",
        },
    )


def test_smoke_gmail_list_unread_manifest_runs_with_fake_google_service(tmp_path: Path, monkeypatch) -> None:
    from runtime.manifest_loader import load_manifest
    from runtime.orchestrator import Orchestrator
    from runtime.tool_runner import ToolRunner

    config_path = _write_config(tmp_path)
    manifest = load_manifest(EXAMPLES / "smoke_gmail_list_unread.manifest.json")
    service = _FakeGoogleService()
    _patch_service(monkeypatch, service)
    with _temporary_external_tools(config_path):
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest)
        frame = orch.prepare_frame(frame)
        runner = ToolRunner(dry_run=False)
        result = runner.run_step(frame, frame.steps[0])
    assert result.ok is True
    assert frame.outputs["unread_messages"]["data"][0]["subject"] == "Unread mail"


def test_smoke_calendar_search_manifest_runs_with_fake_google_service(tmp_path: Path, monkeypatch) -> None:
    from runtime.manifest_loader import load_manifest
    from runtime.orchestrator import Orchestrator
    from runtime.tool_runner import ToolRunner

    config_path = _write_config(tmp_path)
    manifest = load_manifest(EXAMPLES / "smoke_calendar_search.manifest.json")
    service = _FakeGoogleService()
    _patch_service(monkeypatch, service)
    with _temporary_external_tools(config_path):
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest, inputs={"query": "planning"})
        frame = orch.prepare_frame(frame)
        runner = ToolRunner(dry_run=False)
        result = runner.run_step(frame, frame.steps[0])
    assert result.ok is True
    assert frame.outputs["calendar_entries"]["data"][0]["summary"] == "Planning"


def test_smoke_sheets_read_range_manifest_runs_with_fake_google_service(tmp_path: Path, monkeypatch) -> None:
    from runtime.manifest_loader import load_manifest
    from runtime.orchestrator import Orchestrator
    from runtime.tool_runner import ToolRunner

    config_path = _write_config(tmp_path)
    manifest = load_manifest(EXAMPLES / "smoke_sheets_read_range.manifest.json")
    service = _FakeGoogleService()
    _patch_service(monkeypatch, service)
    with _temporary_external_tools(config_path):
        orch = Orchestrator()
        frame = orch.create_frame_from_manifest(manifest, inputs={"spreadsheet_id": "sheet-1", "range_name": "Sheet1!A1:B2"})
        frame = orch.prepare_frame(frame)
        runner = ToolRunner(dry_run=False)
        result = runner.run_step(frame, frame.steps[0])
    assert result.ok is True
    assert frame.outputs["sheet_rows"]["data"]["row_count"] == 2
