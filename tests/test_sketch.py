"""Tests for sketch 2D primitive."""

import pytest
from polyscript.executor import compile_source
from polyscript import ast_nodes as ast
from polyscript.parser import parse
from polyscript.transformer import transform


class TestSketchParsing:
    """Test that sketch syntax parses to correct AST nodes."""

    def test_sketch_lines_only(self):
        tree = parse("sketch [(5, 0), (0, 7), (-5, 0), (0, -7)]")
        prog = transform(tree)
        assert isinstance(prog, ast.Program)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.SketchExpr)
        assert isinstance(stmt.start, ast.TupleLit)
        assert len(stmt.segments) == 3  # 3 line segments after start

    def test_sketch_with_arc(self):
        tree = parse(
            "sketch [(5, 0), arc (0, -5) (-5, 0), (0, 7), (5, 0)]"
        )
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt, ast.SketchExpr)
        assert len(stmt.segments) == 3
        # First segment is arc
        arc = stmt.segments[0]
        assert isinstance(arc, ast.ArcPath)
        assert isinstance(arc.through, ast.TupleLit)
        assert isinstance(arc.end, ast.TupleLit)
        # Second and third are lines (TupleLit)
        assert isinstance(stmt.segments[1], ast.TupleLit)
        assert isinstance(stmt.segments[2], ast.TupleLit)

    def test_sketch_start_is_tuple(self):
        tree = parse("sketch [(1, 2), (3, 4)]")
        prog = transform(tree)
        stmt = prog.statements[0]
        assert isinstance(stmt.start, ast.TupleLit)
        start_vals = stmt.start.values
        assert len(start_vals) == 2


class TestSketchCodegen:
    """Test that sketch generates correct CadQuery code."""

    def test_sketch_lines_codegen(self):
        code = compile_source(
            "sketch [(5, 0), (0, 7), (-5, 0), (0, -7)]"
        )
        assert ".sketch(" in code
        assert '("line"' in code

    def test_sketch_arc_codegen(self):
        code = compile_source(
            "sketch [(5, 0), arc (0, -5) (-5, 0), (0, 7)]"
        )
        assert ".sketch(" in code
        assert '("arc"' in code
        assert '("line"' in code

    def test_sketch_extrude(self):
        code = compile_source(
            "sketch [(5, 0), (0, 7), (-5, 0)] | extrude 10"
        )
        assert ".sketch(" in code
        assert ".extrude(" in code

    def test_sketch_context_is_2d(self):
        """Sketch should be recognized as 2D source for pipeline context."""
        code = compile_source(
            "sketch [(5, 0), (0, 7), (-5, 0)] | extrude 10"
        )
        assert ".extrude(" in code


class TestSketchExecution:
    """Test sketch execution with OCP backend."""

    def test_sketch_lines_execute(self):
        from polyscript.executor import execute
        result = execute(
            "sketch [(5, 0), (0, 7), (-5, 0), (0, -7)]"
        )
        assert result is not None
        # Should have a wire (2D face)
        assert hasattr(result, '_wires')

    def test_sketch_with_arc_execute(self):
        from polyscript.executor import execute
        result = execute(
            "sketch [(5, 0), arc (0, -5) (-5, 0), (0, 7), (5, 0)]"
        )
        assert result is not None

    def test_sketch_extrude_execute(self):
        from polyscript.executor import execute
        result = execute(
            "sketch [(5, 0), (0, 7), (-5, 0), (0, -7)] | extrude 10"
        )
        assert result is not None
        assert result._shape is not None

    def test_sketch_with_arc_extrude_execute(self):
        from polyscript.executor import execute
        result = execute(
            "sketch [(5, 0), arc (0, -5) (-5, 0), (0, 7), (5, 0)] | extrude 5"
        )
        assert result is not None
        assert result._shape is not None

    def test_sketch_with_expressions(self):
        """Sketch should support expressions in coordinates."""
        from polyscript.executor import execute
        result = execute(
            "$r = 5\nsketch [($r, 0), (0, $r), (-$r, 0), (0, -$r)] | extrude 10"
        )
        assert result is not None
        assert result._shape is not None
