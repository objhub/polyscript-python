"""Additional tests to improve codegen.py coverage."""

import pytest
from polyscript.executor import compile_source
from polyscript.codegen_ocp import OCPCodegen
from polyscript import ast_nodes as ast
from polyscript.errors import CodegenError


class TestNoResult:
    """Line 58: _result = None when no statements produce geometry."""

    def test_empty_program(self):
        from polyscript.codegen import generate
        code = generate(ast.Program(statements=[]))
        assert '_result = None' in code

    def test_only_funcdef(self):
        code = compile_source("def f($x) = $x + 1")
        assert '_result = None' in code


class TestGenExprEdgeCases:
    """Lines 89, 100: None expr and TagRef."""

    def test_tag_ref_in_expr(self):
        # $tag in selector context
        code = compile_source('box 50 50 10 | faces >Z as $top | fillet 1 | faces $top | workplane')
        assert 'tag("top")' in code
        assert 'faces(tag="top")' in code

    def test_edges_tag_ref(self):
        code = compile_source('box 50 50 10 | edges =Z as $side | fillet 1 | edges $side | chamfer 0.5')
        assert 'tag("side")' in code
        assert 'edges(tag="side")' in code

    def test_verts_tag_ref(self):
        code = compile_source('box 50 50 10 | verts >Z as $top | fillet 1 | verts $top | chamfer 0.5')
        assert 'tag("top")' in code
        assert 'vertices(tag="top")' in code


class TestArcPath:
    """Lines 262-264: arc path generation."""

    def test_arc(self):
        code = compile_source("arc (0, 0) (5, 10) (10, 0)")
        assert 'threePointArc' in code


class TestAsTag:
    """Line 173, 336: as $tag pipe op."""

    def test_as_tag_standalone(self):
        code = compile_source('box 50 50 10 | as $base')
        assert '.tag("base")' in code


class TestPointsListLit:
    """Lines 323-328: points with list literal and fallback."""

    def test_points_list(self):
        code = compile_source(
            'box 50 50 10 | faces >Z | workplane'
            ' | points [(5, 5), (-5, 5), (0, -5)]'
            ' | hole 3'
        )
        assert 'pushPoints' in code
        assert '.hole(3)' in code


class TestSweep:
    """Line 195: sweep pipe op."""

    def test_sweep_with_helix(self):
        code = compile_source("circle 2 | sweep (helix 5 20 10)")
        assert '.sweep(' in code
        assert 'makeHelix' in code


class TestRotateEdgeCases:
    """Lines 420, 422, 426: rotate with specific zero axes."""

    def test_rotate_x_only(self):
        code = compile_source("box 10 10 10 | rotate 90 0 0")
        assert '.rotate((0,0,0), (1,0,0), 90)' in code
        # y and z are 0, should not appear
        assert '(0,1,0)' not in code
        assert '(0,0,1)' not in code

    def test_rotate_y_only(self):
        code = compile_source("box 10 10 10 | rotate 0 45 0")
        assert '.rotate((0,0,0), (0,1,0), 45)' in code
        assert '(1,0,0)' not in code
        assert '(0,0,1)' not in code

    def test_rotate_all_axes(self):
        code = compile_source("box 10 10 10 | rotate 10 20 30")
        assert '.rotate((0,0,0), (1,0,0), 10)' in code
        assert '.rotate((0,0,0), (0,1,0), 20)' in code
        assert '.rotate((0,0,0), (0,0,1), 30)' in code


class TestImplicit2D:
    """Lines 448-456: implicit 2D primitives in pipe (circle, ellipse, error)."""

    def test_implicit_rect(self):
        code = compile_source(
            'box 50 50 10 | faces >Z | workplane | rect 30 20 | cut'
        )
        assert '.rect(30, 20)' in code
        assert '.cutThruAll()' in code

    def test_implicit_circle(self):
        code = compile_source(
            'box 50 50 10 | faces >Z | workplane | circle 10 | cut'
        )
        assert '.circle(10)' in code

    def test_implicit_ellipse(self):
        code = compile_source(
            'box 50 50 10 | faces >Z | workplane | ellipse 10 5 | cut'
        )
        assert '.ellipse(10, 5)' in code

    def test_implicit_polygon(self):
        code = compile_source(
            'box 50 50 10 | faces >Z | workplane | polygon 6 8 | cut'
        )
        assert '.polygon(6, 8)' in code
        assert '.cutThruAll()' in code


