"""PolyScript executor - orchestrates parse, transform, codegen, and execution."""

from __future__ import annotations

from pathlib import Path

from .parser import parse
from .transformer import transform
from .codegen import generate
from . import ast_nodes as ast
from .errors import ExecutionError, ParseError

def _resolve_import(import_path: str, source_dir: Path | None = None) -> Path:
    """Resolve an import path to a .poly file relative to the source file.

    Security: rejects absolute paths, parent-directory traversal (``..``),
    and symlinks that escape *source_dir*.
    """
    # Reject absolute paths
    if import_path.startswith("/") or import_path.startswith("\\"):
        raise ParseError(f'Absolute import path not allowed: "{import_path}"')
    # Reject parent directory traversal
    if ".." in import_path:
        raise ParseError(
            f'Parent directory traversal not allowed in import: "{import_path}"'
        )

    name = import_path if import_path.endswith(".poly") else import_path + ".poly"

    if source_dir:
        resolved_source_dir = source_dir.resolve()
        candidate = (source_dir / name).resolve()
        # Verify the resolved path stays within the source directory
        try:
            candidate.relative_to(resolved_source_dir)
        except ValueError:
            raise ParseError(
                f'Import path escapes source directory: "{import_path}"'
            )
        if candidate.exists():
            return candidate

    raise ParseError(f'Cannot find import "{import_path}"')


def _process_imports(
    program: ast.Program,
    source_dir: Path | None = None,
    imported: set[str] | None = None,
) -> ast.Program:
    """Resolve Import nodes: load, parse, and merge FuncDefs."""
    if imported is None:
        imported = set()

    new_stmts: list[ast.Node] = []
    for stmt in program.statements:
        if isinstance(stmt, ast.Import):
            path = _resolve_import(stmt.path, source_dir)
            resolved = str(path.resolve())
            if resolved in imported:
                continue  # skip circular / duplicate imports
            imported.add(resolved)

            # Parse and transform the imported file
            source = path.read_text()
            tree = parse(source)
            imported_ast = transform(tree)

            # Recursively resolve imports in imported file
            imported_ast = _process_imports(
                imported_ast, source_dir=path.parent, imported=imported
            )

            # Extract only FuncDef and Assignment nodes
            for imp_stmt in imported_ast.statements:
                if isinstance(imp_stmt, (ast.FuncDef, ast.Assignment)):
                    new_stmts.append(imp_stmt)
        else:
            new_stmts.append(stmt)

    return ast.Program(statements=new_stmts)


def compile_source(
    source: str,
    source_dir: Path | None = None,
    overrides: dict[str, object] | None = None,
) -> str:
    """Compile PolyScript source to Python code string.

    This is used by ``--emit-python`` and ``-o file.py``.  No ``exec()`` is
    performed -- the caller gets the generated Python source back.

    Args:
        source: PolyScript source code.
        source_dir: Directory for resolving imports.
        overrides: Optional dict of variable name -> value to override
            top-level assignments.
    """
    tree = parse(source)
    program = transform(tree)
    program = _process_imports(program, source_dir=source_dir)

    # Apply overrides to top-level assignments
    if overrides:
        _apply_overrides(program, overrides)

    return generate(program)


def _value_to_ast_node(val: object) -> ast.Node | None:
    """Convert a Python value to an AST literal node.

    Returns None for unsupported types (P12: extracted helper).
    """
    if isinstance(val, bool):
        return ast.BoolConst(value=val)
    if isinstance(val, (int, float)):
        if val < 0:
            return ast.UnaryNeg(operand=ast.NumberLit(value=-val))
        return ast.NumberLit(value=val)
    if isinstance(val, str):
        return ast.StringLit(value=val)
    return None


def _apply_overrides(program: ast.Program, overrides: dict[str, object]) -> None:
    """Replace the value of top-level Assignment nodes with override values.

    S9: If the assignment carries a @param annotation with min/max bounds,
    numeric overrides are validated against those bounds.
    """
    for stmt in program.statements:
        if isinstance(stmt, ast.Assignment) and stmt.name in overrides:
            val = overrides[stmt.name]

            # S9: validate @param min/max range
            if (
                isinstance(val, (int, float))
                and not isinstance(val, bool)
                and stmt.annotation is not None
            ):
                opts = stmt.annotation.options
                param_min = opts.get("min")
                param_max = opts.get("max")
                if param_min is not None and val < param_min:
                    raise ParseError(
                        f"Override '{stmt.name}={val}' is below "
                        f"minimum ({param_min})"
                    )
                if param_max is not None and val > param_max:
                    raise ParseError(
                        f"Override '{stmt.name}={val}' exceeds "
                        f"maximum ({param_max})"
                    )

            node = _value_to_ast_node(val)
            if node is not None:
                stmt.value = node
            # Unsupported types: leave unchanged


