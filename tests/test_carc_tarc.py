"""Tests for carc (center arc) and tarc (tangent arc) sketch segments."""

import math
import pytest
from polyscript import ast_nodes as ast
from polyscript.parser import parse
from polyscript.transformer import transform
from polyscript.executor import compile_source, execute
from polyscript.errors import ExecutionError


# ---------------------------------------------------------------------------
# Parsing tests
# ---------------------------------------------------------------------------

class TestCarcParsing:
    """Test that carc syntax parses to correct AST nodes."""

    def test_carc_center(self):
        tree = parse("sketch [(10, 0), carc (0, 10) (0, 0), (0, 0)]")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.SketchExpr)
        seg = stmt.segments[0]
        assert isinstance(seg, ast.CenterArcPath)
        assert isinstance(seg.end, ast.TupleLit)
        assert isinstance(seg.center, ast.TupleLit)
        assert seg.radius is None

    def test_carc_radius(self):
        tree = parse("sketch [(10, 0), carc (0, 10) r:10, (0, 0)]")
        prog = transform(tree)
        seg = prog.statements[0].segments[0]
        assert isinstance(seg, ast.CenterArcPath)
        assert isinstance(seg.end, ast.TupleLit)
        assert seg.center is None
        assert seg.radius is not None

    def test_carc_radius_with_variable(self):
        tree = parse("$r = 10\nsketch [($r, 0), carc (0, $r) r:$r, (0, 0)]")
        prog = transform(tree)
        sketch = prog.statements[1]
        seg = sketch.segments[0]
        assert isinstance(seg, ast.CenterArcPath)
        assert seg.radius is not None

    def test_carc_center_with_expressions(self):
        tree = parse("sketch [(5+5, 0), carc (0, 10) (0, 0), (0, 0)]")
        prog = transform(tree)
        seg = prog.statements[0].segments[0]
        assert isinstance(seg, ast.CenterArcPath)
        assert isinstance(seg.center, ast.TupleLit)


class TestTarcParsing:
    """Test that tarc syntax parses to correct AST nodes."""

    def test_tarc_inherit(self):
        tree = parse("sketch [(0, 0), (10, 0), tarc (15, 5)]")
        prog = transform(tree)
        stmt = prog.statements[0]
        seg = stmt.segments[1]
        assert isinstance(seg, ast.TangentArcPath)
        assert isinstance(seg.end, ast.TupleLit)
        assert seg.tangent is None

    def test_tarc_explicit(self):
        tree = parse("sketch [(0, 0), (10, 0), tarc (15, 5) (1, 0)]")
        prog = transform(tree)
        seg = prog.statements[0].segments[1]
        assert isinstance(seg, ast.TangentArcPath)
        assert isinstance(seg.end, ast.TupleLit)
        assert isinstance(seg.tangent, ast.TupleLit)


# ---------------------------------------------------------------------------
# Path primitive parsing tests
# ---------------------------------------------------------------------------

class TestPathPrimitiveParsing:
    """Test carc/tarc as standalone path primitives."""

    def test_carc_path_center(self):
        tree = parse("carc (0, 10) (0, 0)")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.CenterArcPath)
        assert stmt.center is not None
        assert stmt.radius is None

    def test_carc_path_radius(self):
        tree = parse("carc (0, 10) r:10")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.CenterArcPath)
        assert stmt.center is None
        assert stmt.radius is not None

    def test_tarc_path_inherit(self):
        tree = parse("tarc (15, 5)")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.TangentArcPath)
        assert stmt.tangent is None

    def test_tarc_path_explicit(self):
        tree = parse("tarc (15, 5) (1, 0)")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.TangentArcPath)
        assert stmt.tangent is not None


# ---------------------------------------------------------------------------
# Codegen tests
# ---------------------------------------------------------------------------

