"""
Utility for loading static JSON fixture files from the data/ directory.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

_DATA_DIR = Path(__file__).parent.parent.parent / "data"

_FIXTURE_FILES = {
    "dependency_graph": "dependency_graph.json",
    "test_cases":       "test_cases.json",
    "defect_history":   "defect_history.json",
    "telemetry":        "telemetry.json",
    "browser_matrix":   "browser_matrix.json",
    "user_stories":     "user_stories.json",
}


@lru_cache(maxsize=None)
def load_fixture(name: str):
    """
    Load and return the contents of a fixture file by logical name.

    Args:
        name: one of 'dependency_graph', 'test_cases', 'defect_history',
              'telemetry', 'browser_matrix', 'user_stories'

    Returns:
        Parsed JSON content (list or dict depending on the fixture).
    """
    if name not in _FIXTURE_FILES:
        raise ValueError(
            f"Unknown fixture '{name}'. Available: {list(_FIXTURE_FILES.keys())}"
        )
    path = _DATA_DIR / _FIXTURE_FILES[name]
    if not path.exists():
        raise FileNotFoundError(f"Fixture file not found: {path}")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_fixture_as_dict(name: str, key_field: str) -> dict:
    """
    Load a list fixture and convert it to a dict keyed by `key_field`.
    Useful for O(1) lookup by module name, test_id, etc.
    """
    items = load_fixture(name)
    return {item[key_field]: item for item in items}
