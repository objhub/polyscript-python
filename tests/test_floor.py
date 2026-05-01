"""Tests for the floor pipe operation."""

from polyscript.executor import compile_source, execute


class TestFloorParse:
    def test_floor_parse(self):
        """box 10 10 10 | floor should parse to an AST containing a Floor node."""
        code = compile_source("box 10 10 10 | floor")
        # codegen output should contain the floor pattern: BoundingBox().zmin and translate
        assert "BoundingBox().zmin" in code
        assert ".translate((0, 0, -" in code


class TestFloorCodegen:
    def test_floor_box(self):
        """box (centered) | floor should place bottom at z=0."""
        wp = execute("box 10 10 10 | floor")
        bb = wp.val().BoundingBox()
        assert abs(bb.zmin) < 1e-6
        assert abs(bb.zmax - 10) < 1e-6

    def test_floor_sphere(self):
        """sphere 10 | floor should place bottom at z=0, top at z=20."""
        wp = execute("sphere 10 | floor")
        bb = wp.val().BoundingBox()
        assert abs(bb.zmin) < 1e-6
        assert abs(bb.zmax - 20) < 1e-6

    def test_floor_already_aligned(self):
        """polygon 6 5 | extrude 10 | floor is a no-op (zmin already 0)."""
        wp = execute("polygon 6 5 | extrude 10 | floor")
        bb = wp.val().BoundingBox()
        assert abs(bb.zmin) < 1e-6

    def test_floor_after_diff(self):
        """box 10 10 10 | diff (sphere 3) | floor should have zmin == 0."""
        wp = execute("box 10 10 10 | diff (sphere 3) | floor")
        bb = wp.val().BoundingBox()
        assert abs(bb.zmin) < 1e-6

    def test_floor_translated_shape(self):
        """A shape translated upward, then floored, should have zmin == 0."""
        wp = execute("box 10 10 10 | translate 0 0 50 | floor")
        bb = wp.val().BoundingBox()
        assert abs(bb.zmin) < 1e-6
        assert abs(bb.zmax - 10) < 1e-6
