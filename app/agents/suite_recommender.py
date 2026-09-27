"""
Agent 4 — Regression Suite Recommender

Sub-modules:
  4.1 Coverage Analyser    — ensures all impacted journeys have at least one test
  4.2 Budget Constraint Solver — greedy selection by risk score within time budget
  4.3 Deduplication Filter — removes redundant tests with same coverage_fingerprint
  4.4 Suite Composer       — LLM assembles final suite with per-test justification

Input:  context["risk_ranked_tests"] (RiskRankedTestList from Agent 3)
        context["impact_map"]        (ImpactMap from Agent 2)
Output: context["recommended_suite"] = RecommendedSuite dict
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from app.utils import llm_client
from app.utils.fixture_loader import load_fixture, load_fixture_as_dict

logger = logging.getLogger(__name__)

# ── 4.3 Deduplication Filter ──────────────────────────────────────────────────

def _deduplicate(ranked_tests: list[dict], test_cases_by_id: dict[str, dict]) -> list[dict]:
    """
    Group tests by coverage_fingerprint and keep only the highest-risk one per group.
    Tests without a fingerprint are kept as-is.
    """
    seen_fingerprints: dict[str, dict] = {}  # fingerprint → best test so far
    no_fingerprint: list[dict] = []

    for test in ranked_tests:
        tc_meta = test_cases_by_id.get(test["test_id"], {})
        fp = tc_meta.get("coverage_fingerprint", "")
        if not fp:
            no_fingerprint.append(test)
            continue
        if fp not in seen_fingerprints:
            seen_fingerprints[fp] = test
        else:
            # Keep the higher-risk test for this fingerprint
            if test["risk_score"] > seen_fingerprints[fp]["risk_score"]:
                seen_fingerprints[fp] = test

    deduped = list(seen_fingerprints.values()) + no_fingerprint
    deduped.sort(key=lambda x: x["risk_score"], reverse=True)
    return deduped


# ── 4.2 Budget Constraint Solver ─────────────────────────────────────────────

def _select_within_budget(
    deduped_tests: list[dict],
    test_cases_by_id: dict[str, dict],
    budget_seconds: int,
) -> tuple[list[dict], int]:
    """
    Greedy selection: add tests in risk-rank order until the budget is consumed.
    Returns (selected_tests, total_duration_seconds).
    """
    selected: list[dict] = []
    total_duration = 0

    for test in deduped_tests:
        tc_meta = test_cases_by_id.get(test["test_id"], {})
        duration = tc_meta.get("estimated_duration_s", 60)
        if total_duration + duration <= budget_seconds:
            selected.append({**test, "estimated_duration_s": duration})
            total_duration += duration

    return selected, total_duration


# ── 4.1 Coverage Analyser ────────────────────────────────────────────────────

def _ensure_journey_coverage(
    selected: list[dict],
    user_journeys: list[dict],
    ranked_tests: list[dict],
    test_cases_by_id: dict[str, dict],
) -> tuple[list[dict], list[str], int]:
    """
    Ensure every impacted user journey has at least one test in the suite.
    Force-adds the top-ranked test for any uncovered journey (may exceed budget).
    Returns (updated_selected, coverage_gaps_filled, added_duration).
    """
    selected_journey_ids = {t.get("journey_id", "") for t in selected}
    selected_test_ids    = {t["test_id"] for t in selected}
    gaps_filled: list[str] = []
    added_duration = 0

    for journey in user_journeys:
        jid = journey["journey_id"]
        if jid in selected_journey_ids:
            continue

        # Find the top-ranked test for this journey not already in suite
        for test in ranked_tests:
            if test.get("journey_id") == jid and test["test_id"] not in selected_test_ids:
                tc_meta = test_cases_by_id.get(test["test_id"], {})
                duration = tc_meta.get("estimated_duration_s", 60)
                selected.append({**test, "estimated_duration_s": duration})
                selected_test_ids.add(test["test_id"])
                gaps_filled.append(jid)
                added_duration += duration
                logger.info("Force-added TC %s for uncovered journey %s.", test["test_id"], jid)
                break

    return selected, gaps_filled, added_duration


# ── 4.4 Suite Composer ────────────────────────────────────────────────────────

_COMPOSER_SYSTEM = """You are a QA test suite optimiser.
Given a list of selected test cases with risk scores, assign each a priority (1=highest)
and write a short justification (max 15 words) explaining why it is included.
Respond ONLY with valid JSON."""

_COMPOSER_PROMPT = """The following test cases have been selected for the regression suite:

{tests_json}

