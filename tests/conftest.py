from __future__ import annotations

import pytest

from tests.marker_rules import markers_for_path


def pytest_collection_modifyitems(config, items):
    for item in items:
        for marker_name in markers_for_path(item.path):
            item.add_marker(marker_name)


@pytest.fixture(autouse=True)
def _backend_auth_test_tokens(monkeypatch):
    monkeypatch.setenv("TASKFRAME_BACKEND_AUTH_ENABLED", "true")
    monkeypatch.setenv("TASKFRAME_BACKEND_ALLOW_DEV_BYPASS", "false")
    monkeypatch.setenv("TASKFRAME_BACKEND_ADMIN_TOKEN", "test-admin-token")
    monkeypatch.setenv("TASKFRAME_BACKEND_OPERATOR_TOKEN", "test-operator-token")
    monkeypatch.setenv("TASKFRAME_BACKEND_VIEWER_TOKEN", "test-viewer-token")
