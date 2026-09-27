"""
AST analyser — extracts changed function/class/component names from source files
using tree-sitter. Supports Python and JavaScript. Falls back gracefully for
unsupported languages.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Language detection by file extension
_EXT_TO_LANG: dict[str, str] = {
    ".py":   "python",
    ".js":   "javascript",
    ".jsx":  "javascript",
    ".ts":   "javascript",   # tree-sitter-javascript handles TS reasonably
    ".tsx":  "javascript",
    ".mjs":  "javascript",
    ".cjs":  "javascript",
}

_parsers: dict[str, object] = {}  # lazy-loaded cache


def _get_parser(language: str):
    """Lazy-load and cache a tree-sitter parser for the given language."""
    if language in _parsers:
        return _parsers[language]

    try:
        import tree_sitter_python as tspython
        import tree_sitter_javascript as tsjavascript
        from tree_sitter import Language, Parser

        lang_map = {
            "python":     Language(tspython.language()),
            "javascript": Language(tsjavascript.language()),
        }
        if language not in lang_map:
            return None

        parser = Parser(lang_map[language])
        _parsers[language] = parser
        return parser
    except Exception as exc:  # noqa: BLE001
        logger.warning("tree-sitter not available (%s); AST analysis disabled.", exc)
        return None


def _detect_language(file_path: str) -> str | None:
    ext = Path(file_path).suffix.lower()
    return _EXT_TO_LANG.get(ext)


def _extract_python_symbols(tree, source_bytes: bytes) -> list[dict]:
    """Walk a Python AST and collect function_definition / class_definition nodes."""
    symbols = []
    cursor = tree.walk()

    def visit(node):
        if node.type in ("function_definition", "async_function_definition"):
            name_node = node.child_by_field_name("name")
            if name_node:
                symbols.append({
                    "type":       "function",
                    "name":       source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace"),
                    "start_line": node.start_point[0] + 1,
                    "end_line":   node.end_point[0] + 1,
                })
        elif node.type == "class_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                symbols.append({
                    "type":       "class",
                    "name":       source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace"),
                    "start_line": node.start_point[0] + 1,
                    "end_line":   node.end_point[0] + 1,
                })
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return symbols


def _extract_js_symbols(tree, source_bytes: bytes) -> list[dict]:
    """Walk a JavaScript AST and collect function / class declarations."""
    symbols = []

    def visit(node):
        if node.type in (
            "function_declaration",
            "generator_function_declaration",
            "function",
            "arrow_function",
        ):
            name_node = node.child_by_field_name("name")
            if name_node:
                symbols.append({
                    "type":       "function",
                    "name":       source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace"),
                    "start_line": node.start_point[0] + 1,
                    "end_line":   node.end_point[0] + 1,
                })
        elif node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                symbols.append({
                    "type":       "class",
                    "name":       source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace"),
                    "start_line": node.start_point[0] + 1,
                    "end_line":   node.end_point[0] + 1,
                })
        elif node.type == "method_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                symbols.append({
                    "type":       "method",
                    "name":       source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace"),
                    "start_line": node.start_point[0] + 1,
                    "end_line":   node.end_point[0] + 1,
                })
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return symbols


def extract_symbols(file_path: str, source_code: str, language: str | None = None) -> list[dict]:
    """
    Extract function/class/method symbols from source code using tree-sitter.

    Args:
        file_path:   Path to the source file (used for language detection if not provided)
        source_code: The full source code text
        language:    Override language ('python' or 'javascript'). Auto-detected if None.

    Returns:
        List of symbol dicts: [{type, name, start_line, end_line}]
        Returns [] if the language is unsupported or parsing fails.
    """
    lang = language or _detect_language(file_path)
    if not lang:
        return []

    parser = _get_parser(lang)
    if parser is None:
        return []

    try:
        source_bytes = source_code.encode("utf-8")
        tree = parser.parse(source_bytes)

        if lang == "python":
            return _extract_python_symbols(tree, source_bytes)
        elif lang == "javascript":
            return _extract_js_symbols(tree, source_bytes)
        return []
    except Exception as exc:  # noqa: BLE001
        logger.warning("AST extraction failed for %s: %s", file_path, exc)
        return []
