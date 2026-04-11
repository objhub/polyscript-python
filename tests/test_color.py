"""Tests for the color pipe operation."""

import pytest
from polyscript.executor import compile_source
from polyscript.parser import parse
from polyscript.transformer import transform
from polyscript import ast_nodes as ast
from polyscript.colors import (
    NAMED_COLORS,
    parse_hex_color,
    normalize_rgb,
    resolve_color,
)


# --- Color palette tests ---


class TestColorPalette:
    def test_named_colors_tier1(self):
        assert NAMED_COLORS["red"] == (1.0, 0.0, 0.0)
        assert NAMED_COLORS["blue"] == (0.0, 0.0, 1.0)
        assert NAMED_COLORS["green"][1] == pytest.approx(128 / 255)

    def test_named_colors_tier2(self):
        assert "silver" in NAMED_COLORS
        assert "gold" in NAMED_COLORS
        assert "steel" in NAMED_COLORS
        assert "copper" in NAMED_COLORS
        assert "brass" in NAMED_COLORS
        assert "aluminum" in NAMED_COLORS

    def test_grey_alias(self):
        assert NAMED_COLORS["gray"] == NAMED_COLORS["grey"]
        assert NAMED_COLORS["darkgray"] == NAMED_COLORS["darkgrey"]
        assert NAMED_COLORS["lightgray"] == NAMED_COLORS["lightgrey"]

    def test_parse_hex_6_digit(self):
        assert parse_hex_color("#FF0000") == (1.0, 0.0, 0.0)
        assert parse_hex_color("#00FF00") == (0.0, 1.0, 0.0)
        assert parse_hex_color("#0000FF") == (0.0, 0.0, 1.0)

    def test_parse_hex_3_digit(self):
        r, g, b = parse_hex_color("#F00")
        assert r == pytest.approx(1.0)
        assert g == pytest.approx(0.0)
        assert b == pytest.approx(0.0)

    def test_parse_hex_invalid(self):
        assert parse_hex_color("FF0000") is None  # no #
        assert parse_hex_color("#GG0000") is None
        assert parse_hex_color("#FF00") is None  # wrong length

    def test_normalize_rgb_float(self):
        assert normalize_rgb(0.5, 0.3, 0.1) == (0.5, 0.3, 0.1)

    def test_normalize_rgb_int(self):
        r, g, b = normalize_rgb(255, 128, 0)
        assert r == pytest.approx(1.0)
        assert g == pytest.approx(128 / 255)
        assert b == pytest.approx(0.0)

    def test_normalize_rgb_mixed(self):
        # If any > 1, all divided by 255
        r, g, b = normalize_rgb(1.0, 0.5, 2.0)
        assert r == pytest.approx(1.0 / 255)

    def test_resolve_named(self):
        assert resolve_color("red") == (1.0, 0.0, 0.0)
        assert resolve_color("silver")[0] == pytest.approx(192 / 255)

    def test_resolve_hex(self):
        assert resolve_color("#FF0000") == (1.0, 0.0, 0.0)

    def test_resolve_rgb_tuple(self):
        assert resolve_color((0.5, 0.3, 0.1)) == (0.5, 0.3, 0.1)

    def test_resolve_rgb_tuple_int(self):
        r, g, b = resolve_color((255, 0, 0))
        assert r == pytest.approx(1.0)
        assert g == pytest.approx(0.0)

    def test_resolve_css_color(self):
        rgb = resolve_color("coral")
        assert rgb[0] == pytest.approx(1.0)

    def test_resolve_unknown(self):
        with pytest.raises(ValueError, match="Unknown color name"):
            resolve_color("nonexistent_color")

    def test_resolve_invalid_hex(self):
        with pytest.raises(ValueError, match="Invalid HEX"):
            resolve_color("#GG0000")


# --- Parser / AST tests ---


