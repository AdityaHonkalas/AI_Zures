"""
Tests for Agent 5 — Test Scenario Generator.

Asserts Gherkin output contains required BDD keywords and Playwright stub is valid.
"""
import pytest
from unittest.mock import patch


IMPACT_MAP_WITH_GAP = {
    "directly_impacted_modules": ["checkout"],
    "transitively_impacted_modules": [],
    "user_journeys": [
        {"journey_id": "UJ-02", "name": "Checkout Flow",        "impacted_modules": ["checkout"]},
        {"journey_id": "UJ-03", "name": "Guest Checkout Flow",   "impacted_modules": ["checkout"]},
    ],
    "browser_env_matrix": [{"browser": "chrome", "env": "staging"}],
}

# Suite covers UJ-02 but NOT UJ-03 → gap for UJ-03
SUITE_WITH_GAP = {
    "suite": [
        {
            "test_id": "TC-003", "test_name": "Checkout with valid credit card",
            "module": "checkout", "journey_id": "UJ-02",
            "browser": "chrome", "environment": "staging",
            "priority": 1, "estimated_duration_s": 60, "risk_score": 0.88,
        }
    ],
    "total_estimated_duration_s": 60,
    "coverage_gaps": [],
    "budget_limit_s": 1800,
}

SUITE_NO_GAP = {
    "suite": [
        {
            "test_id": "TC-003", "test_name": "Checkout with valid credit card",
            "module": "checkout", "journey_id": "UJ-02",
            "browser": "chrome", "environment": "staging",
            "priority": 1, "estimated_duration_s": 60, "risk_score": 0.88,
        },
        {
            "test_id": "TC-019", "test_name": "Checkout flow on mobile viewport",
            "module": "checkout", "journey_id": "UJ-03",
            "browser": "chrome", "environment": "staging",
            "priority": 2, "estimated_duration_s": 70, "risk_score": 0.65,
        }
    ],
    "total_estimated_duration_s": 130,
    "coverage_gaps": [],
    "budget_limit_s": 1800,
}


def _make_context(suite=None) -> dict:
    return {
        "pr_url": "https://github.com/org/repo/pull/1",
        "pr_metadata": {},
        "diff_raw": "",
        "change_context": {},
        "impact_map": IMPACT_MAP_WITH_GAP,
        "risk_ranked_tests": {},
        "recommended_suite": suite or SUITE_WITH_GAP,
        "generated_scenarios": {},
        "errors": [],
    }


SAMPLE_GHERKIN = """Feature: Guest Checkout Flow

  Scenario: Guest user completes checkout
    Given the user is not logged in
    When the user adds a product to the cart
    And proceeds to guest checkout
    Then the order is placed successfully
    And a confirmation email is sent"""

SAMPLE_PLAYWRIGHT = """import { test, expect } from '@playwright/test';

test('Guest Checkout Flow - Guest user completes checkout', async ({ page }) => {
  // TODO: navigate to product page
  // TODO: click add to cart
  // TODO: proceed as guest
  // TODO: assert order confirmation
});"""


@patch("app.agents.scenario_generator._scaffold_playwright", return_value=SAMPLE_PLAYWRIGHT)
@patch("app.agents.scenario_generator._write_gherkin", return_value=SAMPLE_GHERKIN)
@patch("app.agents.scenario_generator._interpret_user_story",
       return_value={"acceptance_criteria": ["Guest can checkout"], "edge_cases": []})
@patch("app.agents.scenario_generator._save_generated_files", return_value="features/uj_03.feature")
def test_run_detects_coverage_gap(mock_save, mock_interp, mock_gherkin, mock_playwright):
    """Agent 5 should detect UJ-03 as a coverage gap when not in the suite."""
    from app.agents import scenario_generator
    ctx = scenario_generator.run(_make_context(SUITE_WITH_GAP))

    assert "generated_scenarios" in ctx
    gs = ctx["generated_scenarios"]
    assert "UJ-03" in gs["coverage_gaps"]
    assert len(gs["scenarios"]) == 1


@patch("app.agents.scenario_generator.llm_client.chat")
@patch("app.agents.scenario_generator._save_generated_files")
def test_no_scenarios_when_no_gaps(mock_save, mock_chat):
    """When all journeys are covered, no scenarios should be generated."""
    from app.agents import scenario_generator
    ctx = scenario_generator.run(_make_context(SUITE_NO_GAP))

    assert ctx["generated_scenarios"]["scenarios"] == []
    assert ctx["generated_scenarios"]["coverage_gaps"] == []
    mock_chat.assert_not_called()


@patch("app.agents.scenario_generator._scaffold_playwright", return_value=SAMPLE_PLAYWRIGHT)
@patch("app.agents.scenario_generator._write_gherkin", return_value=SAMPLE_GHERKIN)
@patch("app.agents.scenario_generator._interpret_user_story",
       return_value={"acceptance_criteria": ["User can checkout as guest"], "edge_cases": []})
@patch("app.agents.scenario_generator._save_generated_files", return_value="features/uj_03.feature")
def test_gherkin_contains_required_keywords(mock_save, mock_interp, mock_gherkin, mock_playwright):
    """Generated Gherkin must contain Feature, Scenario, Given, When, Then keywords."""
    from app.agents import scenario_generator
    ctx = scenario_generator.run(_make_context(SUITE_WITH_GAP))

    gherkin = ctx["generated_scenarios"]["scenarios"][0]["gherkin"]
    for keyword in ("Feature:", "Scenario:", "Given", "When", "Then"):
        assert keyword in gherkin, f"Missing Gherkin keyword: '{keyword}'"


@patch("app.agents.scenario_generator._scaffold_playwright", return_value=SAMPLE_PLAYWRIGHT)
@patch("app.agents.scenario_generator._write_gherkin", return_value=SAMPLE_GHERKIN)
@patch("app.agents.scenario_generator._interpret_user_story",
       return_value={"acceptance_criteria": [], "edge_cases": []})
@patch("app.agents.scenario_generator._save_generated_files", return_value="features/uj_03.feature")
def test_scenario_output_fields(mock_save, mock_interp, mock_gherkin, mock_playwright):
    """Each generated scenario must have journey_id, gherkin, playwright_stub, and feature_file."""
    from app.agents import scenario_generator
    ctx = scenario_generator.run(_make_context(SUITE_WITH_GAP))

    required = {"journey_id", "gherkin", "playwright_stub", "feature_file"}
    for scenario in ctx["generated_scenarios"]["scenarios"]:
        assert required.issubset(scenario.keys()), f"Missing keys in scenario: {scenario.keys()}"


@patch("app.agents.scenario_generator.llm_client.chat", side_effect=Exception("LLM down"))
@patch("app.agents.scenario_generator._save_generated_files", return_value="features/uj_03.feature")
def test_fallback_gherkin_on_llm_failure(mock_save, mock_chat):
    """When LLM fails, fallback Gherkin should still be returned with Feature: keyword."""
    from app.agents import scenario_generator
    ctx = scenario_generator.run(_make_context(SUITE_WITH_GAP))

    gherkin = ctx["generated_scenarios"]["scenarios"][0]["gherkin"]
    assert "Feature:" in gherkin