class TestUnionSourceEdgeCases:
    """Union/diff/inter as source commands."""

    def test_union_single_item(self):
        code = compile_source("union [box 10 10 10]")
        assert '.box(10, 10, 10)' in code

    def test_union_with_circles(self):
        code = compile_source("union [circle 5, circle 10] | extrude 5")
        assert '.union(' in code
        assert '.circle(5)' in code
        assert '.circle(10)' in code

    def test_union_with_rects(self):
        code = compile_source("union [rect 40 10, rect 10 40] | extrude 5")
        assert '.union(' in code
        assert '.rect(40, 10' in code
        assert '.rect(10, 40' in code


class TestCodegenError:
    """Lines 151, 209: error on unknown node types."""

    def test_unknown_expr_node(self):
        gen = OCPCodegen()
        with pytest.raises(CodegenError, match="Unknown expression node"):
            gen._gen_expr(object())

    def test_unknown_pipe_op(self):
        gen = OCPCodegen()
        with pytest.raises(CodegenError, match="Unknown pipe operation"):
            gen._gen_pipe_op("current", object())

    def test_unknown_pipe_op_error(self):
        """Pipe op with unknown node type raises CodegenError."""
        gen = OCPCodegen()
        with pytest.raises(CodegenError, match="Unknown pipe operation"):
            gen._gen_pipe_op("current", object())


class TestEdgesVerticesWithTag:
    """Lines 292, 295-297, 302, 305-307: edges/verts with tag selector and as clause."""

    def test_edges_with_as_tag(self):
        code = compile_source('box 50 50 10 | edges =Z as $vert_edges | fillet 2')
        assert '.tag("vert_edges")' in code
        assert ".edges('|Z')" in code

    def test_verts_with_as_tag(self):
        code = compile_source('box 50 50 10 | verts >Z as $top_verts | chamfer 1')
        assert '.tag("top_verts")' in code
        assert ".vertices('>Z')" in code


class TestWorkplaneWithPlane:
    """Line 333: workplane with plane argument (both branches identical currently)."""

    def test_workplane_default(self):
        code = compile_source('box 10 10 10 | faces >Z | workplane')
        assert '.workplane()' in code

    def test_workplane_with_plane(self):
        code = compile_source('box 10 10 10 | faces >Z | workplane "XZ"')
        assert '.workplane().transformed(rotate=(-90, 0, 0))' in code

    def test_workplane_with_yz_plane(self):
        code = compile_source('box 10 10 10 | faces >Z | workplane "YZ"')
        assert '.workplane().transformed(rotate=(0, 90, 0))' in code

    def test_workplane_with_xy_plane(self):
        """XY is the default plane, so no transform needed."""
        code = compile_source('box 10 10 10 | faces >Z | workplane "XY"')
        assert '.workplane()' in code
        assert 'transformed' not in code


class TestGenExprNone:
    """Line 89: _gen_expr called with None."""

    def test_gen_expr_none(self):
        gen = OCPCodegen()
        assert gen._gen_expr(None) == "None"

    def test_tag_ref_expr(self):
        gen = OCPCodegen()
        node = ast.TagRef(name="mytag")
        assert gen._gen_expr(node) == "'mytag'"


class TestRotateFallback:
    """Line 426: rotate with non-3-tuple falls back to no-op rotate."""

    def test_rotate_fallback(self):
        gen = OCPCodegen()
        op = ast.Rotate(angles=ast.NumberLit(value=45))
        result = gen._gen_rotate("shape", op)
        assert '.rotate((0,0,0), (0,0,1), 0)' in result


class TestMoveFallback:
    """Lines 433, 440: move/moveto with non-tuple argument."""

    def test_move_non_tuple(self):
        gen = OCPCodegen()
        op = ast.Move(offset=ast.NumberLit(value=10))
        result = gen._gen_move("shape", op)
        assert result == "shape"

    def test_moveto_non_tuple(self):
        gen = OCPCodegen()
        op = ast.MoveTo(position=ast.NumberLit(value=10))
        result = gen._gen_moveto("shape", op)
        assert result == "shape"

    def test_move_uses_center(self):
        """move should use .center() for relative movement."""
        code = compile_source('box 50 50 10 | faces >Z | workplane | move 10 5')
        assert '.center(10, 5)' in code

    def test_moveto_uses_moveTo(self):
        """moveto should use .moveTo() for absolute positioning."""
        code = compile_source('box 50 50 10 | faces >Z | workplane | moveto 30 20')
        assert '.moveTo(30, 20)' in code

    def test_moveto_differs_from_move(self):
        """move and moveto should generate different CadQuery calls."""
        move_code = compile_source('box 50 50 10 | faces >Z | workplane | move 10 5')
        moveto_code = compile_source('box 50 50 10 | faces >Z | workplane | moveto 10 5')
        assert '.center(' in move_code
        assert '.moveTo(' in moveto_code
        assert '.center(' not in moveto_code
        assert '.moveTo(' not in move_code


