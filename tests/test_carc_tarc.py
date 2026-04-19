"""Tests for arc unified syntax (3-point, center, radius).

Breaking change: carc keyword removed; all arc variants now use 'arc'.
  arc start through end              -- 3-point arc (ArcPath)
  arc start end center:(cx,cy)       -- center arc (CenterArcPath)
  arc start end radius:radius         -- radius arc (CenterArcPath)

Also tests auto-line connection when segment start doesn't match
the previous segment's end.
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

class TestArcCenterParsing:
    """Test that arc center: syntax parses to CenterArcPath."""

    def test_arc_center(self):
        tree = parse("sketch [(10, 0), arc (10, 0) (0, 10) center:(0, 0), (0, 0)]")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.SketchExpr)
        seg = stmt.segments[0]
        assert isinstance(seg, ast.CenterArcPath)
        assert isinstance(seg.start, ast.TupleLit)
        assert isinstance(seg.end, ast.TupleLit)
        assert isinstance(seg.center, ast.TupleLit)
        assert seg.radius is None

    def test_arc_radius(self):
        tree = parse("sketch [(10, 0), arc (10, 0) (0, 10) radius:10, (0, 0)]")
        prog = transform(tree)
        seg = prog.statements[0].segments[0]
        assert isinstance(seg, ast.CenterArcPath)
        assert isinstance(seg.start, ast.TupleLit)
        assert isinstance(seg.end, ast.TupleLit)
        assert seg.center is None
        assert seg.radius is not None

    def test_arc_radius_with_variable(self):
        tree = parse("$r = 10\nsketch [($r, 0), arc ($r, 0) (0, $r) radius:$r, (0, 0)]")
        prog = transform(tree)
        sketch = prog.statements[1]
        seg = sketch.segments[0]
        assert isinstance(seg, ast.CenterArcPath)
        assert seg.start is not None
        assert seg.radius is not None

    def test_arc_center_with_expressions(self):
        tree = parse("sketch [(5+5, 0), arc (5+5, 0) (0, 10) center:(0, 0), (0, 0)]")
        prog = transform(tree)
        seg = prog.statements[0].segments[0]
        assert isinstance(seg, ast.CenterArcPath)
        assert isinstance(seg.center, ast.TupleLit)


class TestCarcRemoved:
    """Verify that carc keyword is no longer reserved."""

    def test_carc_sketch_parse_error(self):
        """carc is no longer a keyword in sketch segments; should fail."""
        with pytest.raises(Exception):
            parse("sketch [(0, 0), (10, 0), carc (15, 5) (0, 0) (5, 0)]")

    def test_carc_standalone_is_var_or_func(self):
        """carc as standalone is parsed as a variable reference (no longer keyword)."""
        tree = parse("carc")
        prog = transform(tree)
        stmt = prog.statements[0]
        # carc is no longer a keyword; it becomes a VarRef
        assert isinstance(stmt, ast.VarRef)
        assert stmt.name == "carc"

    def test_carc_as_identifier(self):
        """carc can be used as a variable name."""
        tree = parse("carc = 42")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.Assignment)
        assert stmt.name == "carc"


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
        assert not hasattr(ast, 'TangentArcPath') or not isinstance(stmt, getattr(ast, 'TangentArcPath', type(None)))
        assert isinstance(stmt, ast.FuncCall)
        assert stmt.name == "tarc"


# ---------------------------------------------------------------------------
# Path primitive parsing tests
# ---------------------------------------------------------------------------

class TestPathPrimitiveParsing:
    """Test arc as standalone path primitive with center/radius kwargs."""

    def test_arc_path_center(self):
        tree = parse("arc (0, 0) (0, 10) center:(0, 5)")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.CenterArcPath)
        assert stmt.start is not None
        assert stmt.center is not None
        assert stmt.radius is None

    def test_arc_path_radius(self):
        tree = parse("arc (0, 0) (0, 10) radius:10")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.CenterArcPath)
        assert stmt.start is not None
        assert stmt.center is None
        assert stmt.radius is not None

    def test_arc_path_3point(self):
        """3-point arc via standalone arc."""
        tree = parse("arc (0, 0) (5, 5) (10, 0)")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.ArcPath)
        assert stmt.start is not None
        assert stmt.through is not None
        assert stmt.end is not None


# ---------------------------------------------------------------------------
# Codegen tests
# ---------------------------------------------------------------------------

class TestArcCodegen:
    """Test that arc center/radius generates correct internal representation."""

    def test_arc_center_codegen(self):
        code = compile_source(
            'sketch [(10, 0), arc (10, 0) (0, 10) center:(0, 0), (0, 0), (10, 0)]'
        )
        assert ".sketch(" in code
        assert '("carc_center"' in code

    def test_arc_radius_codegen(self):
        code = compile_source(
            'sketch [(10, 0), arc (10, 0) (0, 10) radius:10, (0, 0), (10, 0)]'
        )
        assert ".sketch(" in code
        assert '("carc_radius"' in code


# ---------------------------------------------------------------------------
# Execution tests
# ---------------------------------------------------------------------------

class TestArcCenterExecution:
    """Test arc center/radius execution producing correct geometry."""

    def test_arc_center_quarter_arc(self):
        """Quarter arc: (10,0) -> (0,10) around center (0,0)."""
        result = execute(
            "sketch [(10, 0), arc (10, 0) (0, 10) center:(0, 0), (0, 0), (10, 0)]"
        )
        assert result is not None
        assert hasattr(result, '_wires')
        assert len(result._wires) > 0

    def test_arc_center_extrude(self):
        """Quarter arc extruded to 3D solid."""
        result = execute(
            "sketch [(10, 0), arc (10, 0) (0, 10) center:(0, 0), (0, 0), (10, 0)] | extrude 5"
        )
        assert result is not None
        assert result._shape is not None

    def test_arc_radius_quarter_arc(self):
        """Quarter arc using radius specification."""
        result = execute(
            "$r = 10\n"
            "sketch [($r, 0), arc ($r, 0) (0, $r) radius:$r, (0, 0), ($r, 0)]"
        )
        assert result is not None
        assert len(result._wires) > 0

    def test_arc_radius_extrude(self):
        """Radius-based arc extruded to 3D solid."""
        result = execute(
            "$r = 10\n"
            "sketch [($r, 0), arc ($r, 0) (0, $r) radius:$r, (0, 0), ($r, 0)] | extrude 5"
        )
        assert result is not None
        assert result._shape is not None

    def test_arc_rounded_rect(self):
        """Rounded rectangle with 4 arc radius: segments."""
        src = """
