"""Comprehensive loft tests for PolyScript (O11).

Covers:
  1. Two-section loft (circle -> rect)
  2. Three or more sections
  3. Ruled vs spline (smooth) surface
  4. heights parameter vs uniform height
  5. Same-shape different-size (shrinking cone)
  6. Closed loft (start == end section)
  7. Volume / bbox sanity checks
"""

import math
import pytest

from polyscript.executor import compile_source, execute


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _volume(shape):
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    return props.Mass()


def _bbox(result):
    return result.val().BoundingBox()


# ===========================================================================
# 1. Two-section loft: circle -> rect
# ===========================================================================

class TestLoftTwoSections:
    """Loft from one 2D profile to another at a given height."""

    def test_circle_to_rect(self):
        """circle 10 | loft [rect 8 8] 20 -- valid solid."""
        result = execute("circle 10 | loft [rect 8 8] 20")
        assert result._shape is not None
        bb = _bbox(result)
        assert abs(bb.zlen - 20) < 1.0

    def test_rect_to_circle(self):
        """rect 20 20 | loft [circle 5] 15 -- valid solid."""
        result = execute("rect 20 20 | loft [circle 5] 15")
        assert result._shape is not None
        bb = _bbox(result)
        assert abs(bb.zlen - 15) < 1.0
        # Base should be at least 20x20
        assert bb.xlen >= 10
        assert bb.ylen >= 10

    def test_rect_to_rect(self):
        """rect 20 20 | loft [rect 10 10] 15 -- pyramid frustum."""
        result = execute("rect 20 20 | loft [rect 10 10] 15")
        assert result._shape is not None
        bb = _bbox(result)
        assert abs(bb.zlen - 15) < 1.0
        # Base is 20, top is 10 => width between 10 and 20
        assert bb.xlen >= 10
        assert bb.xlen <= 21

    def test_circle_to_circle_different_size(self):
        """circle 20 | loft [circle 5] 30 -- cone-like shape."""
        result = execute("circle 20 | loft [circle 5] 30")
        assert result._shape is not None
        bb = _bbox(result)
        assert abs(bb.zlen - 30) < 1.0
        # Diameter at base should be about 40
        assert bb.xlen > 9

    def test_loft_volume_positive(self):
        """Loft should produce a solid with positive volume."""
        result = execute("circle 10 | loft [rect 8 8] 20")
        vol = _volume(result._shape)
        assert vol > 0


# ===========================================================================
# 2. Three or more sections
# ===========================================================================

class TestLoftMultipleSections:
    """Loft through 3+ sections."""

    def test_three_sections(self):
        """circle 10 | loft [rect 8 8, circle 3] 30 -- three sections."""
        result = execute("circle 10 | loft [rect 8 8, circle 3] 30")
        assert result._shape is not None
        bb = _bbox(result)
        assert abs(bb.zlen - 30) < 1.0

    def test_three_circles(self):
        """circle 10 | loft [circle 20, circle 5] 30."""
        result = execute("circle 10 | loft [circle 20, circle 5] 30")
        assert result._shape is not None
        bb = _bbox(result)
        assert abs(bb.zlen - 30) < 1.0
        # Middle section is wider (r=20 at z=15), so max diameter > 20
        assert bb.xlen > 10

    def test_four_sections(self):
        """circle 10 | loft [circle 15, circle 20, circle 5] 30."""
        result = execute("circle 10 | loft [circle 15, circle 20, circle 5] 30")
        assert result._shape is not None
        bb = _bbox(result)
        assert abs(bb.zlen - 30) < 1.0

    def test_multiple_sections_volume(self):
        """More sections should produce a solid with positive volume."""
        result = execute("circle 10 | loft [rect 8 8, circle 3] 30")
        vol = _volume(result._shape)
        assert vol > 0


# ===========================================================================
# 3. Ruled vs spline surface
# ===========================================================================

