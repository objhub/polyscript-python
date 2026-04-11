"""Tests for expressions, operators, and math functions."""

import math
import pytest
from polyscript.executor import compile_source, execute
from polyscript.parser import parse
from polyscript.transformer import transform
from polyscript import ast_nodes as ast


class TestArithmetic:
    def test_add(self):
        code = compile_source("$x = 1 + 2\nbox $x $x $x")
        assert '(1 + 2)' in code

    def test_sub(self):
        code = compile_source("$x = 10 - 3\nbox $x $x $x")
        assert '(10 - 3)' in code

    def test_mul(self):
        code = compile_source("$x = 2 * 3\nbox $x $x $x")
        assert '(2 * 3)' in code

    def test_div(self):
        code = compile_source("$x = 10 / 3\nbox $x $x $x")
        assert '(10 / 3)' in code

    def test_idiv(self):
        code = compile_source("$x = 10 // 3\nbox $x $x $x")
        assert '(10 // 3)' in code

    def test_mod(self):
        code = compile_source("$x = 10 % 3\nbox $x $x $x")
        assert '(10 % 3)' in code

    def test_power(self):
        code = compile_source("$x = 2 ** 3\nbox $x $x $x")
        assert '(2 ** 3)' in code

    def test_negation(self):
        code = compile_source("$x = -5\nbox $x $x $x")
        assert '(-5)' in code

    def test_precedence(self):
        code = compile_source("$x = 1 + 2 * 3\nbox $x $x $x")
        assert '(1 + (2 * 3))' in code


class TestComparison:
    def test_eq(self):
        code = compile_source("def f($x) = if $x == 0 then 1 else 2\nf(1)")
        assert '==' in code

    def test_neq(self):
        code = compile_source("def f($x) = if $x != 0 then 1 else 2\nf(1)")
        assert '!=' in code

    def test_lt(self):
        code = compile_source("def f($x) = if $x < 5 then 1 else 2\nf(1)")
        assert '<' in code

    def test_gt(self):
        code = compile_source("def f($x) = if $x > 5 then 1 else 2\nf(1)")
        assert '>' in code

    def test_lte(self):
        code = compile_source("def f($x) = if $x <= 5 then 1 else 2\nf(1)")
        assert '<=' in code

    def test_gte(self):
        code = compile_source("def f($x) = if $x >= 5 then 1 else 2\nf(1)")
        assert '>=' in code


class TestLogical:
    def test_and(self):
        code = compile_source("def f($x) = if $x > 0 and $x < 10 then 1 else 2\nf(5)")
        assert ' and ' in code

    def test_or(self):
        code = compile_source("def f($x) = if $x < 0 or $x > 10 then 1 else 2\nf(5)")
        assert ' or ' in code


class TestConditional:
    def test_if_then_else(self):
        code = compile_source("def f($x) = if $x == 0 then 10 else 20\nf(1)")
        assert '(10 if (x == 0) else 20)' in code


class TestListComp:
    def test_basic(self):
        code = compile_source("$x = [$i for $i in range(6)]\nbox 1 1 1")
        assert '[i for i in range(6)]' in code

    def test_with_expr(self):
        code = compile_source("$x = [$i * 2 for $i in range(5)]\nbox 1 1 1")
        assert '(i * 2) for i in range(5)' in code


class TestMathFunctions:
    def test_sin(self):
        code = compile_source("$x = sin(1)\nbox $x $x $x")
        assert 'math.sin(1)' in code

    def test_cos(self):
        code = compile_source("$x = cos(0)\nbox $x $x $x")
        assert 'math.cos(0)' in code

    def test_sqrt(self):
        code = compile_source("$x = sqrt(4)\nbox $x $x $x")
        assert 'math.sqrt(4)' in code

    def test_radians_alias(self):
        code = compile_source("$x = rad(180)\nbox $x $x $x")
        assert 'math.radians(180)' in code

    def test_degrees_alias(self):
        code = compile_source("$x = deg(3.14)\nbox $x $x $x")
        assert 'math.degrees(3.14)' in code

    def test_floor(self):
        code = compile_source("$x = floor(3.7)\nbox $x $x $x")
        assert 'math.floor(3.7)' in code

    def test_ceil(self):
        code = compile_source("$x = ceil(3.2)\nbox $x $x $x")
        assert 'math.ceil(3.2)' in code

    def test_atan2(self):
        code = compile_source("$x = atan2(1, 1)\nbox $x $x $x")
        assert 'math.atan2(1, 1)' in code


class TestConstants:
    def test_pi_in_expr(self):
        code = compile_source("$x = 2 * pi\nbox $x $x $x")
        assert repr(math.pi) in code

    def test_true(self):
        code = compile_source("def f($x) = if true then 1 else 2\nf(0)")
        assert 'True' in code

    def test_false(self):
        code = compile_source("def f($x) = if false then 1 else 2\nf(0)")
        assert 'False' in code


class TestTuplesAndLists:
    def test_tuple(self):
        code = compile_source("$x = (10, 20, 30)\nbox 1 1 1")
        assert '(10, 20, 30)' in code

    def test_list(self):
        code = compile_source("$x = [(0, 0), (10, 5), (20, 0)]\nbox 1 1 1")
        assert '[(0, 0), (10, 5), (20, 0)]' in code


class TestGreedySumLevel:
    """Greedy arguments allow addition/subtraction (+/-) in expressions."""

    def test_fillet_addition(self):
        """fillet 2 + 1 should be fillet(3)."""
        result = execute("box 80 60 10 | fillet 2 + 1")
        assert result._shape is not None

    def test_fillet_subtraction(self):
        """fillet 4 - 1 should be fillet(3)."""
        result = execute("box 80 60 10 | fillet 4 - 1")
        assert result._shape is not None

    def test_box_arg_with_addition(self):
        """box 10 5 + 3 20 should be box(10, 8, 20)."""
        result = execute("box 10 5 + 3 20")
        assert result._shape is not None
        bb = result.val().BoundingBox()
        assert abs(bb.xlen - 10) < 0.5
        assert abs(bb.ylen - 8) < 0.5
        assert abs(bb.zlen - 20) < 0.5

    def test_fillet_unary_minus_still_works(self):
        """fillet -1 should still parse as fillet(-1) (unary minus)."""
        tree = parse("box 10 10 10 | fillet -1")
        prog = transform(tree)
        pipeline = prog.statements[0]
        fillet_node = pipeline.operations[0]
        assert isinstance(fillet_node, ast.Fillet)

    def test_chamfer_with_addition(self):
        """chamfer 1 + 1 should be chamfer(2)."""
        result = execute("box 80 60 10 | edges =Z | chamfer 1 + 1")
        assert result._shape is not None
