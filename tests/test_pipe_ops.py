"""Tests for pipe operations."""

import pytest
from polyscript.executor import compile_source, execute
from polyscript.parser import parse
from polyscript.transformer import transform
from polyscript import ast_nodes as ast
from polyscript.errors import CodegenError


class TestModifiers:
    def test_fillet(self):
        code = compile_source("box 50 50 10 | fillet 2")
        assert '.fillet(2)' in code

    def test_chamfer(self):
        code = compile_source("box 50 50 10 | chamfer 1")
        assert '.chamfer(1)' in code

    def test_shell(self):
        code = compile_source("box 50 50 10 | shell 2")
        assert '.shell(2)' in code

    def test_shell_with_open(self):
        code = compile_source('box 50 50 10 | faces >Z | shell 2')
        assert ".faces('>Z')" in code
        assert '.shell(2)' in code

    def test_offset_2d(self):
        code = compile_source("rect 80 60 | offset -10 | extrude 5")
        assert '.offset(' in code

    def test_offset_face_selection(self):
        code = compile_source("box 80 60 10 | faces >Z | offset -10 | cut 3")
        assert ".faces('>Z')" in code
        assert '.offset(' in code
        assert 'cutBlind' in code or '.cut(' in code


class TestBoolean:
    def test_diff(self):
        code = compile_source("box 50 50 10 | diff cylinder 5 10")
        assert '.cut(' in code
        assert '.cylinder(5, 10)' in code

    def test_union(self):
        code = compile_source("box 50 50 10 | union sphere 5")
        assert '.union(' in code
        assert '.sphere(5)' in code

    def test_inter(self):
        code = compile_source("box 50 50 10 | inter sphere 30")
        assert '.intersect(' in code

    def test_diff_with_at(self):
        code = compile_source("box 50 50 10 | diff cylinder 3 10 at:(15, 15, 0)")
        assert '.cut(' in code
        assert '.translate(' in code

    def test_diff_group(self):
        code = compile_source("box 50 50 10 | diff [cylinder 5 10, sphere 3]")
        assert '.cut(' in code

    def test_diff_var(self):
        code = compile_source("$holes = cylinder 5 10\nbox 50 50 10 | diff $holes")
        assert '.cut(' in code

    def test_diff_paren_compat(self):
        code = compile_source("box 50 50 10 | diff (cylinder 5 10)")
        assert '.cut(' in code


class TestPlace:
    def test_place_var_with_cut(self):
        code = compile_source("$s = rect 5 5\nbox 10 10 10 | faces >Z | place $s | cut")
        assert '.place(' in code
        assert 'cutThruAll' in code or 'cutBlind' in code

    def test_place_var_with_extrude(self):
        code = compile_source("$s = rect 5 5\nbox 10 10 10 | faces >Z | place $s | extrude 3")
        assert '.place(' in code
        assert '.extrude(3)' in code

    def test_place_circle_var(self):
        code = compile_source("$c = circle 3\nbox 10 10 10 | faces >Z | place $c | cut 5")
        assert '.place(' in code

    def test_place_inline_sketch(self):
        code = compile_source(
            'box 10 10 10 | faces >Z | place sketch [(5,0), (0,5), (-5,0), (0,-5), (5,0)] | cut'
        )
        assert '.place(' in code

    def test_place_inserts_workplane_from_face_selection(self):
        code = compile_source("$s = rect 5 5\nbox 10 10 10 | faces >Z | place $s | cut")
        assert '.workplane().place(' in code

    def test_place_invalid_3d_context(self):
        with pytest.raises(CodegenError, match="place.*requires"):
            compile_source("$s = rect 5 5\nbox 10 10 10 | place $s")


class TestExtrudeRevolveSweep:
    def test_extrude(self):
        code = compile_source("rect 60 40 | extrude 15")
        assert '.extrude(15)' in code

    def test_extrude_with_draft(self):
        code = compile_source("rect 60 40 | extrude 15 draft:5")
        assert '.extrude(15, taper=5)' in code

    def test_revolve(self):
        code = compile_source("circle 20 | revolve 360")
        assert '.revolve(360)' in code

    def test_revolve_with_axis(self):
        code = compile_source('circle 20 | revolve 360 axis:"X"')
        assert '.revolve(360' in code


