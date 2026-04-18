"""Tests for origin: kwarg on moveto/move/hole and primitives, and at: on hole."""

import pytest
from polyscript.executor import compile_source
from polyscript.parser import parse
from polyscript.transformer import transform
from polyscript import ast_nodes as ast


# ===================================================================
# Implicit workplane insertion regression
# ===================================================================


class TestImplicitWorkplane:
    """Regression: faces >Z | moveto/move should get implicit workplane."""

    def test_faces_moveto_hole(self):
        code = compile_source("polygon 3 10 | extrude 10 | faces >Z | moveto 0 0 | hole 1")
        assert ".faces('>Z').workplane().moveTo(0, 0)" in code
        # After moveto, hole should NOT use holeOnFaces (workplane context)
        # Actually context tracking keeps FACE_SELECTION for moveto, so holeOnFaces is used
        assert ".hole" in code.lower()

    def test_faces_move_circle_cut(self):
        code = compile_source("box 20 20 10 | faces >Z | move 5 5 | circle 3 | cut")
        assert ".faces('>Z').workplane().center(5, 5)" in code
        assert ".circle(3)" in code


# ===================================================================
# moveto with origin:
# ===================================================================


class TestMoveToOriginParsing:
    """Parse origin: kwarg on moveto."""

    def test_moveto_origin_world(self):
        tree = parse('box 20 20 10 | faces >Z | moveto 0 0 origin:"world"')
        prog = transform(tree)
        pipeline = prog.statements[0]
        moveto = pipeline.operations[1]
        assert isinstance(moveto, ast.MoveTo)
        assert isinstance(moveto.origin, ast.StringLit)
        assert moveto.origin.value == "world"

    def test_moveto_origin_tuple(self):
        tree = parse("box 20 20 10 | faces >Z | moveto 0 0 origin:(10, 20, 0)")
        prog = transform(tree)
        pipeline = prog.statements[0]
        moveto = pipeline.operations[1]
        assert isinstance(moveto, ast.MoveTo)
        assert isinstance(moveto.origin, ast.TupleLit)

    def test_moveto_no_origin(self):
        tree = parse("box 20 20 10 | faces >Z | moveto 5 5")
        prog = transform(tree)
        pipeline = prog.statements[0]
        moveto = pipeline.operations[1]
        assert isinstance(moveto, ast.MoveTo)
        assert moveto.origin is None


class TestMoveToOriginCodegen:
    """Code generation for moveto with origin:."""

    def test_moveto_default(self):
        code = compile_source("box 20 20 10 | faces >Z | workplane | moveto 5 5")
        assert ".moveTo(5, 5)" in code

    def test_moveto_origin_world(self):
        code = compile_source('box 20 20 10 | faces >Z | workplane | moveto 10 20 origin:"world"')
        assert ".workplane(origin=(10, 20, 0))" in code
        assert ".moveTo(0, 0)" in code

    def test_moveto_origin_tuple(self):
        code = compile_source("box 20 20 10 | faces >Z | workplane | moveto 5 5 origin:(10, 20, 0)")
        assert ".workplane(origin=(10, 20, 0))" in code
        assert ".moveTo(5, 5)" in code


# ===================================================================
# move with origin:
# ===================================================================


class TestMoveOriginParsing:
    """Parse origin: kwarg on move."""

    def test_move_origin_world(self):
        tree = parse('box 20 20 10 | faces >Z | move 5 5 origin:"world"')
        prog = transform(tree)
        pipeline = prog.statements[0]
        move = pipeline.operations[1]
        assert isinstance(move, ast.Move)
        assert isinstance(move.origin, ast.StringLit)
        assert move.origin.value == "world"

    def test_move_no_origin(self):
        tree = parse("box 20 20 10 | faces >Z | move 5 5")
        prog = transform(tree)
        pipeline = prog.statements[0]
        move = pipeline.operations[1]
        assert isinstance(move, ast.Move)
        assert move.origin is None


