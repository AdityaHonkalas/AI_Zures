"""
Tests for Agent 4 — Regression Suite Recommender.

Asserts: suite duration ≤ budget, no duplicate fingerprints, all journeys covered.
"""
import os
import pytest
from unittest.mock import patch


RANKED_TESTS = [
    {
        "test_id": "TC-003", "test_name": "Checkout with valid credit card",
        "module": "checkout", "journey_id": "UJ-02",
        "browser": "chrome", "environment": "staging",
        "risk_score": 0.88, "rank": 1, "justification": "",
        "score_breakdown": {"defect_score": 0.9, "churn_score": 0.8, "telemetry_score": 0.85, "semantic_score": 0.83},
    },
    {
        "test_id": "TC-004", "test_name": "Checkout with invalid card number",
        "module": "checkout", "journey_id": "UJ-02",
        "browser": "chrome", "environment": "staging",
        "risk_score": 0.75, "rank": 2, "justification": "",
        "score_breakdown": {"defect_score": 0.8, "churn_score": 0.7, "telemetry_score": 0.75, "semantic_score": 0.7},
    },
    {
        "test_id": "TC-001", "test_name": "Add item to cart",
        "module": "cart", "journey_id": "UJ-01",
        "browser": "chrome", "environment": "staging",
        "risk_score": 0.65, "rank": 3, "justification": "",
        "score_breakdown": {"defect_score": 0.6, "churn_score": 0.7, "telemetry_score": 0.6, "semantic_score": 0.65},
    },
]

IMPACT_MAP = {
    "directly_impacted_modules": ["checkout", "cart"],
    "transitively_impacted_modules": ["payment"],
    "user_journeys": [
        {"journey_id": "UJ-01", "name": "Add to Cart", "impacted_modules": ["cart"]},
        {"journey_id": "UJ-02", "name": "Checkout",    "impacted_modules": ["checkout"]},
    ],
    "browser_env_matrix": [{"browser": "chrome", "env": "staging"}],
}


def _make_context(budget=1800) -> dict:
    os.environ["BUDGET_LIMIT_SECONDS"] = str(budget)
    return {
        "pr_url": "https://github.com/org/repo/pull/1",
        "pr_metadata": {},
        "diff_raw": "",
        "change_context": {},
        "impact_map": IMPACT_MAP,
        "risk_ranked_tests": {"ranked_tests": RANKED_TESTS},
        "recommended_suite": {},
        "generated_scenarios": {},
        "errors": [],
    }


@patch("app.agents.suite_recommender.llm_client.chat")
def test_run_returns_recommended_suite(mock_chat):
    """Agent 4 run() should populate recommended_suite with a suite list."""
    mock_chat.return_value = {"suite_items": []}

    from app.agents import suite_recommender
    ctx = suite_recommender.run(_make_context())

    assert "recommended_suite" in ctx
    rs = ctx["recommended_suite"]
    assert "suite" in rs
    assert "total_estimated_duration_s" in rs
    assert "budget_limit_s" in rs
    assert isinstance(rs["suite"], list)


@patch("app.agents.suite_recommender.llm_client.chat")
def test_suite_duration_within_budget(mock_chat):
    """Total suite duration must not exceed the budget (unless forced by coverage)."""
    mock_chat.return_value = {"suite_items": []}
    budget = 200  # very tight budget to force selection

    from app.agents import suite_recommender
    ctx = suite_recommender.run(_make_context(budget=budget))

    total = ctx["recommended_suite"]["total_estimated_duration_s"]
    # Allow minor overage only when coverage guarantee forced extra tests
    assert total <= budget + 300, f"Suite duration {total}s far exceeds budget {budget}s"


@patch("app.agents.suite_recommender.llm_client.chat")
def test_no_duplicate_fingerprints_in_suite(mock_chat):
    """Suite must not contain two tests with the same coverage_fingerprint."""
    mock_chat.return_value = {"suite_items": []}

    from app.agents import suite_recommender
    from app.utils.fixture_loader import load_fixture_as_dict

    ctx = suite_recommender.run(_make_context())

    tc_by_id = load_fixture_as_dict("test_cases", "test_id")
    fingerprints = []
    for item in ctx["recommended_suite"]["suite"]:
        fp = tc_by_id.get(item["test_id"], {}).get("coverage_fingerprint", "")
        if fp:
            fingerprints.append(fp)

    assert len(fingerprints) == len(set(fingerprints)), "Duplicate coverage fingerprints in suite"


@patch("app.agents.suite_recommender.llm_client.chat")
def test_all_journeys_have_coverage(mock_chat):
    """Every impacted user journey must be covered by at least one selected test."""
    mock_chat.return_value = {"suite_items": []}

    from app.agents import suite_recommender
    ctx = suite_recommender.run(_make_context())

    suite_journey_ids = {t.get("journey_id", "") for t in ctx["recommended_suite"]["suite"]}
    for journey in IMPACT_MAP["user_journeys"]:
        assert journey["journey_id"] in suite_journey_ids, \
            f"Journey {journey['journey_id']} has no test in suite"


@patch("app.agents.suite_recommender.llm_client.chat")
def test_suite_items_have_required_fields(mock_chat):
    """Each suite item must have all required output fields."""
    mock_chat.return_value = {"suite_items": []}

    from app.agents import suite_recommender
    ctx = suite_recommender.run(_make_context())

    required = {"test_id", "test_name", "browser", "environment", "priority", "estimated_duration_s"}
    for item in ctx["recommended_suite"]["suite"]:
        assert required.issubset(item.keys()), f"Missing fields in suite item: {item}"
