"""Tests for wire [...] literal (open wire)."""

import pytest
from polyscript.executor import compile_source
from polyscript import ast_nodes as ast
from polyscript.parser import parse
from polyscript.transformer import transform


class TestPathParsing:
    """Test that wire [...] syntax parses to correct AST nodes."""

    def test_basic_path_tuples(self):
        """wire [(0,0), (10,0), (10,10)] - start + two line-to segments."""
        tree = parse("wire [(0,0), (10,0), (10,10)]")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.WireLiteral)
        assert isinstance(stmt.start, ast.TupleLit)
        assert len(stmt.segments) == 2  # two line segments after start

    def test_single_line(self):
        """wire [(0,0), (10,0)] - start + one line segment."""
        tree = parse("wire [(0,0), (10,0)]")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.WireLiteral)
        assert isinstance(stmt.start, ast.TupleLit)
        assert len(stmt.segments) == 1

    def test_arc_center_mixed(self):
        """path with arc center: mixed in."""
        tree = parse("wire [(0,0), arc (0,0) (10,10) center:(10,0)]")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.WireLiteral)
        assert isinstance(stmt.start, ast.TupleLit)
        assert len(stmt.segments) == 1
        seg = stmt.segments[0]
        assert isinstance(seg, ast.CenterArcPath)
        assert seg.center is not None

    def test_arc_radius(self):
        """path with arc radius mixed in."""
        tree = parse("wire [(0,0), arc (0,0) (10,10) radius:5]")
        prog = transform(tree)
        stmt = prog.statements[0]
        seg = stmt.segments[0]
        assert isinstance(seg, ast.CenterArcPath)
        assert seg.radius is not None

    def test_arc_mixed(self):
        """path with 3-point arc."""
        tree = parse("wire [(0,0), arc (0,0) (5,5) (10,0)]")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert len(stmt.segments) == 1
        seg = stmt.segments[0]
        assert isinstance(seg, ast.ArcPath)

    def test_3d_coords(self):
        """wire [(0,0,0), (10,0,10), (20,0,20)] - 3D tuples."""
        tree = parse("wire [(0,0,0), (10,0,10), (20,0,20)]")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.WireLiteral)
        # Start is a 3D tuple
        assert len(stmt.start.values) == 3
        # Segments are 3D tuples (line-to)
        assert len(stmt.segments) == 2

    def test_2d_3d_mixed(self):
        """wire [(0,0), (10,0,5)] - 2D start, 3D line-to."""
        tree = parse("wire [(0,0), (10,0,5)]")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert len(stmt.start.values) == 2
        assert len(stmt.segments) == 1
        seg = stmt.segments[0]
        assert isinstance(seg, ast.TupleLit)
        assert len(seg.values) == 3

    def test_explicit_line_segment(self):
        """wire [line (0,0) (10,0)] - explicit line segment."""
        tree = parse("wire [line (0,0) (10,0)]")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert stmt.start is None  # no bare tuple start
        assert len(stmt.segments) == 1
        seg = stmt.segments[0]
        assert isinstance(seg, ast.LinePath)

    def test_bezier_segment(self):
        """wire [(0,0), bezier [(0,0), (5,5), (10,0)]]"""
        tree = parse("wire [(0,0), bezier [(0,0), (5,5), (10,0)]]")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert len(stmt.segments) == 1
        seg = stmt.segments[0]
        assert isinstance(seg, ast.BezierPath)

    def test_spline_segment(self):
        """wire [(0,0), spline [(0,0), (5,5), (10,0)]]"""
        tree = parse("wire [(0,0), spline [(0,0), (5,5), (10,0)]]")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert len(stmt.segments) == 1
        seg = stmt.segments[0]
        assert isinstance(seg, ast.SplinePath)

    def test_path_in_assignment(self):
        """p = wire [(0,0), (10,0), (10,10)]"""
        tree = parse("p = wire [(0,0), (10,0), (10,10)]")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.Assignment)
        assert isinstance(stmt.value, ast.WireLiteral)

    def test_path_multiline(self):
        """Multi-line path with trailing comma."""
        src = """\
wire [
  (0, 0),
  (10, 0),
  (10, 10),
]"""
        tree = parse(src)
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.WireLiteral)
        assert len(stmt.segments) == 2

    # --- workplane | wire [...] AST tests ---

    def test_workplane_xz_pipe_path_ast(self):
        """workplane XZ | wire [...] -> Pipeline(Workplane, [Implicit2DPrimitive(PathLiteral)])."""
        tree = parse("workplane XZ | wire [(0,0), (10,0), (10,10)]")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.Pipeline)
        assert isinstance(stmt.source, ast.Workplane)
        assert stmt.source.plane == "XZ"
        assert len(stmt.operations) == 1
        op = stmt.operations[0]
        assert isinstance(op, ast.Implicit2DPrimitive)
        assert isinstance(op.primitive, ast.WireLiteral)

    def test_workplane_yz_pipe_path_ast(self):
        """workplane YZ | wire [...] -> Pipeline(Workplane, [Implicit2DPrimitive(PathLiteral)])."""
        tree = parse("workplane YZ | wire [(0,0), (10,0), (10,10)]")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.Pipeline)
        assert isinstance(stmt.source, ast.Workplane)
        assert stmt.source.plane == "YZ"
        assert len(stmt.operations) == 1
        op = stmt.operations[0]
        assert isinstance(op, ast.Implicit2DPrimitive)
        assert isinstance(op.primitive, ast.WireLiteral)

    def test_workplane_quoted_xz_pipe_path_ast(self):
        """workplane "XZ" | wire [...] should produce identical AST to unquoted form."""
        tree = parse('workplane "XZ" | wire [(0,0), (10,0), (10,10)]')
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.Pipeline)
        assert isinstance(stmt.source, ast.Workplane)
        assert stmt.source.plane == "XZ"
        op = stmt.operations[0]
        assert isinstance(op, ast.Implicit2DPrimitive)
        assert isinstance(op.primitive, ast.WireLiteral)