class TestCutHole:
    def test_cut_thru(self):
        code = compile_source(
            'rect 60 40 | extrude 15 | faces >Z | workplane | rect 40 20 | cut'
        )
        assert '.cutThruAll()' in code

    def test_cut_depth(self):
        code = compile_source(
            'rect 60 40 | extrude 15 | faces >Z | workplane | rect 40 20 | cut 10'
        )
        assert '.cutBlind(-10)' in code

    def test_hole(self):
        code = compile_source(
            'cylinder 30 5 | faces >Z | workplane | points (polar 4 10) | hole 3'
        )
        assert '.hole(3 * 2)' in code

    def test_hole_with_depth(self):
        code = compile_source(
            'cylinder 30 5 | faces >Z | workplane | hole 3 depth:5'
        )
        assert '.hole(3 * 2, 5)' in code

    def test_hole_from_face_selection(self):
        """FaceSelection -> hole: generates holeOnFaces(radius)."""
        code = compile_source(
            'box 80 60 10 | faces >Z | hole 5'
        )
        assert '.holeOnFaces(5)' in code

    def test_hole_from_face_selection_with_depth(self):
        """FaceSelection -> hole with depth: generates holeOnFaces(radius, depth)."""
        code = compile_source(
            'box 80 60 10 | faces >Z | hole 5 depth:3'
        )
        assert '.holeOnFaces(5, 3)' in code

    def test_hole_from_face_selection_multiple_faces(self):
        """FaceSelection with multiple selectors -> hole."""
        code = compile_source(
            'box 80 60 10 | faces >Z | hole 5'
        )
        assert '.faces(' in code
        assert '.holeOnFaces(5)' in code


class TestSelection:
    def test_faces(self):
        code = compile_source('box 50 50 10 | faces >Z')
        assert ".faces('>Z')" in code

    def test_edges(self):
        code = compile_source('box 50 50 10 | edges =Z')
        assert ".edges('|Z')" in code

    def test_verts(self):
        code = compile_source('box 50 50 10 | verts >Z')
        assert ".vertices('>Z')" in code

    def test_faces_with_tag(self):
        code = compile_source('box 50 50 10 | faces >Z as $top')
        assert '.tag("top")' in code
        assert ".faces('>Z')" in code

    def test_workplane(self):
        code = compile_source('box 50 50 10 | faces >Z | workplane')
        assert '.workplane()' in code

    def test_points_polar(self):
        code = compile_source(
            'cylinder 30 5 | faces >Z | workplane | points (polar 6 20)'
        )
        assert 'pushPoints' in code
        assert 'math.cos' in code

    def test_points_grid(self):
        code = compile_source(
            'box 50 50 10 | faces >Z | workplane | points (grid 3 3 10)'
        )
        assert '.rarray(10, 10, 3, 3)' in code


class TestTransform:
    def test_translate(self):
        code = compile_source("box 10 10 10 | translate 5 0 0")
        assert '.translate((5, 0, 0))' in code

    def test_translate_vertex_selection(self):
        """translate in VertexSelection context offsets points."""
        code = compile_source("rect 80 60 | verts | translate 10 10 10 | cone 2 0 6")
        assert '.translate_points((10, 10, 10))' in code

    def test_translate_point_selection(self):
        """translate in PointSelection context offsets points."""
        code = compile_source("box 10 10 10 | points polar 4 20 | translate 5 0 0 | sphere 2")
        assert '.translate_points((5, 0, 0))' in code

    def test_rotate(self):
        code = compile_source("box 10 10 10 | rotate 0 0 45")
        assert '.rotate(' in code
        assert '45' in code

    def test_move(self):
        code = compile_source(
            'box 50 50 10 | faces >Z | workplane | move 10 5'
        )
        assert '.center(10, 5)' in code

    def test_moveto(self):
        code = compile_source(
            'box 50 50 10 | faces >Z | workplane | moveto 10 5'
        )
        assert '.moveTo(10, 5)' in code


