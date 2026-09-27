"""
GitHub API client — fetches PR metadata, raw unified diff, file contents, and repo test tree.

Supports GitHub PR web URLs:  https://github.com/owner/repo/pull/42

Functions:
  fetch_pr_diff(pr_url)                          → (pr_metadata, raw_diff)
  fetch_file_contents(owner, repo, path, ref)    → source_code str ('' on failure)
  fetch_repo_test_files(owner, repo, ref)        → list[{path, sha, size}]

Set GITHUB_TOKEN in .env for private repos or to avoid the 60 req/hr unauthenticated limit.
Authenticated requests allow 5 000 req/hr.
"""
from __future__ import annotations

import base64
import logging
import os
import re
import requests

logger = logging.getLogger(__name__)

_API_BASE = "https://api.github.com"
_WEB_PR_RE = re.compile(
    r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)", re.IGNORECASE
)

# File extensions considered to be source code (fetched for AST analysis)
_SOURCE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".java", ".rb", ".go", ".cs",
}

# Patterns for test file detection (matched against the full file path in the repo)
_TEST_PATH_PATTERNS = [
    re.compile(r"(^|/)tests?/"),                               # tests/ or test/ at any depth
    re.compile(r"(^|/)spec(s)?/"),                             # spec/ or specs/
    re.compile(r"(^|/)__tests__/"),                            # Jest __tests__/
    re.compile(r"(^|/)e2e/"),                                  # e2e/ directory
    re.compile(r"test_[^/]+\.(py|js|ts)$"),                    # test_foo.py / test_foo.ts
    re.compile(r"[^/]+_test\.(py|js|ts)$"),                    # foo_test.py / foo_test.ts
    re.compile(r"[^/]+\.(spec|test)\.(js|ts|jsx|tsx)$"),       # foo.spec.ts / foo.test.ts
    re.compile(r"[^/]+\.spec\.py$"),                           # foo.spec.py (pytest-spec)
]

# Maximum source file size to fetch (bytes). Larger files are skipped to avoid timeouts.
_MAX_SOURCE_BYTES = 150_000  # 150 KB


# ── Auth / headers ────────────────────────────────────────────────────────────

