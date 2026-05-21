from __future__ import annotations

import unittest

from runtime.live_guardrails import guardrail_gmail_send, run_live_guardrail
from runtime.gmail_send_tool import build_gmail_send_pending_action


def _base_action(
    *,
    to: list[str] | None = None,
    subject: str = "Test",
    body: str = "Body",
    business_ref: str = "ref-001",
    idempotency_key: str = "idem-001",
    status: str = "APPROVED",
) -> dict:
    _to = to if to is not None else ["user@example.com"]
    action = build_gmail_send_pending_action(
        action_id="pa-001",
        business_ref=business_ref,
        idempotency_key=idempotency_key,
        to=_to,
        subject=subject,
        body=body,
        status=status,
    )
    action["status"] = status
    return action


def _live_tool_spec() -> dict:
    return {
        "side_effect": True,
        "requires_approval": True,
        "allow_live": True,
        "allow_live_side_effect": True,
        "live_guardrail": "gmail_send",
    }


class TestGuardrailGmailSendBasic(unittest.TestCase):
    def test_all_checks_pass_returns_ok(self):
        action = _base_action()
        result = guardrail_gmail_send(action, _live_tool_spec())
        self.assertTrue(result["ok"])
        self.assertEqual(result["guardrail"], "gmail_send")
        self.assertIsInstance(result["checks"], list)

    def test_result_has_expected_structure(self):
        result = guardrail_gmail_send(_base_action(), _live_tool_spec())
        self.assertIn("ok", result)
        self.assertIn("guardrail", result)
        self.assertIn("checks", result)

    def test_all_checks_have_name_ok_message(self):
        result = guardrail_gmail_send(_base_action(), _live_tool_spec())
        for check in result["checks"]:
            self.assertIn("name", check)
            self.assertIn("ok", check)
            self.assertIn("message", check)


class TestGuardrailActionApproved(unittest.TestCase):
    def test_unapproved_action_fails(self):
        action = _base_action(status="PENDING_APPROVAL")
        result = guardrail_gmail_send(action, _live_tool_spec())
        self.assertFalse(result["ok"])
        check = next(c for c in result["checks"] if c["name"] == "action_approved")
        self.assertFalse(check["ok"])

    def test_approved_action_passes(self):
        action = _base_action(status="APPROVED")
        result = guardrail_gmail_send(action, _live_tool_spec())
        check = next(c for c in result["checks"] if c["name"] == "action_approved")
        self.assertTrue(check["ok"])


class TestGuardrailToolCheck(unittest.TestCase):
    def test_wrong_tool_fails(self):
        action = _base_action()
        action["tool"] = "g/send"
        result = guardrail_gmail_send(action, _live_tool_spec())
        self.assertFalse(result["ok"])
        check = next(c for c in result["checks"] if c["name"] == "tool_is_gmail_send")
        self.assertFalse(check["ok"])

    def test_correct_tool_passes(self):
        action = _base_action()
        result = guardrail_gmail_send(action, _live_tool_spec())
        check = next(c for c in result["checks"] if c["name"] == "tool_is_gmail_send")
        self.assertTrue(check["ok"])

    def test_tool_not_live_capable_fails(self):
        action = _base_action()
        spec = dict(_live_tool_spec())
        spec["allow_live_side_effect"] = False
        result = guardrail_gmail_send(action, spec)
        self.assertFalse(result["ok"])
        check = next(c for c in result["checks"] if c["name"] == "tool_allows_live_side_effect")
        self.assertFalse(check["ok"])


class TestGuardrailPayloadChecks(unittest.TestCase):
    def test_empty_recipients_fails(self):
        action = _base_action(to=[])
        result = guardrail_gmail_send(action, _live_tool_spec())
        self.assertFalse(result["ok"])
        check = next(c for c in result["checks"] if c["name"] == "recipients_not_empty")
        self.assertFalse(check["ok"])

    def test_empty_subject_fails(self):
        action = _base_action(subject="")
        result = guardrail_gmail_send(action, _live_tool_spec())
        self.assertFalse(result["ok"])
        check = next(c for c in result["checks"] if c["name"] == "subject_not_empty")
        self.assertFalse(check["ok"])

    def test_empty_body_fails(self):
        action = _base_action(body="")
        result = guardrail_gmail_send(action, _live_tool_spec())
        self.assertFalse(result["ok"])
        check = next(c for c in result["checks"] if c["name"] == "body_not_empty")
        self.assertFalse(check["ok"])

    def test_missing_business_ref_fails(self):
        action = _base_action(business_ref="")
        result = guardrail_gmail_send(action, _live_tool_spec())
        self.assertFalse(result["ok"])
        check = next(c for c in result["checks"] if c["name"] == "business_ref_exists")
        self.assertFalse(check["ok"])

    def test_missing_idempotency_key_fails(self):
        action = _base_action(idempotency_key="")
        result = guardrail_gmail_send(action, _live_tool_spec())
        self.assertFalse(result["ok"])
        check = next(c for c in result["checks"] if c["name"] == "idempotency_key_present")
        self.assertFalse(check["ok"])


