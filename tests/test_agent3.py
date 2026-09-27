"""
Tests for Agent 3 — Risk Scorer & Test Prioritiser.

Uses a fixed ImpactMap and asserts score ranges and ranking correctness.
"""
import pytest
from unittest.mock import patch


FIXED_IMPACT_MAP = {
    "directly_impacted_modules":     ["checkout", "cart"],
    "transitively_impacted_modules": ["payment", "notification"],
    "user_journeys": [
        {"journey_id": "UJ-01", "name": "Add to Cart", "impacted_modules": ["cart"]},
        {"journey_id": "UJ-02", "name": "Checkout",    "impacted_modules": ["checkout", "payment"]},
    ],
    "browser_env_matrix": [
        {"browser": "chrome", "env": "staging"},
        {"browser": "edge",   "env": "staging"},
    ],
}


def _make_context() -> dict:
    return {
        "pr_url": "https://github.com/org/repo/pull/1",
        "pr_metadata": {},
        "diff_raw": "--- a/src/checkout/cart.py\n+++ b/src/checkout/cart.py\n@@ -1,1 +1,1 @@\n+# change",
        "change_context": {
            "changed_files":    [],
            "changed_symbols":  [],
            "impacted_modules": ["checkout", "cart"],
            "linked_user_stories": [],
        },
        "impact_map": FIXED_IMPACT_MAP,
        "risk_ranked_tests": {},
        "recommended_suite": {},
        "generated_scenarios": {},
        "errors": [],
    }


@patch("app.agents.risk_scorer.llm_client.chat")
@patch("app.agents.risk_scorer.llm_client.embed", return_value=[0.1] * 768)
@patch("app.agents.risk_scorer.vector_store.query", return_value=[])
def test_run_returns_ranked_tests(mock_query, mock_embed, mock_chat):
    """Agent 3 run() should populate risk_ranked_tests with ranked_tests list."""
    mock_chat.return_value = {"justifications": {}}

    from app.agents import risk_scorer
    ctx = risk_scorer.run(_make_context())

    assert "risk_ranked_tests" in ctx
    rr = ctx["risk_ranked_tests"]
    assert "ranked_tests" in rr
    assert isinstance(rr["ranked_tests"], list)
    assert len(rr["ranked_tests"]) > 0


@patch("app.agents.risk_scorer.llm_client.chat")
@patch("app.agents.risk_scorer.llm_client.embed", return_value=[0.1] * 768)
@patch("app.agents.risk_scorer.vector_store.query", return_value=[])
def test_scores_are_in_unit_range(mock_query, mock_embed, mock_chat):
    """All risk_score values must be in [0, 1]."""
    mock_chat.return_value = {"justifications": {}}

    from app.agents import risk_scorer
    ctx = risk_scorer.run(_make_context())

    for t in ctx["risk_ranked_tests"]["ranked_tests"]:
        assert 0.0 <= t["risk_score"] <= 1.0, f"Score out of range for {t['test_id']}: {t['risk_score']}"


@patch("app.agents.risk_scorer.llm_client.chat")
@patch("app.agents.risk_scorer.llm_client.embed", return_value=[0.1] * 768)
@patch("app.agents.risk_scorer.vector_store.query", return_value=[])
def test_ranked_tests_are_sorted_descending(mock_query, mock_embed, mock_chat):
    """ranked_tests must be sorted by risk_score descending."""
    mock_chat.return_value = {"justifications": {}}

    from app.agents import risk_scorer
    ctx = risk_scorer.run(_make_context())

    scores = [t["risk_score"] for t in ctx["risk_ranked_tests"]["ranked_tests"]]
    assert scores == sorted(scores, reverse=True), "Tests are not sorted by risk_score descending"


@patch("app.agents.risk_scorer.llm_client.chat")
@patch("app.agents.risk_scorer.llm_client.embed", return_value=[0.1] * 768)
@patch("app.agents.risk_scorer.vector_store.query", return_value=[])
def test_rank_field_matches_position(mock_query, mock_embed, mock_chat):
    """The rank field should equal the 1-based position in the sorted list."""
    mock_chat.return_value = {"justifications": {}}

    from app.agents import risk_scorer
    ctx = risk_scorer.run(_make_context())

    for i, t in enumerate(ctx["risk_ranked_tests"]["ranked_tests"]):
        assert t["rank"] == i + 1, f"rank mismatch at position {i}: got {t['rank']}"


@patch("app.agents.risk_scorer.llm_client.chat")
@patch("app.agents.risk_scorer.llm_client.embed", return_value=[0.1] * 768)
@patch("app.agents.risk_scorer.vector_store.query", return_value=[])
def test_score_breakdown_keys_present(mock_query, mock_embed, mock_chat):
    """Each test in ranked_tests must have all four score breakdown keys."""
    mock_chat.return_value = {"justifications": {}}

    from app.agents import risk_scorer
    ctx = risk_scorer.run(_make_context())

    required_keys = {"defect_score", "churn_score", "telemetry_score", "semantic_score"}
    for t in ctx["risk_ranked_tests"]["ranked_tests"]:
        assert required_keys.issubset(t["score_breakdown"].keys()), \
            f"Missing score_breakdown keys for {t['test_id']}"


@patch("app.agents.risk_scorer.llm_client.chat")
@patch("app.agents.risk_scorer.llm_client.embed", return_value=[0.1] * 768)
@patch("app.agents.risk_scorer.vector_store.query", return_value=[])
def test_only_tests_for_impacted_modules_included(mock_query, mock_embed, mock_chat):
    """Only tests whose module is in the impacted set should be scored."""
    mock_chat.return_value = {"justifications": {}}

    from app.agents import risk_scorer
    ctx = risk_scorer.run(_make_context())

    impacted = {"checkout", "cart", "payment", "notification"}
    for t in ctx["risk_ranked_tests"]["ranked_tests"]:
        assert t["module"] in impacted, f"Test {t['test_id']} module '{t['module']}' not in impacted set"
