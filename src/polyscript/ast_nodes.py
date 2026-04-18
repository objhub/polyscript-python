"""AST node definitions for PolyScript."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Node:
    """Base AST node."""
    pass


# --- Top-level ---

@dataclass
class Program(Node):
    statements: list[Node] = field(default_factory=list)


@dataclass
class ParamAnnotation(Node):
    """@param annotation attached to a variable declaration."""
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class Assignment(Node):
    name: str = ""
    value: Node | None = None
    annotation: ParamAnnotation | None = None


@dataclass
class FuncDef(Node):
    name: str = ""
    params: list[str] = field(default_factory=list)
    body: Node | None = None


# --- Pipeline ---

@dataclass
class Pipeline(Node):
    source: Node | None = None
    operations: list[Node] = field(default_factory=list)


# --- Literals ---

@dataclass
class NumberLit(Node):
    value: float = 0.0


@dataclass
class StringLit(Node):
    value: str = ""


@dataclass
class VarRef(Node):
    name: str = ""
    dollar: bool = False  # True when written as $name (explicit variable ref)


@dataclass
class TagRef(Node):
    name: str = ""


@dataclass
class BinOp(Node):
    op: str = ""
    left: Node | None = None
    right: Node | None = None


@dataclass
class UnaryNeg(Node):
    operand: Node | None = None


@dataclass
class TupleLit(Node):
    values: list[Node] = field(default_factory=list)


@dataclass
class ListLit(Node):
    values: list[Node] = field(default_factory=list)


@dataclass
class ListComp(Node):
    expr: Node | None = None
    var: str = ""
    iter_expr: Node | None = None


@dataclass
class IndexAccess(Node):
    obj: Node | None = None
    index: Node | None = None


@dataclass
class IfExpr(Node):
    cond: Node | None = None
    then_expr: Node | None = None
    else_expr: Node | None = None


@dataclass
class BoolConst(Node):
    value: bool = False


@dataclass
class SelectorLit(Node):
    """Selector literal, e.g. >Z, <X, =Z, +Z, top, bottom."""
    value: str = ""


@dataclass
class Import(Node):
    path: str = ""


# --- 3D Primitives ---

@dataclass
class Box(Node):
    width: Node | None = None
    height: Node | None = None
    depth: Node | None = None
    center: Node | None = None
    at: Node | None = None
    origin: Node | None = None


@dataclass
class Cylinder(Node):
    height: Node | None = None
    radius: Node | None = None
    center: Node | None = None
    at: Node | None = None
    origin: Node | None = None


@dataclass
class Sphere(Node):
    radius: Node | None = None
    center: Node | None = None
    at: Node | None = None
    origin: Node | None = None


@dataclass
class Cone(Node):
    height: Node | None = None
    r1: Node | None = None
    r2: Node | None = None
    pnt: Node | None = None
    dir: Node | None = None
    angle: Node | None = None
    center: Node | None = None
    at: Node | None = None
    origin: Node | None = None


@dataclass
class Torus(Node):
    r1: Node | None = None
    r2: Node | None = None
    center: Node | None = None
    at: Node | None = None
    origin: Node | None = None


@dataclass
class Wedge(Node):
    dx: Node | None = None
    dy: Node | None = None
    dz: Node | None = None
    ltx: Node | None = None
    center: Node | None = None
    at: Node | None = None
    origin: Node | None = None


# --- 2D Primitives ---

@dataclass
class Rect(Node):
    width: Node | None = None
    height: Node | None = None
    center: Node | None = None
    at: Node | None = None
    origin: Node | None = None


@dataclass
class Circle(Node):
    radius: Node | None = None
    center: Node | None = None
    at: Node | None = None
    origin: Node | None = None


@dataclass
class Ellipse(Node):
    rx: Node | None = None
    ry: Node | None = None
    center: Node | None = None
    at: Node | None = None
    origin: Node | None = None


@dataclass
class Polyline(Node):
    points: Node | None = None


@dataclass
class Polygon(Node):
    n: Node | None = None
    r: Node | None = None
    angle: Node | None = None
    at: Node | None = None
    origin: Node | None = None


@dataclass
class Text(Node):
    content: Node | None = None
    size: Node | None = None


@dataclass
class SketchExpr(Node):
    """sketch [...] — closed 2D wire from line/arc/bezier segments."""
    start: Node | None = None
    segments: list[Node] = field(default_factory=list)


@dataclass
class PathLiteral(Node):
    """path [...] — open wire from line/arc/bezier/spline segments.

    Like sketch but without auto-close. Supports 2D and 3D coordinates.
    """
    start: Node | None = None    # first tuple if it's a bare start point
    segments: list[Node] = field(default_factory=list)


# --- Path Primitives ---

@dataclass
class LinePath(Node):
    start: Node | None = None
    end: Node | None = None


@dataclass
class ArcPath(Node):
    start: Node | None = None
    through: Node | None = None
    end: Node | None = None


@dataclass
class CenterArcPath(Node):
    """Center arc: start + end + center, or start + end + radius."""
    start: Node | None = None
    end: Node | None = None
    center: Node | None = None
    radius: Node | None = None  # center or radius is non-None
    cw: bool = False  # future: clockwise / long-arc flag


@dataclass
class BezierPath(Node):
    points: Node | None = None


@dataclass
class HelixPath(Node):
    pitch: Node | None = None
    height: Node | None = None
    radius: Node | None = None


@dataclass
class SplinePath(Node):
    points: Node | None = None


# --- Placement ---

@dataclass
class AtPlacement(Node):
    shape: Node | None = None
    placement: Node | None = None


@dataclass
class Polar(Node):
    count: Node | None = None
    radius: Node | None = None
    orient: Node | None = None


@dataclass
class Grid(Node):
    nx: Node | None = None
    ny: Node | None = None
    spacing: Node | None = None


# --- Pipe Operations ---

@dataclass
class FacesSelect(Node):
    selector: Node | None = None
    selectors: list[Node] | None = None
    tag: str | None = None


@dataclass
class EdgesSelect(Node):
    selector: Node | None = None
    selectors: list[Node] | None = None
    tag: str | None = None


@dataclass
class VerticesSelect(Node):
    selector: Node | None = None
    selectors: list[Node] | None = None
    tag: str | None = None


@dataclass
class PointsSelect(Node):
    spec: Node | None = None


@dataclass
class Workplane(Node):
    plane: str | None = None
    origin: Node | None = None


@dataclass
class AsTag(Node):
    name: str = ""


@dataclass
class Fillet(Node):
    radius: Node | None = None


@dataclass
class Chamfer(Node):
    radius: Node | None = None


@dataclass
class Shell(Node):
    thickness: Node | None = None


@dataclass
class Offset(Node):
    distance: Node | None = None
    join_type: str | None = None  # "arc", "miter", "tangent"
    cap: str | None = None  # "round" (default), "square"


@dataclass
class Diff(Node):
    shape: Node | None = None


@dataclass
class Union(Node):
    shape: Node | None = None


@dataclass
class Inter(Node):
    shape: Node | None = None


@dataclass
class Hole(Node):
    radius: Node | None = None
    depth: Node | None = None
    at: Node | None = None
    origin: Node | None = None


@dataclass
class Cut(Node):
    depth: Node | None = None


@dataclass
class Extrude(Node):
    height: Node | None = None
    draft: Node | None = None


@dataclass
class Revolve(Node):
    axis: str = ""          # 'X' | 'Y' | 'Z'
    degrees: Node | None = None  # None means 360


@dataclass
class Sweep(Node):
    path: Node | None = None


@dataclass
class Loft(Node):
    sections: Node | None = None   # ListLit of 2D expressions
    height: Node | None = None     # total height (number) or heights list
    ruled: bool = False


@dataclass
class Translate(Node):
    vector: Node | None = None
    origin: Node | None = None


@dataclass
class Rotate(Node):
    angles: Node | None = None
    origin: Node | None = None


@dataclass
class Scale(Node):
    vector: Node | None = None
    origin: Node | None = None


@dataclass
class Mirror(Node):
    axis: str | None = None


@dataclass
class ColorOp(Node):
    args: list = field(default_factory=list)
    named_args: dict[str, Any] = field(default_factory=dict)


@dataclass
class Move(Node):
    offset: Node | None = None
    origin: Node | None = None


@dataclass
class MoveTo(Node):
    position: Node | None = None
    origin: Node | None = None


# --- Function Call ---

@dataclass
class FuncCall(Node):
    name: str = ""
    args: list[Node] = field(default_factory=list)
    kwargs: dict[str, Node] = field(default_factory=dict)


# --- Implicit 2D Union (2D primitive appearing in pipe) ---

@dataclass
class Place(Node):
    shape: Node | None = None


@dataclass
class Implicit2DPrimitive(Node):
    primitive: Node | None = None


# --- Implicit 3D Placement (3D primitive appearing in pipe, e.g. verts | box) ---

@dataclass
class Implicit3DPrimitive(Node):
    primitive: Node | None = None