class TestColorParser:
    def _parse_to_ast(self, source):
        tree = parse(source)
        return transform(tree)

    def test_color_named(self):
        prog = self._parse_to_ast('box 10 10 10 | color "red"')
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.Pipeline)
        assert isinstance(stmt.operations[0], ast.ColorOp)
        op = stmt.operations[0]
        assert len(op.args) == 1
        assert isinstance(op.args[0], ast.StringLit)
        assert op.args[0].value == "red"

    def test_color_hex(self):
        prog = self._parse_to_ast('sphere 15 | color "#FF0000"')
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.Pipeline)
        op = stmt.operations[0]
        assert isinstance(op, ast.ColorOp)
        assert op.args[0].value == "#FF0000"

    def test_color_rgb_float(self):
        prog = self._parse_to_ast("cylinder 5 10 | color 0.8 0.2 0.1")
        stmt = prog.statements[0]
        op = stmt.operations[0]
        assert isinstance(op, ast.ColorOp)
        assert len(op.args) == 3
        assert isinstance(op.args[0], ast.NumberLit)
        assert op.args[0].value == pytest.approx(0.8)

    def test_color_rgb_int(self):
        prog = self._parse_to_ast("box 20 20 20 | color 255 128 0")
        stmt = prog.statements[0]
        op = stmt.operations[0]
        assert isinstance(op, ast.ColorOp)
        assert len(op.args) == 3
        assert op.args[0].value == 255

    def test_color_with_alpha(self):
        prog = self._parse_to_ast('box 10 10 10 | color "red" alpha:0.5')
        stmt = prog.statements[0]
        op = stmt.operations[0]
        assert isinstance(op, ast.ColorOp)
        assert op.args[0].value == "red"
        assert "alpha" in op.named_args
        assert isinstance(op.named_args["alpha"], ast.NumberLit)
        assert op.named_args["alpha"].value == pytest.approx(0.5)

    def test_color_in_pipeline(self):
        prog = self._parse_to_ast('box 10 10 10 | fillet 2 | color "blue"')
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.Pipeline)
        assert len(stmt.operations) == 2
        assert isinstance(stmt.operations[0], ast.Fillet)
        assert isinstance(stmt.operations[1], ast.ColorOp)


# --- Code generation tests ---


class TestColorCodegen:
    def test_codegen_named_color(self):
        code = compile_source('box 10 10 10 | color "red"')
        assert ".setColor(1.0, 0.0, 0.0, 1.0)" in code

    def test_codegen_hex_color(self):
        code = compile_source('sphere 15 | color "#FF0000"')
        assert ".setColor(1.0, 0.0, 0.0, 1.0)" in code

    def test_codegen_hex_color_mixed(self):
        code = compile_source('sphere 15 | color "#FF6600"')
        assert ".setColor(" in code

    def test_codegen_rgb_float(self):
        code = compile_source("cylinder 5 10 | color 0.8 0.2 0.1")
        assert ".setColor(" in code
        # Should have normalization logic
        assert "_r" in code
        assert "_g" in code
        assert "_b" in code

    def test_codegen_rgb_int(self):
        code = compile_source("box 20 20 20 | color 255 128 0")
        assert ".setColor(" in code

    def test_codegen_alpha(self):
        code = compile_source('box 10 10 10 | color "red" alpha:0.5')
        assert ".setColor(1.0, 0.0, 0.0, 0.5)" in code

    def test_codegen_named_silver(self):
        code = compile_source('box 10 10 10 | color "silver"')
        assert ".setColor(" in code

    def test_codegen_color_in_pipeline(self):
        code = compile_source('box 10 10 10 | fillet 2 | color "blue"')
        assert ".fillet(2)" in code
        assert ".setColor(0.0, 0.0, 1.0, 1.0)" in code


# --- Error tests ---


class TestColorErrors:
    def test_unknown_color_name(self):
        with pytest.raises(Exception):
            compile_source('box 10 10 10 | color "nonexistent"')