class TestGuardrailDomainChecks(unittest.TestCase):
    def test_blocked_domain_fails(self):
        config = {"gmail_send": {"blocked_recipient_domains": ["spam.com"]}}
        action = _base_action(to=["bad@spam.com"])
        result = guardrail_gmail_send(action, _live_tool_spec(), config=config)
        self.assertFalse(result["ok"])
        check = next(c for c in result["checks"] if c["name"] == "no_blocked_domains")
        self.assertFalse(check["ok"])

    def test_non_blocked_domain_passes(self):
        config = {"gmail_send": {"blocked_recipient_domains": ["spam.com"]}}
        action = _base_action(to=["good@example.com"])
        result = guardrail_gmail_send(action, _live_tool_spec(), config=config)
        checks_by_name = {c["name"]: c for c in result["checks"]}
        if "no_blocked_domains" in checks_by_name:
            self.assertTrue(checks_by_name["no_blocked_domains"]["ok"])

    def test_allowlist_enforced(self):
        config = {"gmail_send": {"allowed_recipient_domains": ["trusted.com"]}}
        action = _base_action(to=["user@untrusted.com"])
        result = guardrail_gmail_send(action, _live_tool_spec(), config=config)
        self.assertFalse(result["ok"])
        check = next(c for c in result["checks"] if c["name"] == "recipient_domain_allowlist")
        self.assertFalse(check["ok"])

    def test_allowlist_passes_for_approved_domain(self):
        config = {"gmail_send": {"allowed_recipient_domains": ["trusted.com"]}}
        action = _base_action(to=["user@trusted.com"])
        result = guardrail_gmail_send(action, _live_tool_spec(), config=config)
        checks_by_name = {c["name"]: c for c in result["checks"]}
        if "recipient_domain_allowlist" in checks_by_name:
            self.assertTrue(checks_by_name["recipient_domain_allowlist"]["ok"])

    def test_no_domain_checks_when_lists_empty(self):
        result = guardrail_gmail_send(_base_action(), _live_tool_spec())
        check_names = {c["name"] for c in result["checks"]}
        self.assertNotIn("no_blocked_domains", check_names)
        self.assertNotIn("recipient_domain_allowlist", check_names)


class TestGuardrailRecipientLimits(unittest.TestCase):
    def test_too_many_recipients_fails(self):
        config = {"gmail_send": {"max_recipients": 2}}
        action = _base_action(to=["a@b.com", "c@b.com", "d@b.com"])
        result = guardrail_gmail_send(action, _live_tool_spec(), config=config)
        self.assertFalse(result["ok"])
        check = next(c for c in result["checks"] if c["name"] == "max_recipients")
        self.assertFalse(check["ok"])

    def test_exactly_max_recipients_passes(self):
        config = {"gmail_send": {"max_recipients": 2}}
        action = _base_action(to=["a@b.com", "c@b.com"])
        result = guardrail_gmail_send(action, _live_tool_spec(), config=config)
        check = next(c for c in result["checks"] if c["name"] == "max_recipients")
        self.assertTrue(check["ok"])


class TestGuardrailAttachments(unittest.TestCase):
    def test_attachments_blocked_by_default(self):
        action = _base_action()
        action["payload"]["attachments"] = ["file.pdf"]
        result = guardrail_gmail_send(action, _live_tool_spec())
        self.assertFalse(result["ok"])
        check = next(c for c in result["checks"] if c["name"] == "attachments_allowed")
        self.assertFalse(check["ok"])

    def test_attachments_allowed_when_config_permits(self):
        config = {"gmail_send": {"allow_attachments": True}}
        action = _base_action()
        action["payload"]["attachments"] = ["file.pdf"]
        result = guardrail_gmail_send(action, _live_tool_spec(), config=config)
        check = next(c for c in result["checks"] if c["name"] == "attachments_allowed")
        self.assertTrue(check["ok"])

    def test_no_attachments_always_passes(self):
        result = guardrail_gmail_send(_base_action(), _live_tool_spec())
        check = next(c for c in result["checks"] if c["name"] == "attachments_allowed")
        self.assertTrue(check["ok"])


class TestRunLiveGuardrailDispatch(unittest.TestCase):
    def test_dispatch_to_gmail_send(self):
        action = _base_action()
        result = run_live_guardrail("gmail_send", action, _live_tool_spec())
        self.assertEqual(result["guardrail"], "gmail_send")

    def test_dispatch_unknown_returns_blocked(self):
        action = _base_action()
        result = run_live_guardrail("unknown_guardrail", action, _live_tool_spec())
        self.assertFalse(result["ok"])

    def test_gmail_send_error_field_when_failed(self):
        action = _base_action(status="PENDING_APPROVAL")
        result = guardrail_gmail_send(action, _live_tool_spec())
        self.assertFalse(result["ok"])
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