def _headers(accept: str = "application/vnd.github.v3+json") -> dict[str, str]:
    token = os.environ.get("GITHUB_TOKEN", "")
    h = {"Accept": accept, "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


# ── URL parsing ───────────────────────────────────────────────────────────────

def _parse_pr_url(pr_url: str) -> tuple[str, str, str]:
    """Return (owner, repo_name, pull_number) from a GitHub PR web URL."""
    m = _WEB_PR_RE.match(pr_url.strip())
    if not m:
        raise ValueError(
            f"Unrecognised GitHub PR URL format: '{pr_url}'. "
            "Expected https://github.com/owner/repo/pull/N"
        )
    return m.group(1), m.group(2), m.group(3)


def _is_test_path(path: str) -> bool:
    """Return True if the file path matches any known test-file pattern."""
    return any(p.search(path) for p in _TEST_PATH_PATTERNS)


def _is_source_path(path: str) -> bool:
    """Return True if the file extension is a recognised source language."""
    ext = os.path.splitext(path)[1].lower()
    return ext in _SOURCE_EXTENSIONS


# ── Public API ────────────────────────────────────────────────────────────────

def fetch_pr_diff(pr_url: str) -> tuple[dict, str]:
    """
    Fetch PR metadata and the raw unified diff for a GitHub pull request.

    Returns:
        (pr_metadata dict, raw_diff string)

    pr_metadata keys:
        pr_number, title, body, author, base_branch, head_branch,
        head_sha, base_sha,          ← NEW: used by fetch_file_contents / fetch_repo_test_files
        repo (owner/repo_name),
        owner, repo_name,            ← NEW: pre-parsed for downstream callers
        state, html_url, commits, changed_files, additions, deletions

    Raises:
        ValueError:            if the URL cannot be parsed
        requests.HTTPError:    if the GitHub API request fails
    """
    owner, repo_name, pull_number = _parse_pr_url(pr_url)
    meta_url = f"{_API_BASE}/repos/{owner}/{repo_name}/pulls/{pull_number}"

    # 1. Fetch structured PR metadata
    meta_resp = requests.get(meta_url, headers=_headers(), timeout=30)
    meta_resp.raise_for_status()
    pr_data = meta_resp.json()

    pr_metadata = {
        "pr_number":     int(pull_number),
        "title":         pr_data.get("title", ""),
        "body":          pr_data.get("body", "") or "",
        "author":        pr_data.get("user", {}).get("login", ""),
        "base_branch":   pr_data.get("base", {}).get("ref", ""),
        "head_branch":   pr_data.get("head", {}).get("ref", ""),
        # Commit SHAs — used to fetch exact file state at the PR head/base
        "head_sha":      pr_data.get("head", {}).get("sha", ""),
        "base_sha":      pr_data.get("base", {}).get("sha", ""),
        "repo":          f"{owner}/{repo_name}",
        "owner":         owner,
        "repo_name":     repo_name,
        "state":         pr_data.get("state", ""),
        "html_url":      pr_data.get("html_url", pr_url),
        "commits":       pr_data.get("commits", 0),
        "changed_files": pr_data.get("changed_files", 0),
        "additions":     pr_data.get("additions", 0),
        "deletions":     pr_data.get("deletions", 0),
    }

    # 2. Fetch raw unified diff
    diff_resp = requests.get(
        meta_url,
        headers=_headers(accept="application/vnd.github.v3.diff"),
        timeout=60,
    )
    diff_resp.raise_for_status()
    raw_diff = diff_resp.text

    return pr_metadata, raw_diff


def fetch_file_contents(
    owner: str,
    repo_name: str,
    file_path: str,
    ref: str,
) -> str:
    """
    Fetch the decoded source code of a single file at a given commit ref.

    Uses the GitHub Contents API which returns base64-encoded file content.
    Returns '' (empty string) silently on any failure so callers never crash.

    Args:
        owner:      GitHub repository owner (user or org)
        repo_name:  Repository name (without owner prefix)
        file_path:  Path to the file inside the repo (e.g. 'src/cart/cart.py')
        ref:        Commit SHA or branch name (use pr_metadata["head_sha"])

    Returns:
        Decoded UTF-8 source code string, or '' on any failure.
    """
    if not ref:
        return ""

    url = f"{_API_BASE}/repos/{owner}/{repo_name}/contents/{file_path}"
    try:
        resp = requests.get(url, headers=_headers(), params={"ref": ref}, timeout=20)
        if resp.status_code == 404:
            logger.debug("File not found in repo at %s@%s: %s", repo_name, ref[:8], file_path)
            return ""
        resp.raise_for_status()
        data = resp.json()

        # Contents API returns type='file' for normal files; dirs/symlinks have no content
        if data.get("type") != "file":
            return ""
        if data.get("size", 0) > _MAX_SOURCE_BYTES:
            logger.debug("Skipping large file (%d bytes): %s", data["size"], file_path)
            return ""

        # GitHub base64 content includes newlines inside the encoded string — strip before decode
        encoded = data.get("content", "")
        return base64.b64decode(encoded.replace("\n", "")).decode("utf-8", errors="replace")

    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not fetch source for %s@%s: %s", file_path, ref[:8] if ref else "?", exc)
        return ""


def fetch_repo_test_files(
    owner: str,
    repo_name: str,
    ref: str,
    max_files: int = 200,
) -> list[dict]:
    """
    Walk the full repository file tree and return metadata for all detected test files.

    Uses the GitHub Git Trees API with recursive=1 to retrieve the complete tree
    in a single request, then filters using _TEST_PATH_PATTERNS.

    Args:
        owner:      Repository owner
        repo_name:  Repository name
        ref:        Commit SHA or branch name (use pr_metadata["head_sha"])
        max_files:  Cap on results to prevent overwhelming downstream consumers

    Returns:
        List of dicts:
            path  — file path relative to repo root (e.g. 'tests/test_cart.py')
            sha   — blob SHA
            size  — file size in bytes
        Returns [] if the tree cannot be fetched.
    """
    if not ref:
        logger.warning("fetch_repo_test_files: no ref provided, returning [].")
        return []

    url = f"{_API_BASE}/repos/{owner}/{repo_name}/git/trees/{ref}"
    try:
        resp = requests.get(url, headers=_headers(), params={"recursive": "1"}, timeout=30)
        if resp.status_code == 404:
            logger.warning("Repo tree not found: %s/%s@%s", owner, repo_name, ref[:8])
            return []
        resp.raise_for_status()
        tree_data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not fetch repo tree for %s/%s: %s", owner, repo_name, exc)
        return []

    if tree_data.get("truncated"):
        logger.warning(
            "GitHub truncated the repo tree for %s/%s — test discovery may be incomplete. "
            "Consider fetching sub-trees for large repositories.",
            owner, repo_name,
        )

    test_files: list[dict] = []
    for item in tree_data.get("tree", []):
        if item.get("type") != "blob":
            continue
        path: str = item.get("path", "")
        if _is_test_path(path) and _is_source_path(path):
            test_files.append({
                "path": path,
                "sha":  item.get("sha", ""),
                "size": item.get("size", 0),
            })
            if len(test_files) >= max_files:
                logger.info(
                    "Test file cap (%d) reached for %s/%s; truncating.",
                    max_files, owner, repo_name,
                )
                break

    logger.info(
        "Discovered %d test file(s) in %s/%s@%s",
        len(test_files), owner, repo_name, ref[:8],
    )
    return test_files
