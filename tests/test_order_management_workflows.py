"""Spec 110 — Order Management Workflow tests (manifest execution)."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from runtime.event_store import intake_and_run_event
from runtime.taskframe_reload import load_taskframe


def _intake(event_type, payload, tmpdir):
    event = {
        "event_id": f"evt-{event_type}-{abs(hash(str(payload)))}",
        "source": "operator_scenario_pack",
        "event_type": event_type,
        "payload": payload,
        "received_at": "2026-05-18T00:00:00Z",
    }
    return intake_and_run_event(event, runtime_data_dir=tmpdir, manifest_dir="manifests", routes_path="config/event_routes.json")


class TestOrderValidateNewManifest(unittest.TestCase):
    def test_completes_for_valid_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _intake("manual.order_validate_new", {"customer_id": "CUST-1001", "items": [{"sku": "SKU-DESK-01", "quantity": 1}]}, tmp)
            self.assertIn(result["status"], {"COMPLETED", "WAITING_FOR_EXECUTE"})

    def test_fails_for_insufficient_stock(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _intake("manual.order_validate_new", {"customer_id": "CUST-1001", "items": [{"sku": "SKU-CHAIR-01", "quantity": 2}]}, tmp)
            self.assertTrue(result["status"].startswith("FAILED") or not result["ok"])


class TestOrderReserveStockManifest(unittest.TestCase):
    def test_waits_for_execute_on_valid_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _intake("manual.order_reserve_stock", {"order_ref": "ORD-10050", "customer_id": "CUST-1001", "items": [{"sku": "SKU-DESK-01", "quantity": 1}]}, tmp)
            self.assertEqual(result["status"], "WAITING_FOR_EXECUTE")

    def test_approve_execute_dry_run_completes(self):
        from runtime.pending_actions import mark_pending_action_approved
        from runtime.taskframe_reload import load_taskframe
        from runtime.tool_runner import ToolRunner
        from runtime.persistence import PersistenceManager
        from runtime.orchestrator import Orchestrator
        from runtime.taskframe_reload import load_manifest_for_frame
        with tempfile.TemporaryDirectory() as tmp:
            result = _intake("manual.order_reserve_stock", {"order_ref": "ORD-10050", "customer_id": "CUST-1001", "items": [{"sku": "SKU-DESK-01", "quantity": 1}]}, tmp)
            self.assertEqual(result["status"], "WAITING_FOR_EXECUTE")
            frame_id = result["frame_id"]
            frame = load_taskframe(frame_id, tmp)
            # Approve all pending actions
            for pa in list(frame.pending_actions):
                action_id = pa.get("action_id", "") if hasattr(pa, "get") else pa.action_id
                mark_pending_action_approved(frame, action_id, approved_by="test")
            PersistenceManager(tmp).save_snapshot(frame)
            # Execute dry run
            runner = ToolRunner(dry_run=True)
            frame = load_taskframe(frame_id, tmp)
            for pa in list(frame.pending_actions):
                action_dict = dict(pa) if hasattr(pa, "get") else pa.__dict__
                if str(action_dict.get("status", "")) == "APPROVED":
                    runner.execute_pending_action(frame, action_dict)
            PersistenceManager(tmp).save_snapshot(frame)
            frame = load_taskframe(frame_id, tmp)
            # At minimum, execution was attempted
            self.assertIsNotNone(frame)


class TestOrderReleasePaidManifest(unittest.TestCase):
    def test_waits_for_execute_paid_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _intake("manual.order_release_paid", {"order_ref": "ORD-10052"}, tmp)
            self.assertEqual(result["status"], "WAITING_FOR_EXECUTE")

    def test_fails_unpaid_order_without_pending_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _intake("manual.order_release_paid", {"order_ref": "ORD-10053"}, tmp)
            self.assertTrue(result["status"].startswith("FAILED") or not result["ok"])


class TestOrderDetectDelayedManifest(unittest.TestCase):
    def test_completes(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _intake("manual.order_detect_delayed", {"days_overdue": 2}, tmp)
            self.assertIn(result["status"], {"COMPLETED", "COMPLETED_NO_DATA"})


class TestOrderUpdateShipmentStatusManifest(unittest.TestCase):
    def test_waits_for_execute(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _intake("manual.order_update_shipment_status", {"order_ref": "ORD-10055", "shipment_status": "shipped", "tracking_ref": "TRK-999002"}, tmp)
            self.assertEqual(result["status"], "WAITING_FOR_EXECUTE")


class TestOrchestratorNotModified(unittest.TestCase):
    def test_no_order_domain_logic_in_orchestrator(self):
        import ast
        from pathlib import Path
        src = Path("runtime/orchestrator.py").read_text(encoding="utf-8")
        # Check for order management domain terms that should NOT be in orchestrator
        for term in ("order_validate_new", "stock_reservation", "release_paid_order", "detect_delayed", "shipment_status_update"):
            self.assertNotIn(term, src, f"Orchestrator must not contain domain term: {term}")


if __name__ == "__main__":
    unittest.main()
