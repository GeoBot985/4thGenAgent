import json
import os
import subprocess
import sys
import unittest
from pathlib import Path


class EventWorkflowDemoPackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]

    def test_demo_event_file_exists_and_is_valid(self) -> None:
        path = self.root / "demo" / "customer_message_event.json"
        self.assertTrue(path.is_file())
        event = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(event["event_id"], "evt-demo-customer-001")
        self.assertEqual(event["source"], "callcenter")
        self.assertEqual(event["event_type"], "customer_message")
        self.assertIn("ORD-10042", event["payload"]["message"])

    def test_demo_runner_completes_successfully(self) -> None:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(self.root)
        result = subprocess.run(
            [sys.executable, "scripts/run_event_demo.py"],
            cwd=self.root,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        stdout = result.stdout
        self.assertIn("EVENT WORKFLOW DEMO", stdout)
        self.assertIn("Status: WAITING_FOR_EXECUTE", stdout)
        self.assertIn("route_id: callcenter.customer_message", stdout)
        self.assertIn("manifest_id: customer.message_status_check", stdout)
        self.assertIn("order_id: ORD-10042", stdout)
        self.assertIn("shipped", stdout)
        self.assertIn("send_customer_message", stdout)
        self.assertIn("PENDING_APPROVAL", stdout)
        self.assertIn("Result: PASS", stdout)

    def test_demo_does_not_execute_pending_action(self) -> None:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(self.root)
        result = subprocess.run(
            [sys.executable, "scripts/run_event_demo.py"],
            cwd=self.root,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("Pending Actions", result.stdout)
        self.assertNotIn("EXECUTED", result.stdout)

    def test_demo_documentation_exists(self) -> None:
        path = self.root / "docs" / "event_workflow_demo.md"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("python scripts/run_event_demo.py", text)
        self.assertIn("WAITING_FOR_EXECUTE", text)
        self.assertIn("side effects are gated", text.lower())

    def test_taskframe_state_and_pending_action_remain(self) -> None:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(self.root)
        result = subprocess.run(
            [sys.executable, "scripts/run_event_demo.py"],
            cwd=self.root,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("Status: WAITING_FOR_EXECUTE", result.stdout)
        self.assertIn("status: PENDING_APPROVAL", result.stdout)


if __name__ == "__main__":
    unittest.main()