class TestPathCodegen:
    """Test that path generates correct code."""

    def test_path_lines_codegen(self):
        code = compile_source("wire [(0,0), (10,0), (10,10)]")
        assert ".wire(" in code
        assert '("line"' in code

    def test_path_arc_codegen(self):
        code = compile_source(
            "wire [(0,0), arc (0,0) (5,5) (10,0)]"
        )
        assert ".wire(" in code
        assert '("arc"' in code

    def test_path_arc_center_codegen(self):
        code = compile_source(
            "wire [(0,0), arc (0,0) (10,10) center:(10,0)]"
        )
        assert ".wire(" in code
        assert '("carc_center"' in code

    def test_path_arc_radius_codegen(self):
        code = compile_source(
            "wire [(0,0), arc (0,0) (10,10) radius:5]"
        )
        assert ".wire(" in code
        assert '("carc_radius"' in code

    def test_path_explicit_line_codegen(self):
        code = compile_source("wire [line (0,0) (10,0)]")
        assert ".wire(" in code
        assert '("line_se"' in code

    def test_path_sweep_codegen(self):
        """path used as sweep argument."""
        code = compile_source(
            "circle 5 | sweep (wire [(0,0), (10,0), (10,10)])"
        )
        assert ".wire(" in code
        assert ".sweep(" in code

    def test_pipe_path_codegen(self):
        """path used in pipe context (e.g. workplane | wire [...])."""
        code = compile_source(
            'workplane "XZ" | wire [(0,0), (10,0), (10,10)]'
        )
        assert ".wire(" in code

    def test_pipe_path_xz_codegen_uses_xz_workplane(self):
        """workplane XZ | wire [...] should generate Workplane("XZ").wire(...)."""
        code = compile_source(
            'workplane XZ | wire [(0,0), (10,0), (10,10)]'
        )
        assert 'Workplane("XZ")' in code
        assert ".wire(" in code

    def test_pipe_path_yz_codegen_uses_yz_workplane(self):
        """workplane YZ | wire [...] should generate Workplane("YZ").wire(...)."""
        code = compile_source(
            'workplane YZ | wire [(0,0), (10,0), (10,10)]'
        )
        assert 'Workplane("YZ")' in code
        assert ".wire(" in code

    def test_standalone_path_codegen_uses_xy_workplane(self):
        """Standalone wire [...] should generate Workplane("XY").wire(...)."""
        code = compile_source(
            'wire [(0,0), (10,0), (10,10)]'
        )
        assert 'Workplane("XY")' in code
        assert ".wire(" in code