class TestVertsCircleCut:
    """Test the verts | circle | cut pattern for placing holes at rect vertices."""

    def test_codegen_verts_circle_cut(self):
        """Codegen produces .vertices().circle(1).cutThruAll() chain."""
        code = compile_source(
            'box 80 60 10 | faces >Z | rect 70 50 | verts | circle 1 | cut'
        )
        assert '.vertices()' in code
        assert '.circle(1)' in code
        assert '.cutThruAll()' in code
        # Should have implicit workplane between faces and rect
        assert '.workplane().rect(70, 50)' in code

    def test_codegen_verts_with_selector(self):
        """Codegen produces .vertices('>X') when selector is given."""
        code = compile_source(
            'box 80 60 10 | faces >Z | rect 70 50 | verts >X | circle 1 | cut'
        )
        assert ".vertices('>X')" in code


class TestPipePolyline:
    """Test polyline as a pipe operation on workplanes."""

    def test_polyline_cut(self):
        code = compile_source(
            'box 80 60 10 | faces >Z | workplane | polyline [(0,0), (10,0), (5,10)] | cut 3'
        )
        assert '.polyline(' in code
        assert '.close()' in code
        assert '.cutBlind(-3)' in code

    def test_polyline_implicit_workplane(self):
        """polyline after faces should get implicit workplane."""
        code = compile_source(
            'box 80 60 10 | faces >Z | polyline [(0,0), (10,0), (5,10)] | cut'
        )
        assert '.workplane()' in code
        assert '.polyline(' in code
        assert '.close()' in code
        assert '.cutThruAll()' in code


class TestPipeSketch:
    """Test sketch as a pipe operation on workplanes."""

    def test_sketch_cut(self):
        code = compile_source(
            'box 80 60 10 | faces >Z | workplane | sketch [(5,0), (0,5), (-5,0), (0,-5)] | cut 3'
        )
        assert '.sketch(' in code
        assert '.cutBlind(-3)' in code

    def test_sketch_extrude(self):
        code = compile_source(
            'box 80 60 10 | faces >Z | workplane | sketch [(5,0), (0,5), (-5,0), (0,-5)] | extrude 5'
        )
        assert '.sketch(' in code
        assert '.extrude(5)' in code

    def test_sketch_implicit_workplane(self):
        """sketch after faces should get implicit workplane."""
        code = compile_source(
            'box 80 60 10 | faces >Z | sketch [(5,0), (0,5), (-5,0), (0,-5)] | cut'
        )
        assert '.workplane()' in code
        assert '.sketch(' in code
        assert '.cutThruAll()' in code

    def test_sketch_with_arc_in_pipe(self):
        code = compile_source(
            'box 10 10 10 | faces >Z | workplane | sketch [(5,0), arc (0,-5) (-5,0), (0,7), (5,0)] | cut'
        )
        assert '.sketch(' in code
        assert '("arc"' in code
        assert '("line"' in code

    def test_sketch_context_is_2d(self):
        """sketch in pipe should be recognized as 2D context."""
        code = compile_source(
            'box 80 60 10 | faces >Z | sketch [(5,0), (0,5), (-5,0), (0,-5)] | extrude 10'
        )
        assert '.extrude(10)' in code

    def test_sketch_after_box_rejected(self):
        """sketch after 3D shape without face selection should error."""
        with pytest.raises(CodegenError, match="2D primitive 'sketch' requires face selection"):
            compile_source("box 80 60 10 | sketch [(5,0), (0,5), (-5,0)]")

    def test_sketch_does_not_use_standalone_workplane(self):
        """Pipe sketch should use current workplane, not cq.Workplane('XY')."""
        code = compile_source(
            'box 80 60 10 | faces >Z | workplane | sketch [(5,0), (0,5), (-5,0), (0,-5)] | cut'
        )
        # The sketch call should chain off the current pipeline, not start with cq.Workplane("XY")
        # Count occurrences of 'cq.Workplane("XY")' - should only be the initial box
        assert code.count('cq.Workplane("XY")') == 1


class TestPipeText:
    """Test text as a pipe operation on workplanes."""

    def test_text_cut(self):
        code = compile_source(
            'box 80 60 10 | faces >Z | workplane | text "M8" | cut 2'
        )
        assert '.text(' in code
        assert "'M8'" in code
        assert '.cutBlind(-2)' in code

    def test_text_cut_with_size(self):
        code = compile_source(
            'box 80 60 10 | faces >Z | workplane | text "M8" size:10 | cut 2'
        )
        assert '.text(' in code
        assert "'M8'" in code
        assert '10' in code
        assert '.cutBlind(-2)' in code

    def test_text_implicit_workplane(self):
        """text after faces should get implicit workplane."""
        code = compile_source(
            'box 80 60 10 | faces >Z | text "Hello" | cut'
        )
        assert '.workplane()' in code
        assert '.text(' in code


