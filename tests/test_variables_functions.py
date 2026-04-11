"""Tests for variables, functions, and imports."""

import pytest
from pathlib import Path
from polyscript.executor import compile_source


class TestVariables:
    def test_assignment(self):
        code = compile_source("$w = 80\nbox $w 60 10")
        assert 'w = 80' in code
        assert '.box(w, 60, 10)' in code

    def test_multiple_vars(self):
        code = compile_source("$w = 80\n$h = 60\nbox $w $h 10")
        assert 'w = 80' in code
        assert 'h = 60' in code

    def test_var_with_expr(self):
        code = compile_source("$r = 10 + 5\ncircle $r")
        assert 'r = (10 + 5)' in code

    def test_assignment_without_dollar(self):
        code = compile_source("w = 80\nbox w 60 10")
        assert 'w = 80' in code
        assert '.box(w, 60, 10)' in code

    def test_var_ref_without_dollar(self):
        code = compile_source("w = 80\nh = 60\nbox w h 10")
        assert 'w = 80' in code
        assert 'h = 60' in code

    def test_mixed_dollar_and_no_dollar(self):
        code = compile_source("$w = 80\nh = 60\nbox $w h 10")
        assert 'w = 80' in code
        assert 'h = 60' in code

    def test_var_expr_without_dollar(self):
        code = compile_source("r = 10 + 5\ncircle r")
        assert 'r = (10 + 5)' in code

    def test_list_comp_without_dollar(self):
        code = compile_source("[box i 1 1 for i in range(3)]")
        assert 'for i in range' in code

    def test_dollar_keyword_offset(self):
        """$offset = 5 should declare successfully and be referenceable."""
        code = compile_source("$offset = 5\nbox 10 10 $offset")
        assert 'offset = 5' in code
        assert 'offset' in code

    def test_dollar_keyword_box(self):
        """$box = 10 should be valid (keyword 'box' with $ prefix)."""
        code = compile_source("$box = 10\nbox $box $box $box")
        assert 'box = 10' in code
        assert '.box(box, box, box)' in code

    def test_dollar_keyword_scale(self):
        """$scale = 2 in pipeline: box 10 10 10 | scale $scale."""
        code = compile_source("$scale = 2\nbox 10 10 10 | scale $scale")
        assert 'scale = 2' in code

    def test_dollar_keyword_multiple(self):
        """Multiple keyword-named variables with $ prefix."""
        code = compile_source("$offset = 5\n$scale = 2\nbox 10 10 $offset | scale $scale")
        assert 'offset = 5' in code
        assert 'scale = 2' in code

    def test_keyword_without_dollar_fails(self):
        """Using a keyword as variable name without $ should fail."""
        from polyscript.errors import ParseError
        with pytest.raises(ParseError):
            compile_source("box = 10")

    def test_dollar_keyword_in_expr(self):
        """$offset used in arithmetic expression."""
        code = compile_source("$offset = 5\nbox 10 10 $offset + 3")
        assert 'offset = 5' in code
        assert '(offset + 3)' in code

    def test_dollar_keyword_diff(self):
        """$diff as variable name (keyword 'diff' with $ prefix)."""
        code = compile_source("$diff = 3\nbox $diff $diff $diff")
        assert 'diff = 3' in code
        assert '.box(diff, diff, diff)' in code

    def test_dollar_keyword_circle(self):
        """$circle as variable name."""
        code = compile_source("$circle = 8\ncircle $circle")
        assert 'circle = 8' in code

    def test_dollar_keyword_fillet(self):
        """$fillet as variable name used in fillet operation."""
        code = compile_source("$fillet = 2\nbox 10 10 10 | fillet $fillet")
        assert 'fillet = 2' in code


class TestFunctions:
    def test_simple_func(self):
        code = compile_source(
            "def double($x) = $x * 2\nbox double(5) 10 10"
        )
        assert 'def double(x):' in code
        assert 'return (x * 2)' in code

    def test_multi_param_func(self):
        code = compile_source(
            "def standoff($r, $h) = cylinder $r $h\nstandoff 4 10"
        )
        assert 'def standoff(r, h):' in code
        assert 'return' in code

    def test_func_with_pipe(self):
        code = compile_source(
            "def standoff($r, $h, $hole_r) = cylinder $r $h | diff cylinder $hole_r $h\nstandoff 4 10 1.5"
        )
        assert 'def standoff(r, h, hole_r):' in code
        assert '.cut(' in code


class TestImport:
    def test_import_resolves(self, tmp_path):
        lib = tmp_path / "mylib.poly"
        lib.write_text("def add1($x) = $x + 1\n")
        main = "import \"mylib\"\nbox add1(5) 10 10"
        code = compile_source(main, source_dir=tmp_path)
        assert 'def add1(x):' in code
        assert 'return (x + 1)' in code

    def test_import_with_extension(self, tmp_path):
        lib = tmp_path / "mylib.poly"
        lib.write_text("def add1($x) = $x + 1\n")
        main = 'import "mylib.poly"\nbox add1(5) 10 10'
        code = compile_source(main, source_dir=tmp_path)
        assert 'def add1(x):' in code

    def test_import_circular(self, tmp_path):
        a = tmp_path / "a.poly"
        b = tmp_path / "b.poly"
        a.write_text('import "b"\ndef fa($x) = $x + 1\n')
        b.write_text('import "a"\ndef fb($x) = $x + 2\n')
        main = 'import "a"\nbox fa(1) fb(2) 10'
        code = compile_source(main, source_dir=tmp_path)
        assert 'def fa(x):' in code
        assert 'def fb(x):' in code

    def test_import_not_found(self, tmp_path):
        from polyscript.errors import ParseError
        with pytest.raises(ParseError, match="Cannot find"):
            compile_source('import "nonexistent"\nbox 1 1 1', source_dir=tmp_path)

    def test_import_only_funcs_and_vars(self, tmp_path):
        lib = tmp_path / "shapes.poly"
        lib.write_text("def mk($r) = circle $r\nbox 10 10 10\n")
        main = 'import "shapes"\nmk 5 | extrude 10'
        code = compile_source(main, source_dir=tmp_path)
        assert 'def mk(r):' in code
        # The box(10,10,10) from the library should NOT appear as a standalone statement
        # It gets imported but only FuncDef and Assignment are kept
        lines = [l.strip() for l in code.split('\n') if '.box(10, 10, 10)' in l]
        assert len(lines) == 0
