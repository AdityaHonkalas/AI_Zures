"""
Tests for Agent 1 — Change Analyser.

Uses mocked GitHub API calls (fetch_pr_diff, fetch_file_contents, fetch_repo_test_files)
and a synthetic diff fixture.
"""
import pytest
from unittest.mock import patch, MagicMock


# Valid unified diff: context lines start with exactly one space,
# added lines start with +, removed lines start with -.
SAMPLE_DIFF = (
    "diff --git a/src/checkout/cart.py b/src/checkout/cart.py\n"
    "index abc1234..def5678 100644\n"
    "--- a/src/checkout/cart.py\n"
    "+++ b/src/checkout/cart.py\n"
    "@@ -1,4 +1,6 @@\n"
    " class CartService:\n"
    "     def add_item(self, product_id, qty):\n"
    "+        if qty <= 0:\n"
    "+            raise ValueError('qty must be positive')\n"
    "         self._items.append(product_id)\n"
    "         self._recalculate_total()\n"
)

# Minimal valid Python source — allows tree-sitter to actually parse it
SAMPLE_SOURCE = """
class CartService:
    def add_item(self, product_id: str, qty: int) -> None:
        self._items.append({"product_id": product_id, "qty": qty})

    def _recalculate_total(self) -> None:
        self._total = sum(i['qty'] for i in self._items)
"""

SAMPLE_REPO_TEST_FILES = [
    {"path": "tests/test_checkout.py",  "sha": "aaa111", "size": 1024},
    {"path": "tests/test_cart.py",      "sha": "bbb222", "size": 512},
]

SAMPLE_PR_METADATA = {
    "pr_number":     42,
    "title":         "Fix cart quantity validation US-101",
    "body":          "Fixes issue with negative quantities in checkout. Related: US-204",
    "author":        "dev-user",
    "base_branch":   "main",
    "head_branch":   "fix/cart-validation",
    "head_sha":      "abc123def456",
    "base_sha":      "000000aaaaaa",
    "repo":          "org/web-app",
    "owner":         "org",
    "repo_name":     "web-app",
    "state":         "open",
    "html_url":      "https://github.com/org/web-app/pull/42",
    "commits":       1,
    "changed_files": 1,
    "additions":     3,
    "deletions":     0,
}


def _make_context(pr_url: str = "https://github.com/org/web-app/pull/42") -> dict:
    return {
        "pr_url":            pr_url,
        "pr_metadata":       {},
        "diff_raw":          "",
        "repo_test_files":   [],
        "change_context":    {},
        "impact_map":        {},
        "risk_ranked_tests": {},
        "recommended_suite": {},
        "generated_scenarios": {},
        "errors":            [],
    }


# ── Helper: patch all three GitHub API calls together ────────────────────────

def _patch_github(mock_fetch_diff, mock_fetch_source, mock_fetch_tests):
    """Apply standard return values to the three GitHub client mocks."""
    mock_fetch_diff.return_value    = (SAMPLE_PR_METADATA, SAMPLE_DIFF)
    mock_fetch_source.return_value  = SAMPLE_SOURCE
    mock_fetch_tests.return_value   = SAMPLE_REPO_TEST_FILES


# ── Tests ─────────────────────────────────────────────────────────────────────

@patch("app.agents.change_analyser.github_client.fetch_repo_test_files")
@patch("app.agents.change_analyser.github_client.fetch_file_contents")
@patch("app.agents.change_analyser.github_client.fetch_pr_diff")
@patch("app.agents.change_analyser.llm_client.chat")
def test_run_returns_change_context(mock_chat, mock_fetch_diff, mock_fetch_source, mock_fetch_tests):
    """Agent 1 run() should populate change_context with the correct keys."""
    _patch_github(mock_fetch_diff, mock_fetch_source, mock_fetch_tests)
    mock_chat.return_value = {"impacted_modules": ["checkout", "cart"]}

    from app.agents import change_analyser
    ctx = change_analyser.run(_make_context())

    assert "change_context" in ctx
    cc = ctx["change_context"]
    assert "changed_files"       in cc
    assert "changed_symbols"     in cc
    assert "impacted_modules"    in cc
    assert "linked_user_stories" in cc
    assert isinstance(cc["changed_files"],       list)
    assert isinstance(cc["impacted_modules"],    list)
    assert isinstance(cc["linked_user_stories"], list)


@patch("app.agents.change_analyser.github_client.fetch_repo_test_files")
@patch("app.agents.change_analyser.github_client.fetch_file_contents")
@patch("app.agents.change_analyser.github_client.fetch_pr_diff")
@patch("app.agents.change_analyser.llm_client.chat")
def test_repo_test_files_stored_in_context(mock_chat, mock_fetch_diff, mock_fetch_source, mock_fetch_tests):
    """repo_test_files returned by GitHub should be stored in context."""
    _patch_github(mock_fetch_diff, mock_fetch_source, mock_fetch_tests)
    mock_chat.return_value = {"impacted_modules": ["checkout"]}

    from app.agents import change_analyser
    ctx = change_analyser.run(_make_context())

    assert "repo_test_files" in ctx
    assert len(ctx["repo_test_files"]) == len(SAMPLE_REPO_TEST_FILES)


