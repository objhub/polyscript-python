"""Tests for the OCP backend -- verifies codegen_ocp and ocp_kernel work end-to-end."""

import math
import pytest

from polyscript.executor import compile_source, execute


# ---------------------------------------------------------------------------
# Codegen output tests
# ---------------------------------------------------------------------------

class TestOCPCodegen:
    """Verify codegen_ocp produces correct Python code."""

    def test_import_header(self):
        code = compile_source("box 10 20 30")
        assert "from polyscript import ocp_kernel as cq" in code

    def test_no_cadquery_import(self):
        code = compile_source("box 10 20 30")
        assert "import cadquery" not in code

    def test_result_variable(self):
        code = compile_source("box 10 20 30")
        assert "_result" in code

    def test_math_import(self):
        code = compile_source("box 10 20 30")
        assert "import math" in code


# ---------------------------------------------------------------------------
# 3D Primitives
# ---------------------------------------------------------------------------

class TestOCP3DPrimitives:
    def test_box(self):
        result = execute("box 10 20 30")
        bb = result.val().BoundingBox()
        assert abs(bb.xlen - 10) < 0.01
        assert abs(bb.ylen - 20) < 0.01
        assert abs(bb.zlen - 30) < 0.01

    def test_cylinder(self):
        result = execute("cylinder 10 5")
        bb = result.val().BoundingBox()
        assert abs(bb.zlen - 10) < 0.01
        assert abs(bb.xlen - 10) < 0.5  # diameter

    def test_sphere(self):
        result = execute("sphere 5")
        bb = result.val().BoundingBox()
        assert abs(bb.xlen - 10) < 0.5  # diameter


# ---------------------------------------------------------------------------
# 2D Primitives -> Extrude
# ---------------------------------------------------------------------------

class TestOCP2DPrimitives:
    def test_rect_extrude(self):
        result = execute("rect 10 20 | extrude 5")
        bb = result.val().BoundingBox()
        assert abs(bb.xlen - 10) < 0.01
        assert abs(bb.ylen - 20) < 0.01
        assert abs(bb.zlen - 5) < 0.01

    def test_circle_extrude(self):
        result = execute("circle 5 | extrude 10")
        bb = result.val().BoundingBox()
        assert abs(bb.zlen - 10) < 0.01
        assert abs(bb.xlen - 10) < 0.5

    def test_ellipse_extrude(self):
        result = execute("ellipse 10 5 | extrude 3")
        bb = result.val().BoundingBox()
        assert abs(bb.zlen - 3) < 0.01
        assert abs(bb.xlen - 20) < 0.5  # 2*rx


# ---------------------------------------------------------------------------
# Modifiers
# ---------------------------------------------------------------------------

class TestOCPModifiers:
    def test_fillet(self):
        result = execute("box 10 10 10 | fillet 1")
        assert result._shape is not None

    def test_chamfer(self):
        result = execute("box 10 10 10 | chamfer 1")
        assert result._shape is not None

    def test_shell(self):
        result = execute("box 10 10 10 | shell 1")
        assert result._shape is not None

    def test_offset_2d(self):
        result = execute("rect 80 60 | offset -10 | extrude 5")
        assert result._shape is not None

    def test_offset_face_selection(self):
        result = execute("box 80 60 10 | faces >Z | offset -10 | cut 3")
        assert result._shape is not None

    def test_fillet_selected_edges(self):
        result = execute('box 10 10 10 | edges =Z | fillet 1')
        assert result._shape is not None


# ---------------------------------------------------------------------------
# Boolean operations
# ---------------------------------------------------------------------------

class TestOCPBoolean:
    def test_union(self):
        result = execute("box 10 10 10 | union sphere 5")
        assert result._shape is not None

    def test_cut_via_api(self):
        """Test boolean cut directly via ocp_kernel API."""
        from polyscript import ocp_kernel as cq
        wp = cq.Workplane("XY").box(10, 10, 10)
        tool = cq.Workplane("XY").sphere(3)
        result = wp.cut(tool)
        assert result._shape is not None

    def test_intersect_via_api(self):
        """Test boolean intersect directly via ocp_kernel API."""
        from polyscript import ocp_kernel as cq
        wp = cq.Workplane("XY").box(10, 10, 10)
        tool = cq.Workplane("XY").sphere(8)
        result = wp.intersect(tool)
        assert result._shape is not None


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