class TestSelectorSyntax:
    """Tests for new selector syntax: symbol+axis and name aliases."""

    def test_faces_max_z(self):
        code = compile_source('box 10 10 10 | faces >Z')
        assert ".faces('>Z')" in code

    def test_faces_min_z(self):
        code = compile_source('box 10 10 10 | faces <Z')
        assert ".faces('<Z')" in code

    def test_faces_max_x(self):
        code = compile_source('box 10 10 10 | faces >X')
        assert ".faces('>X')" in code

    def test_edges_parallel_z(self):
        """=Z means parallel to Z axis, maps to CadQuery |Z."""
        code = compile_source('box 10 10 10 | edges =Z')
        assert ".edges('|Z')" in code

    def test_edges_parallel_x(self):
        code = compile_source('box 10 10 10 | edges =X')
        assert ".edges('|X')" in code

    def test_faces_perpendicular_z(self):
        """+Z means perpendicular to Z axis, maps to CadQuery #Z."""
        code = compile_source('box 10 10 10 | faces +Z')
        assert ".faces('#Z')" in code

    def test_faces_perpendicular_y(self):
        code = compile_source('box 10 10 10 | faces +Y')
        assert ".faces('#Y')" in code

    # --- Name aliases ---

    def test_faces_top(self):
        code = compile_source('box 10 10 10 | faces top')
        assert ".faces('>Z')" in code

    def test_faces_bottom(self):
        code = compile_source('box 10 10 10 | faces bottom')
        assert ".faces('<Z')" in code

    def test_faces_right(self):
        code = compile_source('box 10 10 10 | faces right')
        assert ".faces('>X')" in code

    def test_faces_left(self):
        code = compile_source('box 10 10 10 | faces left')
        assert ".faces('<X')" in code

    def test_faces_front(self):
        code = compile_source('box 10 10 10 | faces front')
        assert ".faces('<Y')" in code

    def test_faces_back(self):
        code = compile_source('box 10 10 10 | faces back')
        assert ".faces('>Y')" in code

    def test_edges_top(self):
        code = compile_source('box 10 10 10 | edges top')
        assert ".edges('>Z')" in code

    def test_verts_bottom(self):
        code = compile_source('box 10 10 10 | verts bottom')
        assert ".vertices('<Z')" in code

    # --- Shell open with selectors ---

    def test_shell_open_selector(self):
        code = compile_source('box 10 10 10 | faces >Z | shell 2')
        assert ".faces('>Z')" in code
        assert '.shell(2)' in code

    def test_shell_open_name_alias(self):
        code = compile_source('box 10 10 10 | faces top | shell 2')
        assert ".faces('>Z')" in code
        assert '.shell(2)' in code

    # --- Selector with as-tag ---

    def test_faces_selector_with_tag(self):
        code = compile_source('box 10 10 10 | faces >Z as $top')
        assert '.tag("top")' in code
        assert ".faces('>Z')" in code

    def test_faces_alias_with_tag(self):
        code = compile_source('box 10 10 10 | faces top as $t')
        assert '.tag("t")' in code
        assert ".faces('>Z')" in code

    # --- Edge cases ---

    def test_multiline_selector(self):
        """Selector works in multiline pipeline."""
        source = "box 80 60 10\n | edges >Z | chamfer 1\n | shell 1"
        code = compile_source(source)
        assert ".edges('>Z')" in code
        assert '.chamfer(1)' in code
        assert '.shell(1)' in code


