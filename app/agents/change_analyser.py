"""
Agent 1 — Change Analyser

Sub-modules:
  1.1 Diff Parser       — parse raw unified diff into structured changed files
  1.2 AST Analyser      — extract changed function/class names via tree-sitter
  1.3 Module Mapper     — map file paths to logical app modules using LLM
  1.4 User Story Linker — link PR to user stories via keyword matching on fixture data

Input:  context["pr_url"]
Output: context["change_context"] = ChangeContext dict
        context["pr_metadata"]    = PR metadata dict
        context["diff_raw"]       = raw diff string
"""
from __future__ import annotations

import logging
import re
from typing import Any

from app.utils import github_client, diff_parser, ast_analyser, llm_client
from app.utils.fixture_loader import load_fixture, load_fixture_as_dict

logger = logging.getLogger(__name__)

# ── 1.3 Module Mapper prompt ─────────────────────────────────────────────────

_MODULE_MAPPER_SYSTEM = """You are a software module analyser.
Your job is to map changed file paths to the logical application modules they belong to.
Respond ONLY with valid JSON — no explanation, no markdown fences."""

_MODULE_MAPPER_PROMPT = """Given the following changed file paths from a pull request:

{changed_files}

And the known application modules with their typical file path patterns:

{module_taxonomy}

Identify which modules are impacted by these file changes.
Return JSON in exactly this format:
{{
  "impacted_modules": ["module-name-1", "module-name-2"]
}}

Only include modules that are clearly impacted. Use the exact module names from the taxonomy."""


def _build_module_taxonomy(dep_graph: dict) -> str:
    """Build a readable module → file paths mapping string for the LLM prompt."""
    lines = []
    file_map: dict = dep_graph.get("module_file_map", {})
    for module, paths in file_map.items():
        lines.append(f"  {module}: {', '.join(paths)}")
    return "\n".join(lines) if lines else "  (no taxonomy available)"


def _map_files_to_modules_llm(changed_files: list[str], dep_graph: dict) -> list[str]:
    """Use LLM to map changed file paths to module names."""
    taxonomy = _build_module_taxonomy(dep_graph)
    prompt = _MODULE_MAPPER_PROMPT.format(
        changed_files="\n".join(f"  - {f}" for f in changed_files),
        module_taxonomy=taxonomy,
    )
    try:
        result = llm_client.chat(
            prompt=prompt,
            system=_MODULE_MAPPER_SYSTEM,
            model=llm_client.REASONING_MODEL,
            expect_json=True,
        )
        modules = result.get("impacted_modules", [])
        # Validate against known modules
        known = set(dep_graph.get("nodes", []))
        return [m for m in modules if m in known]
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM module mapping failed: %s. Falling back to heuristic.", exc)
        return _map_files_to_modules_heuristic(changed_files, dep_graph)


def _map_files_to_modules_heuristic(changed_files: list[str], dep_graph: dict) -> list[str]:
    """
    Fallback: map files to modules by checking if the module name appears
    in the file path segments.
    """
    modules = set()
    file_map: dict = dep_graph.get("module_file_map", {})
    for module, prefixes in file_map.items():
        for f in changed_files:
            for prefix in prefixes:
                if prefix.rstrip("/") in f:
                    modules.add(module)
                    break
    # Further fallback: check if module name appears in any path component
    known_modules: list[str] = dep_graph.get("nodes", [])
    for module in known_modules:
        for f in changed_files:
            if module.lower() in f.lower():
                modules.add(module)
    return list(modules)


# ── 1.4 User Story Linker ────────────────────────────────────────────────────

def _link_user_stories(pr_title: str, pr_body: str, impacted_modules: list[str]) -> list[str]:
    """
    Link the PR to user story IDs from fixture data using keyword matching.

    Strategy:
      1. Look for explicit story ID mentions in PR title/body (e.g. US-101, #101)
      2. Match impacted modules against stories' linked_modules field
    """
    stories: list[dict] = load_fixture("user_stories")
    linked_ids: set[str] = set()

    combined_text = f"{pr_title} {pr_body}".lower()

    for story in stories:
        sid = story["story_id"]

        # Direct mention in PR text
        if sid.lower() in combined_text:
            linked_ids.add(sid)
            continue

        # Number mention (e.g. #101 matching US-101)
        number = re.search(r"\d+", sid)
        if number and f"#{number.group()}" in combined_text:
            linked_ids.add(sid)
            continue

        # Module overlap
        story_modules = story.get("linked_modules", [])
        if any(m in impacted_modules for m in story_modules):
            linked_ids.add(sid)

    return sorted(linked_ids)


# ── Main agent entry point ────────────────────────────────────────────────────

def run(context: dict[str, Any]) -> dict[str, Any]:
    """
    Run Agent 1 — Change Analyser.

    Populates:
      context["pr_metadata"]
      context["diff_raw"]
      context["change_context"]
    """
    pr_url = context["pr_url"]
    logger.info("Agent 1 — Change Analyser: analysing PR %s", pr_url)

    # ── 1.1 Fetch diff via GitHub API ────────────────────────────────────────
    pr_metadata, raw_diff = github_client.fetch_pr_diff(pr_url)
    context["pr_metadata"] = pr_metadata
    context["diff_raw"] = raw_diff

    # ── 1.1 Parse diff ───────────────────────────────────────────────────────
    changed_files_parsed: list[dict] = diff_parser.parse_diff(raw_diff)
    logger.info("Diff parsed: %d changed files.", len(changed_files_parsed))

    # ── 1.2 AST analysis — extract symbols from changed files ────────────────
    changed_symbols: list[dict] = []
    for cf in changed_files_parsed:
        file_path = cf["file"]
        # We don't have local source in this context; use file path for language detection
        # Symbols will be empty if source not available — this is expected behaviour
        symbols = ast_analyser.extract_symbols(file_path, source_code="", language=None)
        for sym in symbols:
            sym["file"] = file_path
            changed_symbols.append(sym)

    # ── 1.3 Module mapping ───────────────────────────────────────────────────
    dep_graph: dict = load_fixture("dependency_graph")
    file_paths = [cf["file"] for cf in changed_files_parsed]

    impacted_modules = _map_files_to_modules_llm(file_paths, dep_graph)
    if not impacted_modules:
        # Last resort: try heuristic
        impacted_modules = _map_files_to_modules_heuristic(file_paths, dep_graph)
    logger.info("Impacted modules identified: %s", impacted_modules)

    # ── 1.4 User story linking ───────────────────────────────────────────────
    linked_stories = _link_user_stories(
        pr_title=pr_metadata.get("title", ""),
        pr_body=pr_metadata.get("body", ""),
        impacted_modules=impacted_modules,
    )
    logger.info("Linked user stories: %s", linked_stories)

    context["change_context"] = {
        "changed_files":       changed_files_parsed,
        "changed_symbols":     changed_symbols,
        "impacted_modules":    impacted_modules,
        "linked_user_stories": linked_stories,
    }

    return context
