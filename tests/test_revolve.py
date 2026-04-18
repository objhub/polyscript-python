"""Tests for the new revolve syntax: revolve axis [deg]."""

import pytest
from polyscript.parser import parse
from polyscript.transformer import transform
from polyscript.codegen_ocp import generate
from polyscript.errors import CodegenError


def compile_source(source: str) -> str:
    tree = parse(source)
    ast = transform(tree)
    return generate(ast)


# ---------------------------------------------------------------------------
# Parse + codegen: basic axis variants
# ---------------------------------------------------------------------------

class TestRevolveNewSyntax:
    def test_revolve_y(self):
        code = compile_source("rect 10 30 at:(15, 0) | revolve Y")
        assert 'axisEnd=(0,1,0)' in code
        assert '.revolve(360' in code

    def test_revolve_x(self):
        code = compile_source("rect 10 30 at:(15, 0) | revolve X")
        assert 'axisEnd=(1,0,0)' in code
        assert '.revolve(360' in code

    def test_revolve_z(self):
        code = compile_source("rect 10 30 at:(15, 0) | revolve Z")
        assert 'axisEnd=(0,0,1)' in code
        assert '.revolve(360' in code


# ---------------------------------------------------------------------------
# Parse + codegen: partial rotation
# ---------------------------------------------------------------------------

class TestRevolvePartialAngle:
    def test_revolve_y_180(self):
        code = compile_source("rect 10 30 at:(15, 0) | revolve Y 180")
        assert 'axisEnd=(0,1,0)' in code
        assert '.revolve(180' in code

    def test_revolve_x_90(self):
        code = compile_source("rect 10 30 at:(15, 0) | revolve X 90")
        assert 'axisEnd=(1,0,0)' in code
        assert '.revolve(90' in code

    def test_revolve_z_270(self):
        code = compile_source("rect 10 30 at:(15, 0) | revolve Z 270")
        assert 'axisEnd=(0,0,1)' in code
        assert '.revolve(270' in code


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

class TestRevolveErrors:
    def test_revolve_bare_error(self):
        """revolve alone should error with a helpful message."""
        with pytest.raises(CodegenError, match="revolve requires an axis"):
            compile_source("rect 10 30 | revolve")

    def test_revolve_number_first_error(self):
        """revolve 360 should error because axis is missing."""
        with pytest.raises(CodegenError, match="revolve expects an axis first"):
            compile_source("rect 10 30 | revolve 360")

    def test_revolve_named_arg_error(self):
        """revolve axis:'X' 360 is the old syntax and should fail."""
        with pytest.raises(Exception):
            compile_source('rect 10 30 | revolve axis:"X" 360')


# ---------------------------------------------------------------------------
# Geometry validation (OCP kernel)
# ---------------------------------------------------------------------------

class TestRevolveGeometry:
    def test_revolve_ring_volume(self):
        """rect 10 30 at:(15, 0) | revolve Y should produce a ring (torus-like)."""
        code = compile_source("rect 10 30 at:(15, 0) | revolve Y")
        ns = {}
        exec(code, ns)
        result = ns["_result"]
        assert result._shape is not None
        bb = result.val().BoundingBox()
        # The ring should be centered at origin, symmetric
        assert bb.xmin < -5
        assert bb.xmax > 5
        assert abs(bb.ymin + bb.ymax) < 1  # symmetric around Y=0... actually it's symmetric around Y midpoint

    def test_revolve_half_rotation_bbox(self):
        """rect 10 30 at:(15, 0) | revolve Y 180 should produce a half-ring."""
        code = compile_source("rect 10 30 at:(15, 0) | revolve Y 180")
        ns = {}
        exec(code, ns)
        result = ns["_result"]
        assert result._shape is not None
        bb = result.val().BoundingBox()
        # Half ring: should only extend in one direction for X
        # With 180 degrees around Y, the shape extends in X and Z
        assert bb.xmin < 0
        assert bb.xmax > 0

    def test_revolve_x_axis_geometry(self):
        """circle 5 at:(0, 20) | revolve X should produce a torus around X."""
        code = compile_source("circle 5 at:(0, 20) | revolve X")
        ns = {}
        exec(code, ns)
        result = ns["_result"]
        assert result._shape is not None