class TestOCPSelection:
    def test_faces_max_z(self):
        result = execute('box 10 10 10 | faces >Z | fillet 1')
        assert result._shape is not None

    def test_faces_min_z(self):
        result = execute('box 10 10 10 | faces <Z | fillet 1')
        assert result._shape is not None

    def test_edges_parallel_z(self):
        result = execute('box 10 10 10 | edges =Z | fillet 1')
        assert result._shape is not None

    def test_workplane_on_face(self):
        result = execute(
            'box 10 10 10 | faces >Z | workplane | circle 3 | extrude 5',
        )
        bb = result.val().BoundingBox()
        assert bb.zlen > 10  # extruded above the box


# ---------------------------------------------------------------------------
# Cut operations
# ---------------------------------------------------------------------------

class TestOCPCutOps:
    def test_hole(self):
        result = execute("box 20 20 10 | hole 3")
        assert result._shape is not None

    def test_hole_with_depth(self):
        result = execute("box 20 20 10 | hole 3 depth:5")
        assert result._shape is not None

    def test_hole_from_face_selection(self):
        """FaceSelection -> hole: hole at centre of selected face."""
        result = execute("box 80 60 10 | faces >Z | hole 5")
        assert result._shape is not None
        bb = result.val().BoundingBox()
        assert abs(bb.xlen - 80) < 0.01
        assert abs(bb.ylen - 60) < 0.01
        assert abs(bb.zlen - 10) < 0.01
        # The box with a hole should have more faces than the original 6
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopAbs import TopAbs_FACE
        face_count = 0
        exp = TopExp_Explorer(result._shape, TopAbs_FACE)
        while exp.More():
            face_count += 1
            exp.Next()
        assert face_count > 6

    def test_hole_from_face_selection_with_depth(self):
        """FaceSelection -> hole with depth: blind hole."""
        result = execute("box 80 60 10 | faces >Z | hole 5 depth:3")
        assert result._shape is not None
        bb = result.val().BoundingBox()
        assert abs(bb.zlen - 10) < 0.01

    def test_hole_from_face_selection_multiple_faces(self):
        """FaceSelection with multiple faces -> hole at each face centre."""
        # Select both >Z and <Z faces, put holes through both
        result = execute("box 80 60 10 | faces >Z <Z | hole 5")
        assert result._shape is not None
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopAbs import TopAbs_FACE
        face_count = 0
        exp = TopExp_Explorer(result._shape, TopAbs_FACE)
        while exp.More():
            face_count += 1
            exp.Next()
        assert face_count > 6

    def test_hole_on_faces_api(self):
        """Direct API test of holeOnFaces method."""
        from polyscript import ocp_kernel as cq
        wp = cq.Workplane("XY").box(40, 40, 10)
        result = wp.faces(">Z").holeOnFaces(5)
        assert result._shape is not None
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopAbs import TopAbs_FACE
        face_count = 0
        exp = TopExp_Explorer(result._shape, TopAbs_FACE)
        while exp.More():
            face_count += 1
            exp.Next()
        assert face_count > 6

    def test_hole_on_faces_no_shape(self):
        """holeOnFaces with no shape returns self."""
        from polyscript import ocp_kernel as cq
        wp = cq.Workplane("XY")
        result = wp.holeOnFaces(5)
        assert result is wp

    def test_hole_on_faces_no_selected_faces(self):
        """holeOnFaces with no selected faces returns self."""
        from polyscript import ocp_kernel as cq
        wp = cq.Workplane("XY").box(40, 40, 10)
        result = wp.holeOnFaces(5)
        assert result is wp

    def test_cut_thru_via_api(self):
        """Test cutThruAll via ocp_kernel API."""
        from polyscript import ocp_kernel as cq
        wp = cq.Workplane("XY").box(20, 20, 10)
        wp2 = wp.faces(">Z").workplane().circle(3).cutThruAll()
        assert wp2._shape is not None

    def test_cut_blind_via_api(self):
        """Test cutBlind via ocp_kernel API."""
        from polyscript import ocp_kernel as cq
        wp = cq.Workplane("XY").box(20, 20, 10)
        wp2 = wp.faces(">Z").workplane().circle(3).cutBlind(-5)
        assert wp2._shape is not None


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------

