"""Tests for origin keyword argument on rotate and translate."""

import pytest
from polyscript.executor import compile_source
from polyscript.parser import parse
from polyscript.transformer import transform
from polyscript import ast_nodes as ast


class TestRotateOriginParsing:
    """Test that origin kwarg is correctly parsed into AST nodes."""

    def test_rotate_default_no_origin(self):
        tree = parse("box 10 10 10 | rotate 0 0 45")
        prog = transform(tree)
        pipeline = prog.statements[0]
        rotate = pipeline.operations[0]
        assert isinstance(rotate, ast.Rotate)
        assert rotate.origin is None

    def test_rotate_origin_world(self):
        tree = parse('box 10 10 10 | rotate 0 0 45 origin:"world"')
        prog = transform(tree)
        pipeline = prog.statements[0]
        rotate = pipeline.operations[0]
        assert isinstance(rotate, ast.Rotate)
        assert isinstance(rotate.origin, ast.StringLit)
        assert rotate.origin.value == "world"

    def test_rotate_origin_local(self):
        tree = parse('box 10 10 10 | rotate 0 0 45 origin:"local"')
        prog = transform(tree)
        pipeline = prog.statements[0]
        rotate = pipeline.operations[0]
        assert isinstance(rotate, ast.Rotate)
        assert isinstance(rotate.origin, ast.StringLit)
        assert rotate.origin.value == "local"

    def test_rotate_origin_tuple(self):
        tree = parse("box 10 10 10 | rotate 0 0 45 origin:(10, 20, 0)")
        prog = transform(tree)
        pipeline = prog.statements[0]
        rotate = pipeline.operations[0]
        assert isinstance(rotate, ast.Rotate)
        assert isinstance(rotate.origin, ast.TupleLit)
        assert len(rotate.origin.values) == 3


class TestTranslateOriginParsing:
    """Test that origin kwarg is correctly parsed into AST nodes for translate."""

    def test_translate_default_no_origin(self):
        tree = parse("box 10 10 10 | translate 0 0 5")
        prog = transform(tree)
        pipeline = prog.statements[0]
        translate = pipeline.operations[0]
        assert isinstance(translate, ast.Translate)
        assert translate.origin is None

    def test_translate_origin_local(self):
        tree = parse('box 10 10 10 | translate 0 0 5 origin:"local"')
        prog = transform(tree)
        pipeline = prog.statements[0]
        translate = pipeline.operations[0]
        assert isinstance(translate, ast.Translate)
        assert isinstance(translate.origin, ast.StringLit)
        assert translate.origin.value == "local"

    def test_translate_origin_tuple(self):
        tree = parse("box 10 10 10 | translate 0 0 5 origin:(10, 20, 0)")
        prog = transform(tree)
        pipeline = prog.statements[0]
        translate = pipeline.operations[0]
        assert isinstance(translate, ast.Translate)
        assert isinstance(translate.origin, ast.TupleLit)


class TestRotateOriginCodegen:
    """Test CadQuery code generation for rotate with origin."""

    def test_rotate_default_uses_world_origin(self):
        code = compile_source("box 10 10 10 | rotate 0 0 45")
        assert ".rotate((0,0,0), (0,0,1), 45)" in code

    def test_rotate_origin_world_explicit(self):
        code = compile_source('box 10 10 10 | rotate 0 0 45 origin:"world"')
        assert ".rotate((0,0,0), (0,0,1), 45)" in code

    def test_rotate_origin_local(self):
        code = compile_source('box 10 10 10 | rotate 0 0 45 origin:"local"')
        assert "BoundingBox()" in code
        assert "_center" in code
        assert ".rotate(" in code
        # Should NOT use (0,0,0) as origin
        assert ".rotate((0,0,0)" not in code

    def test_rotate_origin_tuple(self):
        code = compile_source("box 10 10 10 | rotate 0 0 45 origin:(10, 20, 0)")
        assert ".rotate((10, 20, 0), (0,0,1), 45)" in code

    def test_rotate_all_axes_with_local_origin(self):
        code = compile_source('box 10 10 10 | rotate 10 20 30 origin:"local"')
        assert "BoundingBox()" in code
        assert ".rotate(" in code
        # All three axis rotations should use the center
        assert "(1,0,0), 10)" in code
        assert "(0,1,0), 20)" in code
        assert "(0,0,1), 30)" in code

    def test_rotate_all_axes_with_tuple_origin(self):
        code = compile_source("box 10 10 10 | rotate 10 20 30 origin:(5, 5, 5)")
        assert ".rotate((5, 5, 5), (1,0,0), 10)" in code
        assert ".rotate((5, 5, 5), (0,1,0), 20)" in code
        assert ".rotate((5, 5, 5), (0,0,1), 30)" in code


class TestTranslateOriginCodegen:
    """Test CadQuery code generation for translate with origin."""

    def test_translate_default_uses_simple_translate(self):
        code = compile_source("box 10 10 10 | translate 5 0 0")
        assert ".translate((5, 0, 0))" in code

    def test_translate_origin_world_explicit(self):
        code = compile_source('box 10 10 10 | translate 5 0 0 origin:"world"')
        assert ".translate((5, 0, 0))" in code

    def test_translate_origin_local(self):
        code = compile_source('box 10 10 10 | translate 0 0 5 origin:"local"')
        assert "BoundingBox()" in code
        assert "_center" in code
        assert "_neg_center" in code
        assert ".translate(" in code

    def test_translate_origin_tuple(self):
        code = compile_source("box 10 10 10 | translate 0 0 5 origin:(10, 20, 0)")
        assert "_origin = (10, 20, 0)" in code
        assert "_neg" in code
        assert ".translate(" in code


class TestBackwardCompatibility:
    """Ensure existing rotate/translate behavior is unchanged."""

    def test_rotate_without_origin_unchanged(self):
        code = compile_source("box 10 10 10 | rotate 0 0 45")
        assert ".rotate((0,0,0), (0,0,1), 45)" in code

    def test_translate_without_origin_unchanged(self):
        code = compile_source("box 10 10 10 | translate 5 0 0")
        assert ".translate((5, 0, 0))" in code

    def test_rotate_multiple_axes_without_origin(self):
        code = compile_source("box 10 10 10 | rotate 10 20 30")
        assert ".rotate((0,0,0), (1,0,0), 10)" in code
        assert ".rotate((0,0,0), (0,1,0), 20)" in code
        assert ".rotate((0,0,0), (0,0,1), 30)" in code