class TestPipelineContextValidation:
    """Test that 2D primitives are rejected in invalid pipeline contexts."""

    def test_circle_after_3d_fillet_rejected(self):
        """box | fillet | circle should error (3D context)."""
        with pytest.raises(CodegenError, match="2D primitive 'circle' requires face selection"):
            compile_source("box 80 60 10 | fillet 2 | circle 10")

    def test_rect_after_box_rejected(self):
        """box | rect should error (3D context)."""
        with pytest.raises(CodegenError, match="2D primitive 'rect' requires face selection"):
            compile_source("box 80 60 10 | rect 20 10")

    def test_circle_after_box_rejected(self):
        """box | circle should error (3D context)."""
        with pytest.raises(CodegenError, match="2D primitive 'circle' requires face selection"):
            compile_source("box 80 60 10 | circle 10")

    def test_ellipse_after_box_rejected(self):
        """box | ellipse should error (3D context)."""
        with pytest.raises(CodegenError, match="2D primitive 'ellipse' requires face selection"):
            compile_source("box 80 60 10 | ellipse 10 5")

    def test_polyline_after_box_rejected(self):
        """box | polyline should error (3D context)."""
        with pytest.raises(CodegenError, match="2D primitive 'polyline' requires face selection"):
            compile_source("box 80 60 10 | polyline [(0,0), (10,0), (5,10)]")

    def test_text_after_box_rejected(self):
        """box | text should error (3D context)."""
        with pytest.raises(CodegenError, match="2D primitive 'text' requires face selection"):
            compile_source('box 80 60 10 | text "hello"')

    def test_circle_after_edges_rejected(self):
        """box | edges | circle should error (EdgeSelection context)."""
        with pytest.raises(CodegenError, match="2D primitive 'circle' requires face selection"):
            compile_source("box 80 60 10 | edges >Z | circle 10")

    def test_circle_after_3d_fillet_circle_cut_rejected(self):
        """Original reported bug: box | fillet | circle | cut should error."""
        with pytest.raises(CodegenError, match="2D primitive 'circle' requires face selection"):
            compile_source("box 80 60 10 | fillet 2 | circle 10 | cut")

    def test_circle_after_chamfer_rejected(self):
        """box | chamfer | circle should error (3D context after chamfer)."""
        with pytest.raises(CodegenError, match="2D primitive 'circle' requires face selection"):
            compile_source("box 80 60 10 | chamfer 2 | circle 10")

    def test_circle_after_diff_rejected(self):
        """box | diff ... | circle should error (3D context after diff)."""
        with pytest.raises(CodegenError, match="2D primitive 'circle' requires face selection"):
            compile_source("box 50 50 10 | diff sphere 5 | circle 10")

    def test_circle_after_translate_3d_rejected(self):
        """box | translate ... | circle should error (3D context preserved by translate)."""
        with pytest.raises(CodegenError, match="2D primitive 'circle' requires face selection"):
            compile_source("box 50 50 10 | translate 5 0 0 | circle 10")

    # --- Valid contexts: these should NOT raise ---

    def test_circle_after_faces_ok(self):
        """box | faces | circle should work (FaceSelection context -> implicit workplane)."""
        code = compile_source("box 80 60 10 | faces >Z | circle 10")
        assert ".circle(10)" in code

    def test_circle_after_workplane_ok(self):
        """box | faces | workplane | circle should work."""
        code = compile_source("box 80 60 10 | faces >Z | workplane | circle 10")
        assert ".circle(10)" in code

    def test_circle_after_verts_ok(self):
        """faces | rect | verts | circle should work (VertexSelection context)."""
        code = compile_source("box 80 60 10 | faces >Z | rect 70 50 | verts | circle 1")
        assert ".circle(1)" in code

    def test_rect_after_faces_ok(self):
        """box | faces | rect should work."""
        code = compile_source("box 80 60 10 | faces >Z | rect 20 10")
        assert ".rect(20, 10)" in code

    def test_circle_after_extrude_rejected(self):
        """rect | extrude | circle should error (3D context after extrude)."""
        with pytest.raises(CodegenError, match="2D primitive 'circle' requires face selection"):
            compile_source("rect 60 40 | extrude 15 | circle 10")

    def test_2d_after_2d_ok(self):
        """rect | circle is 2D->2D, should work (move within 2D context)."""
        # After rect we are in 2D context, piping another 2D primitive is valid
        code = compile_source("box 80 60 10 | faces >Z | rect 70 50 | circle 5")
        assert ".circle(5)" in code


