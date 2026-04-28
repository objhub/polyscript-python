"""@profile annotation parsing and extraction API."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


class ProfileError(Exception):
    """Error raised when @profile parsing fails."""


@dataclass
class ProfileEntry:
    """A single preset entry in a @profile annotation."""
    name: str                        # Preset name (e.g. "S", "M", "L")
    values: dict[str, Any] = field(default_factory=dict)  # var -> value


@dataclass
class Profile:
    """Parsed @profile annotation."""
    entries: list[ProfileEntry] = field(default_factory=list)  # source order


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"""
    \s+                          |  # whitespace (skip)
    //[^\n]*                     |  # line comment (skip)
    \#[^\n]*                     |  # hash comment (skip)
    "(?:[^"\\]|\\.)*"            |  # double-quoted string
    -?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?  |  # number
    [a-zA-Z_]\w*                 |  # identifier / keyword
    [{}:,]                          # punctuation
    """,
    re.VERBOSE,
)


def _tokenize(text: str) -> list[tuple[str, str]]:
    """Tokenize profile body text into (type, value) pairs.

    Token types: STRING, NUMBER, IDENT, LBRACE, RBRACE, COLON, COMMA
    """
    tokens: list[tuple[str, str]] = []
    pos = 0
    while pos < len(text):
        m = _TOKEN_RE.match(text, pos)
        if m is None:
            raise ProfileError(
                f"Unexpected character at position {pos}: {text[pos]!r}"
            )
        val = m.group()
        pos = m.end()

        # Skip whitespace and comments
        if val[0] in (" ", "\t", "\n", "\r", "/", "#"):
            continue

        if val.startswith('"'):
            tokens.append(("STRING", val))
        elif val[0].isdigit() or (val[0] == "-" and len(val) > 1):
            tokens.append(("NUMBER", val))
        elif val[0].isalpha() or val[0] == "_":
            tokens.append(("IDENT", val))
        elif val == "{":
            tokens.append(("LBRACE", val))
        elif val == "}":
            tokens.append(("RBRACE", val))
        elif val == ":":
            tokens.append(("COLON", val))
        elif val == ",":
            tokens.append(("COMMA", val))
        else:
            raise ProfileError(f"Unexpected token: {val!r}")

    return tokens


# ---------------------------------------------------------------------------
# Parser (hand-written recursive descent)
# ---------------------------------------------------------------------------

def _parse_number(s: str) -> int | float:
    """Parse a numeric string to int or float."""
    try:
        return int(s)
    except ValueError:
        return float(s)


def _unquote(s: str) -> str:
    """Remove surrounding double quotes and unescape."""
    assert s.startswith('"') and s.endswith('"')
    inner = s[1:-1]
    # Handle basic escape sequences
    inner = inner.replace('\\"', '"')
    inner = inner.replace("\\\\", "\\")
    inner = inner.replace("\\n", "\n")
    inner = inner.replace("\\t", "\t")
    return inner


class _Parser:
    """Recursive-descent parser for @profile body."""

    def __init__(self, tokens: list[tuple[str, str]]) -> None:
        self.tokens = tokens
        self.pos = 0

    def _peek(self) -> tuple[str, str] | None:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def _advance(self) -> tuple[str, str]:
        if self.pos >= len(self.tokens):
            raise ProfileError("Unexpected end of input")
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _expect(self, ttype: str) -> tuple[str, str]:
        tok = self._advance()
        if tok[0] != ttype:
            raise ProfileError(
                f"Expected {ttype}, got {tok[0]} ({tok[1]!r})"
            )
        return tok

    def parse_profile(self) -> Profile:
        """Parse the entire profile body: { "Name": { ... }, ... }"""
        self._expect("LBRACE")

        entries: list[ProfileEntry] = []
        seen_names: set[str] = set()

        # Check for empty body
        peek = self._peek()
        if peek and peek[0] == "RBRACE":
            self._advance()
            raise ProfileError("Empty @profile body (at least one entry required)")

        # Parse first entry
        entry = self._parse_entry()
        if entry.name in seen_names:
            raise ProfileError(f"Duplicate preset name: {entry.name!r}")
        seen_names.add(entry.name)
        entries.append(entry)

        # Parse remaining entries
        while True:
            peek = self._peek()
            if peek is None:
                raise ProfileError("Unexpected end of input (missing closing '}')")
            if peek[0] == "RBRACE":
                self._advance()
                break
            if peek[0] == "COMMA":
                self._advance()
                # Allow trailing comma before closing brace
                peek = self._peek()
                if peek and peek[0] == "RBRACE":
                    self._advance()
                    break
                entry = self._parse_entry()
                if entry.name in seen_names:
                    raise ProfileError(f"Duplicate preset name: {entry.name!r}")
                seen_names.add(entry.name)
                entries.append(entry)
            else:
                raise ProfileError(
                    f"Expected ',' or '}}', got {peek[0]} ({peek[1]!r})"
                )

        # Check for trailing tokens
        if self.pos < len(self.tokens):
            tok = self.tokens[self.pos]
            raise ProfileError(
                f"Unexpected token after profile body: {tok[0]} ({tok[1]!r})"
            )

        return Profile(entries=entries)

    def _parse_entry(self) -> ProfileEntry:
        """Parse a single entry: "Name": { var: value, ... }"""
        name_tok = self._expect("STRING")
        name = _unquote(name_tok[1])
        self._expect("COLON")
        values = self._parse_values()
        return ProfileEntry(name=name, values=values)

    def _parse_values(self) -> dict[str, Any]:
        """Parse inner object: { ident: value, ... }"""
        self._expect("LBRACE")
        values: dict[str, Any] = {}

        peek = self._peek()
        if peek and peek[0] == "RBRACE":
            self._advance()
            return values  # empty entry is allowed

        # Parse first var assignment
        k, v = self._parse_var_assignment()
        values[k] = v

        # Parse remaining
        while True:
            peek = self._peek()
            if peek is None:
                raise ProfileError(
                    "Unexpected end of input (missing closing '}' in entry)"
                )
            if peek[0] == "RBRACE":
                self._advance()
                break
            if peek[0] == "COMMA":
                self._advance()
                # Allow trailing comma
                peek = self._peek()
                if peek and peek[0] == "RBRACE":
                    self._advance()
                    break
                k, v = self._parse_var_assignment()
                values[k] = v
            else:
                raise ProfileError(
                    f"Expected ',' or '}}', got {peek[0]} ({peek[1]!r})"
                )

        return values

    def _parse_var_assignment(self) -> tuple[str, Any]:
        """Parse: identifier : value"""
        ident_tok = self._expect("IDENT")
        ident = ident_tok[1]

        # Reject null
        if ident == "null":
            raise ProfileError("null is not allowed as an identifier in @profile")

        self._expect("COLON")
        value = self._parse_value()
        return ident, value

    def _parse_value(self) -> Any:
        """Parse a single value: number, string, true, false."""
        tok = self._advance()
        ttype, tval = tok

        if ttype == "NUMBER":
            return _parse_number(tval)
        if ttype == "STRING":
            return _unquote(tval)
        if ttype == "IDENT":
            if tval == "true":
                return True
            if tval == "false":
                return False
            if tval == "null":
                raise ProfileError("null value is not allowed in @profile")
            raise ProfileError(f"Unexpected identifier as value: {tval!r}")

        raise ProfileError(f"Expected value, got {ttype} ({tval!r})")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_profile_block(text: str) -> Profile:
    """Parse the body of a @profile annotation (the ``{...}`` part).

    Args:
        text: The ``{...}`` text including outer braces.

    Returns:
        Parsed Profile object.

    Raises:
        ProfileError: On syntax or semantic errors.
    """
    tokens = _tokenize(text)
    if not tokens:
        raise ProfileError("Empty @profile body")
    parser = _Parser(tokens)
    return parser.parse_profile()


# ---------------------------------------------------------------------------
# Source-level extraction
# ---------------------------------------------------------------------------

# Regex to find @profile followed by its brace-delimited body in source.
_PROFILE_START_RE = re.compile(r"@profile\s*\{")


def _find_brace_block(source: str, start: int) -> str:
    """Extract a brace-balanced block starting at ``start`` (which points to '{').

    Returns the substring including the outer braces.
    Raises ProfileError if braces are unbalanced.
    """
    depth = 0
    i = start
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
                    return source[start : i + 1]
        i += 1

    raise ProfileError("Unbalanced braces in @profile body")


def extract_profile(source: str) -> Profile | None:
    """Extract a ``@profile`` annotation from PolyScript source.

    Args:
        source: Full PolyScript source text.

    Returns:
        Parsed Profile, or None if no ``@profile`` is present.

    Raises:
        ProfileError: If multiple ``@profile`` annotations are found,
            or if the body has syntax/semantic errors.
    """
    matches = list(_PROFILE_START_RE.finditer(source))

    if not matches:
        return None

    if len(matches) > 1:
        raise ProfileError("Multiple @profile annotations found (only one allowed per file)")

    m = matches[0]
    # The '{' is the last character of the match
    brace_start = m.end() - 1
    block = _find_brace_block(source, brace_start)

    return parse_profile_block(block)
