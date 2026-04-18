"""Tests for arc (3-point) and carc (center/radius arc) sketch segments.

Breaking change: arc/carc now require explicit start point (3 tuples).
tarc has been removed entirely.
"""

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
        tree = parse("sketch [(10, 0), carc (10, 0) (0, 10) (0, 0), (0, 0)]")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.SketchExpr)
        seg = stmt.segments[0]
        assert isinstance(seg, ast.CenterArcPath)
        assert isinstance(seg.start, ast.TupleLit)
        assert isinstance(seg.end, ast.TupleLit)
        assert isinstance(seg.center, ast.TupleLit)
        assert seg.radius is None

    def test_carc_radius(self):
        tree = parse("sketch [(10, 0), carc (10, 0) (0, 10) r:10, (0, 0)]")
        prog = transform(tree)
        seg = prog.statements[0].segments[0]
        assert isinstance(seg, ast.CenterArcPath)
        assert isinstance(seg.start, ast.TupleLit)
        assert isinstance(seg.end, ast.TupleLit)
        assert seg.center is None
        assert seg.radius is not None

    def test_carc_radius_with_variable(self):
        tree = parse("$r = 10\nsketch [($r, 0), carc ($r, 0) (0, $r) r:$r, (0, 0)]")
        prog = transform(tree)
        sketch = prog.statements[1]
        seg = sketch.segments[0]
        assert isinstance(seg, ast.CenterArcPath)
        assert seg.start is not None
        assert seg.radius is not None

    def test_carc_center_with_expressions(self):
        tree = parse("sketch [(5+5, 0), carc (5+5, 0) (0, 10) (0, 0), (0, 0)]")
        prog = transform(tree)
        seg = prog.statements[0].segments[0]
        assert isinstance(seg, ast.CenterArcPath)
        assert isinstance(seg.center, ast.TupleLit)


class TestTarcRemoved:
    """Verify that tarc syntax is no longer accepted."""

    def test_tarc_sketch_parse_error(self):
        with pytest.raises(Exception):
            parse("sketch [(0, 0), (10, 0), tarc (15, 5)]")

    def test_tarc_standalone_not_arc(self):
        """tarc as standalone is parsed as a function call, not TangentArcPath."""
        tree = parse("tarc (15, 5)")
        prog = transform(tree)
        stmt = prog.statements[0]
        # tarc is no longer a keyword; it becomes a FuncCall, not TangentArcPath
        assert not hasattr(ast, 'TangentArcPath') or not isinstance(stmt, getattr(ast, 'TangentArcPath', type(None)))
        assert isinstance(stmt, ast.FuncCall)
        assert stmt.name == "tarc"


# ---------------------------------------------------------------------------
# Path primitive parsing tests
# ---------------------------------------------------------------------------

class TestPathPrimitiveParsing:
    """Test carc as standalone path primitive."""

    def test_carc_path_center(self):
        tree = parse("carc (0, 0) (0, 10) (0, 0)")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.CenterArcPath)
        assert stmt.start is not None
        assert stmt.center is not None
        assert stmt.radius is None

    def test_carc_path_radius(self):
        tree = parse("carc (0, 0) (0, 10) r:10")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.CenterArcPath)
        assert stmt.start is not None
        assert stmt.center is None
        assert stmt.radius is not None


# ---------------------------------------------------------------------------
# Codegen tests
# ---------------------------------------------------------------------------

class TestCarcCodegen:
    """Test that carc generates correct internal representation."""

    def test_carc_center_codegen(self):
        code = compile_source(
            'sketch [(10, 0), carc (10, 0) (0, 10) (0, 0), (0, 0), (10, 0)]'
        )
        assert ".sketch(" in code
        assert '("carc_center"' in code

    def test_carc_radius_codegen(self):
        code = compile_source(
            'sketch [(10, 0), carc (10, 0) (0, 10) r:10, (0, 0), (10, 0)]'
        )
        assert ".sketch(" in code
        assert '("carc_radius"' in code


# ---------------------------------------------------------------------------
# Execution tests: carc
# ---------------------------------------------------------------------------

