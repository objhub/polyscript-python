"""Lark parse tree to AST transformer."""

import math

from lark import Transformer as LarkTransformer

from . import ast_nodes as ast


_SELECTOR_NAME_ALIASES = {"top", "bottom", "right", "left", "front", "back"}


class PolyTransformer(LarkTransformer):
    """Transform Lark parse tree into PolyScript AST nodes."""

    @staticmethod
    def _strip_dollar(name: str) -> str:
        """Strip leading '$' from DOLLAR_NAME tokens."""
        s = str(name)
        return s[1:] if s.startswith("$") else s

    # --- Top level ---

    def start(self, items):
        stmts = [i for i in items if i is not None]
        return ast.Program(statements=stmts)

    def import_stmt(self, items):
        return ast.Import(path=str(items[0])[1:-1])  # strip quotes

    def func_def(self, items):
        name = str(items[0])
        params = items[1] if isinstance(items[1], list) else []
        body = items[2]
        return ast.FuncDef(name=name, params=params, body=body)

    def params(self, items):
        return [str(t) for t in items]

    def func_param(self, items):
        return self._strip_dollar(items[0])

    def assignment(self, items):
        return ast.Assignment(name=self._strip_dollar(items[0]), value=items[1])

    def pipeline_stmt(self, items):
        return items[0]

    def paren_expr(self, items):
        return items[0]

    def pipe_expr(self, items):
        if len(items) == 1:
            return items[0]
        source = items[0]
        ops = items[1:]
        return ast.Pipeline(source=source, operations=ops)

    def piped_expr(self, items):
        source = items[0]
        ops = items[1:]
        return ast.Pipeline(source=source, operations=ops)

    # --- Atoms ---

    def source_expr(self, items):
        return items[0]


    def var_ref(self, items):
        return ast.VarRef(name=str(items[0]))

    def dollar_var_ref(self, items):
        return ast.VarRef(name=self._strip_dollar(items[0]), dollar=True)

    # --- 3D Primitives ---

    def box(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.Box(
            width=args[0] if len(args) > 0 else None,
            height=args[1] if len(args) > 1 else None,
            depth=args[2] if len(args) > 2 else None,
            center=kwargs.get("center"),
            at=kwargs.get("at"),
        )

    def cylinder(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.Cylinder(
            radius=args[0] if len(args) > 0 else kwargs.get("r"),
            height=args[1] if len(args) > 1 else kwargs.get("h"),
            center=kwargs.get("center"),
            at=kwargs.get("at"),
        )

    def sphere(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.Sphere(
            radius=args[0] if args else kwargs.get("r"),
            center=kwargs.get("center"),
            at=kwargs.get("at"),
        )

    def cone(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.Cone(
            r1=args[0] if len(args) > 0 else kwargs.get("r1"),
            r2=args[1] if len(args) > 1 else kwargs.get("r2"),
            height=args[2] if len(args) > 2 else kwargs.get("h"),
            pnt=kwargs.get("pnt"),
            dir=kwargs.get("dir"),
            angle=kwargs.get("angle"),
            center=kwargs.get("center"),
            at=kwargs.get("at"),
        )

    def torus(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.Torus(
            r1=args[0] if len(args) > 0 else kwargs.get("r1"),
            r2=args[1] if len(args) > 1 else kwargs.get("r2"),
            center=kwargs.get("center"),
            at=kwargs.get("at"),
        )

    def wedge(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.Wedge(
            dx=args[0] if len(args) > 0 else None,
            dy=args[1] if len(args) > 1 else None,
            dz=args[2] if len(args) > 2 else None,
            ltx=args[3] if len(args) > 3 else None,
            center=kwargs.get("center"),
            at=kwargs.get("at"),
        )

    # --- 2D Primitives ---

    def rect(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.Rect(
            width=args[0] if len(args) > 0 else None,
            height=args[1] if len(args) > 1 else None,
            center=kwargs.get("center"),
            at=kwargs.get("at"),
        )

    def circle(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.Circle(
            radius=args[0] if args else kwargs.get("r"),
            center=kwargs.get("center"),
            at=kwargs.get("at"),
        )

    def ellipse(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.Ellipse(
            rx=args[0] if len(args) > 0 else None,
            ry=args[1] if len(args) > 1 else None,
            center=kwargs.get("center"),
            at=kwargs.get("at"),
        )

    def polyline_prim(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.Polyline(points=args[0] if args else None)

    def polygon_prim(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.Polygon(
            n=args[0] if len(args) > 0 else kwargs.get("n"),
            r=args[1] if len(args) > 1 else kwargs.get("r"),
            angle=kwargs.get("angle"),
            at=kwargs.get("at"),
        )

    def text_prim(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.Text(
            content=args[0] if args else None,
            size=args[1] if len(args) > 1 else kwargs.get("size"),
        )

    # --- Sketch ---

    def sketch_expr(self, items):
        start = items[0]
        segments = items[1:]
        return ast.SketchExpr(start=start, segments=segments)

    def sketch_start(self, items):
        return items[0]

    def sketch_line(self, items):
        return items[0]  # TupleLit

    def sketch_arc(self, items):
        return ast.ArcPath(through=items[0], end=items[1])

    def sketch_bezier(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.BezierPath(points=args[0] if args else None)

    # --- Path Primitives ---

    def line_path(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.LinePath(
            start=args[0] if len(args) > 0 else None,
            end=args[1] if len(args) > 1 else None,
        )

    def arc_path(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.ArcPath(
            through=args[0] if len(args) > 0 else None,
            end=args[1] if len(args) > 1 else None,
        )

    def bezier_path(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.BezierPath(points=args[0] if args else None)

    def helix_path(self, items):
        args, kwargs = self._split_args(items[0])
        pitch = args[0] if len(args) > 0 else kwargs.get("pitch")
        height = args[1] if len(args) > 1 else kwargs.get("height")
        radius = args[2] if len(args) > 2 else kwargs.get("radius")
        return ast.HelixPath(pitch=pitch, height=height, radius=radius)

    def spline_path(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.SplinePath(points=args[0] if args else None)

    # --- Pipe Operations ---

    def as_clause(self, items):
        return self._strip_dollar(items[0])

    def _select_op(self, items, cls):
        """Helper for faces/edges/vertices select with greedy_args + optional as_clause."""
        args, kwargs = self._split_args(items[0])
        selectors = []
        for arg in args:
            if isinstance(arg, ast.VarRef) and arg.dollar:
                selectors.append(ast.TagRef(name=arg.name))
            elif isinstance(arg, ast.VarRef) and arg.name in _SELECTOR_NAME_ALIASES:
                selectors.append(ast.SelectorLit(value=arg.name))
            else:
                selectors.append(arg)
        # Keep backward-compatible `selector` as first element
        selector = selectors[0] if selectors else None
        tag = None
        for item in items[1:]:
            if isinstance(item, str):
                tag = item
        return cls(selector=selector, selectors=selectors if len(selectors) > 1 else None, tag=tag)

    def faces_select(self, items):
        return self._select_op(items, ast.FacesSelect)

    def edges_select(self, items):
        return self._select_op(items, ast.EdgesSelect)

    def verts_select(self, items):
        return self._select_op(items, ast.VerticesSelect)

    def points_select(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.PointsSelect(spec=args[0] if args else None)

    def points_polar(self, items):
        polar = self.polar_spec(items)
        return ast.PointsSelect(spec=polar)

    def points_grid(self, items):
        grid = self.grid_spec(items)
        return ast.PointsSelect(spec=grid)

    def polar_spec(self, items):
        args, kwargs = self._split_args(items[0])
        count = args[0] if len(args) > 0 else kwargs.get("count")
        radius = args[1] if len(args) > 1 else kwargs.get("radius")
        return ast.Polar(count=count, radius=radius)

    def grid_spec(self, items):
        args, kwargs = self._split_args(items[0])
        spacing = None
        if len(args) > 2:
            spacing = args[2]
        if spacing is None:
            spacing = kwargs.get("pitch")
        return ast.Grid(
            nx=args[0] if len(args) > 0 else None,
            ny=args[1] if len(args) > 1 else None,
            spacing=spacing,
        )

    def pipe_polar(self, items):
        args, kwargs = self._split_args(items[0])
        count = args[0] if len(args) > 0 else kwargs.get("count")
        radius = args[1] if len(args) > 1 else kwargs.get("radius")
        return ast.Polar(count=count, radius=radius)

    def pipe_grid(self, items):
        args, kwargs = self._split_args(items[0])
        spacing = None
        if len(args) > 2:
            spacing = args[2]
        if spacing is None:
            spacing = kwargs.get("pitch")
        return ast.Grid(
            nx=args[0] if len(args) > 0 else None,
            ny=args[1] if len(args) > 1 else None,
            spacing=spacing,
        )

    def workplane_op(self, items):
        if not items:
            return ast.Workplane(plane=None)
        args, kwargs = self._split_args(items[0])
        plane = args[0].value if args and isinstance(args[0], ast.StringLit) else None
        origin = kwargs.get("origin")
        return ast.Workplane(plane=plane, origin=origin)

    def as_tag(self, items):
        return ast.AsTag(name=self._strip_dollar(items[0]))

    def fillet(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.Fillet(radius=args[0] if args else None)

    def chamfer(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.Chamfer(radius=args[0] if args else None)

    def shell_op(self, items):
        args, kwargs = self._split_args(items[0])
        thickness = args[0] if args else None
        return ast.Shell(thickness=thickness)

    def offset_op(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.Offset(distance=args[0] if args else None)

    def diff(self, items):
        return ast.Diff(shape=items[0])

    def union_op(self, items):
        return ast.Union(shape=items[0])

    def inter(self, items):
        return ast.Inter(shape=items[0])

    def place_op(self, items):
        return ast.Place(shape=items[0])

    # --- Source commands (union/diff/inter with bracket list) ---

    def union_source(self, items):
        return ast.Union(shape=items[0])

    def diff_source(self, items):
        return ast.Diff(shape=items[0])

    def inter_source(self, items):
        return ast.Inter(shape=items[0])

    def hole(self, items):
        args, kwargs = self._split_args(items[0])
        radius = args[0] if args else None
        depth = kwargs.get("depth")
        return ast.Hole(radius=radius, depth=depth)

    def cut(self, items):
        if not items:
            return ast.Cut(depth=None)
        args, kwargs = self._split_args(items[0])
        return ast.Cut(depth=args[0] if args else None)

    def extrude(self, items):
        args, kwargs = self._split_args(items[0])
        height = args[0] if args else None
        draft = kwargs.get("draft")
        return ast.Extrude(height=height, draft=draft)

    def loft(self, items):
        args, kwargs = self._split_args(items[0])
        sections = args[0] if args else None
        height = args[1] if len(args) > 1 else None
        ruled_val = kwargs.get("ruled")
        ruled = isinstance(ruled_val, ast.BoolConst) and ruled_val.value
        return ast.Loft(sections=sections, height=height, ruled=ruled)

    def revolve(self, items):
        args, kwargs = self._split_args(items[0])
        degrees = args[0] if args else None
        axis_val = kwargs.get("axis")
        axis = axis_val.value if isinstance(axis_val, ast.StringLit) else None
        return ast.Revolve(degrees=degrees, axis=axis)

    def sweep(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.Sweep(path=args[0] if args else None)

    def color_op(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.ColorOp(args=args, named_args=kwargs)

    def translate_op(self, items):
        args, kwargs = self._split_args(items[0])
        origin = kwargs.get("origin")
        return ast.Translate(vector=ast.TupleLit(values=args), origin=origin)

    def rotate_op(self, items):
        args, kwargs = self._split_args(items[0])
        origin = kwargs.get("origin")
        return ast.Rotate(angles=ast.TupleLit(values=args), origin=origin)

    def scale_op(self, items):
        args, kwargs = self._split_args(items[0])
        origin = kwargs.get("origin")
        return ast.Scale(vector=ast.TupleLit(values=args), origin=origin)

    def mirror_op(self, items):
        args, kwargs = self._split_args(items[0])
        axis_val = args[0] if args else None
        axis = axis_val.value if isinstance(axis_val, ast.StringLit) else None
        return ast.Mirror(axis=axis)

    def move_op(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.Move(offset=ast.TupleLit(values=args))

    def moveto_op(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.MoveTo(position=ast.TupleLit(values=args))

    # --- Implicit 2D in pipes ---

    def pipe_rect(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.Implicit2DPrimitive(primitive=ast.Rect(
            width=args[0] if len(args) > 0 else None,
            height=args[1] if len(args) > 1 else None,
            center=kwargs.get("center"),
            at=kwargs.get("at"),
        ))

    def pipe_circle(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.Implicit2DPrimitive(primitive=ast.Circle(
            radius=args[0] if args else kwargs.get("r"),
            center=kwargs.get("center"),
            at=kwargs.get("at"),
        ))

    def pipe_ellipse(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.Implicit2DPrimitive(primitive=ast.Ellipse(
            rx=args[0] if len(args) > 0 else None,
            ry=args[1] if len(args) > 1 else None,
            center=kwargs.get("center"),
            at=kwargs.get("at"),
        ))

    def pipe_polyline(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.Implicit2DPrimitive(primitive=ast.Polyline(
            points=args[0] if args else None,
        ))

    def pipe_polygon(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.Implicit2DPrimitive(primitive=ast.Polygon(
            n=args[0] if len(args) > 0 else kwargs.get("n"),
            r=args[1] if len(args) > 1 else kwargs.get("r"),
            angle=kwargs.get("angle"),
            at=kwargs.get("at"),
        ))

    def pipe_text(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.Implicit2DPrimitive(primitive=ast.Text(
            content=args[0] if args else None,
            size=args[1] if len(args) > 1 else kwargs.get("size"),
        ))

    def pipe_sketch(self, items):
        start = items[0]
        segments = items[1:]
        return ast.Implicit2DPrimitive(primitive=ast.SketchExpr(
            start=start, segments=segments,
        ))

    # --- Implicit 3D in pipes ---

    def pipe_box(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.Implicit3DPrimitive(primitive=ast.Box(
            width=args[0] if len(args) > 0 else None,
            height=args[1] if len(args) > 1 else None,
            depth=args[2] if len(args) > 2 else None,
            center=kwargs.get("center"),
            at=kwargs.get("at"),
        ))

    def pipe_cylinder(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.Implicit3DPrimitive(primitive=ast.Cylinder(
            radius=args[0] if len(args) > 0 else kwargs.get("r"),
            height=args[1] if len(args) > 1 else kwargs.get("h"),
            center=kwargs.get("center"),
            at=kwargs.get("at"),
        ))

    def pipe_sphere(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.Implicit3DPrimitive(primitive=ast.Sphere(
            radius=args[0] if args else kwargs.get("r"),
            center=kwargs.get("center"),
            at=kwargs.get("at"),
        ))

    def pipe_cone(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.Implicit3DPrimitive(primitive=ast.Cone(
            r1=args[0] if len(args) > 0 else kwargs.get("r1"),
            r2=args[1] if len(args) > 1 else kwargs.get("r2"),
            height=args[2] if len(args) > 2 else kwargs.get("h"),
            pnt=kwargs.get("pnt"),
            dir=kwargs.get("dir"),
            angle=kwargs.get("angle"),
            center=kwargs.get("center"),
            at=kwargs.get("at"),
        ))

    def pipe_torus(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.Implicit3DPrimitive(primitive=ast.Torus(
            r1=args[0] if len(args) > 0 else kwargs.get("r1"),
            r2=args[1] if len(args) > 1 else kwargs.get("r2"),
            center=kwargs.get("center"),
            at=kwargs.get("at"),
        ))

    def pipe_wedge(self, items):
        args, kwargs = self._split_args(items[0])
        return ast.Implicit3DPrimitive(primitive=ast.Wedge(
            dx=args[0] if len(args) > 0 else None,
            dy=args[1] if len(args) > 1 else None,
            dz=args[2] if len(args) > 2 else None,
            ltx=args[3] if len(args) > 3 else None,
            center=kwargs.get("center"),
            at=kwargs.get("at"),
        ))

    # --- Bracket expressions (unified group / list) ---

    def bracket_expr(self, items):
        """[...] is always a ListLit. Use `union [...]` for shape fusion."""
        if not items:
            return ast.ListLit(values=[])
        children = items[0]  # bracket_items returns a list
        return ast.ListLit(values=children)

    def bracket_items(self, items):
        """Accumulate bracket items from left-recursive rule."""
        if len(items) == 1:
            # Base case: single expr
            return [items[0]]
        # Recursive case: bracket_items + expr
        prev = items[0]
        if not isinstance(prev, list):
            prev = [prev]
        return prev + [items[1]]

    # --- Arguments ---

    def greedy_args(self, items):
        return items

    def paren_arg(self, items):
        return ("pos", items[0])

    def args(self, items):
        return items

    def posarg(self, items):
        return ("pos", items[0])

    def kwarg(self, items):
        return ("kw", str(items[0]), items[1])

    # --- Expressions ---

    def number(self, items):
        val = float(items[0])
        if val == int(val):
            val = int(val)
        return ast.NumberLit(value=val)

    def string(self, items):
        return ast.StringLit(value=str(items[0])[1:-1])

    def string_lit(self, items):
        return ast.StringLit(value=str(items[0])[1:-1])

    def selector_lit(self, items):
        return ast.SelectorLit(value=str(items[0]))


    def add(self, items):
        return ast.BinOp(op="+", left=items[0], right=items[1])

    def sub(self, items):
        return ast.BinOp(op="-", left=items[0], right=items[1])

    def mul(self, items):
        return ast.BinOp(op="*", left=items[0], right=items[1])

    def div(self, items):
        return ast.BinOp(op="/", left=items[0], right=items[1])

    def pow_expr(self, items):
        return ast.BinOp(op="**", left=items[0], right=items[1])

    def idiv(self, items):
        return ast.BinOp(op="//", left=items[0], right=items[1])

    def mod(self, items):
        return ast.BinOp(op="%", left=items[0], right=items[1])

    # --- Comparison ---

    def eq(self, items):
        return ast.BinOp(op="==", left=items[0], right=items[1])

    def neq(self, items):
        return ast.BinOp(op="!=", left=items[0], right=items[1])

    def lt(self, items):
        return ast.BinOp(op="<", left=items[0], right=items[1])

    def gt(self, items):
        return ast.BinOp(op=">", left=items[0], right=items[1])

    def lte(self, items):
        return ast.BinOp(op="<=", left=items[0], right=items[1])

    def gte(self, items):
        return ast.BinOp(op=">=", left=items[0], right=items[1])

    # --- Logical ---

    def or_op(self, items):
        return ast.BinOp(op="or", left=items[0], right=items[1])

    def and_op(self, items):
        return ast.BinOp(op="and", left=items[0], right=items[1])

    # --- Conditional ---

    def if_expr(self, items):
        return ast.IfExpr(cond=items[0], then_expr=items[1], else_expr=items[2])

    # --- Constants ---

    def pi_const(self, items):
        return ast.NumberLit(value=math.pi)

    def true_const(self, items):
        return ast.BoolConst(value=True)

    def false_const(self, items):
        return ast.BoolConst(value=False)

    def neg(self, items):
        return ast.UnaryNeg(operand=items[0])

    def tuple(self, items):
        return ast.TupleLit(values=items)

    def list_item(self, items):
        return items[0]

    def list_lit(self, items):
        return ast.ListLit(values=[i for i in items if i is not None])

    def list_comp(self, items):
        return ast.ListComp(expr=items[0], var=str(items[1]), iter_expr=items[2])

    def list_comp_expr(self, items):
        return ast.ListComp(expr=items[0], var=self._strip_dollar(items[1]), iter_expr=items[2])

    def index_access(self, items):
        return ast.IndexAccess(obj=items[0], index=items[1])

    def func_call(self, items):
        name = str(items[0])
        # Greedy grammar: items = [NAME, arg1, arg2, ...]
        args_list = items[1:]
        pos, kw = self._split_args(args_list)
        return ast.FuncCall(name=name, args=pos, kwargs=kw)

    def func_call_expr(self, items):
        name = str(items[0])
        args_list = items[1] if len(items) > 1 else []
        pos, kw = self._split_args(args_list)
        return ast.FuncCall(name=name, args=pos, kwargs=kw)

    # --- Helpers ---

    @staticmethod
    def _split_args(args_list):
        """Split a list of ('pos', val) and ('kw', name, val) tuples.

        Implements greedy kwarg collection: positional args that appear after
        a kwarg are merged into that kwarg's value as a TupleLit.
        For example, ``center:false true false`` produces
        ``{center: TupleLit([false, true, false])}``.
        """
        positional = []
        keyword = {}
        if not args_list:
            return positional, keyword
        last_kw_name = None
        for item in args_list:
            if isinstance(item, tuple):
                if item[0] == "pos":
                    if last_kw_name is not None:
                        # Merge into preceding kwarg
                        prev = keyword[last_kw_name]
                        if isinstance(prev, ast.TupleLit):
                            prev.values.append(item[1])
                        else:
                            keyword[last_kw_name] = ast.TupleLit(
                                values=[prev, item[1]]
                            )
                    else:
                        positional.append(item[1])
                elif item[0] == "kw":
                    keyword[item[1]] = item[2]
                    last_kw_name = item[1]
            else:
                if last_kw_name is not None:
                    prev = keyword[last_kw_name]
                    if isinstance(prev, ast.TupleLit):
                        prev.values.append(item)
                    else:
                        keyword[last_kw_name] = ast.TupleLit(
                            values=[prev, item]
                        )
                else:
                    positional.append(item)
        return positional, keyword


def transform(tree) -> ast.Program:
    """Transform a Lark parse tree into PolyScript AST."""
    program = PolyTransformer().transform(tree)

    # Attach @param annotations if present (set by parser)
    annotations = getattr(tree, "_param_annotations", {})
    if annotations:
        from .params import attach_param_annotations
        original_source = getattr(tree, "_original_source", None)
        program = attach_param_annotations(
            program, annotations, source=original_source
        )

    return program
