"""Tests for the preprocessor (line continuation rules)."""

import pytest
from polyscript.parser import _preprocess, _preprocess_with_mapping


class TestLineContinuation:
    def test_pipe_end_of_line(self):
        result = _preprocess("box 10 10 10 |\n  fillet 2")
        assert '|' in result
        assert '\n' not in result.strip() or '| fillet' in result

    def test_pipe_start_of_line(self):
        result = _preprocess("box 10 10 10\n | fillet 2")
        assert ' | fillet' in result

    def test_equals_continuation(self):
        result = _preprocess("$x =\n  10")
        assert '$x = 10' in result

    def test_equals_not_comparison(self):
        # == should NOT trigger continuation
        result = _preprocess("$x == 5")
        assert '== 5' in result

    def test_comma_continuation(self):
        result = _preprocess("polyline [(0, 0),\n  (10, 0)]")
        assert '(0, 0), (10, 0)' in result

    def test_else_continuation(self):
        result = _preprocess("if $x == 0 then 1\n  else 2")
        assert 'then 1 else 2' in result

    def test_plus_continuation(self):
        result = _preprocess("$x = 1\n  + 2")
        assert '1 + 2' in result

    def test_plus_selector_not_joined(self):
        """Selector +Z at line start should NOT be treated as continuation."""
        result = _preprocess("box 10 10 10 | faces\n+Z\n| fillet 2")
        # +Z should remain separate (not joined with previous line as addition)
        # The pipe rules will handle joining; +Z should not be joined via + rule
        assert "+Z" in result

    def test_plus_continuation_still_works_with_variable(self):
        """+ followed by a non-axis letter should still join."""
        result = _preprocess("$x = $a\n  + $b")
        assert '$a + $b' in result

    def test_for_continuation(self):
        result = _preprocess("[$i\n  for $i in range(6)]")
        assert '$i for $i' in result


class TestLineMapping:
    def test_no_continuation_identity(self):
        """Without continuation, line map should be identity."""
        _, line_map = _preprocess_with_mapping("line1\nline2\nline3")
        assert line_map == {1: 1, 2: 2, 3: 3}

    def test_pipe_continuation_maps_to_first_line(self):
        """Joined lines should map to the original first line."""
        _, line_map = _preprocess_with_mapping("box 10 10 10 |\n  fillet 2\nother")
        # Line 1 in preprocessed = original line 1 (box + fillet joined)
        assert line_map[1] == 1
        # Line 2 in preprocessed = original line 3 ("other")
        assert line_map[2] == 3

    def test_equals_continuation_mapping(self):
        _, line_map = _preprocess_with_mapping("$x =\n  10\nbox 5 5 5")
        assert line_map[1] == 1  # "$x = 10" from lines 1-2
        assert line_map[2] == 3  # "box 5 5 5" from line 3

    def test_error_line_number_after_continuation(self):
        """Parse error should report original line number, not preprocessed."""
        from polyscript.errors import ParseError
        source = "$x =\n  10\n???"  # syntax error on original line 3
        with pytest.raises(ParseError) as exc_info:
            from polyscript.parser import parse
            parse(source)
        assert exc_info.value.line == 3


class TestComments:
    def test_comment_ignored(self):
        from polyscript.executor import compile_source
        code = compile_source("# This is a comment\nbox 10 10 10")
        assert '.box(10, 10, 10)' in code

    def test_inline_comment(self):
        from polyscript.executor import compile_source
        code = compile_source("box 10 10 10 # make a box")
        assert '.box(10, 10, 10)' in code
