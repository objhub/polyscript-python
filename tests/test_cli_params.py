"""Tests for CLI parameter passing: -D key=value and --params-file."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from polyscript.cli import _build_overrides, _parse_cli_value


# ---------------------------------------------------------------------------
# _parse_cli_value
# ---------------------------------------------------------------------------


class TestParseCliValue:
    def test_int(self):
        assert _parse_cli_value("100") == 100
        assert isinstance(_parse_cli_value("100"), int)

    def test_negative_int(self):
        assert _parse_cli_value("-5") == -5

    def test_float(self):
        assert _parse_cli_value("1.5") == 1.5
        assert isinstance(_parse_cli_value("1.5"), float)

    def test_float_negative(self):
        assert _parse_cli_value("-0.5") == -0.5

    def test_bool_true(self):
        assert _parse_cli_value("true") is True
        assert _parse_cli_value("True") is True
        assert _parse_cli_value("TRUE") is True

    def test_bool_false(self):
        assert _parse_cli_value("false") is False
        assert _parse_cli_value("False") is False

    def test_string(self):
        assert _parse_cli_value("PLA") == "PLA"
        assert _parse_cli_value("hello world") == "hello world"

    def test_empty_string(self):
        assert _parse_cli_value("") == ""


# ---------------------------------------------------------------------------
# _build_overrides
# ---------------------------------------------------------------------------


class TestBuildOverrides:
    def test_single_define(self):
        assert _build_overrides(["width=100"], None) == {"width": 100}

    def test_multiple_defines(self):
        assert _build_overrides(
            ["width=100", "height=50", "name=PLA"], None
        ) == {"width": 100, "height": 50, "name": "PLA"}

    def test_params_file(self, tmp_path):
        pf = tmp_path / "params.json"
        pf.write_text(json.dumps({"w": 10, "h": 20, "material": "ABS"}))
        assert _build_overrides([], pf) == {"w": 10, "h": 20, "material": "ABS"}

    def test_cli_overrides_params_file(self, tmp_path):
        pf = tmp_path / "params.json"
        pf.write_text(json.dumps({"w": 10, "h": 20}))
        assert _build_overrides(["w=999"], pf) == {"w": 999, "h": 20}

    def test_invalid_define_format(self):
        with pytest.raises(SystemExit) as excinfo:
            _build_overrides(["not_an_equals"], None)
        assert excinfo.value.code == 2

    def test_empty_name(self):
        with pytest.raises(SystemExit) as excinfo:
            _build_overrides(["=100"], None)
        assert excinfo.value.code == 2

    def test_missing_params_file(self, tmp_path):
        with pytest.raises(SystemExit) as excinfo:
            _build_overrides([], tmp_path / "does_not_exist.json")
        assert excinfo.value.code == 2

    def test_invalid_json(self, tmp_path):
        pf = tmp_path / "bad.json"
        pf.write_text("{ invalid json")
        with pytest.raises(SystemExit) as excinfo:
            _build_overrides([], pf)
        assert excinfo.value.code == 2

    def test_json_array_rejected(self, tmp_path):
        pf = tmp_path / "array.json"
        pf.write_text("[1, 2, 3]")
        with pytest.raises(SystemExit) as excinfo:
            _build_overrides([], pf)
        assert excinfo.value.code == 2


# ---------------------------------------------------------------------------
# Integration test via subprocess
# ---------------------------------------------------------------------------


def _run_cli(args, cwd=None):
    """Run `poly` CLI via `python -m polyscript.cli` and capture output."""
    proc = subprocess.run(
        [sys.executable, "-m", "polyscript.cli", *args],
        capture_output=True, text=True, cwd=cwd,
    )
    return proc


class TestCLIIntegration:
    def test_override_changes_volume(self, tmp_path):
        src = tmp_path / "p.poly"
        src.write_text("w = 10\nbox w w w\n")
        out = tmp_path / "out.stl"

        r = _run_cli([str(src), "-D", "w=50", "-v", "-o", str(out)])
        assert r.returncode == 0, f"stderr: {r.stderr}"
        # Verbose output prints volume; 50^3 = 125000
        assert "volume: 125000" in r.stdout

    def test_default_without_override(self, tmp_path):
        src = tmp_path / "p.poly"
        src.write_text("w = 10\nbox w w w\n")
        out = tmp_path / "out.stl"

        r = _run_cli([str(src), "-v", "-o", str(out)])
        assert r.returncode == 0, f"stderr: {r.stderr}"
        assert "volume: 1000" in r.stdout  # 10^3

    def test_unknown_param_warns(self, tmp_path):
        src = tmp_path / "p.poly"
        src.write_text("w = 10\nbox w w w\n")
        out = tmp_path / "out.stl"

        r = _run_cli([str(src), "-D", "unknown_param=42", "-o", str(out)])
        assert r.returncode == 0  # warning, not error
        assert "Warning" in r.stderr
        assert "unknown_param" in r.stderr

    def test_invalid_define_format_exits_2(self, tmp_path):
        src = tmp_path / "p.poly"
        src.write_text("box 10 10 10\n")

        r = _run_cli([str(src), "-D", "no_equals"])
        assert r.returncode == 2
        assert "NAME=VALUE" in r.stderr

    def test_params_file(self, tmp_path):
        src = tmp_path / "p.poly"
        src.write_text("w = 10\nbox w w w\n")
        pf = tmp_path / "params.json"
        pf.write_text(json.dumps({"w": 30}))
        out = tmp_path / "out.stl"

        r = _run_cli([str(src), "--params-file", str(pf), "-v", "-o", str(out)])
        assert r.returncode == 0, f"stderr: {r.stderr}"
        assert "volume: 27000" in r.stdout  # 30^3

    def test_cli_beats_params_file(self, tmp_path):
        src = tmp_path / "p.poly"
        src.write_text("w = 10\nbox w w w\n")
        pf = tmp_path / "params.json"
        pf.write_text(json.dumps({"w": 30}))
        out = tmp_path / "out.stl"

        r = _run_cli([
            str(src), "--params-file", str(pf),
            "-D", "w=40", "-v", "-o", str(out),
        ])
        assert r.returncode == 0, f"stderr: {r.stderr}"
        assert "volume: 64000" in r.stdout  # 40^3 (CLI wins)
