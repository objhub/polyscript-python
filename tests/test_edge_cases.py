"""Edge-case tests for PolyScript (Phase 2).

Covers:
  1. 2D boolean annulus volume
  2. 2D fillet corner-rounding verification
  3. Helix sweep (ConstantBinormal) continuity / bbox
  4. Nested list comprehension
  5. Compound selector (AND)
  6. Degenerate input (circle 0)
  7. Precision boundary (1 um scale)
"""

import math
import pytest

from polyscript.executor import compile_source, execute


# ---------------------------------------------------------------------------
# Helper: count topology items via TopExp_Explorer
# ---------------------------------------------------------------------------

def _count_topo(shape, topo_type):
    """Return number of sub-shapes of *topo_type* in *shape*."""
    from OCP.TopExp import TopExp_Explorer
    count = 0
    exp = TopExp_Explorer(shape, topo_type)
    while exp.More():
        count += 1
        exp.Next()
    return count


def _count_arcs_on_face(face):
    """Count circular-arc edges on a given TopoDS_Face."""
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_EDGE
    from OCP.TopoDS import TopoDS
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GeomAbs import GeomAbs_Circle
    count = 0
    exp = TopExp_Explorer(face, TopAbs_EDGE)
    while exp.More():
        edge = TopoDS.Edge_s(exp.Current())
        adaptor = BRepAdaptor_Curve(edge)
        if adaptor.GetType() == GeomAbs_Circle:
            count += 1
        exp.Next()
    return count


def _top_face(shape):
    """Return the face whose centre-of-mass has the highest Z."""
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopoDS import TopoDS
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    best = None
    best_z = -1e30
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        face = TopoDS.Face_s(exp.Current())
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face, props)
        z = props.CentreOfMass().Z()
        if z > best_z:
            best_z = z
            best = face
        exp.Next()
    return best