def _default_use_evaluator() -> bool:
    import os
    env = os.environ.get("POLY_USE_EVALUATOR")
    if env is not None:
        return env not in ("0", "")
    return True  # Phase 5: evaluator is the default


def execute(
    source: str,
    source_dir: Path | None = None,
    overrides: dict[str, object] | None = None,
    use_evaluator: bool | None = None,
):
    """Compile and execute PolyScript, returning the result.

    Args:
        source: PolyScript source code.
        source_dir: Directory for resolving imports.
        overrides: Optional dict of variable name -> value to override
            top-level assignments.
        use_evaluator: If True (default), use the AST-walking evaluator.
            If False, use legacy codegen + exec path.
            If None, consult POLY_USE_EVALUATOR env var or default to True.
    """
    if use_evaluator is None:
        use_evaluator = _default_use_evaluator()
    if use_evaluator:
        return _execute_evaluator(source, source_dir=source_dir, overrides=overrides)
    return _execute_codegen(source, source_dir=source_dir, overrides=overrides)


def _execute_evaluator(
    source: str,
    source_dir: Path | None = None,
    overrides: dict[str, object] | None = None,
):
    """Execute PolyScript using the AST-walking evaluator (no exec())."""
    from .evaluator import Evaluator

    tree = parse(source)
    program = transform(tree)
    program = _process_imports(program, source_dir=source_dir)

    # S9: validate @param min/max before evaluation
    if overrides:
        _apply_overrides(program, overrides)

    evaluator = Evaluator(overrides=overrides)
    try:
        result = evaluator.evaluate(program)
    except Exception as e:
        raise ExecutionError(f"Execution error: {e}") from e

    # If the result is a list of shapes, union them into a single shape
    from .ocp_kernel import Workplane
    if isinstance(result, list):
        merged = None
        for item in result:
            if item is None:
                continue
            if merged is None:
                merged = item
            elif isinstance(merged, Workplane) and isinstance(item, Workplane):
                merged = merged.union(item)
        result = merged

    return result


def _execute_codegen(
    source: str,
    source_dir: Path | None = None,
    overrides: dict[str, object] | None = None,
):
    """Legacy path: compile to Python, then exec().

    Retained for ``POLY_USE_EVALUATOR=0`` and ``use_evaluator=False``.
    """
    code = compile_source(source, source_dir=source_dir, overrides=overrides)

    from . import ocp_kernel as cq
    import math

    # Restricted import: only allow modules used by generated code
    _ALLOWED_IMPORTS = {"polyscript", "math"}

    def _safe_import(name, *args, **kwargs):
        if name.split(".")[0] not in _ALLOWED_IMPORTS:
            raise ImportError(f"Import of '{name}' is not allowed")
        return __import__(name, *args, **kwargs)

    safe_builtins = {
        "__import__": _safe_import,
        "range": range,
        "len": len,
        "abs": abs,
        "min": min,
        "max": max,
        "round": round,
        "int": int,
        "float": float,
        "hasattr": hasattr,
        "None": None,
        "True": True,
        "False": False,
    }
    namespace = {"cq": cq, "math": math, "__builtins__": safe_builtins}

    try:
        exec(code, namespace)  # noqa: S102
    except Exception as e:
        raise ExecutionError(f"Execution error: {e}\n\nGenerated code:\n{code}") from e

    result = namespace.get("_result")

    # If the result is a list of shapes, union them into a single shape
    # (PolyScript spec: multiple top-level shapes are implicitly unioned)
    if isinstance(result, list):
        merged = None
        for item in result:
            if item is None:
                continue
            if merged is None:
                merged = item
            else:
                merged = merged.union(item)
        result = merged

    return result


def export(result, output_path: str):
    """Export result to file based on extension."""
    path = Path(output_path)

    if result is None:
        return  # library-only file, nothing to export

    from .ocp_kernel import exporters
    exporters.export(result, str(path), path.suffix.lower())
