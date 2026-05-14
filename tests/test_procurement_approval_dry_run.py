import tempfile

from runtime.procurement_tools import supplier_send_message
from src.operator_approval_actions import approve_pending_action, execute_approved_pending_actions_dry_run
from src.operator_scenario_runner import run_scenario
from runtime.taskframe_reload import load_taskframe


def _run_procurement(runtime_data_dir: str):
    return run_scenario("procurement_low_stock_happy_path", runtime_data_dir=runtime_data_dir, reset_dataset=True)


def test_procurement_pending_action_can_be_approved():
    with tempfile.TemporaryDirectory() as tmp:
        result = _run_procurement(tmp)
        frame_id = result["frame_id"]
        frame = load_taskframe(frame_id, tmp)
        action_id = frame.pending_actions[0]["action_id"]
        approve_result = approve_pending_action(frame_id, action_id, approved_by="pytest", reason="approve", runtime_data_dir=tmp)
        assert approve_result["ok"] is True


def test_procurement_approved_action_executes_dry_run():
    with tempfile.TemporaryDirectory() as tmp:
        result = _run_procurement(tmp)
        frame_id = result["frame_id"]
        frame = load_taskframe(frame_id, tmp)
        action_id = frame.pending_actions[0]["action_id"]
        approve_pending_action(frame_id, action_id, approved_by="pytest", reason="approve", runtime_data_dir=tmp)
        execute_result = execute_approved_pending_actions_dry_run(frame_id, runtime_data_dir=tmp)
        assert execute_result["ok"] is True


def test_procurement_approve_execute_reaches_completed():
    with tempfile.TemporaryDirectory() as tmp:
        result = _run_procurement(tmp)
        frame_id = result["frame_id"]
        frame = load_taskframe(frame_id, tmp)
        action_id = frame.pending_actions[0]["action_id"]
        approve_pending_action(frame_id, action_id, approved_by="pytest", reason="approve", runtime_data_dir=tmp)
        execute_approved_pending_actions_dry_run(frame_id, runtime_data_dir=tmp)
        final_frame = load_taskframe(frame_id, tmp)
        assert final_frame.state == "COMPLETED"


def test_procurement_dry_run_execution_records_executed_action():
    with tempfile.TemporaryDirectory() as tmp:
        result = _run_procurement(tmp)
        frame_id = result["frame_id"]
        frame = load_taskframe(frame_id, tmp)
        action_id = frame.pending_actions[0]["action_id"]
        approve_pending_action(frame_id, action_id, approved_by="pytest", reason="approve", runtime_data_dir=tmp)
        execute_approved_pending_actions_dry_run(frame_id, runtime_data_dir=tmp)
        final_frame = load_taskframe(frame_id, tmp)
        assert len(final_frame.executed_actions) == 1
        assert final_frame.executed_actions[0]["tool"] == "supplier/send_message"
        assert final_frame.executed_actions[0]["dry_run"] is True
        assert final_frame.outputs["supplier_message_send"]["dry_run"] is True
        assert final_frame.outputs["supplier_message_send"]["sent"] is False


def test_procurement_dry_run_does_not_live_send():
    with tempfile.TemporaryDirectory() as tmp:
        result = _run_procurement(tmp)
        frame = load_taskframe(result["frame_id"], tmp)
        action = frame.pending_actions[0]
        assert action["tool"] == "supplier/send_message"
        assert action["status"] == "PENDING_APPROVAL"


def test_supplier_send_tool_blocks_live_mode():
    result = supplier_send_message("orders@capetech.example", "Purchase Order PO-DRAFT-TEST", "body", {"po_id": "PO-DRAFT-TEST"}, dry_run=False)
    assert result["ok"] is False
    assert result["sent"] is False
    assert "Live supplier send is not supported" in result["error"]
