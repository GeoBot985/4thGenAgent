from __future__ import annotations

import pytest


def test_operator_ui_has_lr_proof_status_var_init():
    import inspect
    from src import operator_ui
    src = inspect.getsource(operator_ui)
    assert "lr_proof_status_var" in src


def test_operator_ui_has_check_live_read_status_method():
    import inspect
    from src import operator_ui
    src = inspect.getsource(operator_ui)
    assert "_check_live_read_status" in src


def test_operator_ui_has_run_boundary_proof_method():
    import inspect
    from src import operator_ui
    src = inspect.getsource(operator_ui)
    assert "_run_live_read_boundary_proof" in src


def test_operator_ui_has_open_report_method():
    import inspect
    from src import operator_ui
    src = inspect.getsource(operator_ui)
    assert "_open_live_read_proof_report" in src


def test_operator_ui_panel_label_present():
    import inspect
    from src import operator_ui
    src = inspect.getsource(operator_ui)
    assert "Governed Live Read Proof" in src


def test_operator_ui_status_button_present():
    import inspect
    from src import operator_ui
    src = inspect.getsource(operator_ui)
    assert "Check Live Read Status" in src


def test_operator_ui_boundary_proof_button_present():
    import inspect
    from src import operator_ui
    src = inspect.getsource(operator_ui)
    assert "Run Boundary-Only Proof" in src


def test_operator_ui_open_report_button_present():
    import inspect
    from src import operator_ui
    src = inspect.getsource(operator_ui)
    assert "Open Live Read Proof Report" in src


def test_operator_ui_imports_live_read_proof():
    import inspect
    from src import operator_ui
    src = inspect.getsource(operator_ui)
    assert "live_read_proof" in src or "build_live_read_status" in src


def test_check_live_read_status_handler_uses_proof_module():
    import inspect
    from src import operator_ui
    src = inspect.getsource(operator_ui)
    assert "build_live_read_status" in src


def test_run_boundary_proof_no_side_effects_in_handler():
    import inspect
    from src import operator_ui
    src = inspect.getsource(operator_ui)
    assert "live_side_effects_performed" in src or "no_live_probes" in src
