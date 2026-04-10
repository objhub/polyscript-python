"""Tests for the preprocessor (line continuation rules)."""

import pytest
from polyscript.parser import _preprocess


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

    def test_for_continuation(self):
        result = _preprocess("[$i\n  for $i in range(6)]")
        assert '$i for $i' in result


class TestComments:
    def test_comment_ignored(self):
        from polyscript.executor import compile_source
        code = compile_source("# This is a comment\nbox 10 10 10")
        assert '.box(10, 10, 10)' in code

    def test_inline_comment(self):
        from polyscript.executor import compile_source
        code = compile_source("box 10 10 10 # make a box")
        assert '.box(10, 10, 10)' in code