class TestOCPTransform:
    def test_translate(self):
        result = execute("box 10 10 10 | translate 20 0 0")
        bb = result.val().BoundingBox()
        assert bb.xmin > 10

    def test_translate_vertex_selection(self):
        """translate in VertexSelection context offsets vertex positions."""
        result = execute("rect 80 60 | verts | translate 10 10 10 | cone 6 2 0")
        assert result._shape is not None
        bb = result.val().BoundingBox()
        # All cones should be shifted by (10,10,10) from original rect vertices
        # Original rect vertices are at (+/-40, +/-30, 0) on XY plane
        # After translate 10 10 10, they should be around (-30..50, -20..40, 10)
        assert bb.zmin > 5  # z should be around 10 (shifted up)

    def test_rotate(self):
        result = execute("box 10 10 10 | rotate 90 0 0")
        assert result._shape is not None


# ---------------------------------------------------------------------------
# Revolve / Sweep
# ---------------------------------------------------------------------------

class TestOCPRevolveSweep:
    def test_revolve_offset_rect(self):
        """Revolve requires the profile to not cross the axis."""
        from polyscript import ocp_kernel as cq
        wp = cq.Workplane("XY").center(10, 0).rect(5, 10).revolve(180)
        assert wp._shape is not None

    def test_sweep_circle_along_line(self):
        """Sweep a circle along a wire path."""
        from polyscript import ocp_kernel as cq
        # Create a path
        path = cq.Workplane("XZ").polyline([(0, 0), (0, 10), (10, 10)])
        # Sweep
        wp = cq.Workplane("XY").circle(2).sweep(path)
        assert wp._shape is not None


# ---------------------------------------------------------------------------
# Variables and expressions
# ---------------------------------------------------------------------------

class TestOCPExpressions:
    def test_variable(self):
        result = execute("$w = 10\nbox $w $w $w")
        bb = result.val().BoundingBox()
        assert abs(bb.xlen - 10) < 0.01

    def test_math_expr(self):
        result = execute("box (2 + 3) (10 / 2) (3 * 2)")
        bb = result.val().BoundingBox()
        assert abs(bb.xlen - 5) < 0.01
        assert abs(bb.ylen - 5) < 0.01
        assert abs(bb.zlen - 6) < 0.01

    def test_trig(self):
        result = execute("$x = sin(pi / 6) * 20\nbox $x $x $x")
        bb = result.val().BoundingBox()
        assert abs(bb.xlen - 10) < 0.1


# ---------------------------------------------------------------------------
# Wire class
# ---------------------------------------------------------------------------

class TestOCPWire:
    def test_make_helix(self):
        from polyscript import ocp_kernel as cq
        wire = cq.Wire.makeHelix(2, 10, 5)
        assert wire is not None


# ---------------------------------------------------------------------------
# Exporters
# ---------------------------------------------------------------------------

class TestOCPExporters:
    def test_export_stl(self, tmp_path):
        result = execute("box 10 10 10")
        from polyscript.ocp_kernel import exporters
        path = str(tmp_path / "test.stl")
        exporters.export(result, path)
        assert (tmp_path / "test.stl").exists()
        assert (tmp_path / "test.stl").stat().st_size > 0

    def test_export_step(self, tmp_path):
        result = execute("box 10 10 10")
        from polyscript.ocp_kernel import exporters
        path = str(tmp_path / "test.step")
        exporters.export(result, path)
        assert (tmp_path / "test.step").exists()
        assert (tmp_path / "test.step").stat().st_size > 0


# ---------------------------------------------------------------------------
# Verts | circle | cut pipeline
# ---------------------------------------------------------------------------

