import json
import tempfile
import unittest
from pathlib import Path

from runtime.errors import EventValidationError, ManifestRouteNotFoundError
from runtime.event_router import EventRouter
from runtime.events import create_event


def write_manifest(tmpdir: Path, manifest_id: str, command: str = "[t:g/check -> unread_mail] max_results=5") -> Path:
    path = tmpdir / f"{manifest_id.replace('.', '_')}.manifest.json"
    path.write_text(
        json.dumps(
            {
                "manifest_id": manifest_id,
                "name": manifest_id,
                "version": 1,
                "trigger": {"type": "manual"},
                "inputs": [],
                "steps": [{"id": "check_mail", "command": command}],
                "validations": [],
                "completion": {"success_outputs": ["unread_mail"]},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def write_routes(tmpdir: Path, routes: list[dict]) -> Path:
    path = tmpdir / "event_routes.json"
    path.write_text(json.dumps({"routes": routes}, indent=2), encoding="utf-8")
    return path


class EventRouterTests(unittest.TestCase):
    def test_load_routes_loads_valid_routes(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_manifest(tmpdir, "smoke.gmail_check")
            write_routes(
                tmpdir,
                [
                    {"event_type": "manual.gmail_check", "manifest_id": "smoke.gmail_check", "enabled": True},
                ],
            )
            router = EventRouter(routes_path=tmpdir / "event_routes.json", manifest_dir=tmpdir)

            routes = router.load_routes()

            self.assertEqual(len(routes), 1)
            self.assertEqual(routes[0]["event_type"], "manual.gmail_check")

    def test_resolve_manifest_id_finds_enabled_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_manifest(tmpdir, "smoke.gmail_check")
            write_routes(
                tmpdir,
                [
                    {"event_type": "manual.gmail_check", "manifest_id": "smoke.gmail_check", "enabled": True},
                ],
            )
            router = EventRouter(routes_path=tmpdir / "event_routes.json", manifest_dir=tmpdir)
            event = create_event("manual.gmail_check", "manual")

            self.assertEqual(router.resolve_manifest_id(event), "smoke.gmail_check")

    def test_resolve_manifest_loads_manifest_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_manifest(tmpdir, "smoke.gmail_check")
            write_routes(
                tmpdir,
                [
                    {"event_type": "manual.gmail_check", "manifest_id": "smoke.gmail_check", "enabled": True},
                ],
            )
            router = EventRouter(routes_path=tmpdir / "event_routes.json", manifest_dir=tmpdir)
            event = create_event("manual.gmail_check", "manual")

            manifest = router.resolve_manifest(event)

            self.assertEqual(manifest.manifest_id, "smoke.gmail_check")

    def test_unknown_event_type_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_manifest(tmpdir, "smoke.gmail_check")
            write_routes(
                tmpdir,
                [
                    {"event_type": "manual.gmail_check", "manifest_id": "smoke.gmail_check", "enabled": True},
                ],
            )
            router = EventRouter(routes_path=tmpdir / "event_routes.json", manifest_dir=tmpdir)
            event = create_event("manual.unknown", "manual")

            with self.assertRaises(ManifestRouteNotFoundError):
                router.resolve_manifest_id(event)

    def test_disabled_route_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_manifest(tmpdir, "smoke.gmail_check")
            write_routes(
                tmpdir,
                [
                    {"event_type": "manual.gmail_check", "manifest_id": "smoke.gmail_check", "enabled": False},
                ],
            )
            router = EventRouter(routes_path=tmpdir / "event_routes.json", manifest_dir=tmpdir)
            event = create_event("manual.gmail_check", "manual")

            with self.assertRaises(ManifestRouteNotFoundError):
                router.resolve_manifest_id(event)

    def test_duplicate_enabled_route_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_manifest(tmpdir, "smoke.gmail_check")
            write_manifest(tmpdir, "live.calendar_next")
            write_routes(
                tmpdir,
                [
                    {"event_type": "manual.gmail_check", "manifest_id": "smoke.gmail_check", "enabled": True},
                    {"event_type": "manual.gmail_check", "manifest_id": "live.calendar_next", "enabled": True},
                ],
            )
            router = EventRouter(routes_path=tmpdir / "event_routes.json", manifest_dir=tmpdir)

            with self.assertRaises(EventValidationError):
                router.load_routes()

    def test_route_missing_event_type_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_manifest(tmpdir, "smoke.gmail_check")
            write_routes(
                tmpdir,
                [
                    {"manifest_id": "smoke.gmail_check", "enabled": True},
                ],
            )
            router = EventRouter(routes_path=tmpdir / "event_routes.json", manifest_dir=tmpdir)

            with self.assertRaises(EventValidationError):
                router.load_routes()

    def test_route_missing_manifest_id_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_manifest(tmpdir, "smoke.gmail_check")
            write_routes(
                tmpdir,
                [
                    {"event_type": "manual.gmail_check", "enabled": True},
                ],
            )
            router = EventRouter(routes_path=tmpdir / "event_routes.json", manifest_dir=tmpdir)

            with self.assertRaises(EventValidationError):
                router.load_routes()

    def test_route_with_missing_manifest_id_target_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_manifest(tmpdir, "smoke.gmail_check")
            write_routes(
                tmpdir,
                [
                    {"event_type": "manual.gmail_check", "manifest_id": "missing.manifest", "enabled": True},
                ],
            )
            router = EventRouter(routes_path=tmpdir / "event_routes.json", manifest_dir=tmpdir)

            with self.assertRaises(ManifestRouteNotFoundError):
                router.load_routes()

    def test_disabled_route_with_missing_manifest_id_target_does_not_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            write_manifest(tmpdir, "smoke.gmail_check")
            write_routes(
                tmpdir,
                [
                    {"event_type": "manual.gmail_check", "manifest_id": "missing.manifest", "enabled": False},
                ],
            )
            router = EventRouter(routes_path=tmpdir / "event_routes.json", manifest_dir=tmpdir)

            routes = router.load_routes()

            self.assertEqual(len(routes), 1)


if __name__ == "__main__":
    unittest.main()
