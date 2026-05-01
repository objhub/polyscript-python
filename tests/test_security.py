"""Security tests for PolyScript Python implementation.

Covers S1-S10 from the security audit.
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch

from polyscript.executor import execute, compile_source, _resolve_import
from polyscript.evaluator import Evaluator, EvalError, MAX_RANGE, MAX_DIMENSION, MAX_TEXT_LENGTH
from polyscript.errors import ParseError, ExecutionError, PolyScriptError
from polyscript.cli import main, MAX_SOURCE_SIZE


# ---------------------------------------------------------------------------
# S1: Import path traversal
# ---------------------------------------------------------------------------

class TestS1ImportPathTraversal:
    """S1: import path must not escape source directory."""

    def test_reject_parent_traversal(self, tmp_path):
        """import with '..' is rejected."""
        with pytest.raises(ParseError, match="Parent directory traversal"):
            _resolve_import("../../etc/passwd", source_dir=tmp_path)

    def test_reject_absolute_path(self, tmp_path):
        """import with absolute path is rejected."""
        with pytest.raises(ParseError, match="Absolute import path"):
            _resolve_import("/etc/passwd.poly", source_dir=tmp_path)

    def test_reject_symlink_escape(self, tmp_path):
        """import via symlink escaping source dir is rejected."""
        # Create a symlink inside tmp_path that points outside
        evil_link = tmp_path / "evil"
        evil_link.symlink_to("/tmp")
        with pytest.raises(ParseError, match="escapes source directory"):
            _resolve_import("evil/outside.poly", source_dir=tmp_path)

    def test_valid_import_works(self, tmp_path):
        """A valid import within source dir still works."""
        lib = tmp_path / "lib.poly"
        lib.write_text("def f($x) = $x + 1")
        result = _resolve_import("lib", source_dir=tmp_path)
        assert result == lib

    def test_import_traversal_in_execute(self, tmp_path):
        """import traversal detected during execute()."""
        src = tmp_path / "main.poly"
        src.write_text('import "../../etc/passwd"')
        with pytest.raises((ParseError, ExecutionError)):
            execute(src.read_text(), source_dir=src.parent)


# ---------------------------------------------------------------------------
# S2: CLI output path validation
# ---------------------------------------------------------------------------

class TestS2OutputPathValidation:
    """S2: CLI rejects relative output paths escaping cwd."""

    def test_reject_relative_escape(self, tmp_path, capsys):
        """Output path with .. that escapes cwd is rejected."""
        src = tmp_path / "test.poly"
        src.write_text("box 10 10 10")
        with patch("sys.argv", [
            "poly", str(src), "-o", "../../etc/cron.d/evil.stl"
        ]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "output path escapes" in captured.err

    def test_absolute_path_allowed(self, tmp_path, capsys):
        """Explicit absolute output paths are allowed (intentional usage)."""
        src = tmp_path / "test.poly"
        src.write_text("box 10 10 10")
        out = tmp_path / "out.stl"
        with patch("sys.argv", ["poly", str(src), "-o", str(out)]):
            main()
        assert out.exists()


# ---------------------------------------------------------------------------
# S3: range() / list comp OOM defence
# ---------------------------------------------------------------------------

class TestS3RangeOOM:
    """S3: range and list comprehension size limits."""

    def test_list_comp_exceeds_max(self):
        """List comprehension over MAX_RANGE raises EvalError."""
        source = f"x = [i for i in {MAX_RANGE + 1}]"
        with pytest.raises(ExecutionError, match="exceeds maximum"):
            execute(source)

    def test_range_in_list_comp_exceeds_max(self):
        """List comprehension with range-like iteration over MAX_RANGE raises."""
        source = f"x = [i for i in {MAX_RANGE + 1}]"
        with pytest.raises(ExecutionError, match="exceeds maximum"):
            execute(source)

    def test_small_range_works(self):
        """Normal-sized list comprehension still works."""
        from polyscript.parser import parse
        from polyscript.transformer import transform
        ev = Evaluator()
        tree = parse("x = [i for i in 5]")
        program = transform(tree)
        ev.evaluate(program)
        assert ev.env.get("x") == [0, 1, 2, 3, 4]


# ---------------------------------------------------------------------------
# S4: Huge primitive dimensions
# ---------------------------------------------------------------------------

class TestS4HugeDimensions:
    """S4: primitives with dimensions exceeding MAX_DIMENSION are rejected."""

    def test_box_too_large(self):
        """box with dimension > MAX_DIMENSION raises error."""
        source = f"box {MAX_DIMENSION * 10} 10 10"
        with pytest.raises(ExecutionError, match="exceeds maximum"):
            execute(source)

    def test_cylinder_too_large(self):
        """cylinder with huge radius raises error."""
        source = f"cylinder {MAX_DIMENSION * 10} 10"
        with pytest.raises(ExecutionError, match="exceeds maximum"):
            execute(source)

    def test_sphere_too_large(self):
        """sphere with huge radius raises error."""
        source = f"sphere {MAX_DIMENSION * 10}"
        with pytest.raises(ExecutionError, match="exceeds maximum"):
            execute(source)

    def test_normal_dimensions_work(self):
        """Normal dimensions within limit still work."""
        result = execute("box 100 100 100")
        assert result is not None


# ---------------------------------------------------------------------------
# S5: NaN/Inf detection and division by zero
# ---------------------------------------------------------------------------

class TestS5NaNInf:
    """S5: division by zero and NaN/Inf detection."""

    def test_division_by_zero_error(self):
        """1 / 0 raises EvalError instead of returning 0."""
        with pytest.raises(ExecutionError, match="Division by zero"):
            execute("x = 1 / 0")

    def test_modulo_by_zero_error(self):
        """5 % 0 raises EvalError."""
        with pytest.raises(ExecutionError, match="Division by zero"):
            execute("x = 5 % 0")

    def test_floor_division_by_zero_error(self):
        """5 // 0 raises EvalError."""
        with pytest.raises(ExecutionError, match="Division by zero"):
            execute("x = 5 // 0")

    def test_normal_division_works(self):
        """Normal division still works."""
        result = execute("x = 10 / 3")
        assert abs(result - 10 / 3) < 1e-10


