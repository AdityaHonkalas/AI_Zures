"""
Tests for Agent 1 — Change Analyser.

Uses mocked GitHub API and a synthetic diff fixture.
"""
import pytest
from unittest.mock import patch, MagicMock


SAMPLE_DIFF = """diff --git a/src/checkout/cart.py b/src/checkout/cart.py
index abc1234..def5678 100644
--- a/src/checkout/cart.py
+++ b/src/checkout/cart.py
@@ -10,6 +10,10 @@ class CartService:
     def add_item(self, product_id: str, qty: int) -> None:
+        if qty <= 0:
+            raise ValueError("Quantity must be positive")
         self._items.append({"product_id": product_id, "qty": qty})
+        self._recalculate_total()
"""

SAMPLE_PR_METADATA = {
    "pr_number": 42,
    "title": "Fix cart quantity validation US-101",
    "body": "Fixes issue with negative quantities in checkout. Related: US-204",
    "author": "dev-user",
    "base_branch": "main",
    "head_branch": "fix/cart-validation",
    "repo": "org/web-app",
    "state": "open",
    "html_url": "https://github.com/org/web-app/pull/42",
    "commits": 1,
    "changed_files": 1,
    "additions": 3,
    "deletions": 0,
}


def _make_context(pr_url: str = "https://github.com/org/web-app/pull/42") -> dict:
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


@patch("app.agents.change_analyser.github_client.fetch_pr_diff")
@patch("app.agents.change_analyser.llm_client.chat")
def test_run_returns_change_context(mock_chat, mock_fetch, monkeypatch):
    """Agent 1 run() should populate change_context with the correct keys."""
    mock_fetch.return_value = (SAMPLE_PR_METADATA, SAMPLE_DIFF)
    mock_chat.return_value = {"impacted_modules": ["checkout", "cart"]}

    from app.agents import change_analyser
    ctx = change_analyser.run(_make_context())

    assert "change_context" in ctx
    cc = ctx["change_context"]
    assert "changed_files" in cc
    assert "impacted_modules" in cc
    assert "linked_user_stories" in cc
    assert isinstance(cc["changed_files"], list)
    assert isinstance(cc["impacted_modules"], list)
    assert isinstance(cc["linked_user_stories"], list)


@patch("app.agents.change_analyser.github_client.fetch_pr_diff")
@patch("app.agents.change_analyser.llm_client.chat")
def test_impacted_modules_are_valid_nodes(mock_chat, mock_fetch):
    """Returned impacted_modules must only contain known graph nodes."""
    mock_fetch.return_value = (SAMPLE_PR_METADATA, SAMPLE_DIFF)
    mock_chat.return_value = {"impacted_modules": ["checkout", "cart", "nonexistent-module"]}

    from app.agents import change_analyser
    ctx = change_analyser.run(_make_context())

    known_nodes = {"checkout", "payment", "cart", "product-catalog", "user-auth",
                   "notification", "order-history", "search", "recommendations", "wishlist"}
    for module in ctx["change_context"]["impacted_modules"]:
        assert module in known_nodes, f"Unknown module in output: {module}"


@patch("app.agents.change_analyser.github_client.fetch_pr_diff")
@patch("app.agents.change_analyser.llm_client.chat")
def test_user_stories_linked_from_pr_text(mock_chat, mock_fetch):
    """User stories mentioned in PR title/body should be linked."""
    mock_fetch.return_value = (SAMPLE_PR_METADATA, SAMPLE_DIFF)
    mock_chat.return_value = {"impacted_modules": ["checkout"]}

    from app.agents import change_analyser
    ctx = change_analyser.run(_make_context())

    linked = ctx["change_context"]["linked_user_stories"]
    assert "US-101" in linked, "US-101 mentioned in PR title should be linked"


@patch("app.agents.change_analyser.github_client.fetch_pr_diff")
@patch("app.agents.change_analyser.llm_client.chat", side_effect=Exception("LLM unavailable"))
def test_heuristic_fallback_when_llm_fails(mock_chat, mock_fetch):
    """When LLM fails, the heuristic module mapper should still return results."""
    mock_fetch.return_value = (SAMPLE_PR_METADATA, SAMPLE_DIFF)

    from app.agents import change_analyser
    ctx = change_analyser.run(_make_context())

    # Heuristic should find "checkout" from the file path src/checkout/cart.py
    assert isinstance(ctx["change_context"]["impacted_modules"], list)


@patch("app.agents.change_analyser.github_client.fetch_pr_diff")
def test_empty_diff_produces_empty_changed_files(mock_fetch):
    """An empty diff should result in no changed files and no impacted modules."""
    mock_fetch.return_value = ({**SAMPLE_PR_METADATA, "changed_files": 0}, "")

    from app.agents import change_analyser
    with patch("app.agents.change_analyser.llm_client.chat", return_value={"impacted_modules": []}):
        ctx = change_analyser.run(_make_context())

    assert ctx["change_context"]["changed_files"] == []
    assert ctx["change_context"]["impacted_modules"] == []