class TestImplicit3DPrimitive:
    """Test 3D primitives in pipe context (vertex/point placement)."""

    def test_box_after_verts(self):
        """rect | verts | box should place boxes at each vertex."""
        code = compile_source("rect 100 100 | verts | box 5 5 5")
        assert ".vertices()" in code
        assert "place_3d_at_points" in code
        assert ".box(5, 5, 5)" in code

    def test_cylinder_after_verts(self):
        """rect | verts | cylinder should place cylinders at each vertex."""
        code = compile_source("rect 100 100 | verts | cylinder 3 10")
        assert ".vertices()" in code
        assert "place_3d_at_points" in code
        assert ".cylinder(3, 10)" in code

    def test_sphere_after_verts(self):
        """rect | verts | sphere should place spheres at each vertex."""
        code = compile_source("rect 100 100 | verts | sphere 5")
        assert ".vertices()" in code
        assert "place_3d_at_points" in code
        assert ".sphere(5)" in code

    def test_cone_after_verts(self):
        """rect | verts | cone should place cones at each vertex."""
        code = compile_source("rect 100 100 | verts | cone 10 5 2")
        assert ".vertices()" in code
        assert "place_3d_at_points" in code
        assert ".cone(10, 5, 2)" in code

    def test_torus_after_verts(self):
        """rect | verts | torus should place tori at each vertex."""
        code = compile_source("rect 100 100 | verts | torus 10 3")
        assert ".vertices()" in code
        assert "place_3d_at_points" in code
        assert ".torus(10, 3)" in code

    def test_box_after_3d_verts(self):
        """box | verts | sphere should place spheres at box vertices."""
        code = compile_source("box 50 50 50 | verts | sphere 3")
        assert ".vertices()" in code
        assert "place_3d_at_points" in code
        assert ".sphere(3)" in code

    def test_3d_prim_in_invalid_context_rejected(self):
        """3D primitive after faces (not verts) should error."""
        with pytest.raises(CodegenError, match="3D primitive 'box' in pipe requires vertex or point selection"):
            compile_source("box 80 60 10 | faces >Z | box 5 5 5")

    def test_3d_prim_in_3d_context_rejected(self):
        """3D primitive after another 3D (no selection) should error."""
        with pytest.raises(CodegenError, match="3D primitive 'sphere' in pipe requires vertex or point selection"):
            compile_source("box 80 60 10 | sphere 5")

    def test_3d_prim_in_2d_context_rejected(self):
        """3D primitive in 2D context should error."""
        with pytest.raises(CodegenError, match="3D primitive 'cylinder' in pipe requires vertex or point selection"):
            compile_source("rect 100 100 | cylinder 5 10")

    def test_3d_prim_output_context_is_3d(self):
        """After placing 3D prims, context should be 3D -- fillet should work."""
        code = compile_source("rect 100 100 | verts | sphere 5 | fillet 1")
        assert "place_3d_at_points" in code
        assert ".fillet(1)" in code


class TestLoftCodegen:
    """Codegen tests for loft -- no OCP runtime needed."""

    def test_loft_basic(self):
        """circle | loft [rect] height -- generates .loft() call."""
        code = compile_source("circle 10 | loft [rect 8 8] 20")
        assert ".loft(" in code
        assert ".circle(10)" in code
        assert ".rect(8, 8)" in code
        assert "20" in code

    def test_loft_multiple_sections(self):
        """circle | loft [rect, circle] height."""
        code = compile_source("circle 10 | loft [rect 8 8, circle 3] 30")
        assert ".loft(" in code
        assert ".rect(8, 8)" in code
        assert ".circle(3)" in code

    def test_loft_ruled(self):
        """circle | loft [rect] h ruled:true -- generates ruled=True."""
        code = compile_source("circle 10 | loft [rect 8 8] 20 ruled:true")
        assert "ruled=True" in code

    def test_loft_explicit_heights(self):
        """circle | loft [rect, circle] [10, 20] -- explicit offset list."""
        code = compile_source("circle 10 | loft [rect 8 8, circle 3] [10, 25]")
        assert "heights=" in code


