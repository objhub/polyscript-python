"""PolyScript executor - orchestrates parse, transform, codegen, and execution."""

from __future__ import annotations

from pathlib import Path

from .parser import parse
from .transformer import transform
from .codegen import generate
from . import ast_nodes as ast
from .errors import ExecutionError, ParseError

def _resolve_import(import_path: str, source_dir: Path | None = None) -> Path:
    """Resolve an import path to a .poly file relative to the source file."""
    name = import_path if import_path.endswith(".poly") else import_path + ".poly"

    if source_dir:
        candidate = source_dir / name
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
    """Compile PolyScript source to Python code.

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


def _apply_overrides(program: ast.Program, overrides: dict[str, object]) -> None:
    """Replace the value of top-level Assignment nodes with override values."""
    for stmt in program.statements:
        if isinstance(stmt, ast.Assignment) and stmt.name in overrides:
            val = overrides[stmt.name]
            if isinstance(val, bool):
                stmt.value = ast.BoolConst(value=val)
            elif isinstance(val, int):
                if val < 0:
                    stmt.value = ast.UnaryNeg(operand=ast.NumberLit(value=-val))
                else:
                    stmt.value = ast.NumberLit(value=val)
            elif isinstance(val, float):
                if val < 0:
                    stmt.value = ast.UnaryNeg(operand=ast.NumberLit(value=-val))
                else:
                    stmt.value = ast.NumberLit(value=val)
            elif isinstance(val, str):
                stmt.value = ast.StringLit(value=val)
            # Other types: leave unchanged


def execute(
    source: str,
    source_dir: Path | None = None,
    overrides: dict[str, object] | None = None,
):
    """Compile and execute PolyScript, returning the result."""
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
        "None": None,
        "True": True,
        "False": False,
    }
    namespace = {"cq": cq, "math": math, "__builtins__": safe_builtins}

    try:
        exec(code, namespace)
    except Exception as e:
        raise ExecutionError(f"Execution error: {e}\n\nGenerated code:\n{code}") from e

    result = namespace.get("_result")

    # If the result is a list of shapes, union them into a single shape
    # (PolyScript spec: multiple top-level shapes are implicitly unioned)
    if isinstance(result, list):
        from .ocp_kernel import Workplane as _WP
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

    from .ocp_kernel import exporters, ExportTypes
    exporters.export(result, str(path), path.suffix.lower())
