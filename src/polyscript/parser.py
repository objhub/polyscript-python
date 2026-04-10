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
    # Normalize line endings
    source = source.replace("\r\n", "\n")

    # Strip comments before line joining
    source = _strip_comments(source)

    # Join lines: line ending with | continues to next line
    source = re.sub(r"\|\s*\n\s*", "| ", source)

    # Join lines: next line starting with | continues from previous
    source = re.sub(r"\n\s*\|", " |", source)

    # Join lines: line ending with = (but not ==, !=, <=, >=) continues
    source = re.sub(r"(?<![=!<>])=\s*\n\s*", "= ", source)

    # Join lines: line ending with , continues (tuples, lists, args)
    source = re.sub(r",\s*\n\s*", ", ", source)

    # Join lines: next line starting with else continues from previous
    source = re.sub(r"\n\s*else\b", " else", source)

    # Join lines: next line starting with + continues (expression continuation)
    source = re.sub(r"\n\s*\+", " +", source)

    # Join lines: next line starting with for continues (list comprehension)
    source = re.sub(r"\n\s*for\b", " for", source)

    # Join lines: next line starting with ] continues (closing bracket)
    source = re.sub(r"\n\s*\]", " ]", source)

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
    cleaned, annotations = _extract_param_annotations(source)
    preprocessed = _preprocess(cleaned)
    try:
        tree = get_parser().parse(preprocessed)
    except lark_exceptions.UnexpectedInput as e:
        raise ParseError(
            f"Syntax error: {e}",
            line=getattr(e, "line", None),
            column=getattr(e, "column", None),
        ) from e
    tree._param_annotations = annotations
    tree._original_source = source
    return tree


def parse_param_annotations(source: str) -> dict[int, str]:
    """Extract @param annotations from source without full parsing.

    Returns a dict mapping 0-based line index of the following statement
    to the raw @param option text.
    """
    _, annotations = _extract_param_annotations(source)
    return annotations