class TestCarcCodegen:
    """Test that carc/tarc generates correct internal representation."""

    def test_carc_center_codegen(self):
        code = compile_source(
            'sketch [(10, 0), carc (0, 10) (0, 0), (0, 0), (10, 0)]'
        )
        assert ".sketch(" in code
        assert '("carc_center"' in code

    def test_carc_radius_codegen(self):
        code = compile_source(
            'sketch [(10, 0), carc (0, 10) r:10, (0, 0), (10, 0)]'
        )
        assert ".sketch(" in code
        assert '("carc_radius"' in code

    def test_tarc_inherit_codegen(self):
        code = compile_source(
            'sketch [(0, 0), (10, 0), tarc (15, 5), (15, 10)]'
        )
        assert '("tarc"' in code

    def test_tarc_explicit_codegen(self):
        code = compile_source(
            'sketch [(0, 0), (10, 0), tarc (15, 5) (1, 0), (15, 10)]'
        )
        assert '("tarc_explicit"' in code


# ---------------------------------------------------------------------------
# Execution tests: carc
# ---------------------------------------------------------------------------

class TestCarcExecution:
    """Test carc execution producing correct geometry."""

    def test_carc_center_quarter_arc(self):
        """Quarter arc: (10,0) -> (0,10) around center (0,0)."""
        result = execute(
            "sketch [(10, 0), carc (0, 10) (0, 0), (0, 0), (10, 0)]"
        )
        assert result is not None
        assert hasattr(result, '_wires')
        assert len(result._wires) > 0

    def test_carc_center_extrude(self):
        """Quarter arc extruded to 3D solid."""
        result = execute(
            "sketch [(10, 0), carc (0, 10) (0, 0), (0, 0), (10, 0)] | extrude 5"
        )
        assert result is not None
        assert result._shape is not None

    def test_carc_radius_quarter_arc(self):
        """Quarter arc using radius specification."""
        result = execute(
            "$r = 10\n"
            "sketch [($r, 0), carc (0, $r) r:$r, (0, 0), ($r, 0)]"
        )
        assert result is not None
        assert len(result._wires) > 0

    def test_carc_radius_extrude(self):
        """Radius-based carc extruded to 3D solid."""
        result = execute(
            "$r = 10\n"
            "sketch [($r, 0), carc (0, $r) r:$r, (0, 0), ($r, 0)] | extrude 5"
        )
        assert result is not None
        assert result._shape is not None

    def test_carc_rounded_rect(self):
        """Rounded rectangle with 4 carc r: segments (SPEC example)."""
        src = """
$w = 20
$h = 10
$cr = 2
sketch [
  ($w/2 - $cr, -$h/2),
  carc ($w/2, -$h/2 + $cr) r:$cr,
  ($w/2, $h/2 - $cr),
  carc ($w/2 - $cr, $h/2) r:$cr,
  (-$w/2 + $cr, $h/2),
  carc (-$w/2, $h/2 - $cr) r:$cr,
  (-$w/2, -$h/2 + $cr),
  carc (-$w/2 + $cr, -$h/2) r:$cr
] | extrude 5
"""
        result = execute(src)
        assert result is not None
        assert result._shape is not None

    def test_carc_center_equidistance_error(self):
        """Center not equidistant from start and end should raise ExecutionError."""
        with pytest.raises(ExecutionError, match="equidistant"):
            execute(
                "sketch [(10, 0), carc (0, 5) (1, 1), (0, 0), (10, 0)]"
            )

    def test_carc_radius_too_small(self):
        """Radius smaller than half chord length should raise ExecutionError."""
        with pytest.raises(ExecutionError, match="chord length"):
            execute(
                "sketch [(10, 0), carc (0, 10) r:3, (0, 0), (10, 0)]"
            )


# ---------------------------------------------------------------------------
# Execution tests: tarc
# ---------------------------------------------------------------------------

