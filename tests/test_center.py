"""Tests for center: keyword argument on 2D/3D primitives."""

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
# Parsing & AST — center kwarg is captured
# ---------------------------------------------------------------------------

class TestCenterParsing:
    """center: kwarg is parsed and stored on AST nodes."""

    def test_box_center_false(self):
        tree = parse("box 10 20 30 center:false")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.Box)
        assert isinstance(stmt.center, ast.BoolConst)
        assert stmt.center.value is False

    def test_box_center_true(self):
        tree = parse("box 10 20 30 center:true")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.Box)
        assert isinstance(stmt.center, ast.BoolConst)
        assert stmt.center.value is True

    def test_box_center_tuple(self):
        tree = parse("box 10 20 30 center:(false, true, false)")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.Box)
        assert isinstance(stmt.center, ast.TupleLit)
        assert len(stmt.center.values) == 3
        assert stmt.center.values[0].value is False
        assert stmt.center.values[1].value is True
        assert stmt.center.values[2].value is False

    def test_box_no_center(self):
        tree = parse("box 10 20 30")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.Box)
        assert stmt.center is None

    def test_cylinder_center(self):
        tree = parse("cylinder 5 10 center:false")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.Cylinder)
        assert isinstance(stmt.center, ast.BoolConst)
        assert stmt.center.value is False

    def test_sphere_center(self):
        tree = parse("sphere 5 center:false")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.Sphere)
        assert isinstance(stmt.center, ast.BoolConst)
        assert stmt.center.value is False

    def test_cone_center(self):
        tree = parse("cone 10 5 2 center:false")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.Cone)
        assert isinstance(stmt.center, ast.BoolConst)
        assert stmt.center.value is False

    def test_torus_center(self):
        tree = parse("torus 10 3 center:false")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.Torus)
        assert isinstance(stmt.center, ast.BoolConst)
        assert stmt.center.value is False

    def test_rect_center(self):
        tree = parse("rect 10 20 center:false")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.Rect)
        assert isinstance(stmt.center, ast.BoolConst)
        assert stmt.center.value is False

    def test_circle_center(self):
        tree = parse("circle 5 center:false")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.Circle)
        assert isinstance(stmt.center, ast.BoolConst)
        assert stmt.center.value is False

    def test_ellipse_center(self):
        tree = parse("ellipse 10 5 center:false")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.Ellipse)
        assert isinstance(stmt.center, ast.BoolConst)
        assert stmt.center.value is False

    def test_rect_center_tuple(self):
        tree = parse("rect 10 20 center:(false, true)")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.Rect)
        assert isinstance(stmt.center, ast.TupleLit)
        assert len(stmt.center.values) == 2
        assert stmt.center.values[0].value is False
        assert stmt.center.values[1].value is True


# ---------------------------------------------------------------------------
# Code generation — center: generates centered= kwarg
# ---------------------------------------------------------------------------

class TestCenterCodegen3D:
    """Code generation for 3D primitives with center:."""

    def test_box_center_false(self):
        code = _parse_and_gen("box 10 20 30 center:false")
        assert ".box(10, 20, 30, centered=(False, False, False))" in code

    def test_box_center_true(self):
        code = _parse_and_gen("box 10 20 30 center:true")
        assert ".box(10, 20, 30, centered=(True, True, True))" in code

    def test_box_center_tuple(self):
        code = _parse_and_gen("box 10 20 30 center:(false, true, false)")
        assert ".box(10, 20, 30, centered=(False, True, False))" in code

    def test_box_no_center(self):
        code = _parse_and_gen("box 10 20 30")
        assert "centered=" not in code
        assert ".box(10, 20, 30)" in code

    def test_cylinder_center_false(self):
        code = _parse_and_gen("cylinder 5 10 center:false")
        assert ".cylinder(10, 5, centered=(False, False, False))" in code

    def test_sphere_center_false(self):
        code = _parse_and_gen("sphere 5 center:false")
        assert ".sphere(5, centered=(False, False, False))" in code

    def test_cone_center_false(self):
        code = _parse_and_gen("cone 10 5 2 center:false")
        assert ".cone(10, 5, 2, centered=(False, False, False))" in code

    def test_torus_center_false(self):
        code = _parse_and_gen("torus 10 3 center:false")
        assert ".torus(10, 3, centered=(False, False, False))" in code


class TestCenterCodegen2D:
    """Code generation for 2D primitives with center:."""

    def test_rect_center_false(self):
        code = _parse_and_gen("rect 10 20 center:false")
        assert ".rect(10, 20, centered=(False, False))" in code

    def test_circle_center_false(self):
        code = _parse_and_gen("circle 5 center:false")
        assert ".circle(5, centered=(False, False))" in code

    def test_ellipse_center_false(self):
        code = _parse_and_gen("ellipse 10 5 center:false")
        assert ".ellipse(10, 5, centered=(False, False))" in code

    def test_rect_center_tuple(self):
        code = _parse_and_gen("rect 10 20 center:(false, true)")
        assert ".rect(10, 20, centered=(False, True))" in code


class TestCenterCodegenPipe:
    """Code generation for pipe primitives with center:."""

    def test_pipe_rect_center_false(self):
        code = _parse_and_gen("box 10 10 10 | faces top | rect 5 5 center:false | extrude 3")
        assert ".rect(5, 5, centered=(False, False))" in code

    def test_pipe_circle_center_false(self):
        code = _parse_and_gen("box 10 10 10 | faces top | circle 3 center:false | extrude 3")
        assert ".circle(3, centered=(False, False))" in code

    def test_pipe_box_center_false(self):
        code = _parse_and_gen("rect 100 100 | verts | box 10 20 30 center:false")
        assert ".box(10, 20, 30, centered=(False, False, False))" in code

    def test_pipe_cylinder_center_false(self):
        code = _parse_and_gen("rect 100 100 | verts | cylinder 5 10 center:false")
        assert ".cylinder(10, 5, centered=(False, False, False))" in code


# ---------------------------------------------------------------------------
# Multi-value center: (space-separated, no parentheses)
# ---------------------------------------------------------------------------

class TestCenterMultiValue:
    """center:false true false (space-separated) -> per-axis tuple."""

    def test_box_center_multi_value(self):
        tree = parse("box 10 20 30 center:false true false")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.Box)
        assert isinstance(stmt.center, ast.TupleLit)
        assert len(stmt.center.values) == 3
        assert stmt.center.values[0].value is False
        assert stmt.center.values[1].value is True
        assert stmt.center.values[2].value is False

    def test_box_center_multi_value_codegen(self):
        code = _parse_and_gen("box 10 20 30 center:false true false")
        assert ".box(10, 20, 30, centered=(False, True, False))" in code

    def test_rect_center_multi_value(self):
        tree = parse("rect 10 20 center:false true")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.Rect)
        assert isinstance(stmt.center, ast.TupleLit)
        assert len(stmt.center.values) == 2
        assert stmt.center.values[0].value is False
        assert stmt.center.values[1].value is True

    def test_rect_center_multi_value_codegen(self):
        code = _parse_and_gen("rect 10 20 center:false true")
        assert ".rect(10, 20, centered=(False, True))" in code

    def test_cylinder_center_multi_value_codegen(self):
        code = _parse_and_gen("cylinder 5 10 center:false true false")
        assert ".cylinder(10, 5, centered=(False, True, False))" in code

    def test_sphere_center_multi_value_codegen(self):
        code = _parse_and_gen("sphere 5 center:false false true")
        assert ".sphere(5, centered=(False, False, True))" in code
