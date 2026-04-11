"""Tests for the CLI module (cli.py)."""

import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from polyscript.cli import main


class TestCLIBasic:
    """Test CLI argument parsing and basic flows."""

    def test_no_args_exits(self):
        """CLI with no arguments should exit with error."""
        with patch("sys.argv", ["poly"]):
            with pytest.raises(SystemExit):
                main()

    def test_file_not_found(self, tmp_path, capsys):
        """CLI with nonexistent file should print error and exit."""
        fake = tmp_path / "nonexistent.poly"
        with patch("sys.argv", ["poly", str(fake)]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Error: file not found" in captured.err

    def test_output_py(self, tmp_path, capsys):
        """Output to .py should write generated code."""
        src = tmp_path / "test.poly"
        src.write_text("box 10 10 10")
        out = tmp_path / "out.py"
        with patch("sys.argv", ["poly", str(src), "-o", str(out)]):
            main()
        assert out.exists()
        content = out.read_text()
        assert "box(10, 10, 10)" in content
        captured = capsys.readouterr()
        assert "Generated:" in captured.out

    def test_output_stl(self, tmp_path, capsys):
        """Output to .stl should export geometry."""
        src = tmp_path / "test.poly"
        src.write_text("box 10 10 10")
        out = tmp_path / "out.stl"
        with patch("sys.argv", ["poly", str(src), "-o", str(out)]):
            main()
        assert out.exists()
        assert out.stat().st_size > 0
        captured = capsys.readouterr()
        assert "Exported:" in captured.out

    def test_output_step(self, tmp_path, capsys):
        """Output to .step should export geometry."""
        src = tmp_path / "test.poly"
        src.write_text("box 10 10 10")
        out = tmp_path / "out.step"
        with patch("sys.argv", ["poly", str(src), "-o", str(out)]):
            main()
        assert out.exists()
        captured = capsys.readouterr()
        assert "Exported:" in captured.out

    def test_default_output_stl(self, tmp_path, capsys, monkeypatch):
        """Default output should be .stl in current directory."""
        src = tmp_path / "model.poly"
        src.write_text("box 10 10 10")
        monkeypatch.chdir(tmp_path)
        with patch("sys.argv", ["poly", str(src)]):
            main()
        stl = tmp_path / "model.stl"
        assert stl.exists()

    def test_library_only_file(self, tmp_path, capsys):
        """File with no geometry should print message."""
        src = tmp_path / "lib.poly"
        src.write_text("def f($x) = $x + 1")
        out = tmp_path / "lib.stl"
        with patch("sys.argv", ["poly", str(src), "-o", str(out)]):
            main()
        captured = capsys.readouterr()
        assert "No geometry to export" in captured.out


class TestCLIVerbose:
    """Test CLI -v / --verbose option."""

    def test_verbose_output(self, tmp_path, capsys):
        """-v should print bbox, volume, and topology."""
        src = tmp_path / "test.poly"
        src.write_text("box 10 10 10")
        out = tmp_path / "out.stl"
        with patch("sys.argv", ["poly", str(src), "-o", str(out), "-v"]):
            main()
        captured = capsys.readouterr()
        assert "bbox:" in captured.out
        assert "volume:" in captured.out
        assert "topology:" in captured.out
        assert "faces" in captured.out
        assert "edges" in captured.out
        assert "vertices" in captured.out

    def test_verbose_with_output(self, tmp_path, capsys):
        """-v -o should print info and export file."""
        src = tmp_path / "test.poly"
        src.write_text("box 10 10 10")
        out = tmp_path / "out.stl"
        with patch("sys.argv", ["poly", str(src), "-v", "-o", str(out)]):
            main()
        assert out.exists()
        assert out.stat().st_size > 0
        captured = capsys.readouterr()
        assert "bbox:" in captured.out
        assert "Exported:" in captured.out

    def test_verbose_not_shown_without_flag(self, tmp_path, capsys):
        """Without -v, no B-Rep info should be printed."""
        src = tmp_path / "test.poly"
        src.write_text("box 10 10 10")
        out = tmp_path / "out.stl"
        with patch("sys.argv", ["poly", str(src), "-o", str(out)]):
            main()
        captured = capsys.readouterr()
        assert "bbox:" not in captured.out
        assert "volume:" not in captured.out


class TestCLIErrors:
    """Test CLI error handling."""

    def test_polyscript_error(self, tmp_path, capsys):
        """PolyScript errors should be caught and printed."""
        src = tmp_path / "bad.poly"
        src.write_text("box(")
        with patch("sys.argv", ["poly", str(src)]):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Error:" in captured.err

    def test_internal_error(self, tmp_path, capsys):
        """Internal errors should be caught and printed."""
        src = tmp_path / "test.poly"
        src.write_text("box 10 10 10")
        with patch("sys.argv", ["poly", str(src)]):
            with patch("polyscript.cli.execute", side_effect=RuntimeError("boom")):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Internal error:" in captured.err