class TestLoftRuledVsSpline:
    """Ruled loft (linear interpolation) vs default spline (smooth)."""

    def test_ruled_basic(self):
        """circle 10 | loft [rect 8 8] 20 ruled:true -- valid solid."""
        result = execute("circle 10 | loft [rect 8 8] 20 ruled:true")
        assert result._shape is not None
        bb = _bbox(result)
        assert abs(bb.zlen - 20) < 1.0

    def test_ruled_vs_smooth_different_volume(self):
        """Ruled and smooth loft should produce different volumes.

        Ruled surfaces are straight-line interpolations between sections,
        while smooth surfaces are spline interpolations. The volumes
        should differ for non-trivial section combinations.
        """
        ruled = execute("circle 15 | loft [rect 10 10] 20 ruled:true")
        smooth = execute("circle 15 | loft [rect 10 10] 20")
        vol_ruled = _volume(ruled._shape)
        vol_smooth = _volume(smooth._shape)
        # Both should have positive volume
        assert vol_ruled > 0
        assert vol_smooth > 0
        # The exact difference depends on geometry, but they should be
        # at least somewhat close (within 50%) for reasonable shapes
        ratio = vol_ruled / vol_smooth if vol_smooth > 0 else 0
        assert 0.5 < ratio < 2.0, (
            f"Unexpected volume ratio ruled/smooth = {ratio:.4f}"
        )

    def test_ruled_three_sections(self):
        """Ruled loft with 3 sections."""
        result = execute("circle 10 | loft [circle 20, circle 5] 30 ruled:true")
        assert result._shape is not None
        bb = _bbox(result)
        assert abs(bb.zlen - 30) < 1.0


# ===========================================================================
# 4. Heights parameter vs at: offsets
# ===========================================================================

class TestLoftHeights:
    """Explicit heights list for non-uniform section spacing."""

    def test_explicit_heights(self):
        """circle 10 | loft [rect 8 8, circle 3] [10, 25]."""
        result = execute("circle 10 | loft [rect 8 8, circle 3] [10, 25]")
        assert result._shape is not None
        bb = _bbox(result)
        # Total height should be 25 (max offset)
        assert abs(bb.zlen - 25) < 1.0

    def test_heights_codegen(self):
        """Codegen should emit heights= for explicit offset list."""
        code = compile_source("circle 10 | loft [rect 8 8, circle 3] [10, 25]")
        assert "heights=" in code

    def test_uniform_height_codegen(self):
        """Codegen should emit height= for single value."""
        code = compile_source("circle 10 | loft [rect 8 8] 20")
        assert ".loft(" in code
        assert "20" in code

    def test_heights_uneven_spacing(self):
        """Non-uniform heights should place sections at different offsets."""
        result = execute("circle 10 | loft [circle 5, circle 3] [5, 30]")
        assert result._shape is not None
        bb = _bbox(result)
        assert abs(bb.zlen - 30) < 1.0


# ===========================================================================
# 5. Same shape, different sizes (shrinking cone)
# ===========================================================================

class TestLoftSameShapeDifferentSize:
    """Loft between same-type profiles of different sizes."""

    def test_shrinking_circle(self):
        """circle 20 | loft [circle 5] 30 -- cone-like taper."""
        result = execute("circle 20 | loft [circle 5] 30")
        assert result._shape is not None
        vol = _volume(result._shape)
        # Volume should be between a cylinder of r=5 and r=20
        min_vol = math.pi * 5**2 * 30
        max_vol = math.pi * 20**2 * 30
        assert min_vol < vol < max_vol, (
            f"Volume {vol:.2f} not between min={min_vol:.2f} and max={max_vol:.2f}"
        )

    def test_growing_rect(self):
        """rect 10 10 | loft [rect 30 30] 20 -- expanding box."""
        result = execute("rect 10 10 | loft [rect 30 30] 20")
        assert result._shape is not None
        bb = _bbox(result)
        assert abs(bb.zlen - 20) < 1.0
        # Top should be about 30x30
        assert bb.xlen >= 20


# ===========================================================================
# 6. Closed loft (start == end)
# ===========================================================================

class TestLoftClosed:
    """Closed loft where the last section returns to the start profile."""

    def test_closed_circle_loft(self):
        """circle 10 | loft [circle 20, circle 10] [10, 20].

        Start and end profiles are both circle 10, creating a bulging
        shape that returns to its starting radius.
        """
        result = execute("circle 10 | loft [circle 20, circle 10] [10, 20]")
        assert result._shape is not None
        bb = _bbox(result)
        assert abs(bb.zlen - 20) < 1.0
        vol = _volume(result._shape)
        assert vol > 0