For each test case:
1. Assign a priority integer (1 = run first, higher number = run later), ordered by risk_score descending.
2. Write a short justification string (max 15 words) explaining why this test is important.

Return JSON in exactly this format:
{{
  "suite_items": [
    {{
      "test_id": "TC-001",
      "priority": 1,
      "justification": "Short justification here."
    }}
  ]
}}"""


def _compose_suite(
    selected: list[dict],
    test_cases_by_id: dict[str, dict],
) -> list[dict]:
    """Use LLM to assign priorities and justifications, then merge with selected tests."""
    slim = [
        {
            "test_id":    t["test_id"],
            "test_name":  t["test_name"],
            "module":     t.get("module", ""),
            "risk_score": round(t["risk_score"], 3),
        }
        for t in selected
    ]

    try:
        result = llm_client.chat(
            prompt=_COMPOSER_PROMPT.format(tests_json=json.dumps(slim, indent=2)),
            system=_COMPOSER_SYSTEM,
            model=llm_client.REASONING_MODEL,
            expect_json=True,
        )
        items_by_id = {
            item["test_id"]: item
            for item in result.get("suite_items", [])
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM suite composition failed: %s. Using defaults.", exc)
        items_by_id = {}

    # Merge LLM output back into selected tests
    composed: list[dict] = []
    for i, test in enumerate(selected):
        tc_meta = test_cases_by_id.get(test["test_id"], {})
        llm_item = items_by_id.get(test["test_id"], {})
        composed.append({
            "test_id":    test["test_id"],
            "test_name":  test["test_name"],
            "module":     test.get("module", ""),
            "journey_id": test.get("journey_id", ""),
            "browser":    tc_meta.get("browser", test.get("browser", "chrome")),
            "environment": tc_meta.get("environment", test.get("environment", "staging")),
            "priority":   llm_item.get("priority", i + 1),
            "risk_score": round(test["risk_score"], 4),
            "estimated_duration_s": test.get("estimated_duration_s", 60),
            "justification": llm_item.get("justification", test.get("justification", "")),
        })

    return composed


# ── Main agent entry point ────────────────────────────────────────────────────

def run(context: dict[str, Any]) -> dict[str, Any]:
    """
    Run Agent 4 — Regression Suite Recommender.

    Populates context["recommended_suite"] with RecommendedSuite.
    """
    risk_ranked: dict = context.get("risk_ranked_tests", {})
    ranked_tests: list[dict] = risk_ranked.get("ranked_tests", [])
    impact_map: dict = context.get("impact_map", {})
    user_journeys: list[dict] = impact_map.get("user_journeys", [])
    budget_seconds = int(os.environ.get("BUDGET_LIMIT_SECONDS", 1800))

    if not ranked_tests:
        logger.warning("Agent 4 — no ranked tests from Agent 3; returning empty suite.")
        context["recommended_suite"] = {
            "suite": [], "total_estimated_duration_s": 0,
            "coverage_gaps": [], "budget_limit_s": budget_seconds,
        }
        return context

    logger.info("Agent 4 — Suite Recommender: selecting from %d ranked tests (budget %ds).",
                len(ranked_tests), budget_seconds)

    # Load test case metadata for duration and fingerprint lookups
    test_cases_by_id: dict[str, dict] = load_fixture_as_dict("test_cases", "test_id")

    # ── 4.3 Deduplication ────────────────────────────────────────────────────
    deduped = _deduplicate(ranked_tests, test_cases_by_id)
    logger.info("After deduplication: %d tests.", len(deduped))

    # ── 4.2 Budget selection ─────────────────────────────────────────────────
    selected, total_duration = _select_within_budget(deduped, test_cases_by_id, budget_seconds)
    logger.info("After budget selection: %d tests, %ds total.", len(selected), total_duration)

    # ── 4.1 Coverage guarantee ───────────────────────────────────────────────
    selected, gaps_filled, extra_duration = _ensure_journey_coverage(
        selected, user_journeys, ranked_tests, test_cases_by_id
    )
    total_duration += extra_duration

    # ── 4.4 Suite composition ────────────────────────────────────────────────
    suite = _compose_suite(selected, test_cases_by_id)
    suite.sort(key=lambda x: x["priority"])

    logger.info("Agent 4 complete: %d tests selected, %ds total.", len(suite), total_duration)

    context["recommended_suite"] = {
        "suite":                    suite,
        "total_estimated_duration_s": total_duration,
        "coverage_gaps":            gaps_filled,
        "budget_limit_s":           budget_seconds,
    }
    return context