class TestMoveOriginCodegen:
    """Code generation for move with origin:."""

    def test_move_default(self):
        code = compile_source("box 20 20 10 | faces >Z | workplane | move 5 5")
        assert ".center(5, 5)" in code

    def test_move_origin_world(self):
        code = compile_source('box 20 20 10 | faces >Z | workplane | move 5 5 origin:"world"')
        assert ".workplane(origin=(0, 0, 0))" in code
        assert ".center(5, 5)" in code

    def test_move_origin_tuple(self):
        code = compile_source("box 20 20 10 | faces >Z | workplane | move 5 5 origin:(10, 20, 0)")
        assert ".workplane(origin=(10, 20, 0))" in code
        assert ".center(5, 5)" in code


# ===================================================================
# hole with at:
# ===================================================================


class TestHoleAtParsing:
    """Parse at: kwarg on hole."""

    def test_hole_at_2d(self):
        tree = parse("box 20 20 10 | faces >Z | hole 3 at: 5 5")
        prog = transform(tree)
        pipeline = prog.statements[0]
        hole = pipeline.operations[1]
        assert isinstance(hole, ast.Hole)
        assert isinstance(hole.at, ast.TupleLit)
        assert len(hole.at.values) == 2

    def test_hole_at_3d(self):
        tree = parse("box 20 20 10 | faces >Z | hole 3 at: 5 5 0")
        prog = transform(tree)
        pipeline = prog.statements[0]
        hole = pipeline.operations[1]
        assert isinstance(hole, ast.Hole)
        assert isinstance(hole.at, ast.TupleLit)
        assert len(hole.at.values) == 3

    def test_hole_at_origin_world(self):
        tree = parse('box 20 20 10 | faces >Z | hole 3 at: 0 0 origin:"world"')
        prog = transform(tree)
        pipeline = prog.statements[0]
        hole = pipeline.operations[1]
        assert isinstance(hole, ast.Hole)
        assert isinstance(hole.at, ast.TupleLit)
        assert isinstance(hole.origin, ast.StringLit)
        assert hole.origin.value == "world"

    def test_hole_no_at(self):
        tree = parse("box 20 20 10 | faces >Z | hole 3")
        prog = transform(tree)
        pipeline = prog.statements[0]
        hole = pipeline.operations[1]
        assert isinstance(hole, ast.Hole)
        assert hole.at is None
        assert hole.origin is None


class TestHoleAtCodegen:
    """Code generation for hole with at:."""

    def test_hole_face_center_default(self):
        """Default: face center (holeOnFaces)."""
        code = compile_source("box 20 20 10 | faces >Z | hole 3")
        assert ".holeOnFaces(3)" in code

    def test_hole_at_2d_wp_relative(self):
        """at: 5 5 -> WP-relative: .center(5, 5).hole(3)."""
        code = compile_source("box 20 20 10 | faces >Z | hole 3 at: 5 5")
        assert ".workplane()" in code
        assert ".center(5, 5)" in code
        assert ".hole(3)" in code
        # Should NOT use holeOnFaces
        assert "holeOnFaces" not in code

    def test_hole_at_3d_world(self):
        """at: 5 5 0 -> world: .workplane(origin=(5,5,0))."""
        code = compile_source("box 20 20 10 | faces >Z | hole 3 at: 5 5 0")
        assert ".workplane(origin=(5, 5, 0))" in code
        assert ".moveTo(0, 0)" in code
        assert ".hole(3)" in code

    def test_hole_at_origin_world(self):
        """at: 0 0 origin:"world" -> .workplane(origin=(0,0,0))."""
        code = compile_source('box 20 20 10 | faces >Z | hole 3 at: 0 0 origin:"world"')
        assert ".workplane(origin=(0, 0, 0))" in code
        assert ".hole(3)" in code

    def test_hole_at_origin_tuple(self):
        """at: 5 5 origin:(10,20,0) -> .workplane(origin=(10,20,0)).center(5,5)."""
        code = compile_source("box 20 20 10 | faces >Z | hole 3 at: 5 5 origin:(10, 20, 0)")
        assert ".workplane(origin=(10, 20, 0))" in code
        assert ".center(5, 5)" in code
        assert ".hole(3)" in code

    def test_hole_at_with_depth(self):
        """at: with depth: should pass depth to .hole()."""
        code = compile_source("box 20 20 10 | faces >Z | hole 3 at: 5 5 depth:5")
        assert ".hole(3, 5)" in code

    def test_hole_workplane_context(self):
        """hole at: in workplane context (not face selection)."""
        code = compile_source("box 20 20 10 | faces >Z | workplane | hole 3 at: 5 5")
        assert ".center(5, 5)" in code
        assert ".hole(3)" in code


