"""
Diff parser — converts raw unified diff text into a structured list of changed files.
Uses the `unidiff` library for reliable parsing.
"""
from __future__ import annotations

from unidiff import PatchSet


def parse_diff(raw_diff: str) -> list[dict]:
    """
    Parse a raw unified diff string into a structured list of changed files.

    Args:
        raw_diff: unified diff text (e.g. from GitHub API with Accept: vnd.github.v3.diff)

    Returns:
        List of dicts, each with:
          - file:          target file path (str)
          - source_file:   source file path before rename (str)
          - change_type:   'added' | 'removed' | 'modified' | 'renamed'
          - added_lines:   count of added lines (int)
          - removed_lines: count of removed lines (int)
          - hunks:         list of hunk summaries [{section_header, added, removed}]
    """
    if not raw_diff or not raw_diff.strip():
        return []

    try:
        patch = PatchSet(raw_diff)
    except Exception:  # noqa: BLE001
        return []

    results = []
    for patched_file in patch:
        if patched_file.is_added_file:
            change_type = "added"
        elif patched_file.is_removed_file:
            change_type = "removed"
        elif patched_file.is_rename:
            change_type = "renamed"
        else:
            change_type = "modified"

        hunks = []
        for hunk in patched_file:
            hunks.append({
                "section_header": hunk.section_header.strip() if hunk.section_header else "",
                "added":   hunk.added,
                "removed": hunk.removed,
            })

        results.append({
            "file":          patched_file.path,
            "source_file":   patched_file.source_file,
            "change_type":   change_type,
            "added_lines":   patched_file.added,
            "removed_lines": patched_file.removed,
            "hunks":         hunks,
        })

    return results