# ---------------------------------------------------------------------------
# S6: .poly file size limit
# ---------------------------------------------------------------------------

class TestS6FileSize:
    """S6: source files exceeding MAX_SOURCE_SIZE are rejected."""

    def test_oversized_file_rejected(self, tmp_path, capsys):
        """A file larger than MAX_SOURCE_SIZE is rejected by CLI."""
        src = tmp_path / "big.poly"
        # Create a file slightly over the limit
        src.write_text("# " + "x" * (MAX_SOURCE_SIZE + 100))
        with patch("sys.argv", ["poly", str(src)]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "source file too large" in captured.err


# ---------------------------------------------------------------------------
# S7: --emit-python warning (tested via stderr capture)
# ---------------------------------------------------------------------------

class TestS7EmitPythonWarning:
    """S7: --emit-python prints a warning to stderr."""

    def test_emit_python_shows_warning(self, tmp_path, capsys):
        """--emit-python writes a WARNING header to stderr."""
        src = tmp_path / "test.poly"
        src.write_text("box 10 10 10")
        with patch("sys.argv", ["poly", str(src), "--emit-python"]):
            main()
        captured = capsys.readouterr()
        assert "WARNING" in captured.err
        assert "review" in captured.err.lower()


# ---------------------------------------------------------------------------
# S9: @param min/max override validation
# ---------------------------------------------------------------------------

class TestS9ParamRangeValidation:
    """S9: CLI overrides checked against @param min/max."""

    def test_override_exceeds_max(self):
        """Override exceeding @param max is rejected."""
        source = """\
@param 1..100
x = 50
box x x x
"""
        with pytest.raises((ParseError, ExecutionError), match="exceeds maximum"):
            execute(source, overrides={"x": 1000})

    def test_override_below_min(self):
        """Override below @param min is rejected."""
        source = """\
@param 1..100
x = 50
box x x x
"""
        with pytest.raises((ParseError, ExecutionError), match="below minimum"):
            execute(source, overrides={"x": 0})

    def test_override_within_range(self):
        """Override within @param range succeeds."""
        source = """\
@param 1..100
x = 50
box x x x
"""
        result = execute(source, overrides={"x": 75})
        assert result is not None


# ---------------------------------------------------------------------------
# S10: text() content validation
# ---------------------------------------------------------------------------

class TestS10TextContent:
    """S10: text() with control characters or excess length is rejected."""

    def test_null_character_rejected(self):
        """text with null character raises EvalError."""
        source = 'text "hello\\x00world" 10'
        # The parser may or may not handle \x00 in string literals.
        # Test via evaluator directly.
        ev = Evaluator()
        from polyscript import ast_nodes as ast
        node = ast.Text(
            content=ast.StringLit(value="hello\x00world"),
            size=ast.NumberLit(value=10),
        )
        with pytest.raises(EvalError, match="null character"):
            ev._eval_text(node)

    def test_oversized_text_rejected(self):
        """text with content > MAX_TEXT_LENGTH raises EvalError."""
        ev = Evaluator()
        from polyscript import ast_nodes as ast
        long_text = "A" * (MAX_TEXT_LENGTH + 1)
        node = ast.Text(
            content=ast.StringLit(value=long_text),
            size=ast.NumberLit(value=10),
        )
        with pytest.raises(EvalError, match="exceeds maximum"):
            ev._eval_text(node)

    def test_normal_text_works(self):
        """Normal text content works."""
        result = execute('text "Hello" 10')
        assert result is not None
