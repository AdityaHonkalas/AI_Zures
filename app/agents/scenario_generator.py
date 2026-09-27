"""
Agent 5 — Test Scenario Generator

Sub-modules:
  5.1 Gap Detector        — finds journeys with no selected test coverage
  5.2 User Story Interpreter — extracts acceptance criteria from user_stories.json
  5.3 Scenario Writer     — generates Gherkin BDD feature files (qwen2.5-coder:7b)
  5.4 Script Scaffolder   — converts Gherkin to Playwright TypeScript stubs (qwen2.5-coder:7b)
  5.5 Review Gate         — saves files to output/generated_tests/ (PR creation is future scope)

Input:  context["impact_map"]       (ImpactMap from Agent 2)
        context["recommended_suite"] (RecommendedSuite from Agent 4)
Output: context["generated_scenarios"] = GeneratedScenarios dict
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

from app.utils import llm_client
from app.utils.fixture_loader import load_fixture

logger = logging.getLogger(__name__)

_OUTPUT_DIR = Path("output") / "generated_tests"

# ── Few-shot Gherkin example (hardcoded style guide) ─────────────────────────

_GHERKIN_EXAMPLE = """
Feature: Add Item to Cart
  As a shopper
  I want to add products to my cart
  So that I can purchase them later

  Scenario: Add a single item to an empty cart
    Given the user is on the product detail page for "Running Shoes"
    When the user clicks "Add to Cart"
    Then the cart badge shows "1"
    And the cart total reflects the product price

  Scenario: Add the same item twice
    Given the user has "Running Shoes" in their cart
    When the user clicks "Add to Cart" again on the same product
    Then the cart badge shows "2"
    And the cart total is doubled

  Scenario: Add item when not logged in
    Given the user is not logged in
    When the user clicks "Add to Cart" on any product
    Then the user is prompted to log in or continue as guest
""".strip()


# ── 5.1 Gap Detector ─────────────────────────────────────────────────────────

def _detect_coverage_gaps(
    user_journeys: list[dict],
    recommended_suite: dict,
) -> list[dict]:
    """
    Return the journeys that have no test in the recommended suite.
    """
    suite_journey_ids: set[str] = {
        t.get("journey_id", "") for t in recommended_suite.get("suite", [])
    }
    gaps: list[dict] = []
    for journey in user_journeys:
        jid = journey["journey_id"]
        if jid not in suite_journey_ids:
            gaps.append(journey)
    return gaps


# ── 5.2 User Story Interpreter ───────────────────────────────────────────────

_INTERPRETER_SYSTEM = """You are a QA analyst that extracts testable acceptance criteria from user stories.
Respond ONLY with valid JSON."""

_INTERPRETER_PROMPT = """Extract the testable acceptance criteria and edge cases from this user story.

Story title: {title}
Story description: {description}
Acceptance criteria (raw):
{raw_criteria}

Return JSON in exactly this format:
{{
  "acceptance_criteria": [
    "Criterion 1 as a testable statement",
    "Criterion 2 as a testable statement"
  ],
  "edge_cases": [
    "Edge case 1",
    "Edge case 2"
  ]
}}"""


def _interpret_user_story(story: dict) -> dict:
    """Extract structured acceptance criteria from a user story using LLM."""
    raw_criteria = "\n".join(
        f"  - {c}" for c in story.get("acceptance_criteria", [])
    )
    prompt = _INTERPRETER_PROMPT.format(
        title=story.get("title", ""),
        description=story.get("description", ""),
        raw_criteria=raw_criteria or "  (none provided)",
    )
    try:
        return llm_client.chat(
            prompt=prompt,
            system=_INTERPRETER_SYSTEM,
            model=llm_client.REASONING_MODEL,
            expect_json=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Story interpreter failed: %s. Using raw criteria.", exc)
        return {
            "acceptance_criteria": story.get("acceptance_criteria", []),
            "edge_cases": [],
        }


# ── 5.3 Scenario Writer ───────────────────────────────────────────────────────

_WRITER_SYSTEM = f"""You are a QA engineer that writes Gherkin BDD feature files.
Follow the exact style shown in the example below.
Respond with ONLY the raw Gherkin text — no JSON, no markdown fences.

Style example:
{_GHERKIN_EXAMPLE}"""

_WRITER_PROMPT = """Write a complete Gherkin BDD feature file for the following user journey.

Journey: {journey_name}
Modules involved: {modules}

Acceptance criteria to cover:
{criteria}

Edge cases to cover:
{edge_cases}

Write complete Feature and Scenario blocks covering:
1. The happy path
2. Each edge case
3. At least one negative/error case

Use descriptive scenario names. Output ONLY the Gherkin text."""


def _write_gherkin(journey: dict, interpreted: dict) -> str:
    """Generate a Gherkin feature file for a coverage gap using qwen2.5-coder:7b."""
    criteria_text = "\n".join(
        f"  - {c}" for c in interpreted.get("acceptance_criteria", [])
    ) or "  - (no specific criteria)"

    edge_cases_text = "\n".join(
        f"  - {e}" for e in interpreted.get("edge_cases", [])
    ) or "  - (no edge cases)"

    prompt = _WRITER_PROMPT.format(
        journey_name=journey.get("name", journey["journey_id"]),
        modules=", ".join(journey.get("impacted_modules", [])),
        criteria=criteria_text,
        edge_cases=edge_cases_text,
    )

    try:
        return llm_client.chat(
            prompt=prompt,
            system=_WRITER_SYSTEM,
            model=llm_client.CODE_MODEL,
            temperature=0.3,
            expect_json=False,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gherkin generation failed for %s: %s", journey["journey_id"], exc)
        return _fallback_gherkin(journey)


def _fallback_gherkin(journey: dict) -> str:
    """Minimal fallback Gherkin when LLM is unavailable."""
    name = journey.get("name", journey["journey_id"])
    return f"""Feature: {name}

  Scenario: Happy path for {name}
    Given the user is on the relevant page
    When the user completes the required action
    Then the expected outcome is observed
