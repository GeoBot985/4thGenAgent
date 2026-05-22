from __future__ import annotations

from tests.marker_rules import markers_for_path


def pytest_collection_modifyitems(config, items):
    for item in items:
        for marker_name in markers_for_path(item.path):
            item.add_marker(marker_name)
