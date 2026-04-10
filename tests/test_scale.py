"""Tests for scale transformation."""

import pytest
from polyscript.executor import compile_source
from polyscript.parser import parse
from polyscript.transformer import transform
from polyscript import ast_nodes as ast


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

class TestScaleParsing:
    def test_scale_uniform(self):
        tree = parse("box 10 10 10 | scale 2")
        prog = transform(tree)
        pipeline = prog.statements[0]
        scale = pipeline.operations[0]
        assert isinstance(scale, ast.Scale)
        assert isinstance(scale.vector, ast.TupleLit)
        assert len(scale.vector.values) == 1
        assert scale.origin is None

    def test_scale_non_uniform(self):
        tree = parse("box 10 10 10 | scale 1 2 3")
        prog = transform(tree)
        pipeline = prog.statements[0]
        scale = pipeline.operations[0]
        assert isinstance(scale, ast.Scale)
        assert isinstance(scale.vector, ast.TupleLit)
        assert len(scale.vector.values) == 3

    def test_scale_origin_world(self):
        tree = parse('box 10 10 10 | scale 2 origin:"world"')
        prog = transform(tree)
        pipeline = prog.statements[0]
        scale = pipeline.operations[0]
        assert isinstance(scale, ast.Scale)
        assert isinstance(scale.origin, ast.StringLit)
        assert scale.origin.value == "world"

    def test_scale_origin_local(self):
        tree = parse('box 10 10 10 | scale 2 origin:"local"')
        prog = transform(tree)
        pipeline = prog.statements[0]
        scale = pipeline.operations[0]
        assert isinstance(scale, ast.Scale)
        assert isinstance(scale.origin, ast.StringLit)
        assert scale.origin.value == "local"

    def test_scale_origin_tuple(self):
        tree = parse("box 10 10 10 | scale 2 origin:(5, 5, 5)")
        prog = transform(tree)
        pipeline = prog.statements[0]
        scale = pipeline.operations[0]
        assert isinstance(scale, ast.Scale)
        assert isinstance(scale.origin, ast.TupleLit)
        assert len(scale.origin.values) == 3


# ---------------------------------------------------------------------------
# Codegen
# ---------------------------------------------------------------------------

class TestScaleCodegen:
    def test_uniform_scale(self):
        code = compile_source("box 10 10 10 | scale 2")
        assert ".scale(2, 2, 2, (0,0,0))" in code

    def test_non_uniform_scale(self):
        code = compile_source("box 10 10 10 | scale 1 2 3")
        assert ".scale(1, 2, 3, (0,0,0))" in code

    def test_scale_origin_world(self):
        code = compile_source('box 10 10 10 | scale 2 origin:"world"')
        assert ".scale(2, 2, 2, (0,0,0))" in code

    def test_scale_origin_local(self):
        code = compile_source('box 10 10 10 | scale 2 origin:"local"')
        assert ".scale(" in code
        assert "_center" in code

    def test_scale_origin_tuple(self):
        code = compile_source("box 10 10 10 | scale 2 origin:(5, 5, 5)")
        assert ".scale(2, 2, 2, (5, 5, 5))" in code


# ---------------------------------------------------------------------------
# OCP backend
# ---------------------------------------------------------------------------

class TestScaleOCPBackend:
    def test_uniform_scale(self):
        from polyscript.executor import execute
        result = execute("box 10 10 10 | scale 2")
        bb = result.val().BoundingBox()
        assert abs(bb.xmax - bb.xmin - 20) < 0.01
        assert abs(bb.ymax - bb.ymin - 20) < 0.01
        assert abs(bb.zmax - bb.zmin - 20) < 0.01

    def test_non_uniform_scale(self):
        from polyscript.executor import execute
        result = execute("box 10 10 10 | scale 1 2 3")
        bb = result.val().BoundingBox()
        assert abs(bb.xmax - bb.xmin - 10) < 0.01
        assert abs(bb.ymax - bb.ymin - 20) < 0.01
        assert abs(bb.zmax - bb.zmin - 30) < 0.01

    def test_scale_no_shape(self):
        from polyscript import ocp_kernel as cq
        wp = cq.Workplane("XY")
        result = wp.scale(2)
        assert result._shape is None

    def test_uniform_scale_with_center(self):
        from polyscript import ocp_kernel as cq
        wp = cq.Workplane("XY").box(10, 10, 10)
        result = wp.scale(2, center=(5, 5, 5))
        bb = result.val().BoundingBox()
        # Box centered at (0,0,0), scaled 2x around (5,5,5)
        # Original corners: (-5,-5,-5) to (5,5,5)
        # After scale around (5,5,5): (-5-5)*2+5=-15, (5-5)*2+5=5
        assert abs(bb.xmin - (-15)) < 0.01
        assert abs(bb.xmax - 5) < 0.01