class TestImplicit2DError:
    """Line 456: unsupported primitive in implicit 2D pipe."""

    def test_implicit_2d_unsupported(self):
        gen = OCPCodegen()
        op = ast.Implicit2DPrimitive(primitive=ast.LinePath())
        with pytest.raises(CodegenError, match="Cannot use"):
            gen._gen_implicit_2d("shape", op)


class TestAtKwargFallback:
    """at: kwarg with single value should translate on X axis."""

    def test_at_kwarg_single_value(self):
        gen = OCPCodegen()
        result = gen._gen_at_kwarg("shape", ast.NumberLit(value=5))
        assert '.translate((5, 0, 0))' in result

    def test_at_kwarg_none(self):
        gen = OCPCodegen()
        result = gen._gen_at_kwarg("shape", None)
        assert result == "shape"


class TestTranslateTupleFallback:
    """Line 568: translate tuple with neither 2 nor 3 values."""

    def test_translate_single_value(self):
        gen = OCPCodegen()
        tup = ast.TupleLit(values=[ast.NumberLit(value=5)])
        result = gen._gen_translate_tuple("shape", tup)
        assert result == "shape"


class TestListPlacementWith3DTuple:
    """Line 633: list placement with 3D tuples."""

    def test_at_list_3d_tuples(self):
        code = compile_source("sphere 5 at:[(0, 0, 0), (10, 0, 0)]")
        assert '.translate(' in code


class TestPointsFallback:
    """Lines 327-328: points with variable -- unreachable via grammar (only polar/grid/list_lit).
    Test via direct codegen API."""

    def test_points_var_fallback(self):
        gen = OCPCodegen()
        op = ast.PointsSelect(spec=ast.VarRef(name="pts"))
        result = gen._gen_points_select("shape", op)
        assert 'pushPoints(pts)' in result


class TestImplicitWorkplaneFromFaces:
    """Face selection to 2D primitive inserts implicit workplane."""

    def test_faces_rect_implicit_workplane(self):
        code = compile_source('box 50 50 10 | faces >Z | rect 30 20 | cut')
        assert ".faces('>Z').workplane().rect(30, 20)" in code
        assert '.cutThruAll()' in code

    def test_faces_circle_implicit_workplane(self):
        code = compile_source('box 50 50 10 | faces >Z | circle 10 | cut')
        assert ".faces('>Z').workplane().circle(10)" in code

    def test_faces_ellipse_implicit_workplane(self):
        code = compile_source('box 50 50 10 | faces >Z | ellipse 10 5 | cut')
        assert ".faces('>Z').workplane().ellipse(10, 5)" in code

    def test_explicit_workplane_still_works(self):
        """Explicit workplane should still work as before."""
        code = compile_source('box 50 50 10 | faces >Z | workplane | rect 30 20 | cut')
        assert ".workplane().rect(30, 20)" in code

    def test_explicit_workplane_with_plane(self):
        """Explicit workplane with plane argument should still work."""
        code = compile_source('box 50 50 10 | faces >Z | workplane "XZ" | rect 30 20 | cut')
        assert '.workplane().transformed(rotate=(-90, 0, 0))' in code


class TestVertsFrom2DContext:
    """2D context verts returns vertex selection from 2D shapes."""

    def test_rect_verts(self):
        """verts after a 2D rect should parse correctly."""
        code = compile_source('rect 70 50 | verts | circle 1')
        assert '.vertices()' in code
        assert '.circle(1)' in code

    def test_combined_faces_rect_verts(self):
        """Full pipeline: box | faces | rect | verts | circle | cut."""
        code = compile_source('box 80 60 10 | faces >Z | rect 70 50 | verts | circle 1 | cut')
        assert ".faces('>Z')" in code
        assert '.workplane()' in code
        assert '.rect(70, 50)' in code
        assert '.vertices()' in code
        assert '.circle(1)' in code
        assert '.cutThruAll()' in code
