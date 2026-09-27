"""
Tests for Agent 2 — Impact Mapper.

Uses a fixed ChangeContext fixture and asserts ImpactMap shape and consistency.
"""
import pytest
from unittest.mock import patch


FIXED_CHANGE_CONTEXT = {
    "changed_files": [
        {"file": "src/checkout/cart.py", "change_type": "modified", "added_lines": 3, "removed_lines": 0, "hunks": []}
    ],
    "changed_symbols": [],
    "impacted_modules": ["checkout", "cart"],
    "linked_user_stories": ["US-101"],
}


def _make_context(direct_modules=None) -> dict:
    cc = dict(FIXED_CHANGE_CONTEXT)
    if direct_modules is not None:
        cc = {**cc, "impacted_modules": direct_modules}
    return {
        "pr_url": "https://github.com/org/repo/pull/1",
        "pr_metadata": {},
        "diff_raw": "",
        "change_context": cc,
        "impact_map": {},
        "risk_ranked_tests": {},
        "recommended_suite": {},
        "generated_scenarios": {},
        "errors": [],
    }


@patch("app.agents.impact_mapper.llm_client.chat")
def test_run_returns_impact_map(mock_chat):
    """Agent 2 run() should populate impact_map with the required keys."""
    mock_chat.return_value = {"transitively_impacted_modules": ["payment", "notification"]}

    from app.agents import impact_mapper
    ctx = impact_mapper.run(_make_context())

    assert "impact_map" in ctx
    im = ctx["impact_map"]
    assert "directly_impacted_modules" in im
    assert "transitively_impacted_modules" in im
    assert "user_journeys" in im
    assert "browser_env_matrix" in im


@patch("app.agents.impact_mapper.llm_client.chat")
def test_directly_impacted_preserved(mock_chat):
    """directly_impacted_modules should exactly match the ChangeContext input."""
    mock_chat.return_value = {"transitively_impacted_modules": []}

    from app.agents import impact_mapper
    ctx = impact_mapper.run(_make_context(["checkout", "cart"]))

    assert set(ctx["impact_map"]["directly_impacted_modules"]) == {"checkout", "cart"}


@patch("app.agents.impact_mapper.llm_client.chat")
def test_transitive_modules_are_valid_nodes(mock_chat):
    """Transitive modules returned by LLM must be valid graph nodes."""
    mock_chat.return_value = {"transitively_impacted_modules": ["payment", "fake-module"]}

    from app.agents import impact_mapper
    ctx = impact_mapper.run(_make_context())

    known_nodes = {"checkout", "payment", "cart", "product-catalog", "user-auth",
                   "notification", "order-history", "search", "recommendations", "wishlist"}
    for m in ctx["impact_map"]["transitively_impacted_modules"]:
        assert m in known_nodes, f"Unknown transitive module: {m}"


@patch("app.agents.impact_mapper.llm_client.chat")
def test_user_journeys_have_required_fields(mock_chat):
    """Each user journey in the impact map must have journey_id, name, and impacted_modules."""
    mock_chat.return_value = {"transitively_impacted_modules": ["payment"]}

    from app.agents import impact_mapper
    ctx = impact_mapper.run(_make_context())

    for j in ctx["impact_map"]["user_journeys"]:
        assert "journey_id" in j, "Missing journey_id"
        assert "name" in j, "Missing name"
        assert "impacted_modules" in j, "Missing impacted_modules"
        assert isinstance(j["impacted_modules"], list)


@patch("app.agents.impact_mapper.llm_client.chat")
def test_browser_env_matrix_entries_have_correct_fields(mock_chat):
    """Each browser/env matrix entry must have 'browser' and 'env' fields."""
    mock_chat.return_value = {"transitively_impacted_modules": []}

    from app.agents import impact_mapper
    ctx = impact_mapper.run(_make_context())

    for entry in ctx["impact_map"]["browser_env_matrix"]:
        assert "browser" in entry
        assert "env" in entry


@patch("app.agents.impact_mapper.llm_client.chat", side_effect=Exception("LLM down"))
def test_bfs_fallback_when_llm_fails(mock_chat):
    """When LLM fails, BFS fallback should still return a list of transitive modules."""
    from app.agents import impact_mapper
    ctx = impact_mapper.run(_make_context(["checkout"]))

    assert isinstance(ctx["impact_map"]["transitively_impacted_modules"], list)


def test_empty_direct_modules_returns_empty_impact_map():
    """No directly impacted modules → empty impact map without error."""
    from app.agents import impact_mapper
    ctx = impact_mapper.run(_make_context(direct_modules=[]))

    im = ctx["impact_map"]
    assert im["directly_impacted_modules"] == []
    assert im["user_journeys"] == []
    assert im["browser_env_matrix"] == []