class TestCarcExecution:
    """Test carc execution producing correct geometry."""

    def test_carc_center_quarter_arc(self):
        """Quarter arc: (10,0) -> (0,10) around center (0,0)."""
        result = execute(
            "sketch [(10, 0), carc (10, 0) (0, 10) (0, 0), (0, 0), (10, 0)]"
        )
        assert result is not None
        assert hasattr(result, '_wires')
        assert len(result._wires) > 0

    def test_carc_center_extrude(self):
        """Quarter arc extruded to 3D solid."""
        result = execute(
            "sketch [(10, 0), carc (10, 0) (0, 10) (0, 0), (0, 0), (10, 0)] | extrude 5"
        )
        assert result is not None
        assert result._shape is not None

    def test_carc_radius_quarter_arc(self):
        """Quarter arc using radius specification."""
        result = execute(
            "$r = 10\n"
            "sketch [($r, 0), carc ($r, 0) (0, $r) r:$r, (0, 0), ($r, 0)]"
        )
        assert result is not None
        assert len(result._wires) > 0

    def test_carc_radius_extrude(self):
        """Radius-based carc extruded to 3D solid."""
        result = execute(
            "$r = 10\n"
            "sketch [($r, 0), carc ($r, 0) (0, $r) r:$r, (0, 0), ($r, 0)] | extrude 5"
        )
        assert result is not None
        assert result._shape is not None

    def test_carc_rounded_rect(self):
        """Rounded rectangle with 4 carc r: segments."""
        src = """
$w = 20
$h = 10
$cr = 2
sketch [
  ($w/2 - $cr, -$h/2),
  carc ($w/2 - $cr, -$h/2) ($w/2, -$h/2 + $cr) r:$cr,
  ($w/2, $h/2 - $cr),
  carc ($w/2, $h/2 - $cr) ($w/2 - $cr, $h/2) r:$cr,
  (-$w/2 + $cr, $h/2),
  carc (-$w/2 + $cr, $h/2) (-$w/2, $h/2 - $cr) r:$cr,
  (-$w/2, -$h/2 + $cr),
  carc (-$w/2, -$h/2 + $cr) (-$w/2 + $cr, -$h/2) r:$cr
] | extrude 5
"""
        result = execute(src)
        assert result is not None
        assert result._shape is not None

    def test_carc_center_equidistance_error(self):
        """Center not equidistant from start and end should raise ExecutionError."""
        with pytest.raises(ExecutionError, match="equidistant"):
            execute(
                "sketch [(10, 0), carc (10, 0) (0, 5) (1, 1), (0, 0), (10, 0)]"
            )

    def test_carc_radius_too_small(self):
        """Radius smaller than half chord length should raise ExecutionError."""
        with pytest.raises(ExecutionError, match="chord length"):
            execute(
                "sketch [(10, 0), carc (10, 0) (0, 10) r:3, (0, 0), (10, 0)]"
            )


# ---------------------------------------------------------------------------
# Start mismatch validation tests
# ---------------------------------------------------------------------------

class TestStartMismatch:
    """Test that arc/carc start mismatch raises runtime error."""

    def test_arc_start_mismatch(self):
        """arc start does not match previous segment end."""
        with pytest.raises(ExecutionError, match="does not match"):
            execute(
                "sketch [(0, 0), arc (1, 0) (0.5, 0.5) (1, 1), (0, 0)]"
            )

    def test_carc_center_start_mismatch(self):
        """carc center start does not match previous segment end."""
        with pytest.raises(ExecutionError, match="does not match"):
            execute(
                "sketch [(10, 0), carc (5, 0) (0, 10) (0, 0), (0, 0), (10, 0)]"
            )

    def test_carc_radius_start_mismatch(self):
        """carc radius start does not match previous segment end."""
        with pytest.raises(ExecutionError, match="does not match"):
            execute(
                "sketch [(10, 0), carc (5, 0) (0, 10) r:10, (0, 0), (10, 0)]"
            )


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
            f"sketch [({r}, 0), carc ({r}, 0) (0, {r}) (0, 0), (0, 0), ({r}, 0)] | extrude 1"
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
        src_center = f"sketch [({r}, 0), carc ({r}, 0) (0, {r}) (0, 0), (0, 0), ({r}, 0)] | extrude 1"
        src_radius = f"sketch [({r}, 0), carc ({r}, 0) (0, {r}) r:{r}, (0, 0), ({r}, 0)] | extrude 1"
        result_c = execute(src_center)
        result_r = execute(src_radius)
        bb_c = _bounding_box(result_c._shape).Get()
        bb_r = _bounding_box(result_r._shape).Get()
        for a, b in zip(bb_c, bb_r):
            assert abs(a - b) < 0.1, f"bbox mismatch: {bb_c} vs {bb_r}"


# ---------------------------------------------------------------------------
# Backward compatibility tests (new 3-point syntax)
# ---------------------------------------------------------------------------

class TestArcSyntax:
    """Ensure arc 3-point syntax works correctly."""

    def test_arc_3point_extrude(self):
        result = execute(
            "sketch [(5, 0), arc (5, 0) (0, -5) (-5, 0), (0, 7), (5, 0)] | extrude 10"
        )
        assert result is not None
        assert result._shape is not None

    def test_existing_sketch_lines_still_works(self):
        result = execute(
            "sketch [(5, 0), (0, 7), (-5, 0), (0, -7)] | extrude 10"
        )
        assert result is not None
        assert result._shape is not None
