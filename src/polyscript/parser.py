"""PolyScript parser - Lark grammar wrapper with line continuation preprocessing."""

from __future__ import annotations

import sys
from pathlib import Path
import re

from lark import Lark, exceptions as lark_exceptions

from .errors import ParseError

if getattr(sys, 'frozen', False):
    _GRAMMAR_PATH = Path(sys._MEIPASS) / "polyscript" / "grammar.lark"
else:
    _GRAMMAR_PATH = Path(__file__).parent / "grammar.lark"


def _strip_comments(source: str) -> str:
    """Strip comments before line joining so that operators inside comments
    (e.g. '# |') don't trigger continuation logic.
    Preserve strings by skipping quoted sections."""
    return re.sub(r'"(?:[^"\\]|\\.)*"|#[^\n]*', lambda m: m.group() if m.group()[0] == '"' else '', source)


def _preprocess(source: str) -> str:
    """Handle line continuation: join lines at logical boundaries."""
    result, _ = _preprocess_with_mapping(source)
    return result


def _preprocess_with_mapping(source: str) -> tuple[str, dict[int, int]]:
    """Preprocess source and build a line number mapping.

    Returns:
        A tuple of (preprocessed_source, line_map) where line_map maps
        1-based preprocessed line numbers to 1-based original line numbers.
    """
    # Normalize line endings
    source = source.replace("\r\n", "\n")

    # Strip comments before line joining
    source = _strip_comments(source)

    # Build initial mapping: original line number for each line (1-based)
    orig_lines = source.split("\n")
    # line_origins[i] = original 1-based line number for orig_lines[i]
    line_origins = list(range(1, len(orig_lines) + 1))

    def _join_lines(lines: list[str], origins: list[int], pattern: re.Pattern, mode: str) -> tuple[list[str], list[int]]:
        """Join lines according to a continuation pattern.

        mode:
            'end'   - join when current line ends with pattern (merge next into current)
            'start' - join when next line starts with pattern (merge next into current)
        """
        result_lines: list[str] = []
        result_origins: list[int] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            origin = origins[i]
            if mode == "end":
                # Keep merging while current line matches end pattern
                while i + 1 < len(lines) and pattern.search(line):
                    m = pattern.search(line)
                    # Replace the match (end of line) and append next line
                    line = line[:m.start()] + m.group("repl") + lines[i + 1].lstrip()
                    i += 1
            elif mode == "start":
                # Keep merging while NEXT line matches start pattern
                while i + 1 < len(lines) and pattern.search(lines[i + 1]):
                    m = pattern.search(lines[i + 1])
                    next_line = lines[i + 1]
                    line = line + m.group("repl") + next_line[m.end():]
                    i += 1
            result_lines.append(line)
            result_origins.append(origin)
            i += 1
        return result_lines, result_origins

    # Apply each continuation rule, tracking line origins

    # Rule 1: line ending with | continues to next line
    # Custom handling: replace trailing | with "| " and join
    new_lines: list[str] = []
    new_origins: list[int] = []
    i = 0
    while i < len(orig_lines):
        line = orig_lines[i]
        origin = line_origins[i]
        while i + 1 < len(orig_lines) and re.search(r"\|\s*$", line):
            line = re.sub(r"\|\s*$", "| ", line) + orig_lines[i + 1].lstrip()
            i += 1
        new_lines.append(line)
        new_origins.append(origin)
        i += 1
    orig_lines, line_origins = new_lines, new_origins

    # Rule 2: next line starting with | continues from previous
    new_lines = []
    new_origins = []
    i = 0
    while i < len(orig_lines):
        line = orig_lines[i]
        origin = line_origins[i]
        while i + 1 < len(orig_lines) and re.match(r"\s*\|", orig_lines[i + 1]):
            next_stripped = re.sub(r"^\s*", " ", orig_lines[i + 1])
            line = line + next_stripped
            i += 1
        new_lines.append(line)
        new_origins.append(origin)
        i += 1
    orig_lines, line_origins = new_lines, new_origins

    # Rule 3: line ending with = (but not ==, !=, <=, >=) continues
    new_lines = []
    new_origins = []
    i = 0
    while i < len(orig_lines):
        line = orig_lines[i]
        origin = line_origins[i]
        while i + 1 < len(orig_lines) and re.search(r"(?<![=!<>])=\s*$", line):
            line = re.sub(r"(?<![=!<>])=\s*$", "= ", line) + orig_lines[i + 1].lstrip()
            i += 1
        new_lines.append(line)
        new_origins.append(origin)
        i += 1
    orig_lines, line_origins = new_lines, new_origins

    # Rule 4: line ending with , continues
    new_lines = []
    new_origins = []
    i = 0
    while i < len(orig_lines):
        line = orig_lines[i]
        origin = line_origins[i]
        while i + 1 < len(orig_lines) and re.search(r",\s*$", line):
            line = re.sub(r",\s*$", ", ", line) + orig_lines[i + 1].lstrip()
            i += 1
        new_lines.append(line)
        new_origins.append(origin)
        i += 1
    orig_lines, line_origins = new_lines, new_origins

    # Rule 5: next line starting with 'else' continues
    new_lines = []
    new_origins = []
    i = 0
    while i < len(orig_lines):
        line = orig_lines[i]
        origin = line_origins[i]
        while i + 1 < len(orig_lines) and re.match(r"\s*else\b", orig_lines[i + 1]):
            next_stripped = re.sub(r"^\s*", " ", orig_lines[i + 1])
            line = line + next_stripped
            i += 1
        new_lines.append(line)
        new_origins.append(origin)
        i += 1
    orig_lines, line_origins = new_lines, new_origins

    # Rule 6: next line starting with + continues (but not +X, +Y, +Z selectors)
    new_lines = []
    new_origins = []
    i = 0
    while i < len(orig_lines):
        line = orig_lines[i]
        origin = line_origins[i]
        while i + 1 < len(orig_lines) and re.match(r"\s*\+(?![XYZ](?:\s|$|\|))", orig_lines[i + 1]):
            next_stripped = re.sub(r"^\s*", " ", orig_lines[i + 1])
            line = line + next_stripped
            i += 1
        new_lines.append(line)
        new_origins.append(origin)
        i += 1
    orig_lines, line_origins = new_lines, new_origins

    # Rule 7: next line starting with 'for' continues
    new_lines = []
    new_origins = []
    i = 0
    while i < len(orig_lines):
        line = orig_lines[i]
        origin = line_origins[i]
        while i + 1 < len(orig_lines) and re.match(r"\s*for\b", orig_lines[i + 1]):
            next_stripped = re.sub(r"^\s*", " ", orig_lines[i + 1])
            line = line + next_stripped
            i += 1
        new_lines.append(line)
        new_origins.append(origin)
        i += 1
    orig_lines, line_origins = new_lines, new_origins

    # Rule 8: next line starting with ] continues
    new_lines = []
    new_origins = []
    i = 0
    while i < len(orig_lines):
        line = orig_lines[i]
        origin = line_origins[i]
        while i + 1 < len(orig_lines) and re.match(r"\s*\]", orig_lines[i + 1]):
            next_stripped = re.sub(r"^\s*", " ", orig_lines[i + 1])
            line = line + next_stripped
            i += 1
        new_lines.append(line)
        new_origins.append(origin)
        i += 1
    orig_lines, line_origins = new_lines, new_origins

    # Build the 1-based line map: preprocessed line N -> original line N
    line_map = {i + 1: line_origins[i] for i in range(len(line_origins))}

    return "\n".join(orig_lines), line_map