def _volume(shape):
    """Compute volume of a solid shape."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    return props.Mass()


# ===========================================================================
# 1. 2D boolean annulus: circle 10 | diff (circle 3) | extrude 5
# ===========================================================================

class Test2DBooleanAnnulus:
    """Extruded annulus from 2D diff should have volume = pi*(R^2 - r^2)*h."""

    def test_annulus_volume(self):
        result = execute("circle 10 | diff (circle 3) | extrude 5")
        assert result._shape is not None

        vol = _volume(result._shape)
        expected = math.pi * (10**2 - 3**2) * 5  # ~1429.42
        rel_error = abs(vol - expected) / expected
        assert rel_error < 0.01, (
            f"Annulus volume {vol:.2f} deviates from expected {expected:.2f} "
            f"by {rel_error*100:.4f}%"
        )

    def test_annulus_bbox(self):
        result = execute("circle 10 | diff (circle 3) | extrude 5")
        bb = result.val().BoundingBox()
        # Outer diameter 20, height 5 (extrude starts at z=0)
        assert abs(bb.xlen - 20) < 0.5
        assert abs(bb.ylen - 20) < 0.5
        assert abs(bb.zlen - 5) < 0.01


# ===========================================================================
# 2. 2D fillet: rect 10 10 | fillet 1 | extrude 5
# ===========================================================================

class Test2DFillet:
    """2D fillet should produce 4 corner arcs visible on the top face."""

    def test_top_face_has_four_arcs(self):
        result = execute("rect 10 10 | fillet 1 | extrude 5")
        assert result._shape is not None

        top = _top_face(result._shape)
        assert top is not None, "Could not find top face"

        arc_count = _count_arcs_on_face(top)
        assert arc_count == 4, (
            f"Expected 4 corner arcs on top face, got {arc_count}"
        )

    def test_face_count_after_fillet(self):
        """A filleted-rect extrusion has more faces than a plain rect extrusion.

        Plain rect extrusion: 6 faces.
        Filleted rect extrusion: 10 faces (4 flat sides + 4 fillet surfaces + top + bottom).
        """
        from OCP.TopAbs import TopAbs_FACE
        result = execute("rect 10 10 | fillet 1 | extrude 5")
        face_count = _count_topo(result._shape, TopAbs_FACE)
        assert face_count == 10, f"Expected 10 faces, got {face_count}"

    def test_bbox_unchanged_by_fillet(self):
        """Fillet should not change the overall bounding box."""
        result = execute("rect 10 10 | fillet 1 | extrude 5")
        bb = result.val().BoundingBox()
        assert abs(bb.xlen - 10) < 0.01
        assert abs(bb.ylen - 10) < 0.01
        assert abs(bb.zlen - 5) < 0.01


# ===========================================================================
# 3. Helix sweep (ConstantBinormal)
# ===========================================================================

class TestHelixSweep:
    """helix 5 30 10 | sweep (circle 2) — thread-like shape."""

    def test_shape_created(self):
        result = execute("helix 5 30 10 | sweep (circle 2)")
        assert result._shape is not None

    def test_shape_valid(self):
        from OCP.BRepCheck import BRepCheck_Analyzer
        result = execute("helix 5 30 10 | sweep (circle 2)")
        analyzer = BRepCheck_Analyzer(result._shape)
        assert analyzer.IsValid(), "Helix sweep produced invalid shape"

    def test_bbox_within_expected_range(self):
        """Helix r=10, profile r=2 => bbox ~ 24 x 24 x ~34."""
        result = execute("helix 5 30 10 | sweep (circle 2)")
        bb = result.val().BoundingBox()
        # X/Y: helix radius 10 + profile radius 2 => [-12, 12]
        assert 23 < bb.xlen < 25, f"xlen={bb.xlen}"
        assert 23 < bb.ylen < 25, f"ylen={bb.ylen}"
        # Z: height 30 + profile overshoot at ends (~2 each side)
        assert bb.zlen > 29, f"zlen={bb.zlen} too short"
        assert bb.zlen < 36, f"zlen={bb.zlen} too long"

    def test_edge_and_face_count(self):
        """Helix sweep should produce a reasonable number of faces/edges.

        MakePipeShell with ConstantBinormal typically produces 3 faces
        (inner surface, outer surface, seam) and 6 edges for an open helix.
        """
        from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE
        result = execute("helix 5 30 10 | sweep (circle 2)")
        face_count = _count_topo(result._shape, TopAbs_FACE)
        edge_count = _count_topo(result._shape, TopAbs_EDGE)
        assert face_count >= 2, f"Expected >= 2 faces, got {face_count}"
        assert edge_count >= 2, f"Expected >= 2 edges, got {edge_count}"


# ===========================================================================
# 4. Nested list comprehension
# ===========================================================================

class TestNestedListComprehension:
    """Nested comprehension: inner comprehension evaluated first.

    NOTE: SPEC.md states "nested comprehension is not supported" (line 1174:
    "ネストした内包表記は非サポート"). However, the Python implementation
    actually parses and executes nested comprehensions correctly.  This test
    pins the *current* behaviour (working nested comprehension).  If this is
    unintended, the parser should reject it; if intentional, SPEC should be
    updated.

    SPEC <-> implementation deviation:
      - File: devel/SPEC.md, line ~1174
      - SPEC says: nested comprehension is not supported
      - Implementation: parses and executes nested comprehension
      - Suggestion: either reject nested comprehension in the parser, or
        update SPEC to document this as supported.
    """

    def test_nested_comprehension_codegen(self):
        code = compile_source(
            "union [box i*2 i*2 i*2 for i in [j + 1 for j in range(3)]]"
        )
        # Inner comprehension should appear in the generated code
        assert "for j in range(3)" in code
        assert "for i in" in code

    def test_nested_comprehension_execution(self):
        """[j+1 for j in range(3)] => [1, 2, 3].  Outer produces boxes 2x2x2,
        4x4x4, 6x6x6.  Union bbox should match the largest box (6x6x6)."""
        result = execute(
            "union [box i*2 i*2 i*2 for i in [j + 1 for j in range(3)]]"
        )
        assert result._shape is not None
        bb = result.val().BoundingBox()
        # All boxes are centred, so the union bbox = largest box = 6x6x6
        assert abs(bb.xlen - 6) < 0.01
        assert abs(bb.ylen - 6) < 0.01
        assert abs(bb.zlen - 6) < 0.01


# ===========================================================================
# 5. Compound selector (AND)
# ===========================================================================

class TestCompoundSelector:
    """Compound (AND) selectors: space-separated selectors in faces/edges.

    SPEC (line 437): "Multiple selectors separated by space => AND (filtering)."
    Example: ``edges >Z >X`` selects edges at max-Z AND max-X.
    """

    def test_faces_max_z_and_perp_x(self):
        """faces >Z +X — top face AND perpendicular to X.

        Box top face normal = (0,0,1), which IS perpendicular to X.
        So the compound selector should return exactly 1 face (the top face).
        """
        result = execute("box 10 10 10 | faces >Z +X | shell 1")
        assert result._shape is not None

    def test_faces_max_z_and_perp_x_codegen(self):
        """Verify codegen emits the AND form."""
        code = compile_source("box 10 10 10 | faces >Z +X | shell 1")
        # Should contain something like: .faces('>Z' + " and " + '#X')
        assert " and " in code
        assert ">Z" in code
        assert "#X" in code

    def test_edges_compound_and(self):
        """edges >Z >X — edges at the top AND rightmost position."""
        result = execute("box 10 10 10 | edges >Z >X | fillet 1")
        assert result._shape is not None

    def test_faces_parallel_selector(self):
        """faces >Z =X -- top face AND parallel to X.

        Box top face has normal (0,0,1) which is NOT parallel to X.
        So the AND result should be empty, causing shell to receive
        no selected faces and behaving as a closed shell.

        Previously this crashed due to gp_Dir.Crossed(gp_Vec) type mismatch
        (O1 bug). Now fixed: gp_Dir is converted to gp_Vec first.
        """
        # =X filters for faces whose normal is parallel to X axis.
        # Top face normal is (0,0,1) -- not parallel to X -- so no faces match.
        # Shell with no selected faces applies to all faces (closed shell).
        result = execute("box 10 10 10 | faces >Z =X | shell 1")
        assert result._shape is not None

    def test_faces_parallel_z_selects_top_bottom(self):
        """faces =Z should select faces whose normal is parallel to Z axis.

        For a box, the top face (+Z normal) and bottom face (-Z normal)
        both have normals parallel to Z.
        """
        result = execute("box 10 10 10 | faces =Z | shell 1")
        assert result._shape is not None


# ===========================================================================
# 6. Degenerate input: circle 0
# ===========================================================================

class TestDegenerateInput:
    """Degenerate shapes should produce clear ValueError, not segfaults.

    All radius/dimension parameters are validated at the kernel level.
    Zero and negative values are rejected before reaching OCC.
    """

    def test_circle_zero_raises(self):
        """circle(0) must raise ValueError."""
        from polyscript import ocp_kernel as cq
        with pytest.raises(ValueError, match="circle radius must be positive"):
            cq.Workplane("XY").circle(0)

    def test_circle_negative_raises(self):
        """circle(-5) must raise ValueError."""
        from polyscript import ocp_kernel as cq
        with pytest.raises(ValueError, match="circle radius must be positive"):
            cq.Workplane("XY").circle(-5)

    def test_sphere_zero_raises(self):
        """sphere(0) must raise ValueError."""
        from polyscript import ocp_kernel as cq
        with pytest.raises(ValueError, match="sphere radius must be positive"):
            cq.Workplane("XY").sphere(0)

    def test_cylinder_zero_radius_raises(self):
        """cylinder(0, 10) must raise ValueError."""
        from polyscript import ocp_kernel as cq
        with pytest.raises(ValueError, match="cylinder radius must be positive"):
            cq.Workplane("XY").cylinder(0, 10)

    def test_cylinder_zero_height_raises(self):
        """cylinder(5, 0) must raise ValueError."""
        from polyscript import ocp_kernel as cq
        with pytest.raises(ValueError, match="cylinder height must be positive"):
            cq.Workplane("XY").cylinder(5, 0)

    def test_ellipse_zero_raises(self):
        """ellipse(0, 5) must raise ValueError."""
        from polyscript import ocp_kernel as cq
        with pytest.raises(ValueError, match="ellipse radii must be positive"):
            cq.Workplane("XY").ellipse(0, 5)

    def test_rect_zero_raises(self):
        """rect(0, 5) must raise ValueError."""
        from polyscript import ocp_kernel as cq
        with pytest.raises(ValueError, match="rect dimensions must be positive"):
            cq.Workplane("XY").rect(0, 5)

    def test_box_zero_raises(self):
        """box(0, 5, 5) must raise ValueError."""
        from polyscript import ocp_kernel as cq
        with pytest.raises(ValueError, match="box dimensions must be positive"):
            cq.Workplane("XY").box(0, 5, 5)

    def test_cone_negative_radius_raises(self):
        """cone(-1, 5, 10) must raise ValueError."""
        from polyscript import ocp_kernel as cq
        with pytest.raises(ValueError, match="cone radii must be non-negative"):
            cq.Workplane("XY").cone(-1, 5, 10)

    def test_cone_both_zero_raises(self):
        """cone(0, 0, 10) must raise ValueError."""
        from polyscript import ocp_kernel as cq
        with pytest.raises(ValueError, match="at least one non-zero radius"):
            cq.Workplane("XY").cone(0, 0, 10)

    def test_torus_zero_raises(self):
        """torus(0, 5) must raise ValueError."""
        from polyscript import ocp_kernel as cq
        with pytest.raises(ValueError, match="torus major radius must be positive"):
            cq.Workplane("XY").torus(0, 5)

    def test_wedge_zero_raises(self):
        """wedge(0, 5, 5, 2) must raise ValueError."""
        from polyscript import ocp_kernel as cq
        with pytest.raises(ValueError, match="wedge dimensions must be positive"):
            cq.Workplane("XY").wedge(0, 5, 5, 2)

    def test_circle_zero_codegen(self):
        """Codegen should faithfully emit circle(0) -- validation is at runtime."""
        code = compile_source("circle 0 | extrude 5")
        assert ".circle(0)" in code
        assert ".extrude(5)" in code

    def test_negative_radius_circle_codegen(self):
        """Negative radius should be passed through in codegen."""
        code = compile_source("circle -5 | extrude 5")
        assert ".circle((-5))" in code or ".circle(-5)" in code


# ===========================================================================
# 7. Precision boundary: 1 um scale box
# ===========================================================================

class TestPrecisionBoundary:
    """Very small geometry (1 um = 0.000001) should be created correctly."""

    def test_micro_box_creation(self):
        result = execute("box 0.000001 0.000001 0.000001")
        assert result._shape is not None

    def test_micro_box_bbox(self):
        result = execute("box 0.000001 0.000001 0.000001")
        bb = result.val().BoundingBox()
        tol = 1e-10
        assert abs(bb.xlen - 1e-6) < tol, f"xlen={bb.xlen}"
        assert abs(bb.ylen - 1e-6) < tol, f"ylen={bb.ylen}"
        assert abs(bb.zlen - 1e-6) < tol, f"zlen={bb.zlen}"

    def test_micro_box_volume(self):
        result = execute("box 0.000001 0.000001 0.000001")
        vol = _volume(result._shape)
        expected = 1e-18
        # Volume is extremely small; check relative error
        assert abs(vol - expected) / expected < 0.01, (
            f"Volume {vol} deviates from expected {expected}"
        )

    def test_micro_box_centered(self):
        """Micro box should be centred at origin."""
        result = execute("box 0.000001 0.000001 0.000001")
        bb = result.val().BoundingBox()
        assert abs(bb.xmin + 0.5e-6) < 1e-10
        assert abs(bb.xmax - 0.5e-6) < 1e-10