class TestLoftExecution:
    """OCP execution tests for loft."""

    def test_loft_circle_to_rect(self):
        """Loft from a circle to a rect produces a valid solid."""
        result = execute("circle 10 | loft [rect 8 8] 20")
        assert result._shape is not None
        bb = result.val().BoundingBox()
        # Height should be approximately 20
        assert abs(bb.zlen - 20) < 1.0
        # Width/height should be at least 8 (the rect) and at most 20 (diameter of circle)
        assert bb.xlen >= 7
        assert bb.ylen >= 7

    def test_loft_multiple_sections(self):
        """Loft through multiple sections produces a valid solid."""
        result = execute("circle 10 | loft [rect 8 8, circle 3] 30")
        assert result._shape is not None
        bb = result.val().BoundingBox()
        assert abs(bb.zlen - 30) < 1.0

    def test_loft_ruled(self):
        """Loft with ruled:true produces a valid solid."""
        result = execute("circle 10 | loft [rect 8 8] 20 ruled:true")
        assert result._shape is not None
        bb = result.val().BoundingBox()
        assert abs(bb.zlen - 20) < 1.0

    def test_loft_rect_to_circle(self):
        """Loft from a rect base to a circle top."""
        result = execute("rect 20 20 | loft [circle 5] 15")
        assert result._shape is not None
        bb = result.val().BoundingBox()
        assert abs(bb.zlen - 15) < 1.0
        # Base should be at least 20x20
        assert bb.xlen >= 10
        assert bb.ylen >= 10


class TestExtrudeDraftExecution:
    """Test that extrude with draft:N actually executes successfully.

    Note: the current ocp_kernel.extrude() accepts taper= but does not
    apply it (straight extrusion). We test that the execution does not
    crash and produces a valid solid.
    """

    def test_extrude_draft_basic(self):
        """rect | extrude 15 draft:5 produces a valid solid."""
        result = execute("rect 60 40 | extrude 15 draft:5")
        assert result._shape is not None
        bb = result.val().BoundingBox()
        # Height should be 15
        assert abs(bb.zlen - 15) < 0.5
        # Base should be at least 60x40
        assert bb.xlen >= 30
        assert bb.ylen >= 20

    def test_extrude_draft_circle(self):
        """circle | extrude 10 draft:3 produces a valid solid."""
        result = execute("circle 20 | extrude 10 draft:3")
        assert result._shape is not None
        bb = result.val().BoundingBox()
        assert abs(bb.zlen - 10) < 0.5

    def test_extrude_draft_on_face(self):
        """Extrude with draft on a selected face."""
        result = execute("box 80 60 10 | faces >Z | circle 10 | extrude 20 draft:5")
        assert result._shape is not None
        bb = result.val().BoundingBox()
        # The extruded circle on top should make height > 10
        assert bb.zlen > 10


class TestMirrorAST:
    def test_parse_mirror_x(self):
        tree = parse('box 10 10 10 | mirror "X"')
        prog = transform(tree)
        pipeline = prog.statements[0]
        assert isinstance(pipeline, ast.Pipeline)
        assert isinstance(pipeline.operations[0], ast.Mirror)
        assert pipeline.operations[0].axis == "X"

    def test_parse_mirror_y(self):
        tree = parse('box 10 10 10 | mirror "Y"')
        prog = transform(tree)
        pipeline = prog.statements[0]
        assert isinstance(pipeline.operations[0], ast.Mirror)
        assert pipeline.operations[0].axis == "Y"

    def test_parse_mirror_z(self):
        tree = parse('box 10 10 10 | mirror "Z"')
        prog = transform(tree)
        pipeline = prog.statements[0]
        assert isinstance(pipeline.operations[0], ast.Mirror)
        assert pipeline.operations[0].axis == "Z"


class TestMirrorCodegen:
    def test_codegen_mirror_x(self):
        code = compile_source('box 10 10 10 | mirror "X"')
        assert '.mirror("YZ")' in code

    def test_codegen_mirror_y(self):
        code = compile_source('box 10 10 10 | mirror "Y"')
        assert '.mirror("XZ")' in code

    def test_codegen_mirror_z(self):
        code = compile_source('box 10 10 10 | mirror "Z"')
        assert '.mirror("XY")' in code


class TestImplicit2DAt:
    def test_pipe_rect_at(self):
        code = compile_source("box 100 100 100 center:false | faces front | rect 10 10 at: 20 20")
        assert ".center(20, 20)" in code
        # center should appear before rect
        assert code.index(".center(20, 20)") < code.index(".rect(10, 10")

    def test_pipe_circle_at(self):
        code = compile_source("box 50 50 10 | faces top | circle 5 at: 10 10")
        assert ".center(10, 10)" in code
        assert code.index(".center(10, 10)") < code.index(".circle(5")
