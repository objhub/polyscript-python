"""Integration tests based on SPEC.md examples and edge cases."""

import pytest
from polyscript.executor import compile_source, execute


# ---------------------------------------------------------------------------
# SPEC.md complete examples (parse + codegen)
# ---------------------------------------------------------------------------

class TestSpecExample1:
    """Example 1: rounded box with holes."""

    def test_parse_and_codegen(self):
        source = """\
box 80 60 10
 | fillet 2
 | diff cylinder 10 10
 | diff cylinder 10 2.5 at:(20, 10)"""
        code = compile_source(source)
        assert '.box(80, 60, 10)' in code
        assert '.fillet(2)' in code
        assert '.cut(' in code
        assert '.cylinder(10, 10)' in code
        assert '.cylinder(10, 2.5)' in code
        assert '.translate(' in code

    def test_execute(self):
        source = """\
box 80 60 10
 | fillet 2
 | diff cylinder 10 10
 | diff cylinder 10 2.5 at:(20, 10)"""
        result = execute(source)
        assert result._shape is not None
        bb = result.val().BoundingBox()
        assert abs(bb.xlen - 80) < 0.5
        assert abs(bb.ylen - 60) < 0.5


class TestSpecExample2:
    """Example 2: enclosure."""

    def test_parse_and_codegen(self):
        source = """\
box 100 60 40
 | faces >Z | shell 2
 | edges =Z | fillet 3
 | edges <Z | fillet 1
 | faces >X
 | workplane
 | circle 4 | cut
 | faces <X
 | points (grid 2 4 10)
 | hole 3"""
        code = compile_source(source)
        assert '.box(100, 60, 40)' in code
        assert '.shell(2)' in code
        assert '.fillet(3)' in code
        assert '.fillet(1)' in code
        assert '.circle(4)' in code
        assert '.cutThruAll()' in code
        assert '.hole(3 * 2)' in code
        assert '.rarray(' in code


class TestSpecExample3:
    """Example 3: mount plate with function definition."""

    def test_parse_and_codegen(self):
        source = """\
def plate($size) =
  box $size $size 3
   | fillet 1
   | faces >Z
   | points (polar 4 $size/3)
   | hole 4

$base = box 100 100 5
 | fillet 2
 | faces >Z | union plate 40 at:(0, 0)
 | faces >Z | union plate 40 at:(40, 0)
 | faces >Z | workplane
 | circle 4 | cut"""
        code = compile_source(source)
        assert 'def plate(size):' in code
        assert '.hole(4 * 2)' in code
        assert 'plate(40' in code
        assert '.cutThruAll()' in code


# ---------------------------------------------------------------------------
# Revolve axis tests
# ---------------------------------------------------------------------------

class TestRevolveAxis:
    def test_revolve_default_y_axis(self):
        code = compile_source("circle 5 | revolve 360")
        assert '.revolve(360)' in code

    def test_revolve_x_axis(self):
        code = compile_source('circle 5 | revolve 180 axis:"X"')
        assert 'axisEnd=(1,0,0)' in code

    def test_revolve_y_axis(self):
        code = compile_source('circle 5 | revolve 180 axis:"Y"')
        assert 'axisEnd=(0,1,0)' in code

    def test_revolve_z_axis(self):
        code = compile_source('circle 5 | revolve 180 axis:"Z"')
        assert 'axisEnd=(0,0,1)' in code


# ---------------------------------------------------------------------------
# Text with positional size
# ---------------------------------------------------------------------------

class TestTextPositionalSize:
    def test_text_with_positional_size(self):
        code = compile_source('text "Hello" 10')
        assert '.text(' in code
        assert '10' in code

    def test_text_with_keyword_size(self):
        code = compile_source('text "Hello" size:20')
        assert '.text(' in code
        assert '20' in code


# ---------------------------------------------------------------------------
# Workplane with plane argument
# ---------------------------------------------------------------------------

class TestWorkplanePlane:
    def test_workplane_xz(self):
        code = compile_source('box 10 10 10 | faces >Z | workplane "XZ"')
        assert '.workplane().transformed(rotate=(-90, 0, 0))' in code

    def test_workplane_default(self):
        code = compile_source('box 10 10 10 | faces >Z | workplane')
        assert '.workplane()' in code


# ---------------------------------------------------------------------------
# Hole uses radius (not diameter)
# ---------------------------------------------------------------------------

class TestHoleRadius:
    def test_hole_radius_codegen(self):
        """SPEC: hole 5 = radius 5 hole. Codegen should pass diameter to CadQuery."""
        code = compile_source(
            'box 20 20 10 | faces >Z | workplane | hole 5'
        )
        assert '.hole(5 * 2)' in code

    def test_hole_radius_ocp(self):
        """Verify actual hole radius in OCP backend."""
        result = execute("box 40 40 10 | hole 5")
        assert result._shape is not None


class TestHoleFromFaceSelection:
    """SPEC: Face選択 | hole -> 3D. Equivalent to faces | circle r | cut."""

    def test_face_hole_codegen(self):
        """faces >Z | hole 5 generates holeOnFaces(5)."""
        code = compile_source('box 80 60 10 | faces >Z | hole 5')
        assert '.holeOnFaces(5)' in code

    def test_face_hole_ocp(self):
        """faces >Z | hole 5 produces a valid solid with a hole."""
        result = execute('box 80 60 10 | faces >Z | hole 5')
        assert result._shape is not None
        bb = result.val().BoundingBox()
        assert abs(bb.xlen - 80) < 0.01
        assert abs(bb.ylen - 60) < 0.01
        assert abs(bb.zlen - 10) < 0.01

    def test_face_hole_with_depth_ocp(self):
        """faces >Z | hole 5 depth:3 produces a blind hole."""
        result = execute('box 80 60 10 | faces >Z | hole 5 depth:3')
        assert result._shape is not None

    def test_point_selection_hole_unchanged(self):
        """faces | points | hole still uses the old .hole() path."""
        code = compile_source(
            'box 80 60 10 | faces >Z | points (polar 4 15) | hole 5'
        )
        assert '.hole(5 * 2)' in code


# ---------------------------------------------------------------------------
# Selector #Z (perpendicular)
# ---------------------------------------------------------------------------

class TestPerpendicularSelector:
    def test_faces_perpendicular_z_codegen(self):
        code = compile_source('box 10 10 10 | faces +Z')
        assert ".faces('#Z')" in code

    def test_faces_perpendicular_z_ocp(self):
        """Faces perpendicular to Z = top and bottom faces of a box."""
        result = execute('box 10 10 10 | faces +Z | fillet 1')
        assert result._shape is not None


# ---------------------------------------------------------------------------
# Named keyword arguments
# ---------------------------------------------------------------------------

class TestNamedArgs:
    def test_extrude_draft(self):
        code = compile_source("rect 60 40 | extrude 10 draft:5")
        assert '.extrude(10, taper=5)' in code

    def test_shell_open(self):
        code = compile_source('box 10 10 10 | faces >Z | shell 2')
        assert ".faces('>Z')" in code
        assert '.shell(2)' in code

    def test_helix_kwargs(self):
        code = compile_source("helix 5 30 10")
        assert 'makeHelix(pitch=5, height=30, radius=10)' in code