$w = 20
$h = 10
$cr = 2
sketch [
  ($w/2 - $cr, -$h/2),
  arc ($w/2 - $cr, -$h/2) ($w/2, -$h/2 + $cr) radius:$cr,
  ($w/2, $h/2 - $cr),
  arc ($w/2, $h/2 - $cr) ($w/2 - $cr, $h/2) radius:$cr,
  (-$w/2 + $cr, $h/2),
  arc (-$w/2 + $cr, $h/2) (-$w/2, $h/2 - $cr) radius:$cr,
  (-$w/2, -$h/2 + $cr),
  arc (-$w/2, -$h/2 + $cr) (-$w/2 + $cr, -$h/2) radius:$cr
] | extrude 5
"""
        result = execute(src)
        assert result is not None
        assert result._shape is not None

    def test_arc_center_equidistance_error(self):
        """Center not equidistant from start and end should raise ExecutionError."""
        with pytest.raises(ExecutionError, match="equidistant"):
            execute(
                "sketch [(10, 0), arc (10, 0) (0, 5) center:(1, 1), (0, 0), (10, 0)]"
            )

    def test_arc_radius_too_small(self):
        """Radius smaller than half chord length should raise ExecutionError."""
        with pytest.raises(ExecutionError, match="chord length"):
            execute(
                "sketch [(10, 0), arc (10, 0) (0, 10) radius:3, (0, 0), (10, 0)]"
            )


# ---------------------------------------------------------------------------
# Auto-line connection tests (replaces start mismatch error tests)
# ---------------------------------------------------------------------------

class TestAutoLineConnection:
    """Test that segment start mismatch inserts implicit line instead of error."""

    def test_arc_start_mismatch_auto_line(self):
        """arc start does not match previous segment end -> auto-line inserted."""
        result = execute(
            "sketch [(0, 0), arc (1, 0) (0.5, 0.5) (1, 1), (0, 0)]"
        )
        assert result is not None
        assert len(result._wires) > 0

    def test_arc_center_start_mismatch_auto_line(self):
        """arc center: start does not match previous segment end -> auto-line inserted.
        Use center (0,0) with start (5,0) and end (0,5) -- both at radius 5."""
        result = execute(
            "sketch [(10, 0), arc (5, 0) (0, 5) center:(0, 0), (0, 0), (10, 0)]"
        )
        assert result is not None
        assert len(result._wires) > 0

    def test_arc_radius_start_mismatch_auto_line(self):
        """arc radius: start does not match previous segment end -> auto-line inserted."""
        result = execute(
            "sketch [(10, 0), arc (5, 0) (0, 10) radius:10, (0, 0), (10, 0)]"
        )
        assert result is not None
        assert len(result._wires) > 0

    def test_path_arc_start_mismatch_auto_line(self):
        """path: arc start mismatch inserts implicit line."""
        result = execute(
            "path [(0, 0), arc (5, 5) (7, 3) (10, 0)]"
        )
        assert result is not None
        assert len(result._wires) > 0
        # Count edges: should be 2 (bridge line + arc)
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopAbs import TopAbs_EDGE
        wire = result._wires[0]
        edge_count = 0
        exp = TopExp_Explorer(wire, TopAbs_EDGE)
        while exp.More():
            edge_count += 1
            exp.Next()
        assert edge_count == 2, f"Expected 2 edges (auto-line + arc), got {edge_count}"

    def test_path_arc_center_start_mismatch_auto_line(self):
        """path: arc center: start mismatch inserts implicit line.
        Use center (5,0) with start (0,0) and end (10,0) -- both at radius 5."""
        result = execute(
            "path [(3, 3), arc (0, 0) (10, 0) center:(5, 0)]"
        )
        assert result is not None
        assert len(result._wires) > 0


# ---------------------------------------------------------------------------
# Geometry verification tests
# ---------------------------------------------------------------------------

class TestArcGeometry:
    """Verify geometric correctness of center/radius arcs."""

    def test_arc_quarter_arc_bbox(self):
        """Quarter arc from (r,0) to (0,r) around (0,0) should have bbox [0,r]x[0,r]."""
        from polyscript.ocp_kernel import _bounding_box
        r = 10
        result = execute(
            f"sketch [({r}, 0), arc ({r}, 0) (0, {r}) center:(0, 0), (0, 0), ({r}, 0)] | extrude 1"
        )
        bb = _bounding_box(result._shape)
        xmin, ymin, zmin, xmax, ymax, zmax = bb.Get()
        assert xmin >= -0.1
        assert xmax <= r + 0.1
        assert ymin >= -0.1
        assert ymax <= r + 0.1

    def test_arc_radius_matches_center(self):
        """arc radius:R and arc center: should produce same bbox."""
        from polyscript.ocp_kernel import _bounding_box
        r = 10
        src_center = f"sketch [({r}, 0), arc ({r}, 0) (0, {r}) center:(0, 0), (0, 0), ({r}, 0)] | extrude 1"
        src_radius = f"sketch [({r}, 0), arc ({r}, 0) (0, {r}) radius:{r}, (0, 0), ({r}, 0)] | extrude 1"
        result_c = execute(src_center)
        result_r = execute(src_radius)
        bb_c = _bounding_box(result_c._shape).Get()
        bb_r = _bounding_box(result_r._shape).Get()
        for a, b in zip(bb_c, bb_r):
            assert abs(a - b) < 0.1, f"bbox mismatch: {bb_c} vs {bb_r}"


# ---------------------------------------------------------------------------
# Backward compatibility tests (3-point arc syntax unchanged)
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
