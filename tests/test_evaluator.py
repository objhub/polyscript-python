"""Tests for the AST-walking evaluator (Phase 5).

These tests verify that use_evaluator=True produces the same results
as the existing codegen+exec path for supported features.
"""

import math
import pytest

from polyscript.executor import execute


def _exec(src: str):
    """Execute with the evaluator path."""
    return execute(src, use_evaluator=True)


# ---------------------------------------------------------------------------
# 3D Primitives
# ---------------------------------------------------------------------------

class TestEvaluator3DPrimitives:
    def test_box(self):
        result = _exec("box 10 20 30")
        bb = result.val().BoundingBox()
        assert abs(bb.xlen - 10) < 0.01
        assert abs(bb.ylen - 20) < 0.01
        assert abs(bb.zlen - 30) < 0.01

    def test_cylinder(self):
        result = _exec("cylinder 5 10")
        bb = result.val().BoundingBox()
        assert abs(bb.zlen - 10) < 0.01
        assert abs(bb.xlen - 10) < 0.5  # diameter

    def test_sphere(self):
        result = _exec("sphere 5")
        bb = result.val().BoundingBox()
        assert abs(bb.xlen - 10) < 0.5  # diameter

    def test_wedge(self):
        result = _exec("wedge 10 5 8 3")
        bb = result.val().BoundingBox()
        assert abs(bb.xlen - 10) < 0.01
        assert abs(bb.ylen - 5) < 0.01
        assert abs(bb.zlen - 8) < 0.01

    def test_cone(self):
        result = _exec("cone 5 0 10")
        bb = result.val().BoundingBox()
        assert abs(bb.zlen - 10) < 0.01

    def test_torus(self):
        result = _exec("torus 10 3")
        bb = result.val().BoundingBox()
        assert abs(bb.xlen - 26) < 0.5  # (10+3)*2

    def test_box_with_at(self):
        result = _exec("box 10 10 10 at:5 0 0")
        bb = result.val().BoundingBox()
        assert abs(bb.xmin - 0) < 0.01
        assert abs(bb.xmax - 10) < 0.01


# ---------------------------------------------------------------------------
# 2D -> Extrude
# ---------------------------------------------------------------------------

class TestEvaluator2DExtrude:
    def test_rect_extrude(self):
        result = _exec("rect 10 20 | extrude 5")
        bb = result.val().BoundingBox()
        assert abs(bb.xlen - 10) < 0.01
        assert abs(bb.ylen - 20) < 0.01
        assert abs(bb.zlen - 5) < 0.01

    def test_circle_extrude(self):
        result = _exec("circle 5 | extrude 10")
        bb = result.val().BoundingBox()
        assert abs(bb.zlen - 10) < 0.01

    def test_polygon_extrude(self):
        result = _exec("polygon 6 8 | extrude 5")
        bb = result.val().BoundingBox()
        assert abs(bb.zlen - 5) < 0.01


# ---------------------------------------------------------------------------
# Pipe operations
# ---------------------------------------------------------------------------

class TestEvaluatorPipeOps:
    def test_translate(self):
        result = _exec("box 10 10 10 | translate 20 0 0")
        bb = result.val().BoundingBox()
        assert abs(bb.xmin - 15) < 0.01

    def test_rotate(self):
        result = _exec("box 10 10 10 | rotate 0 0 45")
        bb = result.val().BoundingBox()
        # Rotated 45 degrees around Z: bounding box should be larger
        expected = 10 * math.sqrt(2)
        assert abs(bb.xlen - expected) < 0.5

    def test_scale(self):
        result = _exec("box 10 10 10 | scale 2")
        bb = result.val().BoundingBox()
        assert abs(bb.xlen - 20) < 0.01

    def test_mirror(self):
        result = _exec("box 10 10 10 at:10 0 0 | mirror \"X\"")
        bb = result.val().BoundingBox()
        # Mirror across YZ: original at (5..15), mirror at (-15..-5)
        assert abs(bb.xlen - 30) < 0.5

    def test_floor(self):
        result = _exec("sphere 5 | floor")
        bb = result.val().BoundingBox()
        assert abs(bb.zmin) < 0.01

    def test_diff(self):
        result = _exec("box 20 20 20 | diff (cylinder 5 20)")
        bb = result.val().BoundingBox()
        assert abs(bb.xlen - 20) < 0.01

    def test_union(self):
        result = _exec("box 10 10 10 | union (sphere 8)")
        bb = result.val().BoundingBox()
        # Union should be at least as large as the box
        assert bb.xlen >= 9.9

    def test_inter(self):
        result = _exec("box 20 20 20 | inter (sphere 12)")
        bb = result.val().BoundingBox()
        # Intersection should be smaller than the box
        assert bb.xlen < 20.5

    def test_fillet(self):
        result = _exec("box 50 50 10 | fillet 2")
        assert result is not None

    def test_chamfer(self):
        result = _exec("box 50 50 10 | chamfer 1")
        assert result is not None

    def test_shell(self):
        result = _exec("box 50 50 10 | faces >Z | shell 2")
        assert result is not None

    def test_extrude_with_draft(self):
        result = _exec("rect 20 20 | extrude 10 draft:5")
        assert result is not None
        bb = result.val().BoundingBox()
        assert abs(bb.zlen - 10) < 0.01

    def test_cut_thru_all(self):
        result = _exec("box 30 30 10 | faces >Z | circle 5 | cut")
        assert result is not None

    def test_cut_blind(self):
        result = _exec("box 30 30 10 | faces >Z | circle 5 | cut 5")
        assert result is not None


# ---------------------------------------------------------------------------
# Variables and functions
# ---------------------------------------------------------------------------

