"""@param annotation parsing and parameter extraction API."""

from __future__ import annotations

import json
import re
import warnings
from dataclasses import dataclass, field
from typing import Any

from . import ast_nodes as ast
from .parser import parse
from .profile import Profile, extract_profile
from .transformer import transform


# ---------------------------------------------------------------------------
# @param raw text parser
# ---------------------------------------------------------------------------

def _tokenize_param_raw(raw: str) -> list[str]:
    """Tokenize a @param raw string into individual tokens.

    Handles quoted strings, bracket lists, key:value pairs where value
    can be a quoted string or bracket list, and bare values.
    """
    tokens: list[str] = []
    i = 0
    n = len(raw)

    def _skip_quoted(pos: int) -> int:
        """Skip a quoted string starting at pos (which points to opening quote).
        Returns index after closing quote."""
        pos += 1
        while pos < n and raw[pos] != '"':
            if raw[pos] == "\\":
                pos += 1
            pos += 1
        return pos + 1  # past closing quote

    def _skip_bracket(pos: int) -> int:
        """Skip a bracket list starting at pos (which points to '[').
        Returns index after closing ']'."""
        depth = 1
        pos += 1
        while pos < n and depth > 0:
            if raw[pos] == "[":
                depth += 1
            elif raw[pos] == "]":
                depth -= 1
            elif raw[pos] == '"':
                pos = _skip_quoted(pos)
                continue
            pos += 1
        return pos

    while i < n:
        c = raw[i]
        if c in (" ", "\t"):
            i += 1
            continue
        if c == "#":
            # Comment: stop tokenizing
            break
        if c == '"':
            j = _skip_quoted(i)
            tokens.append(raw[i:j])
            i = j
        elif c == "[":
            j = _skip_bracket(i)
            tokens.append(raw[i:j])
            i = j
        else:
            # Bare token or key:value pair
            # Scan for word chars, then check for ':'
            j = i
            while j < n and raw[j] not in (" ", "\t", "#"):
                if raw[j] == ":" and j > i:
                    # This is a key:value pair. Now scan the value part.
                    j += 1  # skip ':'
                    if j < n and raw[j] == '"':
                        j = _skip_quoted(j)
                    elif j < n and raw[j] == '[':
                        j = _skip_bracket(j)
                    else:
                        # Bare value
                        while j < n and raw[j] not in (" ", "\t", "#"):
                            j += 1
                    break
                j += 1
            tokens.append(raw[i:j])
            i = j
    return tokens


def _parse_number(s: str) -> int | float:
    """Parse a numeric string to int or float."""
    try:
        v = int(s)
        return v
    except ValueError:
        return float(s)


def _parse_value(s: str) -> Any:
    """Parse a value token into a Python value."""
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1]
    if s.startswith("[") and s.endswith("]"):
        # Parse bracket list: ["M3", "M4"] or [1, 2, 3]
        inner = s[1:-1].strip()
        if not inner:
            return []
        items = []
        # Split by comma, respecting quotes
        parts = re.split(r',\s*', inner)
        for part in parts:
            part = part.strip()
            items.append(_parse_value(part))
        return items
    if s == "true":
        return True
    if s == "false":
        return False
    try:
        return _parse_number(s)
    except (ValueError, OverflowError):
        return s


_NUM_PAT = r'-?\d+(?:\.\d+)?(?:e[+-]?\d+)?'
_RANGE_RE = re.compile(
    rf'^({_NUM_PAT})'
    rf'\.\.({_NUM_PAT})'
    rf'(?:\.\.({_NUM_PAT}))?$',
    re.IGNORECASE,
)

_KV_RE = re.compile(r'^(\w+):(.+)$')