class TestOCPVertsCircleCut:
    """Test the verts | circle | cut pattern -- placing holes at rect vertices."""

    def test_verts_extracts_rect_vertices_not_box_vertices(self):
        """After faces | rect | verts, vertices come from the rect wire (4), not the box (8)."""
        from polyscript import ocp_kernel as cq
        wp = cq.Workplane("XY").box(80, 60, 10).faces(">Z").workplane().rect(70, 50)
        wp_v = wp.vertices()
        assert wp_v._points is not None
        assert len(wp_v._points) == 4

    def test_verts_coordinates(self):
        """The 4 vertices of rect 70 50 should be at (+-35, +-25)."""
        from polyscript import ocp_kernel as cq
        wp = cq.Workplane("XY").box(80, 60, 10).faces(">Z").workplane().rect(70, 50)
        wp_v = wp.vertices()
        pts = sorted(wp_v._points)
        expected = sorted([(-35, -25), (-35, 25), (35, -25), (35, 25)])
        for (ax, ay), (ex, ey) in zip(pts, expected):
            assert abs(ax - ex) < 0.01
            assert abs(ay - ey) < 0.01

    def test_circle_at_each_vertex(self):
        """circle(1) after verts should create 4 wire circles."""
        from polyscript import ocp_kernel as cq
        wp = cq.Workplane("XY").box(80, 60, 10).faces(">Z").workplane().rect(70, 50)
        wp_c = wp.vertices().circle(1)
        assert len(wp_c._wires) == 4

    def test_full_pipeline_execution(self):
        """Full pipeline produces a valid solid with holes."""
        result = execute(
            'box 80 60 10 | faces ">Z" | rect 70 50 | verts | circle 1 | cut',
        )
        bb = result.val().BoundingBox()
        assert abs(bb.xlen - 80) < 0.01
        assert abs(bb.ylen - 60) < 0.01
        assert abs(bb.zlen - 10) < 0.01
        # The box with 4 holes should have more faces than the original 6
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopAbs import TopAbs_FACE
        face_count = 0
        exp = TopExp_Explorer(result._shape, TopAbs_FACE)
        while exp.More():
            face_count += 1
            exp.Next()
        assert face_count > 6  # original box has 6, with 4 holes we expect more

    def test_vertex_dedup(self):
        """_get_vertices should not return duplicate vertices for a wire."""
        from polyscript import ocp_kernel as cq
        from polyscript.ocp_kernel import _get_vertices, _make_rect_wire, _make_plane
        plane = _make_plane("XY")
        wire = _make_rect_wire(10, 10, plane, 0, 0)
        verts = _get_vertices(wire)
        assert len(verts) == 4  # rectangle has exactly 4 unique vertices


class TestOCPVerts3DPrimitive:
    """Test 3D primitives placed at vertex positions."""

    def test_place_3d_at_points_sphere(self):
        """place_3d_at_points should create spheres at each rect vertex."""
        from polyscript import ocp_kernel as cq
        wp = cq.Workplane("XY").rect(100, 100).vertices()
        result = wp.place_3d_at_points(lambda: cq.Workplane("XY").sphere(5))
        assert result._shape is not None
        bb = result.val().BoundingBox()
        # The bounding box should span from roughly -55 to 55 (50 + 5 radius)
        assert bb.xlen > 100
        assert bb.ylen > 100

    def test_place_3d_at_points_box(self):
        """place_3d_at_points should create boxes at each rect vertex."""
        from polyscript import ocp_kernel as cq
        wp = cq.Workplane("XY").rect(100, 100).vertices()
        result = wp.place_3d_at_points(lambda: cq.Workplane("XY").box(10, 10, 10))
        assert result._shape is not None
        from OCP.TopExp import TopExp_Explorer
        from OCP.TopAbs import TopAbs_SOLID
        solid_count = 0
        exp = TopExp_Explorer(result._shape, TopAbs_SOLID)
        while exp.More():
            solid_count += 1
            exp.Next()
        # 4 boxes fused together -- at least 1 solid compound
        assert solid_count >= 1

    def test_full_pipeline_verts_sphere(self):
        """Full pipeline: rect | verts | sphere produces valid geometry."""
        result = execute(
            'rect 100 100 | verts | sphere 5',
        )
        assert result._shape is not None
        bb = result.val().BoundingBox()
        # Spheres at corners of 100x100 rect, radius 5
        assert bb.xlen > 100
        assert bb.ylen > 100

    def test_full_pipeline_box_verts_cylinder(self):
        """Full pipeline: box | verts | cylinder produces valid geometry."""
        result = execute(
            'box 50 50 50 | verts | cylinder 10 3',
        )
        assert result._shape is not None
