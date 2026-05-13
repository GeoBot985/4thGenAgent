from __future__ import annotations

from src.demo_story_presenter import build_demo_story


def _customer_status_snapshot() -> dict:
    return {
        "active_event": {
            "payload": {
                "customer_name": "Alex",
                "message": "Where is my order ORD-10042?",
            }
        },
        "active_frame": {
            "state": "WAITING_FOR_EXECUTE",
            "inputs": {
                "customer_name": "Alex",
                "message": "Where is my order ORD-10042?",
            },
            "outputs": {
                "order_id": "ORD-10042",
                "customer": {"name": "Alex"},
                "order": {"status": "shipped"},
                "shipment": {
                    "status": "shipped",
                    "tracking_reference": "TRK-778899",
                    "estimated_delivery_date": "2026-05-03",
                },
                "draft_reply": {
                    "body": "Hi Alex, your order ORD-10042 has shipped and is currently in transit.\nTracking reference: TRK-778899.",
                },
            },
            "validations": [{"step_id": "validate_customer_owns_order", "ok": True}],
            "steps": [
                {"step_id": "extract_order_ref", "ok": True},
                {"step_id": "lookup_order", "ok": True},
                {"step_id": "draft_reply", "ok": True},
                {"step_id": "custom_follow_up", "ok": True},
            ],
            "pending_actions": [{"action_id": "approve_reply", "status": "READY"}],
        },
    }


def _failed_customer_snapshot() -> dict:
    return {
        "active_event": {
            "payload": {
                "customer_name": "Taylor",
                "message": "Where is my order ORD-99999?",
            }
        },
        "active_frame": {
            "state": "FAILED_VALIDATION",
            "inputs": {
                "customer_name": "Taylor",
                "message": "Where is my order ORD-99999?",
            },
            "outputs": {},
            "validations": [{"step_id": "validate_customer_owns_order", "ok": False, "message": "Customer does not own the order."}],
            "steps": [{"step_id": "validate_customer_owns_order", "ok": False}],
            "pending_actions": [],
        },
    }


def _report_snapshot() -> dict:
    return {
        "active_event": {
            "payload": {
                "customer_name": "Alex",
                "message": "Where is my order ORD-10042?",
            }
        },
        "active_frame": {
            "state": "WAITING_FOR_EXECUTE",
            "scenario_id": "report_generation_happy_path",
            "manifest_id": "report_generation_happy_path",
            "inputs": {
                "customer_name": "Alex",
                "message": "Where is my order ORD-10042?",
            },
            "outputs": {
                "report_artifact": "reports/report_generation_happy_path.md",
                "summary": "Business report generated successfully.",
                "evidence_bundle_path": "evidence/report_generation_happy_path.zip",
                "customer_name": "Alex",
                "order_id": "ORD-10042",
            },
            "steps": [
                {"step_id": "read_business_data", "ok": True},
                {"step_id": "check_source_records", "ok": True},
                {"step_id": "build_report_summary", "ok": True},
                {"step_id": "generate_report", "ok": True},
                {"step_id": "prepare_evidence_pack", "ok": True},
            ],
            "pending_actions": [],
        },
    }


def _report_selected_scenario() -> dict:
    return {
        "id": "report_generation_happy_path",
        "label": "Report Generation - Happy Path Report",
        "category": "reporting",
        "description": "Runs happy path and generates markdown/html/evidence bundle.",
    }


def _report_run_result() -> dict:
    return {
        "ok": True,
        "markdown_path": "runtime_data/outputs/reports/report_generation_happy_path_frame_1_run_report.md",
        "html_path": "runtime_data/outputs/reports/report_generation_happy_path_frame_1_run_report.html",
        "evidence_bundle_path": "runtime_data/outputs/evidence/frame_1_evidence_bundle.json",
        "business_report_markdown_path": "runtime_data/outputs/reports/report_generation_happy_path_frame_1.md",
        "business_report_html_path": "runtime_data/outputs/reports/report_generation_happy_path_frame_1.html",
        "business_report_evidence_bundle_path": "runtime_data/outputs/evidence/frame_1_evidence_bundle.json",
        "run_report_markdown_path": "runtime_data/outputs/reports/frame_1_run_report.md",
        "run_report_html_path": "runtime_data/outputs/reports/frame_1_run_report.html",
        "run_report_evidence_bundle_path": "runtime_data/outputs/evidence/frame_1_evidence_bundle.json",
    }