class TestEvaluatorVariables:
    def test_variable(self):
        result = _exec("$w = 10\nbox w 20 30")
        bb = result.val().BoundingBox()
        assert abs(bb.xlen - 10) < 0.01

    def test_expression(self):
        result = _exec("$w = 5 + 5\nbox w 20 30")
        bb = result.val().BoundingBox()
        assert abs(bb.xlen - 10) < 0.01

    def test_function(self):
        result = _exec("def double($x) = $x * 2\nbox (double 5) 20 30")
        bb = result.val().BoundingBox()
        assert abs(bb.xlen - 10) < 0.01

    def test_function_returning_shape(self):
        result = _exec("def mybox($w, $h, $d) = box $w $h $d\nmybox 10 20 30")
        bb = result.val().BoundingBox()
        assert abs(bb.xlen - 10) < 0.01
        assert abs(bb.ylen - 20) < 0.01
        assert abs(bb.zlen - 30) < 0.01

    def test_if_expr(self):
        result = _exec("$x = 5\nbox (if x > 3 then 20 else 10) 10 10")
        bb = result.val().BoundingBox()
        assert abs(bb.xlen - 20) < 0.01

    def test_list_comprehension(self):
        result = _exec("$sizes = [(i + 1) * 10 for i in 3]\n$w = sizes[0]\n$h = sizes[1]\n$d = sizes[2]\nbox w h d")
        bb = result.val().BoundingBox()
        # sizes = [10, 20, 30]
        assert abs(bb.xlen - 10) < 0.01
        assert abs(bb.ylen - 20) < 0.01
        assert abs(bb.zlen - 30) < 0.01

    def test_math_functions(self):
        result = _exec("$r = sqrt(25)\nsphere r")
        bb = result.val().BoundingBox()
        assert abs(bb.xlen - 10) < 0.5  # diameter = 2*5

    def test_trig_in_degrees(self):
        result = _exec("$x = cos(0)\nbox x 1 1")
        bb = result.val().BoundingBox()
        assert abs(bb.xlen - 1.0) < 0.01  # cos(0 deg) = 1

    def test_multiple_toplevel_shapes(self):
        result = _exec("box 10 10 10\ncylinder 20 5 at:30 0 0")
        bb = result.val().BoundingBox()
        # Should be unioned
        assert bb.xlen > 10

    def test_bool_const(self):
        result = _exec("$flag = true\nbox (if flag then 10 else 5) 10 10")
        bb = result.val().BoundingBox()
        assert abs(bb.xlen - 10) < 0.01


# ---------------------------------------------------------------------------
# Revolve
# ---------------------------------------------------------------------------

class TestEvaluatorRevolve:
    def test_revolve(self):
        result = _exec("rect 5 10 at:15 0 | revolve Y")
        assert result is not None
        bb = result.val().BoundingBox()
        assert bb.xlen > 0


# ---------------------------------------------------------------------------
# Face selection
# ---------------------------------------------------------------------------

class TestEvaluatorFaceSelection:
    def test_faces_top(self):
        result = _exec("box 30 30 10 | faces >Z | circle 5 | extrude 5")
        assert result is not None
        bb = result.val().BoundingBox()
        assert abs(bb.zlen - 15) < 0.5

    def test_edges_select(self):
        result = _exec("box 50 50 10 | edges >Z | fillet 2")
        assert result is not None

    def test_hole(self):
        result = _exec("box 30 30 10 | faces >Z | hole 3")
        assert result is not None


# ---------------------------------------------------------------------------
# Color
# ---------------------------------------------------------------------------

class TestEvaluatorColor:
    def test_named_color(self):
        result = _exec('box 10 10 10 | color "red"')
        assert result is not None
        assert result._color == (1.0, 0.0, 0.0, 1.0)

    def test_rgb_color(self):
        result = _exec("box 10 10 10 | color 255 128 0")
        assert result is not None
        assert abs(result._color[0] - 1.0) < 0.01


# ---------------------------------------------------------------------------
# Sweep
# ---------------------------------------------------------------------------

class TestEvaluatorSweep:
    def test_helix_sweep(self):
        result = _exec("helix 2 10 5 | sweep (circle 1)")
        assert result is not None
        bb = result.val().BoundingBox()
        assert bb.zlen > 5


# ---------------------------------------------------------------------------
# Parity with codegen: run the same tests with both paths
# ---------------------------------------------------------------------------

class TestEvaluatorParityWithCodegen:
    """Run identical tests with codegen and evaluator, compare bboxes."""

    @pytest.mark.parametrize("src", [
        "box 80 60 10",
        "cylinder 15 30",
        "sphere 10",
        "wedge 10 5 8 3",
        "cone 10 5 20",
        "torus 10 3",
        "rect 60 40 | extrude 5",
        "circle 5 | extrude 10",
        "polygon 6 8 | extrude 5",
        "box 50 50 10 | translate 10 0 0",
        "box 50 50 10 | rotate 0 0 45",
        "box 50 50 10 | scale 2",
        "sphere 5 | floor",
    ])
    def test_parity(self, src):
        result_codegen = execute(src, use_evaluator=False)
        result_eval = execute(src, use_evaluator=True)

        bb_cg = result_codegen.val().BoundingBox()
        bb_ev = result_eval.val().BoundingBox()

        assert abs(bb_cg.xlen - bb_ev.xlen) < 0.1, f"xlen mismatch for '{src}'"
        assert abs(bb_cg.ylen - bb_ev.ylen) < 0.1, f"ylen mismatch for '{src}'"
        assert abs(bb_cg.zlen - bb_ev.zlen) < 0.1, f"zlen mismatch for '{src}'"
