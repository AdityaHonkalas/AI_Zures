"""
GitHub API client — fetches PR metadata and raw unified diff from a GitHub PR URL.

Supports both:
  - Web URL:  https://github.com/owner/repo/pull/42
  - API URL:  https://api.github.com/repos/owner/repo/pulls/42

Set GITHUB_TOKEN in .env for private repos or to avoid rate limiting.
"""
from __future__ import annotations

import os
import re
import requests

_API_BASE = "https://api.github.com"
_WEB_PR_RE = re.compile(
    r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)", re.IGNORECASE
)


def _headers() -> dict[str, str]:
    token = os.environ.get("GITHUB_TOKEN", "")
    h = {"Accept": "application/vnd.github.v3+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _parse_pr_url(pr_url: str) -> tuple[str, str, str]:
    """Return (owner, repo, pull_number) from a GitHub PR URL."""
    m = _WEB_PR_RE.match(pr_url.strip())
    if not m:
        raise ValueError(
            f"Unrecognised GitHub PR URL format: '{pr_url}'. "
            "Expected https://github.com/owner/repo/pull/N"
        )
    return m.group(1), m.group(2), m.group(3)


def fetch_pr_diff(pr_url: str) -> tuple[dict, str]:
    """
    Fetch PR metadata and the raw unified diff for a GitHub pull request.

    Args:
        pr_url: GitHub PR web URL, e.g. https://github.com/owner/repo/pull/42

    Returns:
        (pr_metadata dict, raw_diff string)

    Raises:
        ValueError: if the URL cannot be parsed
        requests.HTTPError: if the API request fails
    """
    owner, repo, pull_number = _parse_pr_url(pr_url)

    # 1. Fetch PR metadata (title, body, author, etc.)
    meta_url = f"{_API_BASE}/repos/{owner}/{repo}/pulls/{pull_number}"
    meta_resp = requests.get(meta_url, headers=_headers(), timeout=30)
    meta_resp.raise_for_status()
    pr_data = meta_resp.json()

    pr_metadata = {
        "pr_number":    int(pull_number),
        "title":        pr_data.get("title", ""),
        "body":         pr_data.get("body", "") or "",
        "author":       pr_data.get("user", {}).get("login", ""),
        "base_branch":  pr_data.get("base", {}).get("ref", ""),
        "head_branch":  pr_data.get("head", {}).get("ref", ""),
        "repo":         f"{owner}/{repo}",
        "state":        pr_data.get("state", ""),
        "html_url":     pr_data.get("html_url", pr_url),
        "commits":      pr_data.get("commits", 0),
        "changed_files": pr_data.get("changed_files", 0),
        "additions":    pr_data.get("additions", 0),
        "deletions":    pr_data.get("deletions", 0),
    }

    # 2. Fetch raw unified diff
    diff_headers = dict(_headers())
    diff_headers["Accept"] = "application/vnd.github.v3.diff"
    diff_resp = requests.get(meta_url, headers=diff_headers, timeout=60)
    diff_resp.raise_for_status()
    raw_diff = diff_resp.text

    return pr_metadata, raw_diff
