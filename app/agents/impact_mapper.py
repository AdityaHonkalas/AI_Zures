"""
Agent 2 — Impact Mapper

Sub-modules:
  2.1 Dependency Graph Builder  — loaded from dependency_graph.json fixture
  2.2 Transitive Impact Resolver — LLM traverses graph to find blast radius
  2.3 User Journey Mapper        — maps impacted modules to user journeys
  2.4 Browser & Env Filter       — determines browser/environment test matrix

Input:  context["change_context"] (ChangeContext from Agent 1)
Output: context["impact_map"] = ImpactMap dict
"""
from __future__ import annotations

import logging
from typing import Any

from app.utils import llm_client
from app.utils.fixture_loader import load_fixture

logger = logging.getLogger(__name__)

# ── 2.2 Transitive Impact Resolver prompt ────────────────────────────────────

_TRANSITIVE_SYSTEM = """You are a software dependency analyser.
Given a list of directly impacted modules and an application dependency graph,
identify all transitively impacted modules — modules that depend on, or are depended
on by, the directly impacted ones.
Respond ONLY with valid JSON."""

_TRANSITIVE_PROMPT = """Directly impacted modules:
{direct_modules}

Application dependency graph (edges as "A depends on B"):
{graph_edges}

Identify ALL transitively impacted modules (excluding the directly impacted ones already listed).
A module is transitively impacted if it depends on an impacted module OR an impacted module
depends on it (bidirectional blast radius).

Return JSON in exactly this format:
{{
  "transitively_impacted_modules": ["module-1", "module-2"]
}}

Use only module names that appear in the graph. Return an empty list if none are found."""


def _resolve_transitive_impact(
    direct_modules: list[str],
    dep_graph: dict,
) -> list[str]:
    """Use LLM to find transitively impacted modules from the dependency graph."""
    nodes: list[str] = dep_graph.get("nodes", [])
    edges: list[list[str]] = dep_graph.get("edges", [])

    if not edges:
        return []

    edge_lines = "\n".join(f"  {a} → {b}" for a, b in edges)

    prompt = _TRANSITIVE_PROMPT.format(
        direct_modules="\n".join(f"  - {m}" for m in direct_modules),
        graph_edges=edge_lines,
    )

    try:
        result = llm_client.chat(
            prompt=prompt,
            system=_TRANSITIVE_SYSTEM,
            model=llm_client.REASONING_MODEL,
            expect_json=True,
        )
        transitive = result.get("transitively_impacted_modules", [])
        # Validate against known nodes, exclude already-direct modules
        direct_set = set(direct_modules)
        return [m for m in transitive if m in nodes and m not in direct_set]
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM transitive resolution failed: %s. Using graph BFS fallback.", exc)
        return _bfs_transitive(direct_modules, edges, dep_graph.get("nodes", []))


def _bfs_transitive(
    direct_modules: list[str],
    edges: list[list[str]],
    all_nodes: list[str],
) -> list[str]:
    """
    Fallback: BFS over the dependency graph (bidirectional) to find
    all modules reachable from any directly impacted module.
    """
    # Build adjacency list (bidirectional)
    adj: dict[str, set[str]] = {n: set() for n in all_nodes}
    for a, b in edges:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)

    visited = set(direct_modules)
    queue = list(direct_modules)
    while queue:
        node = queue.pop(0)
        for neighbour in adj.get(node, set()):
            if neighbour not in visited:
                visited.add(neighbour)
                queue.append(neighbour)

    return [n for n in visited if n not in set(direct_modules)]


# ── 2.3 User Journey Mapper ──────────────────────────────────────────────────

def _map_user_journeys(all_impacted_modules: list[str]) -> list[dict]:
    """
    Collect all user journeys whose test cases touch any impacted module.
    Returns a deduplicated list of journey dicts.
    """
    test_cases: list[dict] = load_fixture("test_cases")
    seen_journeys: set[str] = set()
    journeys: list[dict] = []

    module_set = set(all_impacted_modules)

    for tc in test_cases:
        jid = tc.get("journey_id", "")
        module = tc.get("module", "")
        if module in module_set and jid and jid not in seen_journeys:
            seen_journeys.add(jid)
            # Collect all modules for this journey
            journey_modules = list({
                t["module"] for t in test_cases
                if t.get("journey_id") == jid and t["module"] in module_set
            })
            journeys.append({
                "journey_id":      jid,
                "name":            _journey_name(jid),
                "impacted_modules": journey_modules,
            })

    return journeys


def _journey_name(journey_id: str) -> str:
    """Map journey ID to a human-readable name from user_stories fixture."""
    stories: list[dict] = load_fixture("user_stories")
    for story in stories:
        if story.get("journey_id") == journey_id:
            return story.get("title", journey_id)
    return journey_id


# ── 2.4 Browser & Env Filter ────────────────────────────────────────────────

def _build_browser_env_matrix(all_impacted_modules: list[str]) -> list[dict]:
    """
    Build a deduplicated browser/environment matrix for all impacted modules
    using the browser_matrix.json fixture.
    """
    browser_matrix: dict = load_fixture("browser_matrix")
    seen: set[tuple] = set()
    matrix: list[dict] = []

    for module in all_impacted_modules:
        for entry in browser_matrix.get(module, []):
            key = (entry["browser"], entry["env"])
            if key not in seen:
                seen.add(key)
                matrix.append({"browser": entry["browser"], "env": entry["env"]})

    return matrix


# ── Main agent entry point ────────────────────────────────────────────────────

def run(context: dict[str, Any]) -> dict[str, Any]:
    """
    Run Agent 2 — Impact Mapper.

    Populates context["impact_map"] with ImpactMap.
    """
    change_context: dict = context.get("change_context", {})
    direct_modules: list[str] = change_context.get("impacted_modules", [])

    if not direct_modules:
        logger.warning("Agent 2 — no directly impacted modules from Agent 1; returning empty impact map.")
        context["impact_map"] = {
            "directly_impacted_modules": [],
            "transitively_impacted_modules": [],
            "user_journeys": [],
            "browser_env_matrix": [],
        }
        return context

    logger.info("Agent 2 — Impact Mapper: resolving transitive impact for %s", direct_modules)

    # ── 2.1 Load dependency graph ────────────────────────────────────────────
    dep_graph: dict = load_fixture("dependency_graph")

    # ── 2.2 Transitive impact resolution ────────────────────────────────────
    transitive_modules = _resolve_transitive_impact(direct_modules, dep_graph)
    logger.info("Transitively impacted: %s", transitive_modules)

    all_impacted = list(dict.fromkeys(direct_modules + transitive_modules))  # preserve order, dedupe

    # ── 2.3 User journey mapping ─────────────────────────────────────────────
    user_journeys = _map_user_journeys(all_impacted)
    logger.info("User journeys identified: %d", len(user_journeys))

    # ── 2.4 Browser/env matrix ───────────────────────────────────────────────
    browser_env_matrix = _build_browser_env_matrix(all_impacted)
    logger.info("Browser/env matrix: %d entries", len(browser_env_matrix))

    context["impact_map"] = {
        "directly_impacted_modules":     direct_modules,
        "transitively_impacted_modules": transitive_modules,
        "user_journeys":                 user_journeys,
        "browser_env_matrix":            browser_env_matrix,
    }

    return context
