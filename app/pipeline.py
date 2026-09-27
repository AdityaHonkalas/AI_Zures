"""
Top-level pipeline orchestrator.
Runs agents 1→5 sequentially, passing a shared PipelineContext dict between them.
Any agent exception is caught, appended to context["errors"], and the pipeline continues.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _make_context(pr_url: str) -> dict[str, Any]:
    return {
        "pr_url": pr_url,
        "pr_metadata": {},
        "diff_raw": "",
        "change_context": {},
        "impact_map": {},
        "risk_ranked_tests": {},
        "recommended_suite": {},
        "generated_scenarios": {},
        "errors": [],
    }


def run_pipeline(pr_url: str) -> dict[str, Any]:
    """Run the full 5-agent pipeline and return the populated context."""
    context = _make_context(pr_url)

    steps = [
        ("change_analyser",    _run_agent, "app.agents.change_analyser"),
        ("impact_mapper",      _run_agent, "app.agents.impact_mapper"),
        ("risk_scorer",        _run_agent, "app.agents.risk_scorer"),
        ("suite_recommender",  _run_agent, "app.agents.suite_recommender"),
        ("scenario_generator", _run_agent, "app.agents.scenario_generator"),
    ]

    for agent_name, runner, module_path in steps:
        try:
            import importlib
            module = importlib.import_module(module_path)
            context = module.run(context)
            logger.info("Agent %s completed successfully.", agent_name)
        except Exception as exc:  # noqa: BLE001
            msg = f"Agent '{agent_name}' failed: {exc}"
            logger.exception(msg)
            context["errors"].append(msg)

    return context


def _run_agent(module_path: str, context: dict) -> dict:
    """Helper kept for clarity — actual call is inlined above."""
    import importlib
    module = importlib.import_module(module_path)
    return module.run(context)
