"""Tests for 3D and 2D primitive compilation."""

import pytest
from polyscript.executor import compile_source


class Test3DPrimitives:
    def test_box(self):
        code = compile_source("box 80 60 10")
        assert '.box(80, 60, 10)' in code

    def test_cylinder(self):
        code = compile_source("cylinder 30 15")
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
        code = compile_source("box 10 10 10\ncylinder 5 20 at 30 0")
        assert '.union(' in code

    def test_single_toplevel_shape(self):
        """Single top-level shape should not produce union."""
        code = compile_source("box 10 10 10")
        assert '.union(' not in code

    def test_assignment_not_in_union(self):
        """Assignments should not be included in implicit union."""
        code = compile_source("$a = box 10 10 10\ncylinder 5 20")
        # Only one top-level shape expression (cylinder), so no union
        assert '.union(' not in code

    def test_three_toplevel_shapes(self):
        """Three top-level shapes produce a union chain."""
        code = compile_source("box 10 10 10\ncylinder 5 20\nsphere 8")
        # Should have two .union() calls
        assert code.count('.union(') == 2
