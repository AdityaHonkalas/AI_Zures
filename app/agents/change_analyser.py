"""
Agent 1 — Change Analyser

Sub-modules:
  1.1 Diff Parser       — parse raw unified diff into structured changed files
  1.2 AST Analyser      — extract changed function/class names from real source code
  1.3 Module Mapper     — map file paths to logical app modules using LLM
                          (enriched with actual repo directory structure)
  1.4 User Story Linker — link PR to user stories via keyword matching on fixture data

Gap fixes applied:
  - 1.2 now fetches the actual file content from GitHub (GET /contents/{path}?ref=head_sha)
        so tree-sitter gets real source instead of an empty string.
  - 1.3 now also passes the real top-level directory names from the repo tree
        alongside the fixture taxonomy, so the LLM can map any real repository.
  - context["repo_test_files"] is populated here (via fetch_repo_test_files) so
        Agent 3 can use real test discovery instead of only the fixture test_cases.json.

Input:  context["pr_url"]
Output: context["pr_metadata"]        — PR metadata dict (includes head_sha, owner, repo_name)
        context["diff_raw"]           — raw unified diff string
        context["repo_test_files"]    — list of test file dicts from the repo [{path, sha, size}]
        context["change_context"]     — ChangeContext dict
"""
from __future__ import annotations

import logging
import re
from pathlib import PurePosixPath
from typing import Any

from app.utils import github_client, diff_parser, ast_analyser, llm_client
from app.utils.fixture_loader import load_fixture

logger = logging.getLogger(__name__)

# ── 1.3 Module Mapper prompts ─────────────────────────────────────────────────

_MODULE_MAPPER_SYSTEM = """You are a software module analyser.
Your job is to map changed source file paths to the logical application modules they belong to.
Respond ONLY with valid JSON — no explanation, no markdown fences."""

_MODULE_MAPPER_PROMPT = """A pull request changed the following source files:

{changed_files}

Known application modules and their associated file path patterns:

{module_taxonomy}

Real top-level directory structure of the repository (for additional context):

{repo_dirs}

Identify which modules from the known taxonomy are impacted by these file changes.
A file impacts a module if it lives under that module's path patterns, or if its directory
name strongly suggests the module (e.g. a directory named "checkout" suggests the "checkout" module).

Return JSON in exactly this format:
{{
  "impacted_modules": ["module-name-1", "module-name-2"]
}}

Use only module names from the taxonomy. Return an empty list if no match is found."""


def _build_module_taxonomy(dep_graph: dict) -> str:
    """Build a readable module → file-path patterns string for the LLM prompt."""
    lines = []
    file_map: dict = dep_graph.get("module_file_map", {})
    for module, paths in file_map.items():
        lines.append(f"  {module}: {', '.join(paths)}")
    return "\n".join(lines) if lines else "  (no taxonomy available)"


def _extract_repo_dirs(repo_test_files: list[dict], changed_files: list[str]) -> str:
    """
    Derive the set of distinct top-level and second-level directory names visible
    in this PR from the changed files and discovered test paths.
    Gives the LLM real structural context about the repo layout.
    """
    dirs: set[str] = set()
    for path in changed_files:
        parts = PurePosixPath(path).parts
        if len(parts) >= 1:
            dirs.add(parts[0])
        if len(parts) >= 2:
            dirs.add(f"{parts[0]}/{parts[1]}")
    for tf in repo_test_files:
        parts = PurePosixPath(tf["path"]).parts
        if len(parts) >= 1:
            dirs.add(parts[0])
    if not dirs:
        return "  (not available)"
    return "\n".join(f"  {d}" for d in sorted(dirs))


def _map_files_to_modules_llm(
    changed_files: list[str],
    dep_graph: dict,
    repo_test_files: list[dict],
) -> list[str]:
    """Use LLM to map changed file paths to logical module names."""
    taxonomy = _build_module_taxonomy(dep_graph)
    repo_dirs = _extract_repo_dirs(repo_test_files, changed_files)
    prompt = _MODULE_MAPPER_PROMPT.format(
        changed_files="\n".join(f"  - {f}" for f in changed_files),
        module_taxonomy=taxonomy,
        repo_dirs=repo_dirs,
    )
    try:
        result = llm_client.chat(
            prompt=prompt,
            system=_MODULE_MAPPER_SYSTEM,
            model=llm_client.REASONING_MODEL,
            expect_json=True,
        )
        modules = result.get("impacted_modules", [])
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
    modules: set[str] = set()
    file_map: dict = dep_graph.get("module_file_map", {})
    for module, prefixes in file_map.items():
        for f in changed_files:
            for prefix in prefixes:
                if prefix.rstrip("/") in f:
                    modules.add(module)
                    break
    # Secondary fallback: module name as a substring of any path component
    for module in dep_graph.get("nodes", []):
        for f in changed_files:
            if module.lower() in f.lower():
                modules.add(module)
    return list(modules)


# ── 1.4 User Story Linker ─────────────────────────────────────────────────────

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

        # Direct mention
        if sid.lower() in combined_text:
            linked_ids.add(sid)
            continue

        # Number reference (#101 → US-101)
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
      context["repo_test_files"]   ← NEW: real test files discovered in the repo
      context["change_context"]
    """
    pr_url = context["pr_url"]
    logger.info("Agent 1 — Change Analyser: analysing PR %s", pr_url)

    # ── 1.1 Fetch PR diff + metadata ─────────────────────────────────────────
    pr_metadata, raw_diff = github_client.fetch_pr_diff(pr_url)
    context["pr_metadata"] = pr_metadata
    context["diff_raw"] = raw_diff

    owner     = pr_metadata.get("owner", "")
    repo_name = pr_metadata.get("repo_name", "")
    head_sha  = pr_metadata.get("head_sha", "")

    # ── Discover real test files in the repo (one API call) ──────────────────
    repo_test_files = github_client.fetch_repo_test_files(owner, repo_name, ref=head_sha)
    context["repo_test_files"] = repo_test_files
    logger.info("Discovered %d test file(s) in repo.", len(repo_test_files))

    # ── 1.1 Parse diff ───────────────────────────────────────────────────────
    changed_files_parsed: list[dict] = diff_parser.parse_diff(raw_diff)
    logger.info("Diff parsed: %d changed file(s).", len(changed_files_parsed))

    # ── 1.2 AST analysis — fetch real source, then extract symbols ───────────
    changed_symbols: list[dict] = []
    for cf in changed_files_parsed:
        file_path = cf["file"]
        if not github_client._is_source_path(file_path):
            # Skip non-source files (configs, docs, etc.) — no AST value
            continue

        # Fetch the full file source at the PR head commit
        source_code = github_client.fetch_file_contents(
            owner, repo_name, file_path, ref=head_sha
        )
        if not source_code:
            logger.debug("No source retrieved for %s; AST symbols skipped.", file_path)
            continue

        symbols = ast_analyser.extract_symbols(file_path, source_code=source_code)
        for sym in symbols:
            sym["file"] = file_path
            changed_symbols.append(sym)

    logger.info(
        "AST extracted %d symbol(s) across %d changed source file(s).",
        len(changed_symbols),
        sum(1 for cf in changed_files_parsed if github_client._is_source_path(cf["file"])),
    )

    # ── 1.3 Module mapping ───────────────────────────────────────────────────
    dep_graph: dict = load_fixture("dependency_graph")
    file_paths = [cf["file"] for cf in changed_files_parsed]

    impacted_modules = _map_files_to_modules_llm(file_paths, dep_graph, repo_test_files)
    if not impacted_modules:
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