def parse_param_options(raw: str) -> dict[str, Any]:
    """Parse @param option text into an options dict.

    Supports:
    - Range shorthand: 1..100 or 1..100..0.5
    - Key:value pairs: min:1 max:100 step:0.5 desc:"text"
    """
    if not raw:
        return {}

    options: dict[str, Any] = {}
    tokens = _tokenize_param_raw(raw)

    i = 0
    # Check for range shorthand at start
    if tokens and _RANGE_RE.match(tokens[0]):
        m = _RANGE_RE.match(tokens[0])
        assert m is not None
        options["min"] = _parse_number(m.group(1))
        options["max"] = _parse_number(m.group(2))
        if m.group(3) is not None:
            options["step"] = _parse_number(m.group(3))
        i = 1

    # Parse remaining key:value pairs
    while i < len(tokens):
        token = tokens[i]
        kv = _KV_RE.match(token)
        if kv:
            key = kv.group(1)
            val_str = kv.group(2)
            # Value might be a quoted string that was split, check next token
            if val_str.startswith('"') and not val_str.endswith('"'):
                # Multi-word quoted string: need to find closing quote
                # This shouldn't happen with our tokenizer, but handle gracefully
                options[key] = _parse_value(val_str)
            else:
                options[key] = _parse_value(val_str)
        i += 1

    return options


# ---------------------------------------------------------------------------
# AST annotation attachment
# ---------------------------------------------------------------------------

def _extract_param_by_varname(source: str) -> dict[str, str]:
    """Extract @param annotations mapped to the variable name they annotate.

    Scans the source line by line. When a @param line is found, the next
    non-blank, non-comment line is checked for a variable assignment pattern
    (NAME = ...). If found, the annotation is mapped to that variable name.
    """
    import re
    _assign_re = re.compile(r'^(?:\$)?(\w+)\s*=(?!=)')

    lines = source.split("\n")
    result: dict[str, str] = {}
    pending_param: str | None = None

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("@param"):
            pending_param = stripped[len("@param"):].strip()
            continue
        if pending_param is not None:
            m = _assign_re.match(stripped)
            if m:
                result[m.group(1)] = pending_param
            pending_param = None

    return result


def attach_param_annotations(
    program: ast.Program, annotations: dict[int, str],
    source: str | None = None,
) -> ast.Program:
    """Attach @param annotations to Assignment nodes.

    Uses variable-name matching: scans the original source to determine
    which variable name each @param annotates, then attaches to the
    matching Assignment node.

    If source is not provided, falls back to sequential matching based
    on the annotations dict order.
    """
    if not annotations:
        return program

    # If we have the original source, use name-based matching
    # (more reliable than line-number matching)
    if source is not None:
        by_name = _extract_param_by_varname(source)
    else:
        by_name = None

    if by_name:
        for stmt in program.statements:
            if isinstance(stmt, ast.Assignment) and stmt.name in by_name:
                options = parse_param_options(by_name[stmt.name])
                stmt.annotation = ast.ParamAnnotation(options=options)
    else:
        # Fallback: sequential matching of annotations to assignments
        sorted_annots = sorted(annotations.items())
        annot_iter = iter(sorted_annots)
        current_annot = next(annot_iter, None)
        for stmt in program.statements:
            if isinstance(stmt, ast.Assignment) and current_annot is not None:
                options = parse_param_options(current_annot[1])
                stmt.annotation = ast.ParamAnnotation(options=options)
                current_annot = next(annot_iter, None)

    return program


# ---------------------------------------------------------------------------
# Parameter extraction API
# ---------------------------------------------------------------------------

@dataclass
class ParamInfo:
    """Information about a single @param-annotated variable."""
    name: str = ""
    type: str = ""
    default: Any = None
    min: float | int | None = None
    max: float | int | None = None
    step: float | int | None = None
    desc: str | None = None
    choices: list[Any] | None = None
    group: str = "General"
    hidden: bool = False


@dataclass
class ParamSet:
    """Extracted parameter information from a PolyScript source."""
    params: list[ParamInfo] = field(default_factory=list)
    parameter_sets: dict[str, dict[str, Any]] = field(default_factory=dict)
    profile: Profile | None = None


def _infer_type(value: Any) -> str:
    """Infer parameter type from a default value."""
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    return "float"


