"""Code generation for PolyScript AST."""

from __future__ import annotations

from . import ast_nodes as ast


def generate(program: ast.Program) -> str:
    """Generate Python code from a PolyScript AST."""
    from .codegen_ocp import OCPCodegen
    gen = OCPCodegen()
    return gen.generate(program)