class TestTarcExecution:
    """Test tarc execution producing correct geometry."""

    def test_tarc_inherit_basic(self):
        """Tangent arc following a straight line."""
        result = execute(
            "sketch [(0, 0), (10, 0), tarc (15, 5), (0, 0)]"
        )
        assert result is not None
        assert len(result._wires) > 0

    def test_tarc_inherit_extrude(self):
        """Tangent arc extruded to 3D solid."""
        result = execute(
            "sketch [(0, 0), (10, 0), tarc (15, 5), (15, 10), (0, 0)] | extrude 5"
        )
        assert result is not None
        assert result._shape is not None

    def test_tarc_explicit(self):
        """Tangent arc with explicit tangent vector."""
        result = execute(
            "sketch [(0, 0), (10, 0), tarc (15, 5) (1, 0), (0, 0)]"
        )
        assert result is not None

    def test_tarc_first_segment_error(self):
        """tarc as first segment should raise ExecutionError."""
        with pytest.raises(ExecutionError, match="tarc cannot be the first segment"):
            execute(
                "sketch [(0, 0), tarc (10, 5)]"
            )

    def test_tarc_after_arc(self):
        """tarc following a 3-point arc should work (tangent inheritance)."""
        result = execute(
            "sketch [(5, 0), arc (0, -5) (-5, 0), tarc (-10, 5), (0, 0), (5, 0)]"
        )
        assert result is not None

    def test_tarc_after_carc(self):
        """tarc following a carc should work (tangent inheritance from carc)."""
        result = execute(
            "sketch [(10, 0), carc (0, 10) (0, 0), tarc (-10, 10), (0, 0), (10, 0)]"
        )
        assert result is not None


# ---------------------------------------------------------------------------
# Geometry verification tests
# ---------------------------------------------------------------------------

class TestCarcGeometry:
    """Verify geometric correctness of carc arcs."""

    def test_carc_quarter_arc_bbox(self):
        """Quarter arc from (r,0) to (0,r) around (0,0) should have bbox [0,r]x[0,r]."""
        from polyscript.ocp_kernel import _bounding_box
        r = 10
        result = execute(
            f"sketch [({r}, 0), carc (0, {r}) (0, 0), (0, 0), ({r}, 0)] | extrude 1"
        )
        bb = _bounding_box(result._shape)
        xmin, ymin, zmin, xmax, ymax, zmax = bb.Get()
        # X range: 0 to r, Y range: 0 to r, Z range: 0 to 1
        assert xmin >= -0.1
        assert xmax <= r + 0.1
        assert ymin >= -0.1
        assert ymax <= r + 0.1

    def test_carc_radius_matches_center(self):
        """carc r:R and carc with explicit center should produce same bbox."""
        from polyscript.ocp_kernel import _bounding_box
        r = 10
        src_center = f"sketch [({r}, 0), carc (0, {r}) (0, 0), (0, 0), ({r}, 0)] | extrude 1"
        src_radius = f"sketch [({r}, 0), carc (0, {r}) r:{r}, (0, 0), ({r}, 0)] | extrude 1"
        result_c = execute(src_center)
        result_r = execute(src_radius)
        bb_c = _bounding_box(result_c._shape).Get()
        bb_r = _bounding_box(result_r._shape).Get()
        for a, b in zip(bb_c, bb_r):
            assert abs(a - b) < 0.1, f"bbox mismatch: {bb_c} vs {bb_r}"


# ---------------------------------------------------------------------------
# Backward compatibility tests
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    """Ensure existing arc syntax still works."""

    def test_existing_arc_still_works(self):
        result = execute(
            "sketch [(5, 0), arc (0, -5) (-5, 0), (0, 7), (5, 0)] | extrude 10"
        )
        assert result is not None
        assert result._shape is not None

    def test_existing_sketch_lines_still_works(self):
        result = execute(
            "sketch [(5, 0), (0, 7), (-5, 0), (0, -7)] | extrude 10"
        )
        assert result is not None
        assert result._shape is not None