def _customer_selected_scenario() -> dict:
    return {
        "id": "customer_status_happy_path",
        "label": "Customer Status - Happy Path",
        "category": "customer_support",
        "description": "A customer asks where their order is.",
    }


def test_report_generation_scenario_does_not_show_customer_request():
    story = build_demo_story(_report_snapshot(), {"state": "WAITING_FOR_EXECUTE", "snapshot": _report_snapshot(), "scenario_id": "report_generation_happy_path"}, _report_selected_scenario())

    assert story["story_type"] == "report_generation"
    assert story["request_title"] == "Report request"
    assert story["request_text"].startswith("Report: Report Generation - Happy Path Report")
    assert "Customer:" not in story["request_text"]
    assert "Order:" not in story["request_text"]


def test_report_generation_scenario_does_not_show_prepared_customer_reply():
    story = build_demo_story(_report_snapshot(), {"state": "WAITING_FOR_EXECUTE", "snapshot": _report_snapshot(), "scenario_id": "report_generation_happy_path"}, _report_selected_scenario())

    assert story["show_prepared_reply"] is False
    assert story["draft_reply"] == ""
    assert story["outcome_title"] == "No business report artifact was found for this run."
    assert "Prepared customer reply" not in story["outcome_title"]


def test_report_generation_scenario_uses_report_labels():
    story = build_demo_story(_report_snapshot(), {"state": "WAITING_FOR_EXECUTE", "snapshot": _report_snapshot(), "scenario_id": "report_generation_happy_path", "report_result": _report_run_result()}, _report_selected_scenario())

    assert story["headline"] == "Report generated successfully"
    assert story["worker_title"] == "What the worker checked"
    assert story["outcome_title"] == "Business report generated"
    assert story["decision_title"] == "Report actions"
    assert story["decision_text"] == "Open the business report or run report. The worker prepared audit evidence for review."
    assert "Business report generated" in story["outcome_text"]
    assert "Run report generated" in story["outcome_text"]
    assert story["business_report_html_path"].endswith("report_generation_happy_path_frame_1.html")
    assert story["run_report_html_path"].endswith("frame_1_run_report.html")


def test_report_generation_scenario_hides_approval_reply_actions():
    story = build_demo_story(_report_snapshot(), {"state": "WAITING_FOR_EXECUTE", "snapshot": _report_snapshot(), "scenario_id": "report_generation_happy_path", "report_result": _report_run_result()}, _report_selected_scenario())

    assert story["show_approval_actions"] is False
    assert story["can_approve"] is False
    assert story["can_reject"] is False
    assert "Approve this prepared reply?" not in story["decision_text"]


def test_selected_report_scenario_does_not_reuse_stale_customer_frame():
    stale_customer_run = {
        "state": "WAITING_FOR_EXECUTE",
        "scenario_id": "customer_status_happy_path",
        "snapshot": _customer_status_snapshot(),
    }
    story = build_demo_story(_customer_status_snapshot(), stale_customer_run, _report_selected_scenario())

    assert story["headline"] == "Selected demo is waiting to run."
    assert story["subheadline"] == "Click Start demo to generate this report."
    assert story["request_text"] == "Selected demo is waiting to run.\nClick Start demo to generate this report."
    assert "Alex" not in story["request_text"]
    assert "ORD-10042" not in story["request_text"]
    assert story["outcome_text"] == "No business report artifact was found for this run."
    assert story["show_prepared_reply"] is False


def test_customer_status_scenario_still_shows_customer_reply_when_valid():
    story = build_demo_story(_customer_status_snapshot(), {"state": "WAITING_FOR_EXECUTE", "snapshot": _customer_status_snapshot(), "scenario_id": "customer_status_happy_path"}, _customer_selected_scenario())

    assert story["story_type"] == "customer_status"
    assert story["request_title"] == "Customer request"
    assert story["show_prepared_reply"] is True
    assert story["show_approval_actions"] is True
    assert story["outcome_title"] == "Prepared customer reply"
    assert story["draft_reply"].startswith("Hi Alex, your order ORD-10042 has shipped")
    assert story["can_approve"] is True