@patch("app.agents.change_analyser.github_client.fetch_repo_test_files")
@patch("app.agents.change_analyser.github_client.fetch_file_contents")
@patch("app.agents.change_analyser.github_client.fetch_pr_diff")
@patch("app.agents.change_analyser.llm_client.chat")
def test_ast_symbols_extracted_from_real_source(mock_chat, mock_fetch_diff, mock_fetch_source, mock_fetch_tests):
    """When fetch_file_contents returns real Python source, AST symbols should be non-empty."""
    _patch_github(mock_fetch_diff, mock_fetch_source, mock_fetch_tests)
    mock_chat.return_value = {"impacted_modules": ["checkout", "cart"]}

    from app.agents import change_analyser
    ctx = change_analyser.run(_make_context())

    symbols = ctx["change_context"]["changed_symbols"]
    assert len(symbols) > 0, "Expected at least one symbol extracted from real source code"
    # SAMPLE_SOURCE contains CartService class and add_item / _recalculate_total functions
    symbol_names = {s["name"] for s in symbols}
    assert "CartService" in symbol_names or "add_item" in symbol_names


@patch("app.agents.change_analyser.github_client.fetch_repo_test_files")
@patch("app.agents.change_analyser.github_client.fetch_file_contents", return_value="")
@patch("app.agents.change_analyser.github_client.fetch_pr_diff")
@patch("app.agents.change_analyser.llm_client.chat")
def test_ast_graceful_when_source_unavailable(mock_chat, mock_fetch_diff, mock_fetch_source, mock_fetch_tests):
    """When fetch_file_contents returns '' (e.g. 404), changed_symbols should be empty list."""
    mock_fetch_diff.return_value  = (SAMPLE_PR_METADATA, SAMPLE_DIFF)
    mock_fetch_tests.return_value = []
    mock_chat.return_value = {"impacted_modules": ["checkout"]}

    from app.agents import change_analyser
    ctx = change_analyser.run(_make_context())

    # No crash; just an empty symbol list
    assert ctx["change_context"]["changed_symbols"] == []


@patch("app.agents.change_analyser.github_client.fetch_repo_test_files")
@patch("app.agents.change_analyser.github_client.fetch_file_contents")
@patch("app.agents.change_analyser.github_client.fetch_pr_diff")
@patch("app.agents.change_analyser.llm_client.chat")
def test_impacted_modules_are_valid_nodes(mock_chat, mock_fetch_diff, mock_fetch_source, mock_fetch_tests):
    """Returned impacted_modules must only contain known graph nodes."""
    _patch_github(mock_fetch_diff, mock_fetch_source, mock_fetch_tests)
    mock_chat.return_value = {"impacted_modules": ["checkout", "cart", "nonexistent-module"]}

    from app.agents import change_analyser
    ctx = change_analyser.run(_make_context())

    known_nodes = {"checkout", "payment", "cart", "product-catalog", "user-auth",
                   "notification", "order-history", "search", "recommendations", "wishlist"}
    for module in ctx["change_context"]["impacted_modules"]:
        assert module in known_nodes, f"Unknown module in output: {module}"


@patch("app.agents.change_analyser.github_client.fetch_repo_test_files")
@patch("app.agents.change_analyser.github_client.fetch_file_contents")
@patch("app.agents.change_analyser.github_client.fetch_pr_diff")
@patch("app.agents.change_analyser.llm_client.chat")
def test_user_stories_linked_from_pr_text(mock_chat, mock_fetch_diff, mock_fetch_source, mock_fetch_tests):
    """User stories mentioned in PR title/body should be linked."""
    _patch_github(mock_fetch_diff, mock_fetch_source, mock_fetch_tests)
    mock_chat.return_value = {"impacted_modules": ["checkout"]}

    from app.agents import change_analyser
    ctx = change_analyser.run(_make_context())

    linked = ctx["change_context"]["linked_user_stories"]
    assert "US-101" in linked, "US-101 mentioned in PR title should be linked"


@patch("app.agents.change_analyser.github_client.fetch_repo_test_files")
@patch("app.agents.change_analyser.github_client.fetch_file_contents")
@patch("app.agents.change_analyser.github_client.fetch_pr_diff")
@patch("app.agents.change_analyser.llm_client.chat", side_effect=Exception("LLM unavailable"))
def test_heuristic_fallback_when_llm_fails(mock_chat, mock_fetch_diff, mock_fetch_source, mock_fetch_tests):
    """When LLM fails, the heuristic module mapper should still return results without crashing."""
    _patch_github(mock_fetch_diff, mock_fetch_source, mock_fetch_tests)

    from app.agents import change_analyser
    ctx = change_analyser.run(_make_context())

    # Heuristic should find "checkout" from the path src/checkout/cart.py
    assert isinstance(ctx["change_context"]["impacted_modules"], list)


@patch("app.agents.change_analyser.github_client.fetch_repo_test_files", return_value=[])
@patch("app.agents.change_analyser.github_client.fetch_file_contents", return_value="")
@patch("app.agents.change_analyser.github_client.fetch_pr_diff")
def test_empty_diff_produces_empty_changed_files(mock_fetch_diff, mock_fetch_source, mock_fetch_tests):
    """An empty diff should result in no changed files and no impacted modules."""
    mock_fetch_diff.return_value = ({**SAMPLE_PR_METADATA, "changed_files": 0}, "")

    from app.agents import change_analyser
    with patch("app.agents.change_analyser.llm_client.chat", return_value={"impacted_modules": []}):
        ctx = change_analyser.run(_make_context())

    assert ctx["change_context"]["changed_files"]    == []
    assert ctx["change_context"]["impacted_modules"] == []
    assert ctx["repo_test_files"]                    == []