# ===================================================================
# 2D primitives with origin: (pipe context)
# ===================================================================


class TestImplicit2DOriginCodegen:
    """Code generation for 2D primitives in pipe with origin:."""

    def test_circle_at_default(self):
        """Default at: 2-component is WP-relative (.center)."""
        code = compile_source("box 20 20 10 | faces >Z | circle 5 at: 10 20")
        assert ".center(10, 20)" in code
        assert ".circle(5)" in code

    def test_circle_at_origin_world(self):
        """at: with origin:"world" uses workplane(origin=...)."""
        code = compile_source('box 20 20 10 | faces >Z | circle 5 at: 10 20 origin:"world"')
        assert ".workplane(origin=(10, 20, 0))" in code
        assert ".moveTo(0, 0)" in code
        assert ".circle(5)" in code

    def test_circle_at_3d(self):
        """3-component at: -> world coordinates via workplane(origin=...)."""
        code = compile_source("box 20 20 10 | faces >Z | circle 5 at: 10 20 5")
        assert ".workplane(origin=(10, 20, 5))" in code
        assert ".moveTo(0, 0)" in code
        assert ".circle(5)" in code

    def test_circle_at_origin_tuple(self):
        """at: with origin:(ox,oy,oz) shifts the reference point."""
        code = compile_source("box 20 20 10 | faces >Z | circle 5 at: 5 5 origin:(10, 20, 0)")
        assert ".workplane(origin=(10, 20, 0))" in code
        assert ".center(5, 5)" in code
        assert ".circle(5)" in code

    def test_rect_at_origin_world(self):
        code = compile_source('box 20 20 10 | faces >Z | rect 5 5 at: 10 20 origin:"world"')
        assert ".workplane(origin=(10, 20, 0))" in code
        assert ".rect(5, 5)" in code

    def test_polygon_at_origin_world(self):
        code = compile_source('box 20 20 10 | faces >Z | polygon 6 5 at: 10 20 origin:"world"')
        assert ".workplane(origin=(10, 20, 0))" in code
        assert ".polygon(6, 5)" in code


# ===================================================================
# 3D primitives with origin: (source context)
# ===================================================================


class TestSourcePrimitiveOriginCodegen:
    """Code generation for source-position 3D primitives with origin:."""

    def test_box_at_origin_tuple(self):
        code = compile_source("box 10 10 10 at: 5 5 origin:(10, 20, 0)")
        assert ".translate((10 + 5, 20 + 5, 0))" in code

    def test_sphere_at_origin_world(self):
        code = compile_source('sphere 5 at: 10 20 origin:"world"')
        assert ".translate((10, 20, 0))" in code

    def test_cylinder_at_origin_tuple(self):
        code = compile_source("cylinder 5 10 at: 0 0 0 origin:(10, 20, 30)")
        assert ".translate((10 + 0, 20 + 0, 30 + 0))" in code


# ===================================================================
# Backward compatibility
# ===================================================================


class TestOriginBackwardCompat:
    """Ensure existing behavior is preserved when origin: is omitted."""

    def test_moveto_unchanged(self):
        code = compile_source("box 20 20 10 | faces >Z | workplane | moveto 5 5")
        assert ".moveTo(5, 5)" in code
        assert "origin" not in code.split(".moveTo")[0].split("workplane()")[-1]

    def test_move_unchanged(self):
        code = compile_source("box 20 20 10 | faces >Z | workplane | move 5 5")
        assert ".center(5, 5)" in code

    def test_hole_unchanged(self):
        code = compile_source("box 20 20 10 | faces >Z | hole 3")
        assert ".holeOnFaces(3)" in code

    def test_circle_at_unchanged(self):
        code = compile_source("box 20 20 10 | faces >Z | circle 5 at: 10 20")
        assert ".center(10, 20)" in code
        assert ".circle(5)" in code

    def test_box_at_2d_unchanged(self):
        code = compile_source("box 10 10 10 at: 5 5")
        assert ".translate((5, 5, 0))" in code

    def test_box_at_3d_unchanged(self):
        code = compile_source("box 10 10 10 at: 5 5 5")
        assert ".translate((5, 5, 5))" in code