def test_selected_scenario_placeholder_does_not_show_previous_run():
    story = build_demo_story(_customer_status_snapshot(), None, {"label": "Customer Status - Missing Customer", "description": "Missing-customer demo"})

    assert story["mode"] == "idle"
    assert story["headline"] == "Selected demo: Customer Status - Missing Customer"
    assert story["subheadline"] == "Missing-customer demo Click Start demo to run this scenario."
    assert story["customer"] == ""
    assert story["order"] == ""
    assert story["message"] == ""
    assert story["show_prepared_reply"] is False
    assert story["show_approval_actions"] is False


def test_missing_customer_scenario_does_not_show_happy_path_customer():
    story = build_demo_story(_customer_status_snapshot(), None, {"label": "Customer Status - Missing Customer"})

    assert story["customer"] == ""
    assert story["order"] == ""
    assert story["message"] == ""


def test_failed_scenario_uses_validation_failed_headline():
    story = build_demo_story(_failed_customer_snapshot(), {"state": "FAILED_VALIDATION", "snapshot": _failed_customer_snapshot(), "scenario_id": "customer_status_missing_customer"}, {"id": "customer_status_missing_customer", "label": "Customer Status - Missing Customer", "category": "customer_support"})

    assert story["mode"] == "failed_validation"
    assert story["headline"] == "Worker stopped — validation failed"
    assert story["subheadline"] == "No customer message was prepared or sent."
    assert story["decision_title"] == "No approval needed."
    assert story["decision_text"] == "The worker stopped before preparing a customer reply."


def test_failed_scenario_does_not_show_prepared_reply():
    story = build_demo_story(_failed_customer_snapshot(), {"state": "FAILED_VALIDATION", "snapshot": _failed_customer_snapshot(), "scenario_id": "customer_status_missing_customer"}, {"id": "customer_status_missing_customer", "label": "Customer Status - Missing Customer", "category": "customer_support"})

    assert story["show_prepared_reply"] is False
    assert story["draft_reply"] == ""
    assert "Prepared reply" not in story["outcome_text"]
    assert "No reply was prepared." in story["outcome_text"]
    assert "No message was sent." in story["outcome_text"]


def test_failed_scenario_does_not_show_facts_checked_order_exists():
    story = build_demo_story(_failed_customer_snapshot(), {"state": "FAILED_VALIDATION", "snapshot": _failed_customer_snapshot(), "scenario_id": "customer_status_missing_customer"}, {"id": "customer_status_missing_customer", "label": "Customer Status - Missing Customer", "category": "customer_support"})

    assert story["facts"] == []
    assert "Facts confirmed" not in story["outcome_text"]
    assert "Order exists" not in story["outcome_text"]


def test_failed_scenario_hides_approval_actions():
    story = build_demo_story(_failed_customer_snapshot(), {"state": "FAILED_VALIDATION", "snapshot": _failed_customer_snapshot(), "scenario_id": "customer_status_missing_customer"}, {"id": "customer_status_missing_customer", "label": "Customer Status - Missing Customer", "category": "customer_support"})

    assert story["show_approval_actions"] is False
    assert story["can_approve"] is False
    assert story["can_reject"] is False
    assert story["can_create_audit_pack"] is True
    assert story["can_open_audit_pack"] is False


def test_failed_step_label_does_not_say_found_when_failed():
    story = build_demo_story(_failed_customer_snapshot(), {"state": "FAILED_VALIDATION", "snapshot": _failed_customer_snapshot(), "scenario_id": "customer_status_missing_customer"}, {"id": "customer_status_missing_customer", "label": "Customer Status - Missing Customer", "category": "customer_support"})

    labels = [step["label"] for step in story["worker_steps"]]
    assert any("Could not confirm the customer record" in label for label in labels)
    assert any("Stopped before checking shipment and payment" in label for label in labels)
    assert all("Found the customer record" not in label for label in labels)