"""


# ── 5.4 Script Scaffolder ─────────────────────────────────────────────────────

_SCAFFOLDER_SYSTEM = """You are a Playwright TypeScript test engineer.
Convert Gherkin scenarios to Playwright test stubs.
Respond with ONLY the TypeScript code — no JSON, no markdown fences."""

_SCAFFOLDER_PROMPT = """Convert the following Gherkin feature file into a Playwright TypeScript test stub.

Use this import pattern:
  import {{ test, expect }} from '@playwright/test';

For each Gherkin Scenario, create one test() block.
Use descriptive test names matching the scenario title.
Add TODO comments inside each test where the actual assertions should go.
Do NOT import page-object models — keep it as a simple stub.

Gherkin:
{gherkin}"""


def _scaffold_playwright(gherkin: str, journey_id: str) -> str:
    """Generate a Playwright TypeScript stub from Gherkin using qwen2.5-coder:7b."""
    try:
        return llm_client.chat(
            prompt=_SCAFFOLDER_PROMPT.format(gherkin=gherkin),
            system=_SCAFFOLDER_SYSTEM,
            model=llm_client.CODE_MODEL,
            temperature=0.3,
            expect_json=False,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Playwright scaffolding failed for %s: %s", journey_id, exc)
        return _fallback_playwright(journey_id)


def _fallback_playwright(journey_id: str) -> str:
    return f"""import {{ test, expect }} from '@playwright/test';

test('{journey_id} - generated scenario', async ({{ page }}) => {{
  // TODO: implement test steps
}});
"""


# ── 5.5 Review Gate (local: save to output/) ─────────────────────────────────

def _save_generated_files(journey_id: str, gherkin: str, playwright_stub: str) -> str:
    """Save generated Gherkin and Playwright files to output/generated_tests/."""
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", journey_id.lower())

    feature_path = _OUTPUT_DIR / f"{safe_id}.feature"
    ts_path      = _OUTPUT_DIR / f"{safe_id}.spec.ts"

    feature_path.write_text(gherkin, encoding="utf-8")
    ts_path.write_text(playwright_stub, encoding="utf-8")

    logger.info("Generated files saved: %s, %s", feature_path, ts_path)
    return f"features/{safe_id}.feature"


# ── Main agent entry point ────────────────────────────────────────────────────

def run(context: dict[str, Any]) -> dict[str, Any]:
    """
    Run Agent 5 — Test Scenario Generator.

    Populates context["generated_scenarios"] with GeneratedScenarios.
    """
    impact_map: dict          = context.get("impact_map", {})
    recommended_suite: dict   = context.get("recommended_suite", {})
    user_journeys: list[dict] = impact_map.get("user_journeys", [])

    # ── 5.1 Gap detection ────────────────────────────────────────────────────
    gaps = _detect_coverage_gaps(user_journeys, recommended_suite)
    logger.info("Agent 5 — Scenario Generator: %d coverage gap(s) found.", len(gaps))

    if not gaps:
        context["generated_scenarios"] = {
            "coverage_gaps": [],
            "scenarios": [],
        }
        return context

    # Load user stories for interpretation
    all_stories: list[dict] = load_fixture("user_stories")
    stories_by_journey: dict[str, dict] = {s["journey_id"]: s for s in all_stories}

    scenarios: list[dict] = []
    gap_ids: list[str] = []

    for journey in gaps:
        jid = journey["journey_id"]
        gap_ids.append(jid)
        logger.info("Generating scenario for gap: %s", jid)

        # ── 5.2 Story interpretation ─────────────────────────────────────────
        story = stories_by_journey.get(jid, {})
        interpreted = _interpret_user_story(story) if story else {
            "acceptance_criteria": [], "edge_cases": []
        }

        # ── 5.3 Gherkin generation ────────────────────────────────────────────
        gherkin = _write_gherkin(journey, interpreted)

        # ── 5.4 Playwright scaffolding ────────────────────────────────────────
        playwright_stub = _scaffold_playwright(gherkin, jid)

        # ── 5.5 Save files ────────────────────────────────────────────────────
        feature_file = _save_generated_files(jid, gherkin, playwright_stub)

        scenarios.append({
            "journey_id":     jid,
            "journey_name":   journey.get("name", jid),
            "feature_file":   feature_file,
            "gherkin":        gherkin,
            "playwright_stub": playwright_stub,
            "story_id":       story.get("story_id", ""),
        })

    logger.info("Agent 5 complete: %d scenario(s) generated.", len(scenarios))

    context["generated_scenarios"] = {
        "coverage_gaps": gap_ids,
        "scenarios":     scenarios,
    }
    return context