class TestPathExecution:
    """Test path execution with OCP backend."""

    def test_path_lines_execute(self):
        from polyscript.executor import execute
        result = execute("wire [(0,0), (10,0), (10,10)]")
        assert result is not None
        assert hasattr(result, '_wires')
        assert len(result._wires) > 0

    def test_path_does_not_autoclose(self):
        """path must NOT auto-close (unlike sketch)."""
        from polyscript.executor import execute

        # Open path: start (0,0) -> (10,0) -> (10,10)
        # The wire should remain open (3 vertices, 2 edges)
        result = execute("wire [(0,0), (10,0), (10,10)]")
        wire = result._wires[0]

        # Count edges: should be 2 (not 3 as sketch would produce)
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopAbs import TopAbs_EDGE
        edge_count = 0
        exp = TopExp_Explorer(wire, TopAbs_EDGE)
        while exp.More():
            edge_count += 1
            exp.Next()
        assert edge_count == 2, f"Expected 2 edges (open path), got {edge_count}"

    def test_sketch_does_autoclose(self):
        """Verify sketch auto-closes for comparison with path."""
        from polyscript.executor import execute

        # Same vertices but sketch should auto-close
        result = execute("sketch [(0,0), (10,0), (10,10)]")
        wire = result._wires[0]

        from OCP.TopExp import TopExp_Explorer
        from OCP.TopAbs import TopAbs_EDGE
        edge_count = 0
        exp = TopExp_Explorer(wire, TopAbs_EDGE)
        while exp.More():
            edge_count += 1
            exp.Next()
        assert edge_count == 3, f"Expected 3 edges (closed sketch), got {edge_count}"

    def test_path_with_arc(self):
        from polyscript.executor import execute
        result = execute(
            "wire [(0,0), arc (0,0) (5,5) (10,0)]"
        )
        assert result is not None
        assert len(result._wires) > 0

    def test_path_with_arc_center(self):
        from polyscript.executor import execute
        result = execute(
            "wire [(0,0), arc (0,0) (10,0) center:(5,0)]"
        )
        assert result is not None
        assert len(result._wires) > 0

    def test_path_with_arc_radius(self):
        from polyscript.executor import execute
        result = execute(
            "wire [(0,0), arc (0,0) (10,0) radius:5]"
        )
        assert result is not None
        assert len(result._wires) > 0

    def test_path_3d_coords(self):
        from polyscript.executor import execute
        result = execute("wire [(0,0,0), (10,0,10), (20,0,20)]")
        assert result is not None
        assert len(result._wires) > 0

    def test_path_2d_3d_mixed(self):
        from polyscript.executor import execute
        result = execute("wire [(0,0), (10,0,5)]")
        assert result is not None
        assert len(result._wires) > 0

    def test_path_explicit_line(self):
        from polyscript.executor import execute
        result = execute("wire [line (0,0) (10,0), (10,10)]")
        assert result is not None
        assert len(result._wires) > 0

    def test_path_sweep(self):
        """circle swept along a path produces a solid."""
        from polyscript.executor import execute
        result = execute(
            "circle 2 | sweep (wire [(0,0), (20,0)])"
        )
        assert result is not None
        assert result._shape is not None

    def test_path_sweep_with_arc_radius(self):
        """circle swept along a path with arc radius:."""
        from polyscript.executor import execute
        result = execute(
            "circle 2 | sweep (wire [(0,0), (10,0), arc (10,0) (15,5) radius:5])"
        )
        assert result is not None
        assert result._shape is not None

    def test_path_auto_line_on_mismatch(self):
        """Start mismatch inserts auto-line instead of raising error."""
        from polyscript.executor import execute
        result = execute("wire [(0,0), arc (5,5) (7,3) (10,0)]")
        assert result is not None
        assert len(result._wires) > 0

    def test_path_as_variable_then_sweep(self):
        """Assign path to variable and use in sweep."""
        from polyscript.executor import execute
        result = execute(
            "p = wire [(0,0), (20,0), (20,20)]\ncircle 2 | sweep p"
        )
        assert result is not None
        assert result._shape is not None

    def test_pipe_path(self):
        """path in pipe context with workplane."""
        from polyscript.executor import execute
        result = execute(
            'workplane "XZ" | wire [(0,0), (10,0), (10,10)]'
        )
        assert result is not None
        assert len(result._wires) > 0

    # --- workplane | path execution tests ---

    def test_workplane_xz_path_produces_wire(self):
        """workplane XZ | wire [...] produces a valid wire."""
        from polyscript.executor import execute
        result = execute(
            'workplane XZ | wire [(0,0), (10,0), (10,10)]'
        )
        assert result is not None
        assert len(result._wires) > 0

    def test_workplane_yz_path_produces_wire(self):
        """workplane YZ | wire [...] produces a valid wire."""
        from polyscript.executor import execute
        result = execute(
            'workplane YZ | wire [(0,0), (10,0), (10,10)]'
        )
        assert result is not None
        assert len(result._wires) > 0

    def test_workplane_xz_path_vertices_on_xz_plane(self):
        """XZ path vertices must have Y=0 (lie on the XZ plane)."""
        from polyscript.executor import execute
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopAbs import TopAbs_VERTEX
        from OCP.BRep import BRep_Tool
        from OCP.TopoDS import TopoDS

        result = execute(
            'workplane XZ | wire [(0,0), (10,0), (10,10)]'
        )
        wire = result._wires[0]
        exp = TopExp_Explorer(wire, TopAbs_VERTEX)
        vertex_count = 0
        while exp.More():
            v = TopoDS.Vertex_s(exp.Current())
            pt = BRep_Tool.Pnt_s(v)
            assert abs(pt.Y()) < 1e-6, (
                f"XZ path vertex should have Y=0, got Y={pt.Y()}"
            )
            vertex_count += 1
            exp.Next()
        assert vertex_count > 0

    def test_workplane_yz_path_vertices_on_yz_plane(self):
        """YZ path vertices must have X=0 (lie on the YZ plane)."""
        from polyscript.executor import execute
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopAbs import TopAbs_VERTEX
        from OCP.BRep import BRep_Tool
        from OCP.TopoDS import TopoDS

        result = execute(
            'workplane YZ | wire [(0,0), (10,0), (10,10)]'
        )
        wire = result._wires[0]
        exp = TopExp_Explorer(wire, TopAbs_VERTEX)
        vertex_count = 0
        while exp.More():
            v = TopoDS.Vertex_s(exp.Current())
            pt = BRep_Tool.Pnt_s(v)
            assert abs(pt.X()) < 1e-6, (
                f"YZ path vertex should have X=0, got X={pt.X()}"
            )
            vertex_count += 1
            exp.Next()
        assert vertex_count > 0

    def test_standalone_path_vertices_on_xy_plane(self):
        """Standalone wire [...] vertices must have Z=0 (lie on the XY plane)."""
        from polyscript.executor import execute
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopAbs import TopAbs_VERTEX
        from OCP.BRep import BRep_Tool
        from OCP.TopoDS import TopoDS

        result = execute(
            'wire [(0,0), (10,0), (10,10)]'
        )
        wire = result._wires[0]
        exp = TopExp_Explorer(wire, TopAbs_VERTEX)
        vertex_count = 0
        while exp.More():
            v = TopoDS.Vertex_s(exp.Current())
            pt = BRep_Tool.Pnt_s(v)
            assert abs(pt.Z()) < 1e-6, (
                f"XY path vertex should have Z=0, got Z={pt.Z()}"
            )
            vertex_count += 1
            exp.Next()
        assert vertex_count > 0

    def test_workplane_xz_path_bounding_box(self):
        """XZ path bounding box should span X and Z, with zero Y extent."""
        from polyscript.executor import execute
        from OCP.Bnd import Bnd_Box
        from OCP.BRepBndLib import BRepBndLib

        result = execute(
            'workplane XZ | wire [(0,0), (10,0), (10,10)]'
        )
        wire = result._wires[0]
        bbox = Bnd_Box()
        BRepBndLib.Add_s(wire, bbox)
        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
        # X spans [0, 10], Y stays at 0, Z spans (on XZ, v maps to -Z)
        assert (xmax - xmin) > 5, f"X extent too small: {xmax - xmin}"
        assert abs(ymax - ymin) < 1e-6, f"Y extent should be ~0: {ymax - ymin}"
        assert (zmax - zmin) > 5, f"Z extent too small: {zmax - zmin}"

    def test_workplane_xz_path_sweep_produces_solid(self):
        """workplane XZ | wire [...] | sweep (circle 2) produces a valid solid."""
        from polyscript.executor import execute
        result = execute(
            'workplane XZ | wire [(0,0),(10,0),(10,10),(0,10),(0,0)] | sweep (circle 2)'
        )
        assert result is not None
        assert result._shape is not None

    def test_workplane_yz_path_sweep_produces_solid(self):
        """workplane YZ | wire [...] | sweep (circle 2) produces a valid solid."""
        from polyscript.executor import execute
        result = execute(
            'workplane YZ | wire [(0,0),(10,0),(10,10),(0,10),(0,0)] | sweep (circle 2)'
        )
        assert result is not None
        assert result._shape is not None
