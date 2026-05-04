from __future__ import annotations

import os
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.events import create_event
from runtime.llm_config import build_llm_adapter
from runtime.runtime_engine import RuntimeEngine


@unittest.skipUnless(os.getenv("TASKFRAME_RUN_LIVE_OLLAMA_TESTS") == "1", "Live Ollama test disabled.")
class LiveOllamaGraniteTests(unittest.TestCase):
    def test_live_ollama_granite_extract_order_ref(self):
        adapter = build_llm_adapter(provider="ollama", model="granite3.3:8b")
        engine = RuntimeEngine(llm_adapter=adapter)
        event = create_event(
            event_type="manual.llm_extract_order_ref",
            source="operator_ui",
            payload={"message": "Please check order ORD-10042."},
        )

        frame = engine.handle_event(event, dry_run=True)

        self.assertIn(frame.state, {"COMPLETED", "WAITING_FOR_EXECUTE"})
        self.assertIn("order_ref", frame.outputs)
        self.assertEqual(frame.outputs["order_ref"].get("order_ref"), "ORD-10042")


if __name__ == "__main__":
    unittest.main()
