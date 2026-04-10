"""Tests for cone, torus, mirror, and spline features."""

import pytest
from polyscript.parser import parse
from polyscript.transformer import transform
from polyscript.codegen_ocp import generate
from polyscript import ast_nodes as ast


def _parse_and_gen(src: str) -> str:
    tree = parse(src)
    prog = transform(tree)
    return generate(prog)


# ---------------------------------------------------------------------------
# Parsing & AST
# ---------------------------------------------------------------------------

class TestConeAST:
    def test_parse_cone_positional(self):
        tree = parse("cone 10 5 2")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.Cone)
        assert isinstance(stmt.height, ast.NumberLit)
        assert stmt.height.value == 10
        assert stmt.r1.value == 5
        assert stmt.r2.value == 2

    def test_parse_cone_kwargs(self):
        tree = parse("cone h:10 r1:5 r2:0")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.Cone)
        assert stmt.height.value == 10
        assert stmt.r1.value == 5
        assert stmt.r2.value == 0

    def test_parse_cone_full_cone(self):
        """r2=0 makes a full cone."""
        tree = parse("cone 10 5 0")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.Cone)
        assert stmt.r2.value == 0


class TestTorusAST:
    def test_parse_torus_positional(self):
        tree = parse("torus 10 3")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.Torus)
        assert stmt.r1.value == 10
        assert stmt.r2.value == 3

    def test_parse_torus_kwargs(self):
        tree = parse("torus r1:10 r2:3")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.Torus)
        assert stmt.r1.value == 10
        assert stmt.r2.value == 3


class TestMirrorAST:
    def test_parse_mirror_x(self):
        tree = parse('box 10 10 10 | mirror "X"')
        prog = transform(tree)
        pipeline = prog.statements[0]
        assert isinstance(pipeline, ast.Pipeline)
        assert isinstance(pipeline.operations[0], ast.Mirror)
        assert pipeline.operations[0].axis == "X"

    def test_parse_mirror_y(self):
        tree = parse('box 10 10 10 | mirror "Y"')
        prog = transform(tree)
        pipeline = prog.statements[0]
        assert isinstance(pipeline.operations[0], ast.Mirror)
        assert pipeline.operations[0].axis == "Y"

    def test_parse_mirror_z(self):
        tree = parse('box 10 10 10 | mirror "Z"')
        prog = transform(tree)
        pipeline = prog.statements[0]
        assert isinstance(pipeline.operations[0], ast.Mirror)
        assert pipeline.operations[0].axis == "Z"


class TestSplineAST:
    def test_parse_spline(self):
        tree = parse("spline [(0,0,0), (5,5,5), (10,0,10)]")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.SplinePath)
        assert isinstance(stmt.points, ast.ListLit)
        assert len(stmt.points.values) == 3


# ---------------------------------------------------------------------------
# Code generation (CadQuery)
# ---------------------------------------------------------------------------

class TestConeCodegen:
    def test_codegen_cone(self):
        code = _parse_and_gen("cone 10 5 2")
        assert ".cone(10, 5, 2)" in code

    def test_codegen_cone_in_pipeline(self):
        code = _parse_and_gen('cone 10 5 0 | translate 5 0 0')
        assert ".cone(10, 5, 0)" in code
        assert ".translate" in code


class TestTorusCodegen:
    def test_codegen_torus(self):
        code = _parse_and_gen("torus 10 3")
        assert "makeTorus" in code
        assert "10" in code
        assert "3" in code

    def test_codegen_torus_in_pipeline(self):
        code = _parse_and_gen('torus 10 3 | rotate 0 0 45')
        assert "makeTorus" in code
        assert ".rotate" in code


class TestMirrorCodegen:
    def test_codegen_mirror_x(self):
        code = _parse_and_gen('box 10 10 10 | mirror "X"')
        assert '.mirror("YZ")' in code

    def test_codegen_mirror_y(self):
        code = _parse_and_gen('box 10 10 10 | mirror "Y"')
        assert '.mirror("XZ")' in code

    def test_codegen_mirror_z(self):
        code = _parse_and_gen('box 10 10 10 | mirror "Z"')
        assert '.mirror("XY")' in code


class TestSplineCodegen:
    def test_codegen_spline(self):
        code = _parse_and_gen("spline [(0,0,0), (5,5,5), (10,0,10)]")
        assert ".spline(" in code

    def test_codegen_spline_sweep(self):
        code = _parse_and_gen(
            'circle 2 | sweep (spline [(0,0,0), (5,5,5), (10,0,10)])'
        )
        assert ".spline(" in code
        assert ".sweep(" in code


# ---------------------------------------------------------------------------
# NAME keyword exclusion (grammar)
# ---------------------------------------------------------------------------

class TestKeywordExclusion:
    """Ensure cone, torus, mirror, spline are not parsed as variable names."""

    def test_cone_not_varref(self):
        tree = parse("cone 10 5 2")
        prog = transform(tree)
        assert isinstance(prog.statements[0], ast.Cone)

    def test_torus_not_varref(self):
        tree = parse("torus 10 3")
        prog = transform(tree)
        assert isinstance(prog.statements[0], ast.Torus)

    def test_spline_not_varref(self):
        tree = parse("spline [(0,0,0), (1,1,1)]")
        prog = transform(tree)
        assert isinstance(prog.statements[0], ast.SplinePath)

    def test_mirror_is_pipe_op(self):
        tree = parse('sphere 5 | mirror "X"')
        prog = transform(tree)
        pipeline = prog.statements[0]
        assert isinstance(pipeline, ast.Pipeline)
        assert isinstance(pipeline.operations[0], ast.Mirror)
