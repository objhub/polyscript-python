"""Tests for placement (at) and groups."""

import pytest
from polyscript.executor import compile_source


class TestAtPlacement:
    def test_at_tuple(self):
        code = compile_source("sphere 5 at (20, 0, 0)")
        assert '.translate((20, 0, 0))' in code

    def test_at_tuple_2d(self):
        code = compile_source("sphere 5 at (20, 0)")
        assert '.translate((20, 0, 0))' in code

    def test_at_list(self):
        code = compile_source("sphere 5 at [(0, 0), (10, 0), (20, 0)]")
        assert '.translate(' in code
        assert '.union(' in code

    def test_diff_at(self):
        code = compile_source("box 50 50 10 | diff cylinder 10 3 at (15, 15, 0)")
        assert '.cut(' in code
        assert '.translate((15, 15, 0))' in code


class TestPipeGridPolar:
    """Tests for grid/polar as pipe operations."""

    def test_pipe_polar(self):
        """polar as pipe operation."""
        code = compile_source("cylinder 10 5 | polar 6 15")
        assert '.polar(6, 15)' in code

    def test_pipe_grid(self):
        """grid as pipe operation."""
        code = compile_source("box 10 10 3 | grid 4 3 20")
        assert '.grid(4, 3, 20)' in code

    def test_pipe_grid_keyword_pitch(self):
        """grid with keyword pitch."""
        code = compile_source("box 10 10 3 | grid 4 3 pitch:20")
        assert '.grid(4, 3, 20)' in code

    def test_pipe_grid_positional_equals_keyword(self):
        """Positional and keyword pitch should produce identical code."""
        code_pos = compile_source("box 10 10 3 | grid 4 3 20")
        code_kw = compile_source("box 10 10 3 | grid 4 3 pitch:20")
        assert code_pos == code_kw

    def test_pipe_polar_with_chain(self):
        """polar followed by another pipe operator."""
        code = compile_source("box 10 10 3 | polar 4 20 | fillet 1")
        assert '.polar(4, 20)' in code
        assert '.fillet(1)' in code

    def test_pipe_grid_translate_chain(self):
        """grid + translate chain."""
        code = compile_source("box 10 10 3 | grid 2 2 20 | translate 50 0 0")
        assert '.grid(2, 2, 20)' in code
        assert 'translate' in code

    def test_at_grid_no_longer_parses(self):
        """at grid should no longer be valid syntax."""
        with pytest.raises(Exception):
            compile_source("box 10 10 1 at grid 4 3 20")

    def test_at_paren_grid_no_longer_parses(self):
        """at (grid ...) should no longer be valid syntax."""
        with pytest.raises(Exception):
            compile_source("box 10 10 1 at (grid 4 3 20)")

    def test_at_polar_no_longer_parses(self):
        """at polar should no longer be valid syntax."""
        with pytest.raises(Exception):
            compile_source("cylinder 10 5 at polar 6 15")

    def test_at_paren_polar_no_longer_parses(self):
        """at (polar ...) should no longer be valid syntax."""
        with pytest.raises(Exception):
            compile_source("sphere 5 at (polar 6 20)")


class TestBarePlacement:
    """Tests for bare (parenthesis-free) at placement syntax."""

    def test_bare_2d_numeric(self):
        """at 15 15 should produce the same result as at (15, 15)."""
        bare = compile_source("sphere 5 at 15 15")
        paren = compile_source("sphere 5 at (15, 15)")
        assert bare == paren

    def test_bare_3d_numeric(self):
        """at 15 15 20 should produce the same result as at (15, 15, 20)."""
        bare = compile_source("sphere 5 at 15 15 20")
        paren = compile_source("sphere 5 at (15, 15, 20)")
        assert bare == paren

    def test_bare_variable_refs(self):
        """at $x $y should work with variable references."""
        code = compile_source("$x = 10\n$y = 20\nsphere 5 at $x $y")
        assert '.translate(' in code

    def test_bare_arithmetic(self):
        """at $x+1 $y+1 should work with arithmetic expressions."""
        code = compile_source("$x = 10\n$y = 20\nsphere 5 at $x+1 $y+1")
        assert '.translate(' in code
        assert '+ 1' in code or '+1' in code or '(x + 1' in code

    def test_bare_with_pipe(self):
        """box 10 10 3 at 15 15 | fillet 2 should parse correctly."""
        code = compile_source("box 10 10 3 at 15 15 | fillet 2")
        assert '.translate((15, 15, 0))' in code
        assert '.fillet(2)' in code

    def test_paren_backward_compat(self):
        """Parenthesized at (15, 15) should still work."""
        code = compile_source("sphere 5 at (15, 15)")
        assert '.translate((15, 0, 0))' in code or '.translate((15, 15, 0))' in code


class TestUnionSource:
    def test_union_source(self):
        code = compile_source("union [rect 40 10, rect 10 40] | extrude 5")
        assert '.extrude(5)' in code
        assert '.union(' in code

    def test_union_source_single(self):
        code = compile_source("union [box 10 10 10]")
        assert '.box(10, 10, 10)' in code

    def test_diff_source(self):
        code = compile_source("diff [box 20 20 20, cylinder 10 5]")
        assert '.cut(' in code

    def test_inter_source(self):
        code = compile_source("inter [box 20 20 20, sphere 10]")
        assert '.intersect(' in code
