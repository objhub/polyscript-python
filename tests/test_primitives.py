"""Tests for 3D and 2D primitive compilation."""

import pytest
from polyscript.executor import compile_source
from polyscript.parser import parse
from polyscript.transformer import transform
from polyscript.codegen_ocp import generate
from polyscript import ast_nodes as ast


def _parse_and_gen(src: str) -> str:
    tree = parse(src)
    prog = transform(tree)
    return generate(prog)


class Test3DPrimitives:
    def test_box(self):
        code = compile_source("box 80 60 10")
        assert '.box(80, 60, 10)' in code

    def test_cylinder(self):
        code = compile_source("cylinder 15 30")
        assert '.cylinder(30, 15)' in code

    def test_sphere(self):
        code = compile_source("sphere 10")
        assert '.sphere(10)' in code


class Test2DPrimitives:
    def test_rect(self):
        code = compile_source("rect 60 40")
        assert '.rect(60, 40)' in code

    def test_circle(self):
        code = compile_source("circle 5")
        assert '.circle(5)' in code

    def test_ellipse(self):
        code = compile_source("ellipse 10 5")
        assert '.ellipse(10, 5)' in code

    def test_polyline(self):
        code = compile_source("polyline [(0, 0), (10, 0), (5, 10)]")
        assert '.polyline(' in code
        assert '.close()' in code

    def test_polygon(self):
        code = compile_source("polygon 6 8")
        assert '.polygon(6, 8 * 2)' in code

    def test_polygon_as_source(self):
        code = compile_source("polygon 6 8 | extrude 10")
        assert '.polygon(6, 8 * 2)' in code
        assert '.extrude(10' in code

    def test_text(self):
        code = compile_source('text "Hello"')
        assert '.text(' in code
        assert "'Hello'" in code

    def test_text_with_size(self):
        code = compile_source('text "Hi" size:20')
        assert '.text(' in code
        assert '20' in code


class TestPathPrimitives:
    def test_line(self):
        code = compile_source("line (0, 0) (10, 10)")
        assert '.moveTo(' in code
        assert '.lineTo(' in code

    def test_helix(self):
        code = compile_source("helix 2 10 5")
        assert 'makeHelix' in code
        assert 'pitch=2' in code

    def test_bezier(self):
        code = compile_source("bezier [(0, 0), (5, 10), (10, 0)]")
        assert '.spline(' in code


class TestImplicitUnion:
    def test_multiple_toplevel_shapes(self):
        """Multiple top-level shapes are implicitly unioned."""
        code = compile_source("box 10 10 10\ncylinder 20 5 at:30 0")
        assert '.union(' in code

    def test_single_toplevel_shape(self):
        """Single top-level shape should not produce union."""
        code = compile_source("box 10 10 10")
        assert '.union(' not in code

    def test_assignment_not_in_union(self):
        """Assignments should not be included in implicit union."""
        code = compile_source("$a = box 10 10 10\ncylinder 20 5")
        # Only one top-level shape expression (cylinder), so no union
        assert '.union(' not in code

    def test_three_toplevel_shapes(self):
        """Three top-level shapes produce a union chain."""
        code = compile_source("box 10 10 10\ncylinder 20 5\nsphere 8")
        # Should have two .union() calls
        assert code.count('.union(') == 2


# ---------------------------------------------------------------------------
# Cone AST & Codegen
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


class TestConeCodegen:
    def test_codegen_cone(self):
        code = _parse_and_gen("cone 10 5 2")
        assert ".cone(10, 5, 2)" in code

    def test_codegen_cone_in_pipeline(self):
        code = _parse_and_gen('cone 10 5 0 | translate 5 0 0')
        assert ".cone(10, 5, 0)" in code
        assert ".translate" in code


# ---------------------------------------------------------------------------
# Torus AST & Codegen
# ---------------------------------------------------------------------------

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


class TestTorusCodegen:
    def test_codegen_torus(self):
        code = _parse_and_gen("torus 10 3")
        assert ".torus(10, 3)" in code

    def test_codegen_torus_in_pipeline(self):
        code = _parse_and_gen('torus 10 3 | rotate 0 0 45')
        assert ".torus(10, 3)" in code
        assert ".rotate" in code


# ---------------------------------------------------------------------------
# Spline AST & Codegen
# ---------------------------------------------------------------------------

class TestSplineAST:
    def test_parse_spline(self):
        tree = parse("spline [(0,0,0), (5,5,5), (10,0,10)]")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.SplinePath)
        assert isinstance(stmt.points, ast.ListLit)
        assert len(stmt.points.values) == 3


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
# Keyword exclusion (grammar)
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