def _strip_profile_block(source: str) -> str:
    """Strip @profile { ... } block from source before Lark parsing.

    The block is replaced with blank lines to preserve line numbering.
    """
    m = re.search(r"@profile\s*\{", source)
    if m is None:
        return source

    # Find the matching closing brace
    start = m.start()
    brace_start = m.end() - 1  # position of '{'
    depth = 0
    i = brace_start
    in_string = False
    while i < len(source):
        ch = source[i]
        if in_string:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    # Replace the block with blank lines (preserve line count)
                    block = source[start : i + 1]
                    blank = "\n" * block.count("\n")
                    return source[:start] + blank + source[i + 1 :]
        i += 1

    # Unbalanced braces -- return as-is and let profile parser report the error
    return source


def _extract_param_annotations(source: str) -> tuple[str, dict[int, str]]:
    """Extract @param annotation lines from source before Lark parsing.

    Returns:
        A tuple of (cleaned_source, annotations_by_line) where
        annotations_by_line maps the 0-based line index of the *next*
        statement to the raw @param text (everything after '@param ').
    """
    lines = source.split("\n")
    cleaned_lines: list[str] = []
    annotations: dict[int, str] = {}
    pending_param: str | None = None

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("@param"):
            # Extract the raw text after @param
            raw = stripped[len("@param"):].strip()
            pending_param = raw
            # Replace @param line with blank to preserve line count concept
            # but for Lark we just skip it
            cleaned_lines.append("")
        else:
            if pending_param is not None:
                # The cleaned line index for the next statement
                annotations[len(cleaned_lines)] = pending_param
                pending_param = None
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines), annotations


def _get_parser() -> Lark:
    grammar_text = _GRAMMAR_PATH.read_text()
    return Lark(
        grammar_text,
        parser="lalr",
        propagate_positions=True,
    )


_parser: Lark | None = None


def get_parser() -> Lark:
    global _parser
    if _parser is None:
        _parser = _get_parser()
    return _parser


def parse(source: str):
    """Parse PolyScript source into a Lark parse tree.

    Also returns extracted @param annotations if any are present.
    """
    source_no_profile = _strip_profile_block(source)
    cleaned, annotations = _extract_param_annotations(source_no_profile)
    preprocessed, line_map = _preprocess_with_mapping(cleaned)
    try:
        tree = get_parser().parse(preprocessed)
    except lark_exceptions.UnexpectedInput as e:
        # Translate preprocessed line number back to original source line
        raw_line = getattr(e, "line", None)
        orig_line = line_map.get(raw_line, raw_line) if raw_line else None
        raise ParseError(
            f"Syntax error: {e}",
            line=orig_line,
            column=getattr(e, "column", None),
        ) from e
    tree._param_annotations = annotations
    tree._original_source = source
    tree._line_map = line_map
    return tree


def parse_param_annotations(source: str) -> dict[int, str]:
    """Extract @param annotations from source without full parsing.

    Returns a dict mapping 0-based line index of the following statement
    to the raw @param option text.
    """
    _, annotations = _extract_param_annotations(source)
    return annotations