def test_pending_approval_scenario_shows_prepared_reply_and_approval_actions():
    story = build_demo_story(_customer_status_snapshot(), {"state": "WAITING_FOR_EXECUTE", "snapshot": _customer_status_snapshot(), "scenario_id": "customer_status_happy_path"}, _customer_selected_scenario())

    assert story["mode"] == "success_pending_approval"
    assert story["show_prepared_reply"] is True
    assert story["show_approval_actions"] is True
    assert story["outcome_title"] == "Prepared customer reply"


def test_customer_status_scenario_uses_customer_story_cards():
    story = build_demo_story(_customer_status_snapshot(), {"state": "WAITING_FOR_EXECUTE", "snapshot": _customer_status_snapshot(), "scenario_id": "customer_status_happy_path"}, _customer_selected_scenario())

    assert [card["kind"] for card in story["cards"][:4]] == ["request", "steps", "outcome", "decision"]
    assert story["cards"][0]["title"] == "Customer request"
    assert story["cards"][1]["title"] == "What the worker checked"
    assert story["cards"][2]["title"] == "Prepared customer reply"
    assert story["actions"]["show_approve"] is True
    assert story["actions"]["show_reject"] is True
    assert story["business_report"]["exists"] is False


def test_report_generation_scenario_uses_report_story_cards():
    story = build_demo_story(_report_snapshot(), {"state": "WAITING_FOR_EXECUTE", "snapshot": _report_snapshot(), "scenario_id": "report_generation_happy_path", "report_result": _report_run_result()}, _report_selected_scenario())

    assert [card["kind"] for card in story["cards"][:5]] == ["request", "steps", "outcome", "decision", "report"]
    assert story["cards"][0]["title"] == "Report request"
    assert story["cards"][2]["title"] == "Business report generated"
    assert story["cards"][4]["title"] == "Report details"
    assert story["actions"]["show_open_business_report"] is True
    assert story["actions"]["show_create_open_run_report"] is True
    assert story["business_report"]["exists"] is True
    assert story["run_report"]["exists"] is True


def test_report_generation_does_not_show_customer_reply_wording():
    story = build_demo_story(_report_snapshot(), {"state": "WAITING_FOR_EXECUTE", "snapshot": _report_snapshot(), "scenario_id": "report_generation_happy_path", "report_result": _report_run_result()}, _report_selected_scenario())

    combined = "\n".join(
        [
            story["headline"],
            story["subheadline"],
            story["cards"][0]["body"],
            story["cards"][2]["body"],
            "\n".join(story["cards"][4]["items"]),
        ]
    )
    assert "Prepared customer reply" not in combined
    assert "Approve this prepared reply?" not in combined
    assert "No live customer message will be sent" not in combined


def test_demo_story_does_not_claim_business_report_exists_without_path():
    story = build_demo_story(_report_snapshot(), {"state": "WAITING_FOR_EXECUTE", "snapshot": _report_snapshot(), "scenario_id": "report_generation_happy_path"}, _report_selected_scenario())

    assert story["business_report"]["exists"] is False
    assert story["business_report"]["html_path"] == ""
    assert "Business report generated" not in "\n".join(story["cards"][4]["items"])


def test_demo_story_exposes_business_report_paths_when_present():
    story = build_demo_story(_report_snapshot(), {"state": "WAITING_FOR_EXECUTE", "snapshot": _report_snapshot(), "scenario_id": "report_generation_happy_path", "report_result": _report_run_result()}, _report_selected_scenario())

    assert story["business_report"]["exists"] is True
    assert story["business_report"]["html_path"].endswith("report_generation_happy_path_frame_1.html")
    assert story["business_report"]["markdown_path"].endswith("report_generation_happy_path_frame_1.md")
    assert story["business_report"]["evidence_path"].endswith("frame_1_evidence_bundle.json")
    assert story["run_report"]["html_path"].endswith("frame_1_run_report.html")
    assert story["draft_reply"] == ""
    assert story["facts"] == [
        "Report summary prepared",
        "Business report generated",
        "Evidence pack prepared",
    ]
    assert story["actions"]["show_open_business_report"] is True
    assert story["actions"]["show_create_open_run_report"] is True

