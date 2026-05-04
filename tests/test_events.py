import unittest

from runtime.errors import EventValidationError
from runtime.events import RuntimeEvent, create_event, new_event_id


class EventTests(unittest.TestCase):
    def test_create_event_creates_event_id(self):
        event = create_event("manual.gmail_check", "manual")
        self.assertIsInstance(event, RuntimeEvent)
        self.assertTrue(event.event_id.startswith("evt_"))

    def test_create_event_sets_fields_and_defaults(self):
        event = create_event("manual.gmail_check", "manual")
        self.assertEqual(event.event_type, "manual.gmail_check")
        self.assertEqual(event.source, "manual")
        self.assertEqual(event.payload, {})
        self.assertEqual(event.metadata, {})
        self.assertTrue(event.received_at)
        self.assertEqual(event.status, "RECEIVED")
        self.assertIsNone(event.linked_frame_id)

    def test_new_event_id_prefix(self):
        self.assertTrue(new_event_id().startswith("evt_"))

    def test_create_event_rejects_empty_event_type(self):
        with self.assertRaises(EventValidationError):
            create_event("", "manual")

    def test_create_event_rejects_empty_source(self):
        with self.assertRaises(EventValidationError):
            create_event("manual.gmail_check", "")

    def test_create_event_rejects_non_dict_payload(self):
        with self.assertRaises(EventValidationError):
            create_event("manual.gmail_check", "manual", payload=[])  # type: ignore[arg-type]

    def test_create_event_rejects_non_dict_metadata(self):
        with self.assertRaises(EventValidationError):
            create_event("manual.gmail_check", "manual", metadata=[])  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