def _eval_default(node: ast.Node | None) -> Any:
    """Evaluate a simple AST node to a Python value for defaults."""
    if node is None:
        return None
    if isinstance(node, ast.NumberLit):
        return node.value
    if isinstance(node, ast.StringLit):
        return node.value
    if isinstance(node, ast.BoolConst):
        return node.value
    if isinstance(node, ast.UnaryNeg):
        inner = _eval_default(node.operand)
        if isinstance(inner, (int, float)):
            return -inner
    if isinstance(node, ast.BinOp):
        left = _eval_default(node.left)
        right = _eval_default(node.right)
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            ops = {
                "+": lambda a, b: a + b,
                "-": lambda a, b: a - b,
                "*": lambda a, b: a * b,
                "/": lambda a, b: a / b,
                "//": lambda a, b: a // b,
                "%": lambda a, b: a % b,
                "**": lambda a, b: a ** b,
            }
            if node.op in ops:
                return ops[node.op](left, right)
    return None


def extract_params(source: str, json_str: str | None = None) -> ParamSet:
    """Extract parameter information from PolyScript source.

    Args:
        source: PolyScript source code.
        json_str: Optional JSON string with additional metadata / presets.

    Returns:
        ParamSet with extracted parameter information.
    """
    tree = parse(source)
    program = transform(tree)
    # transform() already calls attach_param_annotations via the tree metadata

    # Collect annotated assignments
    params: list[ParamInfo] = []
    for stmt in program.statements:
        if isinstance(stmt, ast.Assignment) and stmt.annotation is not None:
            opts = stmt.annotation.options
            default_val = _eval_default(stmt.value)

            # Determine type
            explicit_type = opts.get("type")
            if explicit_type:
                param_type = str(explicit_type)
            else:
                param_type = _infer_type(default_val)

            info = ParamInfo(
                name=stmt.name,
                type=param_type,
                default=default_val,
                min=opts.get("min"),
                max=opts.get("max"),
                step=opts.get("step"),
                desc=opts.get("desc"),
                choices=opts.get("choices"),
                group=opts.get("group", "General"),
                hidden=opts.get("hidden", False),
            )
            params.append(info)

    result = ParamSet(params=params)

    # Extract @profile annotation from source
    result.profile = extract_profile(source)

    # Merge JSON metadata if provided
    if json_str:
        _merge_json(result, json_str)

    return result


def _merge_json(param_set: ParamSet, json_str: str) -> None:
    """Merge JSON metadata into the param set.

    Rules:
    - Variable existence: source is authoritative (JSON-only params are ignored)
    - Metadata: JSON overrides source
    - Default values: parameterSets > JSON default > source declaration
    """
    data = json.loads(json_str)

    # Build lookup for quick access
    param_map = {p.name: p for p in param_set.params}

    # Merge parameter metadata
    json_params = data.get("params", data.get("parameters", {}))
    if isinstance(json_params, dict):
        for name, meta in json_params.items():
            if name not in param_map:
                continue  # source is authoritative
            p = param_map[name]
            if "min" in meta:
                p.min = meta["min"]
            if "max" in meta:
                p.max = meta["max"]
            if "step" in meta:
                p.step = meta["step"]
            if "desc" in meta:
                p.desc = meta["desc"]
            if "choices" in meta:
                p.choices = meta["choices"]
            if "group" in meta:
                p.group = meta["group"]
            if "type" in meta:
                p.type = meta["type"]
            if "hidden" in meta:
                p.hidden = meta["hidden"]
            if "default" in meta:
                p.default = meta["default"]
    elif isinstance(json_params, list):
        for meta in json_params:
            name = meta.get("name")
            if not name or name not in param_map:
                continue
            p = param_map[name]
            for key in ("min", "max", "step", "desc", "choices", "group", "type", "hidden", "default"):
                if key in meta:
                    setattr(p, key, meta[key])

    # Extract parameter sets (presets)
    presets = data.get("parameterSets", {})
    if isinstance(presets, dict) and presets:
        warnings.warn(
            "JSON parameterSets is deprecated, use @profile annotation instead",
            DeprecationWarning,
            stacklevel=3,
        )
        param_set.parameter_sets = presets
        # Apply default preset values: parameterSets values override defaults
        # But we don't override here -- that happens at evaluation time
