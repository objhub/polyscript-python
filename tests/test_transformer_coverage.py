"""Tests to improve transformer.py coverage (lines 54, 184, 223, 322, 442)."""

import pytest
from polyscript.parser import parse
from polyscript.transformer import transform
from polyscript import ast_nodes as ast


class TestWorkplaneNoArgs:
    """Line 184: workplane_op with no items (no args)."""

    def test_workplane_no_args(self):
        """Workplane with no arguments should have plane=None."""
        tree = parse("box 10 10 10 | workplane")
        program = transform(tree)
        # Find the Workplane node in the pipeline
        pipeline = program.statements[0]
        assert isinstance(pipeline, ast.Pipeline)
        workplane_op = pipeline.operations[0]
        assert isinstance(workplane_op, ast.Workplane)
        assert workplane_op.plane is None


class TestCutNoArgs:
    """Line 223: cut with no items (no args)."""

    def test_cut_no_depth(self):
        """Cut with no args should have depth=None."""
        tree = parse("box 10 10 10 | faces >Z | workplane | circle 3 | cut")
        program = transform(tree)
        pipeline = program.statements[0]
        assert isinstance(pipeline, ast.Pipeline)
        # Find Cut in operations
        cut_ops = [op for op in pipeline.operations if isinstance(op, ast.Cut)]
        assert len(cut_ops) == 1
        assert cut_ops[0].depth is None


class TestAtomWithAt:
    """Line 54: atom_with_at with single item (no placement)."""

    def test_atom_no_at(self):
        """Atom without @-placement should just return the atom."""
        tree = parse("box 10 10 10")
        program = transform(tree)
        assert isinstance(program.statements[0], ast.Box)

    def test_atom_with_at(self):
        """Atom with @-placement should wrap in AtPlacement."""
        tree = parse("sphere 5 at (10, 20)")
        program = transform(tree)
        stmt = program.statements[0]
        assert isinstance(stmt, ast.AtPlacement)
        assert isinstance(stmt.shape, ast.Sphere)


class TestStringRule:
    """Line 322: string rule (double-quoted string in non-expression context)."""

    def test_faces_pipe_shell(self):
        """Faces selector piped to shell (replaces old shell open:selector syntax)."""
        tree = parse('box 10 10 10 | faces >Z | shell 2')
        program = transform(tree)
        pipeline = program.statements[0]
        assert isinstance(pipeline, ast.Pipeline)
        faces_ops = [op for op in pipeline.operations if isinstance(op, ast.FacesSelect)]
        shell_ops = [op for op in pipeline.operations if isinstance(op, ast.Shell)]
        assert len(faces_ops) == 1
        assert isinstance(faces_ops[0].selector, ast.SelectorLit)
        assert faces_ops[0].selector.value == '>Z'
        assert len(shell_ops) == 1


class TestSplitArgsNonTuple:
    """Line 442: _split_args with a non-tuple item (direct AST node)."""

    def test_split_args_direct_node(self):
        """Verify _split_args handles non-tuple items by treating them as positional."""
        from polyscript.transformer import PolyTransformer
        # Simulate an args list with a direct node (not wrapped in tuple)
        node = ast.NumberLit(value=42)
        pos, kw = PolyTransformer._split_args([node])
        assert pos == [node]
        assert kw == {}

    def test_split_args_mixed(self):
        """Test mixed positional and keyword args."""
        from polyscript.transformer import PolyTransformer
        node1 = ast.NumberLit(value=1)
        node2 = ast.NumberLit(value=2)
        args_list = [
            ("pos", node1),
            ("kw", "depth", node2),
        ]
        pos, kw = PolyTransformer._split_args(args_list)
        assert pos == [node1]
        assert kw == {"depth": node2}

    def test_split_args_empty(self):
        from polyscript.transformer import PolyTransformer
        pos, kw = PolyTransformer._split_args([])
        assert pos == []
        assert kw == {}

    def test_split_args_none(self):
        from polyscript.transformer import PolyTransformer
        pos, kw = PolyTransformer._split_args(None)
        assert pos == []
        assert kw == {}
