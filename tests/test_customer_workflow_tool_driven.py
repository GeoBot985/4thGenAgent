from src.operator_scenario_runner import run_scenario


def test_customer_status_happy_path_still_reaches_waiting_for_execute():
    result = run_scenario("customer_status_happy_path", runtime_data_dir="runtime_data", reset_dataset=True)
    assert result["state"] == "WAITING_FOR_EXECUTE"
    assert result["snapshot"]["pending_actions"]
    assert len(result["snapshot"]["pending_actions"]) == 1
    assert len(result["snapshot"]["executed_actions"]) == 0


def test_customer_status_happy_path_uses_registered_tools():
    result = run_scenario("customer_status_happy_path", runtime_data_dir="runtime_data", reset_dataset=True)
    tools = [call.get("tool") for call in result["snapshot"]["tool_calls"]]
    assert "customer/read" in tools
    assert "order/read" in tools
    assert "shipment/read" in tools
    assert "customer/prepare_message_action" in tools


def test_customer_status_happy_path_records_llm_calls():
    result = run_scenario("customer_status_happy_path", runtime_data_dir="runtime_data", reset_dataset=True)
    llm_actions = [call.get("action") for call in result["snapshot"]["llm_calls"]]
    assert "extract_order_ref" in llm_actions
    assert "classify_customer_message" in llm_actions
    assert "draft_customer_status_reply" in llm_actions


def test_customer_status_happy_path_stages_pending_action():
    result = run_scenario("customer_status_happy_path", runtime_data_dir="runtime_data", reset_dataset=True)
    pending = result["snapshot"]["pending_actions"][0]
    assert pending["status"] == "PENDING_APPROVAL"
    assert pending["action_type"] == "send_customer_message"
    assert pending["tool"] == "wa/send"


def test_customer_wrong_customer_order_fails_validation():
    result = run_scenario("customer_status_wrong_customer_order", runtime_data_dir="runtime_data", reset_dataset=True)
    assert result["state"].startswith("FAILED")


def test_customer_missing_order_fails_safely():
    result = run_scenario("customer_status_missing_order", runtime_data_dir="runtime_data", reset_dataset=True)
    assert result["state"].startswith("FAILED")


def test_customer_bad_llm_reply_blocks_pending_action():
    result = run_scenario("customer_status_bad_llm_reply", runtime_data_dir="runtime_data", reset_dataset=True)
    assert result["state"].startswith("FAILED")
    assert result["snapshot"]["pending_actions"] == []


def test_customer_approve_execute_dry_run_still_completes():
    result = run_scenario("customer_status_approve_execute_dry_run", runtime_data_dir="runtime_data", reset_dataset=True)
    assert result["state"] == "COMPLETED"
