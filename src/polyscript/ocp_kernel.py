"""OpenCascade (OCP) kernel — CadQuery-compatible API for PolyScript.

Provides Workplane, Wire, and exporters that match CadQuery's API surface,
backed by direct OCP calls. This enables PolyScript to run without CadQuery
and share the same OpenCascade foundation as the TypeScript (opencascade.js) version.
"""

from __future__ import annotations

import math
import warnings

from OCP.gp import (
    gp_Pnt, gp_Vec, gp_Dir, gp_Ax1, gp_Ax2, gp_Ax3, gp_Pln, gp_Trsf,
    gp_Circ, gp_Elips,
)
from OCP.BRepPrimAPI import (
    BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeSphere,
    BRepPrimAPI_MakeCone, BRepPrimAPI_MakeTorus, BRepPrimAPI_MakeWedge,
    BRepPrimAPI_MakePrism, BRepPrimAPI_MakeRevol,
)
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse, BRepAlgoAPI_Common
from OCP.BRepFilletAPI import BRepFilletAPI_MakeFillet, BRepFilletAPI_MakeChamfer
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeThickSolid, BRepOffsetAPI_MakePipe, BRepOffsetAPI_MakePipeShell, BRepOffsetAPI_MakeOffset, BRepOffsetAPI_ThruSections
from OCP.BRepTools import BRepTools, BRepTools_WireExplorer
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_Transform, BRepBuilderAPI_RoundCorner,
)
from OCP.TopoDS import TopoDS_Shape, TopoDS_Face, TopoDS_Edge, TopoDS_Wire, TopoDS, TopoDS_Builder, TopoDS_Compound
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX, TopAbs_REVERSED
from OCP.BRep import BRep_Tool
from OCP.BRepBndLib import BRepBndLib
from OCP.Bnd import Bnd_Box
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.GC import GC_MakeArcOfCircle
from OCP.GeomAPI import GeomAPI_PointsToBSpline
from OCP.TopTools import TopTools_ListOfShape
from OCP.TColgp import TColgp_Array1OfPnt
from OCP.BRepAdaptor import BRepAdaptor_Surface, BRepAdaptor_Curve, BRepAdaptor_CompCurve
from OCP.GeomAbs import GeomAbs_Arc, GeomAbs_Tangent, GeomAbs_Intersection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plane(name: str) -> gp_Pln:
    """Create a gp_Pln from plane name like 'XY', 'XZ', 'YZ'."""
    origin = gp_Pnt(0, 0, 0)
    if name == "XZ":
        return gp_Pln(gp_Ax3(origin, gp_Dir(0, 1, 0), gp_Dir(1, 0, 0)))
    elif name == "YZ":
        return gp_Pln(gp_Ax3(origin, gp_Dir(1, 0, 0), gp_Dir(0, 1, 0)))
    else:  # XY (default)
        return gp_Pln(gp_Ax3(origin, gp_Dir(0, 0, 1), gp_Dir(1, 0, 0)))


def _translate_shape(shape: TopoDS_Shape, vec: gp_Vec) -> TopoDS_Shape:
    trsf = gp_Trsf()
    trsf.SetTranslation(vec)
    return BRepBuilderAPI_Transform(shape, trsf, True).Shape()


def _rotate_shape(shape: TopoDS_Shape, center: tuple, axis: tuple, angle_deg: float) -> TopoDS_Shape:
    trsf = gp_Trsf()
    ax = gp_Ax1(gp_Pnt(*center), gp_Dir(*axis))
    trsf.SetRotation(ax, math.radians(angle_deg))
    return BRepBuilderAPI_Transform(shape, trsf, True).Shape()


def _scale_shape(shape: TopoDS_Shape, sx: float, sy: float, sz: float, center: tuple = (0, 0, 0)) -> TopoDS_Shape:
    """Scale a shape. Uniform scale uses gp_Trsf; non-uniform uses gp_GTrsf."""
    cx, cy, cz = float(center[0]), float(center[1]), float(center[2])
    if sx == sy == sz:
        # Uniform scale
        trsf = gp_Trsf()
        trsf.SetScale(gp_Pnt(cx, cy, cz), sx)
        return BRepBuilderAPI_Transform(shape, trsf, True).Shape()
    else:
        # Non-uniform scale: translate to origin, apply GTrsf, translate back
        from OCP.gp import gp_GTrsf, gp_Mat
        from OCP.BRepBuilderAPI import BRepBuilderAPI_GTransform
        # Move to origin
        if cx != 0 or cy != 0 or cz != 0:
            t1 = gp_Trsf()
            t1.SetTranslation(gp_Vec(-cx, -cy, -cz))
            shape = BRepBuilderAPI_Transform(shape, t1, True).Shape()
        # Apply non-uniform scale
        gt = gp_GTrsf()
        mat = gp_Mat(
            sx, 0, 0,
            0, sy, 0,
            0, 0, sz,
        )
        gt.SetVectorialPart(mat)
        shape = BRepBuilderAPI_GTransform(shape, gt, True).Shape()
        # Move back
        if cx != 0 or cy != 0 or cz != 0:
            t2 = gp_Trsf()
            t2.SetTranslation(gp_Vec(cx, cy, cz))
            shape = BRepBuilderAPI_Transform(shape, t2, True).Shape()
        return shape


def _face_center(face: TopoDS_Face) -> gp_Pnt:
    """Return the face's bounding-box center (matching the TypeScript kernel).

    Using the bbox center keeps the workplane origin at the visual middle of
    the face even when the face is asymmetric (e.g. a side face with a notch
    cut out). The centroid (BRepGProp center of mass) would drift toward the
    heavier side, making `at:` offsets behave differently from the TS output.
    """
    bb = Bnd_Box()
    BRepBndLib.Add_s(face, bb)
    xmin, ymin, zmin, xmax, ymax, zmax = bb.Get()
    return gp_Pnt((xmin + xmax) / 2, (ymin + ymax) / 2, (zmin + zmax) / 2)


def _face_normal(face: TopoDS_Face) -> gp_Dir:
    """Get the outward normal of a face at its center."""
    surf = BRepAdaptor_Surface(face)
    u = (surf.FirstUParameter() + surf.LastUParameter()) / 2
    v = (surf.FirstVParameter() + surf.LastVParameter()) / 2
    pnt = gp_Pnt()
    d1u = gp_Vec()
    d1v = gp_Vec()
    surf.D1(u, v, pnt, d1u, d1v)
    normal = d1u.Crossed(d1v)
    if normal.Magnitude() < 1e-10:
        return gp_Dir(0, 0, 1)
    # REVERSED orientation means the outward normal is the opposite of the
    # geometric surface normal (d1u × d1v). Without this flip, the normal
    # for half of a box's faces points inward, breaking cutBlind/extrude.
    if face.Orientation() == TopAbs_REVERSED:
        normal.Reverse()
    return gp_Dir(normal)


def _edge_center(edge: TopoDS_Edge) -> gp_Pnt:
    props = GProp_GProps()
    BRepGProp.LinearProperties_s(edge, props)
    return props.CentreOfMass()


def _edge_direction(edge: TopoDS_Edge) -> gp_Vec | None:
    """Get approximate direction of an edge (for parallel checks)."""
    curve = BRepAdaptor_Curve(edge)
    p1 = curve.Value(curve.FirstParameter())
    p2 = curve.Value(curve.LastParameter())
    dx = p2.X() - p1.X()
    dy = p2.Y() - p1.Y()
    dz = p2.Z() - p1.Z()
    mag = math.sqrt(dx*dx + dy*dy + dz*dz)
    if mag < 1e-10:
        return None
    return gp_Vec(dx/mag, dy/mag, dz/mag)


def _vertex_point(vertex) -> gp_Pnt:
    try:
        return BRep_Tool.Pnt_s(vertex)
    except AttributeError:
        return BRep_Tool.Pnt(vertex)


def _axis_component(pnt: gp_Pnt, axis: str) -> float:
    """Get the component of a point along an axis."""
    return {"X": pnt.X(), "Y": pnt.Y(), "Z": pnt.Z()}[axis.upper()]


def _dir_component(d: gp_Dir, axis: str) -> float:
    return {"X": d.X(), "Y": d.Y(), "Z": d.Z()}[axis.upper()]


def _vec_component(v: gp_Vec, axis: str) -> float:
    return {"X": v.X(), "Y": v.Y(), "Z": v.Z()}[axis.upper()]


def _get_faces(shape: TopoDS_Shape) -> list[TopoDS_Face]:
    faces = []
    exp = TopExp_Explorer(shape, TopAbs_FACE)
    while exp.More():
        faces.append(TopoDS.Face_s(exp.Current()))
        exp.Next()
    return faces


def _get_edges(shape: TopoDS_Shape) -> list[TopoDS_Edge]:
    edges = []
    exp = TopExp_Explorer(shape, TopAbs_EDGE)
    while exp.More():
        edges.append(TopoDS.Edge_s(exp.Current()))
        exp.Next()
    return edges


def _get_vertices(shape: TopoDS_Shape) -> list:
    verts = []
    seen = set()
    exp = TopExp_Explorer(shape, TopAbs_VERTEX)
    while exp.More():
        v = TopoDS.Vertex_s(exp.Current())
        p = BRep_Tool.Pnt_s(v)
        # Deduplicate vertices at the same location (tolerance 1e-6)
        key = (round(p.X(), 6), round(p.Y(), 6), round(p.Z(), 6))
        if key not in seen:
            seen.add(key)
            verts.append(v)
        exp.Next()
    return verts


def _select_items(items, selector: str, center_fn, direction_fn=None):
    """Generic selector for faces/edges/vertices.

    Selector syntax: ">Z", "<X", "|Z", "#Z", "+Z", "-Z"
    """
    if not items:
        return items

    sel = selector.strip()

    # Compound OR: ">Z or >X" — union of each selector's results
    if " or " in sel:
        parts = sel.split(" or ")
        seen = set()
        result = []
        for part in parts:
            for item in _select_items(items, part.strip(), center_fn, direction_fn):
                item_id = id(item)
                if item_id not in seen:
                    seen.add(item_id)
                    result.append(item)
        return result

    # Compound AND: ">Z and |X" — intersection (progressive filtering)
    if " and " in sel:
        parts = sel.split(" and ")
        result = items
        for part in parts:
            result = _select_items(result, part.strip(), center_fn, direction_fn)
        return result

    if len(sel) < 2:
        return items

    op = sel[0]
    axis = sel[1].upper()

    if op == ">":
        # Maximum along axis
        vals = [(item, _axis_component(center_fn(item), axis)) for item in items]
        max_val = max(v for _, v in vals)
        return [item for item, v in vals if abs(v - max_val) < 1e-6]

    elif op == "<":
        # Minimum along axis
        vals = [(item, _axis_component(center_fn(item), axis)) for item in items]
        min_val = min(v for _, v in vals)
        return [item for item, v in vals if abs(v - min_val) < 1e-6]

    elif op == "|" and direction_fn:
        # Parallel to axis
        axis_dir = {"X": gp_Vec(1, 0, 0), "Y": gp_Vec(0, 1, 0), "Z": gp_Vec(0, 0, 1)}[axis]
        result = []
        for item in items:
            d = direction_fn(item)
            if d is not None:
                cross = d.Crossed(axis_dir)
                if cross.Magnitude() < 0.1:
                    result.append(item)
        return result

    elif op == "#" and direction_fn:
        # Perpendicular to axis (normal/direction is perpendicular to the given axis)
        axis_dir = {"X": gp_Vec(1, 0, 0), "Y": gp_Vec(0, 1, 0), "Z": gp_Vec(0, 0, 1)}[axis]
        result = []
        for item in items:
            d = direction_fn(item)
            if d is not None:
                if isinstance(d, gp_Dir):
                    d_vec = gp_Vec(d.X(), d.Y(), d.Z())
                else:
                    d_vec = d
                dot = abs(d_vec.Dot(axis_dir))
                if dot < 0.1:
                    result.append(item)
        return result

    elif op == "+" and direction_fn:
        # Normal/direction pointing in +axis
        result = []
        for item in items:
            d = direction_fn(item)
            if d is not None:
                comp = _vec_component(d, axis) if isinstance(d, gp_Vec) else _dir_component(d, axis)
                if comp > 0.5:
                    result.append(item)
        return result

    elif op == "-" and direction_fn:
        # Normal/direction pointing in -axis
        result = []
        for item in items:
            d = direction_fn(item)
            if d is not None:
                comp = _vec_component(d, axis) if isinstance(d, gp_Vec) else _dir_component(d, axis)
                if comp < -0.5:
                    result.append(item)
        return result

    return items


def _bounding_box(shape: TopoDS_Shape) -> Bnd_Box:
    bb = Bnd_Box()
    BRepBndLib.Add_s(shape, bb)
    return bb


def _bb_dims(shape: TopoDS_Shape) -> tuple[float, float, float]:
    """Return (xlen, ylen, zlen) of shape's bounding box."""
    bb = _bounding_box(shape)
    xmin, ymin, zmin, xmax, ymax, zmax = bb.Get()
    return (xmax - xmin, ymax - ymin, zmax - zmin)


def shape_info(shape: TopoDS_Shape) -> dict:
    """Return B-Rep info (bbox, volume, topology) for a shape."""
    from OCP.TopTools import TopTools_IndexedMapOfShape
    from OCP.TopExp import TopExp

    bb = _bounding_box(shape)
    xmin, ymin, zmin, xmax, ymax, zmax = bb.Get()

    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    volume = props.Mass()

    face_map = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(shape, TopAbs_FACE, face_map)
    edge_map = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(shape, TopAbs_EDGE, edge_map)
    vert_map = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(shape, TopAbs_VERTEX, vert_map)

    return {
        "bbox": {"min": [xmin, ymin, zmin], "max": [xmax, ymax, zmax]},
        "volume": volume,
        "topology": {
            "faces": face_map.Extent(),
            "edges": edge_map.Extent(),
            "vertices": vert_map.Extent(),
        },
    }


def _make_wire_from_points(points: list[gp_Pnt], close: bool = False) -> TopoDS_Wire:
    builder = BRepBuilderAPI_MakeWire()
    for i in range(len(points) - 1):
        edge = BRepBuilderAPI_MakeEdge(points[i], points[i + 1]).Edge()
        builder.Add(edge)
    if close and len(points) > 2:
        edge = BRepBuilderAPI_MakeEdge(points[-1], points[0]).Edge()
        builder.Add(edge)
    return builder.Wire()


def _make_face_from_wire(wire: TopoDS_Wire) -> TopoDS_Face:
    return BRepBuilderAPI_MakeFace(wire).Face()


def _plane_origin(plane: gp_Pln) -> gp_Pnt:
    return plane.Location()


def _plane_normal(plane: gp_Pln) -> gp_Dir:
    return plane.Axis().Direction()


def _plane_xdir(plane: gp_Pln) -> gp_Dir:
    return plane.XAxis().Direction()


def _plane_ydir(plane: gp_Pln) -> gp_Dir:
    return plane.YAxis().Direction()


def _plane_draw_ydir(plane: gp_Pln) -> gp_Dir:
    """Return the 2D y-axis direction for drawing (2D→3D coordinate mapping).

    OCC derives ydir = normal × xdir via the right-hand rule.  For the named
    XZ plane (normal=(0,1,0), xdir=(1,0,0)) this gives ydir=(0,0,-1), but the
    user expectation — and the TypeScript implementation — is that 2D y maps to
    world +Z.  Detect this case by checking the three axis directions exactly
    and return the corrected direction so that _to_3d/etc. are consistent with TS.
    """
    yd = _plane_ydir(plane)
    # XZ named plane: normal ≈ +Y, xdir ≈ +X → OCC ydir ≈ -Z → correct to +Z.
    if yd.Z() < -0.5 and _plane_normal(plane).Y() > 0.9 and _plane_xdir(plane).X() > 0.9:
        return gp_Dir(0, 0, 1)
    return yd


def _to_3d(plane: gp_Pln, x: float, y: float) -> gp_Pnt:
    """Convert 2D coordinates on a plane to 3D point."""
    o = _plane_origin(plane)
    xd = _plane_xdir(plane)
    yd = _plane_draw_ydir(plane)
    return gp_Pnt(
        o.X() + x * xd.X() + y * yd.X(),
        o.Y() + x * xd.Y() + y * yd.Y(),
        o.Z() + x * xd.Z() + y * yd.Z(),
    )


def _last_edge_of_wire(wire: TopoDS_Wire) -> TopoDS_Edge:
    """Return the last edge in a wire."""
    last = None
    exp = TopExp_Explorer(wire, TopAbs_EDGE)
    while exp.More():
        last = TopoDS.Edge_s(exp.Current())
        exp.Next()
    if last is None:
        raise ValueError("Wire has no edges")
    return last


def _tangent_2d_to_3d(plane: gp_Pln, tx: float, ty: float) -> gp_Vec:
    """Convert a 2D tangent direction to a 3D vector on *plane*."""
    xd = _plane_xdir(plane)
    yd = _plane_draw_ydir(plane)
    return gp_Vec(
        tx * xd.X() + ty * yd.X(),
        tx * xd.Y() + ty * yd.Y(),
        tx * xd.Z() + ty * yd.Z(),
    )


def _edge_end_tangent(edge: TopoDS_Edge) -> gp_Vec:
    """Return the tangent vector at the *end* of an edge."""
    curve = BRepAdaptor_Curve(edge)
    last_param = curve.LastParameter()
    pnt = gp_Pnt()
    vec = gp_Vec()
    curve.D1(last_param, pnt, vec)
    if vec.Magnitude() > 1e-12:
        vec.Normalize()
    return vec


def _make_center_arc_edge(
    p_start: gp_Pnt, p_end: gp_Pnt, p_center: gp_Pnt, plane: gp_Pln,
) -> TopoDS_Edge:
    """Build an arc edge from start, end, center (short-arc, CCW default).

    Computes the midpoint on the minor arc and delegates to the 3-point
    ``GC_MakeArcOfCircle(p1, p2, p3)`` — this avoids the ambiguity of
    gp_Ax2's implicit reference direction that otherwise makes the
    (circle, alpha1, alpha2, sense) form pick the wrong side of the chord.
    """
    r_s = p_start.Distance(p_center)
    r_e = p_end.Distance(p_center)
    if r_s < 1e-12:
        raise ValueError("arc: center coincides with start point")
    if abs(r_s - r_e) / r_s > 0.05:
        raise ValueError(
            f"arc: center is not equidistant from start and end"
            f"(|CS|={r_s:.4f}, |CE|={r_e:.4f})"
        )
    r = (r_s + r_e) / 2.0

    mcx = (p_start.X() + p_end.X()) / 2.0
    mcy = (p_start.Y() + p_end.Y()) / 2.0
    mcz = (p_start.Z() + p_end.Z()) / 2.0
    vx = mcx - p_center.X()
    vy = mcy - p_center.Y()
    vz = mcz - p_center.Z()
    vlen = math.sqrt(vx * vx + vy * vy + vz * vz)
    if vlen > 1e-10:
        k = r / vlen
        p_mid = gp_Pnt(p_center.X() + vx * k, p_center.Y() + vy * k, p_center.Z() + vz * k)
    else:
        # Semicircle: chord passes through center, so use normal x (end - start)
        normal = _plane_normal(plane)
        ex = p_end.X() - p_start.X()
        ey = p_end.Y() - p_start.Y()
        ez = p_end.Z() - p_start.Z()
        px = normal.Y() * ez - normal.Z() * ey
        py = normal.Z() * ex - normal.X() * ez
        pz = normal.X() * ey - normal.Y() * ex
        plen = math.sqrt(px * px + py * py + pz * pz)
        if plen < 1e-12:
            raise ValueError("arc: degenerate start/end/center geometry")
        k = r / plen
        p_mid = gp_Pnt(p_center.X() + px * k, p_center.Y() + py * k, p_center.Z() + pz * k)

    arc_curve = GC_MakeArcOfCircle(p_start, p_mid, p_end).Value()
    return BRepBuilderAPI_MakeEdge(arc_curve).Edge()


def _make_radius_arc_edge(
    p_start: gp_Pnt, p_end: gp_Pnt, radius: float, plane: gp_Pln,
) -> TopoDS_Edge:
    """Build an arc edge from start, end, radius (short-arc default).

    Computes the center from the chord midpoint, then delegates to
    ``_make_center_arc_edge``.
    """
    d = p_start.Distance(p_end)
    if d < 1e-12:
        raise ValueError("arc: start and end are the same point")
    if d > 2 * radius + 1e-9:
        raise ValueError(
            f"arc: chord length ({d:.4f}) > diameter ({2*radius:.4f}), "
            f"arc cannot be formed"
        )

    # Midpoint
    mx = (p_start.X() + p_end.X()) / 2.0
    my = (p_start.Y() + p_end.Y()) / 2.0
    mz = (p_start.Z() + p_end.Z()) / 2.0

    # Chord vector and its length
    chord = gp_Vec(p_start, p_end)
    half_d = d / 2.0

    # Height from midpoint to center
    discriminant = radius * radius - half_d * half_d
    h = math.sqrt(max(discriminant, 0.0))

    # Perpendicular direction: normal x chord
    normal = _plane_normal(plane)
    n_vec = gp_Vec(normal.X(), normal.Y(), normal.Z())
    perp = n_vec.Crossed(chord)
    perp_mag = perp.Magnitude()
    if perp_mag < 1e-12:
        raise ValueError("arc: chord is perpendicular to workplane normal")
    perp.Normalize()

    # Center for short arc (default): midpoint + h * perp
    p_center = gp_Pnt(
        mx + h * perp.X(),
        my + h * perp.Y(),
        mz + h * perp.Z(),
    )

    return _make_center_arc_edge(p_start, p_end, p_center, plane)


def _project_to_2d(plane: gp_Pln, x: float, y: float, z: float) -> tuple[float, float]:
    """Project a 3D world point onto *plane*, returning local 2D (u, v)."""
    o = _plane_origin(plane)
    xd = _plane_xdir(plane)
    yd = _plane_draw_ydir(plane)
    dx, dy, dz = x - o.X(), y - o.Y(), z - o.Z()
    u = dx * xd.X() + dy * xd.Y() + dz * xd.Z()
    v = dx * yd.X() + dy * yd.Y() + dz * yd.Z()
    return (u, v)


def _make_rect_wire(w: float, h: float, plane: gp_Pln, cx: float = 0, cy: float = 0) -> TopoDS_Wire:
    hw, hh = w / 2, h / 2
    pts = [
        _to_3d(plane, cx - hw, cy - hh),
        _to_3d(plane, cx + hw, cy - hh),
        _to_3d(plane, cx + hw, cy + hh),
        _to_3d(plane, cx - hw, cy + hh),
    ]
    return _make_wire_from_points(pts, close=True)


def _make_circle_wire(r: float, plane: gp_Pln, cx: float = 0, cy: float = 0) -> TopoDS_Wire:
    center = _to_3d(plane, cx, cy)
    ax2 = gp_Ax2(center, _plane_normal(plane))
    circ = gp_Circ(ax2, r)
    edge = BRepBuilderAPI_MakeEdge(circ).Edge()
    return BRepBuilderAPI_MakeWire(edge).Wire()


def _make_ellipse_wire(rx: float, ry: float, plane: gp_Pln, cx: float = 0, cy: float = 0) -> TopoDS_Wire:
    center = _to_3d(plane, cx, cy)
    ax2 = gp_Ax2(center, _plane_normal(plane))
    if rx >= ry:
        elips = gp_Elips(ax2, rx, ry)
    else:
        # gp_Elips requires major >= minor, so rotate
        yd = _plane_draw_ydir(plane)
        ax2_rot = gp_Ax2(center, _plane_normal(plane), gp_Dir(yd.X(), yd.Y(), yd.Z()))
        elips = gp_Elips(ax2_rot, ry, rx)
    edge = BRepBuilderAPI_MakeEdge(elips).Edge()
    return BRepBuilderAPI_MakeWire(edge).Wire()


# ---------------------------------------------------------------------------
# BoundingBox wrapper
# ---------------------------------------------------------------------------

class _BoundingBox:
    """Mimics CadQuery's BoundingBox interface."""

    def __init__(self, shape: TopoDS_Shape):
        bb = Bnd_Box()
        BRepBndLib.Add_s(shape, bb)
        xmin, ymin, zmin, xmax, ymax, zmax = bb.Get()
        self.xlen = xmax - xmin
        self.ylen = ymax - ymin
        self.zlen = zmax - zmin
        self.xmin = xmin
        self.xmax = xmax
        self.ymin = ymin
        self.ymax = ymax
        self.zmin = zmin
        self.zmax = zmax


class _ValWrapper:
    """Wraps a TopoDS_Shape to provide .BoundingBox()."""

    def __init__(self, shape: TopoDS_Shape):
        self._shape = shape

    def BoundingBox(self):
        return _BoundingBox(self._shape)


# ---------------------------------------------------------------------------
# Wire class (matches cq.Wire)
# ---------------------------------------------------------------------------

class Wire:
    """Static methods matching CadQuery's Wire class."""

    @staticmethod
    def makeHelix(pitch: float, height: float, radius: float) -> TopoDS_Wire:
        from OCP.Geom import Geom_CylindricalSurface
        from OCP.Geom2d import Geom2d_Line
        from OCP.GCE2d import GCE2d_MakeSegment
        from OCP.gp import gp_Ax3, gp_Pnt2d, gp_Dir2d
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
        from OCP.BRepLib import BRepLib

        # Create helix as edge on cylindrical surface
        ax3 = gp_Ax3(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1))
        cyl = Geom_CylindricalSurface(ax3, radius)

        # Parametric line on the unrolled cylinder surface
        # u = angle, v = height along axis
        geom_line = Geom2d_Line(gp_Pnt2d(0.0, 0.0), gp_Dir2d(2 * math.pi, pitch))

        # Compute segment endpoints on the 2D parameter space
        n_turns = height / pitch
        u_start = geom_line.Value(0.0)
        u_stop = geom_line.Value(
            n_turns * math.sqrt((2 * math.pi) ** 2 + pitch ** 2)
        )
        seg = GCE2d_MakeSegment(u_start, u_stop).Value()

        edge = BRepBuilderAPI_MakeEdge(seg, cyl).Edge()
        wire = BRepBuilderAPI_MakeWire(edge).Wire()

        # Build proper 3D curves from the 2D parametric representation
        BRepLib.BuildCurves3d_s(wire, 1e-6, MaxSegment=2000)
        return wire


# ---------------------------------------------------------------------------
# Exporters (matches cq.exporters)
# ---------------------------------------------------------------------------

class ExportTypes:
    STL = ".stl"
    STEP = ".step"


class exporters:
    ExportTypes = ExportTypes

    @staticmethod
    def export(wp, path: str, fmt=None):
        """Export a Workplane result to file."""
        shape = wp._shape if isinstance(wp, Workplane) else wp
        if shape is None:
            return

        if fmt is None:
            import os
            fmt = os.path.splitext(path)[1].lower()

        ext = fmt
        if ext in (".stl", ExportTypes.STL):
            from OCP.StlAPI import StlAPI_Writer
            from OCP.BRepMesh import BRepMesh_IncrementalMesh
            mesh = BRepMesh_IncrementalMesh(shape, 0.1)
            mesh.Perform()
            writer = StlAPI_Writer()
            writer.Write(shape, path)
        elif ext in (".step", ExportTypes.STEP):
            from OCP.STEPControl import STEPControl_Writer, STEPControl_AsIs
            from OCP.Interface import Interface_Static
            writer = STEPControl_Writer()
            Interface_Static.SetCVal_s("write.step.schema", "AP203")
            writer.Transfer(shape, STEPControl_AsIs)
            writer.Write(path)
        else:
            raise ValueError(f"Unsupported export format: {ext}")


# ---------------------------------------------------------------------------
# Workplane class (matches CadQuery's Workplane API)
# ---------------------------------------------------------------------------

class Workplane:
    """CadQuery-compatible Workplane backed by direct OCP calls."""

    def __init__(self, plane: str | gp_Pln = "XY"):
        if isinstance(plane, str):
            self._plane = _make_plane(plane)
        else:
            self._plane = plane
        self._shape: TopoDS_Shape | None = None
        self._wires: list[TopoDS_Wire] = []
        self._sketch_points: list[tuple[float, float]] = []  # for moveTo/lineTo
        self._selected_faces: list[TopoDS_Face] = []
        self._selected_edges: list[TopoDS_Edge] = []
        self._selected_vertices: list = []
        self._tags: dict[str, TopoDS_Shape] = {}
        self._points: list[tuple[float, float]] | None = None
        self._center_x: float = 0
        self._center_y: float = 0
        self._color: tuple[float, float, float, float] | None = None
        self._color_map: dict[int, tuple[TopoDS_Shape, float, float, float, float]] = {}  # id(shape) -> (shape, r, g, b, a)

    def _copy(self, **overrides) -> Workplane:
        wp = Workplane.__new__(Workplane)
        wp._plane = self._plane
        wp._shape = self._shape
        wp._wires = list(self._wires)
        wp._sketch_points = list(self._sketch_points)
        wp._selected_faces = list(self._selected_faces)
        wp._selected_edges = list(self._selected_edges)
        wp._selected_vertices = list(self._selected_vertices)
        wp._tags = dict(self._tags)
        wp._points = list(self._points) if self._points else None
        wp._center_x = self._center_x
        wp._center_y = self._center_y
        wp._color = self._color
        wp._color_map = dict(self._color_map)
        for k, v in overrides.items():
            setattr(wp, k, v)
        return wp

    # --- 3D Primitives ---

    def box(self, w, h, d, centered=(True, True, True)):
        # MakeBox creates from origin (0,0,0) to (w,h,d)
        shape = BRepPrimAPI_MakeBox(w, h, d).Shape()
        # Translate to center on each axis where centered is True
        tx = -w / 2 if centered[0] else 0
        ty = -h / 2 if centered[1] else 0
        tz = -d / 2 if centered[2] else 0
        if tx != 0 or ty != 0 or tz != 0:
            shape = _translate_shape(shape, gp_Vec(tx, ty, tz))
        return self._copy(_shape=shape, _wires=[], _selected_faces=[], _selected_edges=[])

    def cylinder(self, r, h, centered=(True, True, True)):
        # MakeCylinder creates at origin along Z, base at z=0
        ax2 = gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1))
        shape = BRepPrimAPI_MakeCylinder(ax2, r, h).Shape()
        # centered=True: center on axis; False: bbox min at origin
        tx = 0 if centered[0] else r
        ty = 0 if centered[1] else r
        tz = -h / 2 if centered[2] else 0
        if tx != 0 or ty != 0 or tz != 0:
            shape = _translate_shape(shape, gp_Vec(tx, ty, tz))
        return self._copy(_shape=shape, _wires=[], _selected_faces=[], _selected_edges=[])

    def sphere(self, r, centered=(True, True, True)):
        # MakeSphere creates centered at origin
        shape = BRepPrimAPI_MakeSphere(r).Shape()
        tx = 0 if centered[0] else r
        ty = 0 if centered[1] else r
        tz = 0 if centered[2] else r
        if tx != 0 or ty != 0 or tz != 0:
            shape = _translate_shape(shape, gp_Vec(tx, ty, tz))
        return self._copy(_shape=shape, _wires=[], _selected_faces=[], _selected_edges=[])

    def cone(self, r1, r2, h, pnt=None, dir=None, angle=None, centered=(True, True, True)):
        p = gp_Pnt(*(pnt if pnt else (0, 0, 0)))
        d = gp_Dir(*(dir if dir else (0, 0, 1)))
        ax2 = gp_Ax2(p, d)
        if angle is not None:
            shape = BRepPrimAPI_MakeCone(ax2, r1, r2, h, math.radians(angle)).Shape()
        else:
            shape = BRepPrimAPI_MakeCone(ax2, r1, r2, h).Shape()
        # MakeCone creates base at z=0, apex at z=h
        max_r = max(r1, r2)
        tx = 0 if centered[0] else max_r
        ty = 0 if centered[1] else max_r
        tz = -h / 2 if centered[2] else 0
        if tx != 0 or ty != 0 or tz != 0:
            shape = _translate_shape(shape, gp_Vec(tx, ty, tz))
        return self._copy(_shape=shape, _wires=[], _selected_faces=[], _selected_edges=[])

    def torus(self, r1, r2, centered=(True, True, True)):
        # MakeTorus creates centered at origin
        shape = BRepPrimAPI_MakeTorus(r1, r2).Shape()
        tx = 0 if centered[0] else r1 + r2
        ty = 0 if centered[1] else r1 + r2
        tz = 0 if centered[2] else r2
        if tx != 0 or ty != 0 or tz != 0:
            shape = _translate_shape(shape, gp_Vec(tx, ty, tz))
        return self._copy(_shape=shape, _wires=[], _selected_faces=[], _selected_edges=[])

    def wedge(self, dx, dy, dz, ltx, centered=(True, True, True)):
        # MakeWedge creates from origin (0,0,0) to (dx,dy,dz) with top face width ltx
        shape = BRepPrimAPI_MakeWedge(dx, dy, dz, ltx).Shape()
        tx = -dx / 2 if centered[0] else 0
        ty = -dy / 2 if centered[1] else 0
        tz = -dz / 2 if centered[2] else 0
        if tx != 0 or ty != 0 or tz != 0:
            shape = _translate_shape(shape, gp_Vec(tx, ty, tz))
        return self._copy(_shape=shape, _wires=[], _selected_faces=[], _selected_edges=[])

    def place_3d_at_points(self, factory):
        """Place a 3D primitive at each vertex/point position.

        *factory* is a callable returning a fresh ``Workplane`` with a 3D shape.
        The shape is translated to each point derived from ``_points`` (set by
        ``vertices()`` or ``pushPoints()``) or ``_selected_vertices``.
        All resulting shapes are unioned together and replace the current shape.
        """
        offsets = self._get_offsets()
        shapes = []
        for cx, cy in offsets:
            wp = factory()
            s = wp._shape
            if s is None:
                continue
            # Translate to 3D position on the current workplane
            pt = _to_3d(self._plane, cx, cy)
            trsf = gp_Trsf()
            trsf.SetTranslation(gp_Vec(pt.X(), pt.Y(), pt.Z()))
            moved = BRepBuilderAPI_Transform(s, trsf, True).Shape()
            shapes.append(moved)
        if not shapes:
            return self
        result = shapes[0]
        for s in shapes[1:]:
            result = BRepAlgoAPI_Fuse(result, s).Shape()
        return self._copy(_shape=result, _wires=[], _selected_faces=[], _selected_edges=[],
                          _selected_vertices=[], _points=None)

    # --- 2D Primitives ---

    def rect(self, w, h, centered=True):
        # centered can be True/False (both axes) or (bool, bool)
        if isinstance(centered, (list, tuple)):
            dx = 0 if centered[0] else w / 2
            dy = 0 if centered[1] else h / 2
        else:
            dx = 0 if centered else w / 2
            dy = 0 if centered else h / 2
        offsets = self._get_offsets()
        new_wires = list(self._wires)
        for cx, cy in offsets:
            wire = _make_rect_wire(w, h, self._plane, cx + dx, cy + dy)
            new_wires.append(wire)
        return self._copy(_wires=new_wires)

    def circle(self, r, centered=(True, True)):
        if isinstance(centered, (list, tuple)):
            dx = 0 if centered[0] else r
            dy = 0 if centered[1] else r
        else:
            dx = 0 if centered else r
            dy = 0 if centered else r
        offsets = self._get_offsets()
        new_wires = list(self._wires)
        for cx, cy in offsets:
            wire = _make_circle_wire(r, self._plane, cx + dx, cy + dy)
            new_wires.append(wire)
        return self._copy(_wires=new_wires)

    def ellipse(self, rx, ry, centered=(True, True)):
        if isinstance(centered, (list, tuple)):
            dx = 0 if centered[0] else rx
            dy = 0 if centered[1] else ry
        else:
            dx = 0 if centered else rx
            dy = 0 if centered else ry
        offsets = self._get_offsets()
        new_wires = list(self._wires)
        for cx, cy in offsets:
            wire = _make_ellipse_wire(rx, ry, self._plane, cx + dx, cy + dy)
            new_wires.append(wire)
        return self._copy(_wires=new_wires)

    def polygon(self, n, r=1):
        """Create a regular polygon with n sides and circumscribed-circle radius r."""
        import math
        pts = [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n)) for i in range(n)]
        return self.polyline(pts).close()

    def polyline(self, pts):
        """Create a polyline wire from list of (x,y) or (x,y,z) tuples."""
        points_3d = []
        for p in pts:
            if len(p) == 2:
                points_3d.append(_to_3d(self._plane, p[0] + self._center_x, p[1] + self._center_y))
            else:
                points_3d.append(gp_Pnt(p[0], p[1], p[2]))
        wire = _make_wire_from_points(points_3d, close=False)
        new_wires = list(self._wires)
        new_wires.append(wire)
        return self._copy(_wires=new_wires)

    def close(self):
        """Close the last wire."""
        if not self._wires:
            return self
        # Rebuild last wire as closed
        wire = self._wires[-1]
        edges = []
        exp = TopExp_Explorer(wire, TopAbs_EDGE)
        pts = []
        while exp.More():
            e = TopoDS.Edge_s(exp.Current())
            curve = BRepAdaptor_Curve(e)
            if not pts:
                pts.append(curve.Value(curve.FirstParameter()))
            pts.append(curve.Value(curve.LastParameter()))
            edges.append(e)
            exp.Next()
        if len(pts) >= 3:
            closing_edge = BRepBuilderAPI_MakeEdge(pts[-1], pts[0]).Edge()
            builder = BRepBuilderAPI_MakeWire()
            for e in edges:
                builder.Add(e)
            builder.Add(closing_edge)
            new_wires = list(self._wires)
            new_wires[-1] = builder.Wire()
            return self._copy(_wires=new_wires)
        return self

    def text(self, content, size, depth):
        """Text primitive — approximated as a simple placeholder."""
        # Full text support requires Font_BRepTextBuilder which may not be available.
        # For now, create a rectangular placeholder.
        w = size * len(str(content)) * 0.6
        h = size
        return self.rect(w, h)

    def spline(self, pts):
        """Create a spline (bezier) wire."""
        points_3d = []
        for p in pts:
            if len(p) == 2:
                points_3d.append(_to_3d(self._plane, p[0], p[1]))
            else:
                points_3d.append(gp_Pnt(p[0], p[1], p[2]))
        arr = TColgp_Array1OfPnt(1, len(points_3d))
        for i, p in enumerate(points_3d):
            arr.SetValue(i + 1, p)
        bspline = GeomAPI_PointsToBSpline(arr).Curve()
        edge = BRepBuilderAPI_MakeEdge(bspline).Edge()
        wire = BRepBuilderAPI_MakeWire(edge).Wire()
        new_wires = list(self._wires)
        new_wires.append(wire)
        return self._copy(_wires=new_wires)

    # --- Sketch ---

    def sketch(self, start, *segments):
        """Build a closed 2D face from line/arc/bezier segments.

        *start* is a 2D tuple ``(x, y)`` — the starting point.
        Each subsequent argument is a segment descriptor:
          - ``("line", (x, y))`` — straight line to (x, y)
          - ``("arc", (sx, sy), (tx, ty), (ex, ey))`` — arc: start, through, end
          - ``("carc_center", (sx, sy), (ex, ey), (cx, cy))`` — center arc
          - ``("carc_radius", (sx, sy), (ex, ey), r)`` — radius arc
          - ``("bezier", [(x1,y1), ...])`` — bezier/spline through control points
        The wire is automatically closed and converted to a face.

        If a segment's start does not match the current pen position
        (tolerance 1e-6), an implicit line is inserted to bridge the gap.
        """
        cx, cy = self._center_x, self._center_y
        current = _to_3d(self._plane, start[0] + cx, start[1] + cy)
        builder = BRepBuilderAPI_MakeWire()
        prev_tangent = None  # gp_Vec or None

        for seg in segments:
            kind = seg[0]
            if kind == "line":
                pt = seg[1]
                end_3d = _to_3d(self._plane, pt[0] + cx, pt[1] + cy)
                if current.Distance(end_3d) < 1e-6:
                    continue  # skip zero-length edge
                edge = BRepBuilderAPI_MakeEdge(current, end_3d).Edge()
                builder.Add(edge)
                prev_tangent = gp_Vec(current, end_3d)
                prev_tangent.Normalize()
                current = end_3d
            elif kind == "arc":
                start_2d, through_2d, end_2d = seg[1], seg[2], seg[3]
                p_start = _to_3d(self._plane, start_2d[0] + cx, start_2d[1] + cy)
                if current.Distance(p_start) > 1e-6:
                    # Auto-connect with implicit line
                    bridge = BRepBuilderAPI_MakeEdge(current, p_start).Edge()
                    builder.Add(bridge)
                    current = p_start
                p_through = _to_3d(self._plane, through_2d[0] + cx, through_2d[1] + cy)
                p_end = _to_3d(self._plane, end_2d[0] + cx, end_2d[1] + cy)
                if current.Distance(p_end) < 1e-6:
                    continue  # skip zero-length arc
                # Check collinearity: if points are nearly collinear, fall back to line
                v1 = gp_Vec(current, p_through)
                v2 = gp_Vec(current, p_end)
                cross_mag = v1.Crossed(v2).Magnitude()
                if cross_mag < 1e-6:
                    edge = BRepBuilderAPI_MakeEdge(current, p_end).Edge()
                    prev_tangent = gp_Vec(current, p_end)
                    prev_tangent.Normalize()
                else:
                    arc_curve = GC_MakeArcOfCircle(current, p_through, p_end).Value()
                    edge = BRepBuilderAPI_MakeEdge(arc_curve).Edge()
                    prev_tangent = _edge_end_tangent(edge)
                builder.Add(edge)
                current = p_end
            elif kind == "carc_center":
                start_2d, end_2d, center_2d = seg[1], seg[2], seg[3]
                p_start = _to_3d(self._plane, start_2d[0] + cx, start_2d[1] + cy)
                if current.Distance(p_start) > 1e-6:
                    # Auto-connect with implicit line
                    bridge = BRepBuilderAPI_MakeEdge(current, p_start).Edge()
                    builder.Add(bridge)
                    current = p_start
                p_end = _to_3d(self._plane, end_2d[0] + cx, end_2d[1] + cy)
                p_center = _to_3d(self._plane, center_2d[0] + cx, center_2d[1] + cy)
                if current.Distance(p_end) < 1e-6:
                    continue
                edge = _make_center_arc_edge(current, p_end, p_center, self._plane)
                builder.Add(edge)
                prev_tangent = _edge_end_tangent(edge)
                current = p_end
            elif kind == "carc_radius":
                start_2d, end_2d, radius = seg[1], seg[2], seg[3]
                p_start = _to_3d(self._plane, start_2d[0] + cx, start_2d[1] + cy)
                if current.Distance(p_start) > 1e-6:
                    # Auto-connect with implicit line
                    bridge = BRepBuilderAPI_MakeEdge(current, p_start).Edge()
                    builder.Add(bridge)
                    current = p_start
                p_end = _to_3d(self._plane, end_2d[0] + cx, end_2d[1] + cy)
                if current.Distance(p_end) < 1e-6:
                    continue
                edge = _make_radius_arc_edge(current, p_end, float(radius), self._plane)
                builder.Add(edge)
                prev_tangent = _edge_end_tangent(edge)
                current = p_end
            elif kind == "bezier":
                pts_2d = seg[1]
                all_pts = [current]
                for p in pts_2d:
                    if len(p) == 2:
                        all_pts.append(_to_3d(self._plane, p[0] + cx, p[1] + cy))
                    else:
                        all_pts.append(gp_Pnt(p[0], p[1], p[2]))
                arr = TColgp_Array1OfPnt(1, len(all_pts))
                for i, p in enumerate(all_pts):
                    arr.SetValue(i + 1, p)
                bspline = GeomAPI_PointsToBSpline(arr).Curve()
                edge = BRepBuilderAPI_MakeEdge(bspline).Edge()
                builder.Add(edge)
                prev_tangent = _edge_end_tangent(edge)
                current = all_pts[-1]

        # Auto-close: add closing edge from last point back to start
        # (skip if already at start point)
        start_3d = _to_3d(self._plane, start[0] + cx, start[1] + cy)
        dist = current.Distance(start_3d)
        if dist > 1e-6:
            closing_edge = BRepBuilderAPI_MakeEdge(current, start_3d).Edge()
            builder.Add(closing_edge)

        wire = builder.Wire()
        new_wires = list(self._wires)
        new_wires.append(wire)
        return self._copy(_wires=new_wires)

    # --- Path Literal (open wire) ---

    def wire(self, start, *segments):
        """Build a wire from line/arc/bezier/spline segments.

        Like :meth:`sketch` but does **not** auto-close (resulting wire
        may be open or closed depending on segment data). Supports both
        2D ``(x, y)`` and 3D ``(x, y, z)`` coordinates.

        *start* is a 2D or 3D tuple — the starting point. ``None`` is
        allowed when the first segment carries its own start (e.g. arc,
        line with explicit start/end).

        Segment descriptors:
          - ``("line", (x, y))``             — line to point (2D/3D)
          - ``("line_se", (sx, sy), (ex, ey))`` — line from start to end
          - ``("arc", (s), (t), (e))``       — 3-point arc
          - ``("carc_center", (s), (e), (c))`` — center arc
          - ``("carc_radius", (s), (e), r)`` — radius arc
          - ``("bezier", [(p1), (p2), ...])`` — bezier through points
          - ``("spline", [(p1), (p2), ...])`` — B-spline through points

        If a segment's start does not match the current position
        (tolerance 1e-6), an implicit line is inserted to bridge the gap.
        """
        cx, cy = self._center_x, self._center_y

        def _resolve_pt(pt):
            """Convert a 2D or 3D tuple to gp_Pnt."""
            if len(pt) >= 3:
                return gp_Pnt(float(pt[0]), float(pt[1]), float(pt[2]))
            return _to_3d(self._plane, float(pt[0]) + cx, float(pt[1]) + cy)

        if start is not None:
            current = _resolve_pt(start)
        else:
            current = None

        builder = BRepBuilderAPI_MakeWire()

        for seg in segments:
            kind = seg[0]
            if kind == "line":
                pt = seg[1]
                end_3d = _resolve_pt(pt)
                if current is not None and current.Distance(end_3d) < 1e-6:
                    continue  # skip zero-length edge
                if current is None:
                    current = end_3d
                    continue
                edge = BRepBuilderAPI_MakeEdge(current, end_3d).Edge()
                builder.Add(edge)
                current = end_3d
            elif kind == "line_se":
                p_start = _resolve_pt(seg[1])
                p_end = _resolve_pt(seg[2])
                if current is not None and current.Distance(p_start) > 1e-6:
                    # Auto-connect with implicit line
                    bridge = BRepBuilderAPI_MakeEdge(current, p_start).Edge()
                    builder.Add(bridge)
                if current is None:
                    current = p_start
                if p_start.Distance(p_end) < 1e-6:
                    continue
                edge = BRepBuilderAPI_MakeEdge(p_start, p_end).Edge()
                builder.Add(edge)
                current = p_end
            elif kind == "arc":
                start_pt, through_pt, end_pt = seg[1], seg[2], seg[3]
                p_start = _resolve_pt(start_pt)
                if current is not None and current.Distance(p_start) > 1e-6:
                    # Auto-connect with implicit line
                    bridge = BRepBuilderAPI_MakeEdge(current, p_start).Edge()
                    builder.Add(bridge)
                if current is None:
                    current = p_start
                p_through = _resolve_pt(through_pt)
                p_end = _resolve_pt(end_pt)
                if p_start.Distance(p_end) < 1e-6:
                    continue
                v1 = gp_Vec(p_start, p_through)
                v2 = gp_Vec(p_start, p_end)
                cross_mag = v1.Crossed(v2).Magnitude()
                if cross_mag < 1e-6:
                    edge = BRepBuilderAPI_MakeEdge(p_start, p_end).Edge()
                else:
                    arc_curve = GC_MakeArcOfCircle(p_start, p_through, p_end).Value()
                    edge = BRepBuilderAPI_MakeEdge(arc_curve).Edge()
                builder.Add(edge)
                current = p_end
            elif kind == "carc_center":
                start_pt, end_pt, center_pt = seg[1], seg[2], seg[3]
                p_start = _resolve_pt(start_pt)
                if current is not None and current.Distance(p_start) > 1e-6:
                    # Auto-connect with implicit line
                    bridge = BRepBuilderAPI_MakeEdge(current, p_start).Edge()
                    builder.Add(bridge)
                if current is None:
                    current = p_start
                p_end = _resolve_pt(end_pt)
                p_center = _resolve_pt(center_pt)
                if p_start.Distance(p_end) < 1e-6:
                    continue
                edge = _make_center_arc_edge(p_start, p_end, p_center, self._plane)
                builder.Add(edge)
                current = p_end
            elif kind == "carc_radius":
                start_pt, end_pt, radius = seg[1], seg[2], seg[3]
                p_start = _resolve_pt(start_pt)
                if current is not None and current.Distance(p_start) > 1e-6:
                    # Auto-connect with implicit line
                    bridge = BRepBuilderAPI_MakeEdge(current, p_start).Edge()
                    builder.Add(bridge)
                if current is None:
                    current = p_start
                p_end = _resolve_pt(end_pt)
                if p_start.Distance(p_end) < 1e-6:
                    continue
                edge = _make_radius_arc_edge(p_start, p_end, float(radius), self._plane)
                builder.Add(edge)
                current = p_end
            elif kind == "bezier":
                pts_raw = seg[1]
                all_pts = []
                if current is not None:
                    all_pts.append(current)
                for p in pts_raw:
                    all_pts.append(_resolve_pt(p))
                if len(all_pts) < 2:
                    continue
                arr = TColgp_Array1OfPnt(1, len(all_pts))
                for i, p in enumerate(all_pts):
                    arr.SetValue(i + 1, p)
                bspline = GeomAPI_PointsToBSpline(arr).Curve()
                edge = BRepBuilderAPI_MakeEdge(bspline).Edge()
                builder.Add(edge)
                current = all_pts[-1]
            elif kind == "spline":
                pts_raw = seg[1]
                all_pts = []
                if current is not None:
                    all_pts.append(current)
                for p in pts_raw:
                    all_pts.append(_resolve_pt(p))
                if len(all_pts) < 2:
                    continue
                arr = TColgp_Array1OfPnt(1, len(all_pts))
                for i, p in enumerate(all_pts):
                    arr.SetValue(i + 1, p)
                bspline = GeomAPI_PointsToBSpline(arr).Curve()
                edge = BRepBuilderAPI_MakeEdge(bspline).Edge()
                builder.Add(edge)
                current = all_pts[-1]

        # No auto-close — open wire
        wire = builder.Wire()
        new_wires = list(self._wires)
        new_wires.append(wire)
        return self._copy(_wires=new_wires)

    # --- 2D cursor ---

    def moveTo(self, x, y):
        return self._copy(_sketch_points=[(x, y)], _center_x=x, _center_y=y)

    def lineTo(self, x, y):
        pts = list(self._sketch_points)
        pts.append((x, y))
        return self._copy(_sketch_points=pts)

    def center(self, x, y):
        return self._copy(_center_x=self._center_x + x, _center_y=self._center_y + y)

    def threePointArc(self, through, end):
        """Arc through three points (start is from sketch_points).

        *through* and *end* are 2D tuples ``(x, y)`` in workplane coordinates.
        The start point comes from the last entry of ``_sketch_points``; if
        there are no sketch points yet the workplane origin ``(0, 0)`` is used.
        """
        # Determine the start point in 2D workplane coords
        if self._sketch_points:
            sx, sy = self._sketch_points[-1]
        else:
            sx, sy = 0.0, 0.0

        # Apply center offsets
        cx, cy = self._center_x, self._center_y

        # Convert 2D -> 3D on the current workplane
        p_start = _to_3d(self._plane, sx + cx, sy + cy)
        p_through = _to_3d(self._plane, through[0] + cx, through[1] + cy)
        p_end = _to_3d(self._plane, end[0] + cx, end[1] + cy)

        # Build the arc curve and edge
        arc_curve = GC_MakeArcOfCircle(p_start, p_through, p_end).Value()
        arc_edge = BRepBuilderAPI_MakeEdge(arc_curve).Edge()

        # Append the arc edge to the last wire if one exists, else create new
        new_wires = list(self._wires)
        if new_wires:
            # Rebuild the last wire with the new arc edge appended
            last_wire = new_wires[-1]
            builder = BRepBuilderAPI_MakeWire()
            exp = TopExp_Explorer(last_wire, TopAbs_EDGE)
            while exp.More():
                builder.Add(TopoDS.Edge_s(exp.Current()))
                exp.Next()
            builder.Add(arc_edge)
            new_wires[-1] = builder.Wire()
        else:
            builder = BRepBuilderAPI_MakeWire()
            builder.Add(arc_edge)
            new_wires.append(builder.Wire())

        # Update sketch points so subsequent operations know the cursor pos
        new_pts = list(self._sketch_points)
        new_pts.append((end[0], end[1]))
        return self._copy(_wires=new_wires, _sketch_points=new_pts)

    def centerArc(self, end, center):
        """Center arc from current cursor to *end* with given *center*.

        *end* and *center* are 2D tuples ``(x, y)`` in workplane coordinates.
        """
        sx, sy = (self._sketch_points[-1] if self._sketch_points else (0.0, 0.0))
        cx, cy = self._center_x, self._center_y
        p_start = _to_3d(self._plane, sx + cx, sy + cy)
        p_end = _to_3d(self._plane, end[0] + cx, end[1] + cy)
        p_center = _to_3d(self._plane, center[0] + cx, center[1] + cy)
        arc_edge = _make_center_arc_edge(p_start, p_end, p_center, self._plane)
        return self._append_arc_edge(arc_edge, end)

    def radiusArc(self, end, radius):
        """Radius arc from current cursor to *end* with given *radius*."""
        sx, sy = (self._sketch_points[-1] if self._sketch_points else (0.0, 0.0))
        cx, cy = self._center_x, self._center_y
        p_start = _to_3d(self._plane, sx + cx, sy + cy)
        p_end = _to_3d(self._plane, end[0] + cx, end[1] + cy)
        arc_edge = _make_radius_arc_edge(p_start, p_end, float(radius), self._plane)
        return self._append_arc_edge(arc_edge, end)

    def tangentArc(self, end, tangent_vec=None):
        """Tangent arc from current cursor to *end*.

        If *tangent_vec* is given (2D tuple), it is used as the tangent direction
        at the start. Otherwise the tangent from the last edge of the current wire
        is used.
        """
        sx, sy = (self._sketch_points[-1] if self._sketch_points else (0.0, 0.0))
        cx, cy = self._center_x, self._center_y
        p_start = _to_3d(self._plane, sx + cx, sy + cy)
        p_end = _to_3d(self._plane, end[0] + cx, end[1] + cy)

        if tangent_vec is not None:
            t_vec = _tangent_2d_to_3d(self._plane, tangent_vec[0], tangent_vec[1])
        else:
            # Extract tangent from last edge of current wire
            if not self._wires:
                raise ValueError("tangentArc: no previous wire to derive tangent from")
            last_wire = self._wires[-1]
            last_edge = _last_edge_of_wire(last_wire)
            t_vec = _edge_end_tangent(last_edge)

        arc_curve = GC_MakeArcOfCircle(p_start, t_vec, p_end).Value()
        arc_edge = BRepBuilderAPI_MakeEdge(arc_curve).Edge()
        return self._append_arc_edge(arc_edge, end)

    def _append_arc_edge(self, arc_edge, end):
        """Append an arc edge to the current wire and update cursor."""
        new_wires = list(self._wires)
        if new_wires:
            last_wire = new_wires[-1]
            builder = BRepBuilderAPI_MakeWire()
            exp = TopExp_Explorer(last_wire, TopAbs_EDGE)
            while exp.More():
                builder.Add(TopoDS.Edge_s(exp.Current()))
                exp.Next()
            builder.Add(arc_edge)
            new_wires[-1] = builder.Wire()
        else:
            builder = BRepBuilderAPI_MakeWire()
            builder.Add(arc_edge)
            new_wires.append(builder.Wire())
        new_pts = list(self._sketch_points)
        new_pts.append((end[0], end[1]))
        return self._copy(_wires=new_wires, _sketch_points=new_pts)

    # --- Offsets helper ---

    def _get_offsets(self) -> list[tuple[float, float]]:
        """Return list of (cx, cy) for current operations."""
        if self._points:
            return [(px + self._center_x, py + self._center_y) for px, py in self._points]
        return [(self._center_x, self._center_y)]

    # --- Selection ---

    def faces(self, sel: str | None = None, tag: str | None = None):
        if tag and tag in self._tags:
            # Restore tagged shape and return with it
            return self._copy(_shape=self._tags[tag], _selected_faces=[], _selected_edges=[])
        if self._shape is None:
            return self
        all_faces = _get_faces(self._shape)
        if sel:
            selected = _select_items(all_faces, sel, _face_center, lambda f: _face_normal(f))
        else:
            selected = all_faces
        return self._copy(_selected_faces=selected, _selected_edges=[])

    def edges(self, sel: str | None = None, tag: str | None = None):
        if tag and tag in self._tags:
            return self._copy(_shape=self._tags[tag], _selected_faces=[], _selected_edges=[])
        if self._shape is None:
            return self
        all_edges = _get_edges(self._shape)
        if sel:
            selected = _select_items(all_edges, sel, _edge_center, _edge_direction)
        else:
            selected = all_edges
        return self._copy(_selected_edges=selected, _selected_faces=[])

    def vertices(self, sel: str | None = None, tag: str | None = None):
        if tag and tag in self._tags:
            return self._copy(_shape=self._tags[tag])
        # 2D context: extract vertices from pending wires (e.g. rect on a face)
        # This applies whether or not a 3D shape exists — if wires are present,
        # the user wants vertices of those wires, not of the 3D solid.
        if self._wires:
            all_verts = []
            for wire in self._wires:
                all_verts.extend(_get_vertices(wire))
            if sel:
                selected = _select_items(all_verts, sel, _vertex_point)
            else:
                selected = all_verts
            # Convert vertices to pushPoints for subsequent 2D operations
            pts = []
            for v in selected:
                p = _vertex_point(v)
                # Project onto the current workplane
                o = _plane_origin(self._plane)
                xd = _plane_xdir(self._plane)
                yd = _plane_draw_ydir(self._plane)
                dx = p.X() - o.X()
                dy = p.Y() - o.Y()
                dz = p.Z() - o.Z()
                u = dx * xd.X() + dy * xd.Y() + dz * xd.Z()
                v_coord = dx * yd.X() + dy * yd.Y() + dz * yd.Z()
                pts.append((u, v_coord))
            return self._copy(_selected_vertices=selected, _wires=[], _points=pts)
        if self._shape is None:
            return self
        all_verts = _get_vertices(self._shape)
        if sel:
            selected = _select_items(all_verts, sel, _vertex_point)
        else:
            selected = all_verts
        return self._copy(_selected_vertices=selected)

    # --- Workplane ---

    def workplane(self, plane=None, origin=None):
        if self._selected_faces:
            face = self._selected_faces[0]
            center = _face_center(face)
            normal = _face_normal(face)
            # Compute a reasonable X direction
            if abs(normal.Z()) > 0.9:
                xdir = gp_Dir(1, 0, 0)
            else:
                cross = gp_Dir(0, 0, 1).Crossed(normal)
                mag2 = cross.X()**2 + cross.Y()**2 + cross.Z()**2
                xdir = gp_Dir(cross.X(), cross.Y(), cross.Z()) if mag2 > 1e-12 else gp_Dir(1, 0, 0)
            new_plane = gp_Pln(gp_Ax3(center, normal, xdir))
            if origin is not None:
                if len(origin) == 2:
                    # 2D: interpret as world coordinates along the plane's local axes.
                    # Map (x, y) to the 3D world point x*xDir + y*yDir (missing axis = 0).
                    xd = _plane_xdir(new_plane)
                    yd = _plane_ydir(new_plane)
                    wx = origin[0] * xd.X() + origin[1] * yd.X()
                    wy = origin[0] * xd.Y() + origin[1] * yd.Y()
                    wz = origin[0] * xd.Z() + origin[1] * yd.Z()
                    u, v = _project_to_2d(new_plane, wx, wy, wz)
                else:
                    u, v = _project_to_2d(new_plane, origin[0], origin[1], origin[2])
                new_origin = _to_3d(new_plane, u, v)
                new_plane = gp_Pln(gp_Ax3(new_origin, normal, xdir))
            return self._copy(
                _plane=new_plane, _wires=[], _selected_faces=[], _selected_edges=[],
                _center_x=0, _center_y=0, _points=None,
            )
        if plane:
            new_plane = _make_plane(plane)
            return self._copy(
                _plane=new_plane, _wires=[], _center_x=0, _center_y=0, _points=None,
            )
        return self._copy(_wires=[], _center_x=0, _center_y=0, _points=None)

    # --- Place ---

    def place(self, profile):
        """Place a 2D profile (wires) onto the current workplane.

        Takes wires from the given profile (a Workplane with 2D wires)
        and adds them to the current state, similar to how Implicit2DPrimitive
        works but with an externally provided shape.
        """
        if not isinstance(profile, Workplane):
            warnings.warn("place: argument is not a Workplane")
            return self
        new_wires = list(self._wires)
        for wire in profile._wires:
            new_wires.append(wire)
        return self._copy(_wires=new_wires)

    # --- Points ---

    def pushPoints(self, pts):
        return self._copy(_points=[(p[0], p[1]) for p in pts])

    def rarray(self, xspacing, yspacing, nx, ny):
        pts = []
        for ix in range(int(nx)):
            for iy in range(int(ny)):
                x = (ix - (nx - 1) / 2) * xspacing
                y = (iy - (ny - 1) / 2) * yspacing
                pts.append((x, y))
        return self._copy(_points=pts)

    # --- Tags ---

    def tag(self, name: str):
        tags = dict(self._tags)
        tags[name] = self._shape
        return self._copy(_tags=tags)

    # --- Modifiers ---

    def fillet(self, r):
        if self._shape is None:
            return self
        edges = self._selected_edges
        if not edges and self._selected_faces:
            seen = set()
            edges = []
            for face in self._selected_faces:
                for edge in _get_edges(face):
                    h = edge.__hash__()
                    if h not in seen:
                        seen.add(h)
                        edges.append(edge)
        if not edges:
            edges = _get_edges(self._shape)
        # Try all at once
        try:
            mk = BRepFilletAPI_MakeFillet(self._shape)
            for edge in edges:
                mk.Add(float(r), edge)
            shape = mk.Shape()
            return self._copy(_shape=shape, _selected_faces=[], _selected_edges=[])
        except Exception:
            pass
        # Fallback: apply one edge at a time
        shape = self._shape
        for edge in edges:
            try:
                mk = BRepFilletAPI_MakeFillet(shape)
                mk.Add(float(r), edge)
                shape = mk.Shape()
            except Exception:
                pass
        if shape is not self._shape:
            return self._copy(_shape=shape, _selected_faces=[], _selected_edges=[])
        warnings.warn(f"fillet({r}) failed on all edges")
        return self

    def chamfer(self, r):
        if self._shape is None:
            return self
        edges = self._selected_edges
        if not edges and self._selected_faces:
            seen = set()
            edges = []
            for face in self._selected_faces:
                for edge in _get_edges(face):
                    h = edge.__hash__()
                    if h not in seen:
                        seen.add(h)
                        edges.append(edge)
        if not edges:
            edges = _get_edges(self._shape)
        # Try all at once
        try:
            mk = BRepFilletAPI_MakeChamfer(self._shape)
            for edge in edges:
                mk.Add(float(r), edge)
            shape = mk.Shape()
            return self._copy(_shape=shape, _selected_faces=[], _selected_edges=[])
        except Exception:
            pass
        # Fallback: apply one edge at a time
        shape = self._shape
        for edge in edges:
            try:
                mk = BRepFilletAPI_MakeChamfer(shape)
                mk.Add(float(r), edge)
                shape = mk.Shape()
            except Exception:
                pass
        if shape is not self._shape:
            return self._copy(_shape=shape, _selected_faces=[], _selected_edges=[])
        warnings.warn(f"chamfer({r}) failed on all edges")
        return self

    def shell(self, thickness):
        if self._shape is None:
            return self
        faces_to_remove = TopTools_ListOfShape()
        if self._selected_faces:
            for f in self._selected_faces:
                faces_to_remove.Append(f)
        mk = BRepOffsetAPI_MakeThickSolid()
        mk.MakeThickSolidByJoin(self._shape, faces_to_remove, float(-thickness), 1e-3)
        shape = mk.Shape()
        return self._copy(_shape=shape, _selected_faces=[], _selected_edges=[])

    _JOIN_TYPE_MAP = {
        "arc": GeomAbs_Arc,
        "miter": GeomAbs_Intersection,
        "tangent": GeomAbs_Tangent,
    }

    def offset(self, distance, join_type=None, cap=None):
        """2D wire offset.

        Works in two contexts:
        1. Face selection -- extracts the outer wire of the first selected face,
           creates a workplane on that face, then offsets the wire.
        2. 2D context -- offsets existing wires on the current workplane.

        Positive distance = outward, negative = inward.
        join_type: "arc" (default, round), "miter" (square), "tangent".
        cap: "round" (default), "square" (perpendicular end caps for open wires).
        """
        distance = float(distance)
        jt = self._JOIN_TYPE_MAP.get(join_type, GeomAbs_Arc) if join_type else GeomAbs_Arc

        def _do_offset(wire):
            mk = BRepOffsetAPI_MakeOffset()
            mk.Init(jt)
            mk.AddWire(wire)
            mk.Perform(distance)
            offset_wire = TopoDS.Wire_s(mk.Shape())
            if cap == "square" and not wire.Closed():
                return self._trim_round_caps(wire, offset_wire, distance)
            return offset_wire

        # Face selection context: extract outer wire, create workplane, offset
        if self._selected_faces:
            face = self._selected_faces[0]
            outer_wire = BRepTools.OuterWire_s(face)
            wp_state = self.workplane()
            offset_wire = _do_offset(outer_wire)
            return wp_state._copy(_wires=[offset_wire])

        # 2D context: offset existing wires
        if not self._wires:
            warnings.warn("offset: no wires or selected faces in context")
            return self

        new_wires = [_do_offset(wire) for wire in self._wires]
        return self._copy(_wires=new_wires)

    @staticmethod
    def _trim_round_caps(wire, offset_wire, distance):
        """Trim round caps from offset wire using boolean cut, returning square-capped wire."""
        import math
        # Extract ordered vertices from wire
        explorer = BRepTools_WireExplorer(wire)
        points = []
        while explorer.More():
            v = explorer.CurrentVertex()
            p = BRep_Tool.Pnt_s(v)
            points.append((p.X(), p.Y(), p.Z()))
            explorer.Next()
        # Add the last vertex
        v = explorer.CurrentVertex()
        p = BRep_Tool.Pnt_s(v)
        last = (p.X(), p.Y(), p.Z())
        if not points or abs(last[0] - points[-1][0]) > 1e-8 or abs(last[1] - points[-1][1]) > 1e-8:
            points.append(last)

        n = len(points)
        d = abs(distance)
        z = points[0][2]
        big = d * 4

        # Start tangent (inward)
        sdx = points[1][0] - points[0][0]
        sdy = points[1][1] - points[0][1]
        slen = math.sqrt(sdx * sdx + sdy * sdy)
        stx, sty = sdx / slen, sdy / slen

        # End tangent (inward)
        edx = points[n - 1][0] - points[n - 2][0]
        edy = points[n - 1][1] - points[n - 2][1]
        elen = math.sqrt(edx * edx + edy * edy)
        etx, ety = edx / elen, edy / elen

        def _make_rect_face(cx, cy, tx, ty):
            """Make a rectangular face covering the cap area outside the endpoint."""
            pts = [
                gp_Pnt(cx - tx * big - ty * big, cy - ty * big + tx * big, z),
                gp_Pnt(cx - tx * big + ty * big, cy - ty * big - tx * big, z),
                gp_Pnt(cx            + ty * big, cy            - tx * big, z),
                gp_Pnt(cx            - ty * big, cy            + tx * big, z),
            ]
            edges = []
            for i in range(4):
                edges.append(BRepBuilderAPI_MakeEdge(pts[i], pts[(i + 1) % 4]).Edge())
            builder = BRepBuilderAPI_MakeWire()
            for e in edges:
                builder.Add(e)
            return BRepBuilderAPI_MakeFace(builder.Wire()).Face()

        face = BRepBuilderAPI_MakeFace(offset_wire).Face()
        start_cut = _make_rect_face(points[0][0], points[0][1], stx, sty)
        end_cut = _make_rect_face(points[n - 1][0], points[n - 1][1], -etx, -ety)
        face = BRepAlgoAPI_Cut(face, start_cut).Shape()
        face = BRepAlgoAPI_Cut(face, end_cut).Shape()

        # Extract outer wire from result
        exp = TopExp_Explorer(face, TopAbs_FACE)
        if exp.More():
            return BRepTools.OuterWire_s(TopoDS.Face_s(exp.Current()))
        return BRepTools.OuterWire_s(TopoDS.Face_s(face))

    # --- Boolean ---

    def cut(self, other):
        if isinstance(other, Workplane):
            other_shape = other._shape
        else:
            other_shape = other
        if self._shape is None or other_shape is None:
            return self
        shape = BRepAlgoAPI_Cut(self._shape, other_shape).Shape()
        return self._copy(_shape=shape)

    def union(self, other):
        if isinstance(other, Workplane):
            other_shape = other._shape
            other_wires = other._wires
            other_color_map = other._color_map if isinstance(other, Workplane) else {}
        else:
            other_shape = other
            other_wires = []
            other_color_map = {}
        if other_shape is None and not other_wires:
            return self
        if self._shape is None and other_shape is None:
            # Both are 2D (wires only): merge wires for later extrude/revolve
            wp = self._copy(_wires=list(self._wires) + list(other_wires))
            wp._color_map = {**self._color_map, **other_color_map}
            return wp
        if other_shape is None:
            return self
        if self._shape is None:
            wp = self._copy(_shape=other_shape)
            wp._color_map = {**self._color_map, **other_color_map}
            return wp
        shape = BRepAlgoAPI_Fuse(self._shape, other_shape).Shape()
        wp = self._copy(_shape=shape)
        wp._color_map = {**self._color_map, **other_color_map}
        return wp

    def intersect(self, other):
        if isinstance(other, Workplane):
            other_shape = other._shape
            other_color_map = other._color_map if isinstance(other, Workplane) else {}
        else:
            other_shape = other
            other_color_map = {}
        if self._shape is None or other_shape is None:
            return self
        shape = BRepAlgoAPI_Common(self._shape, other_shape).Shape()
        wp = self._copy(_shape=shape)
        wp._color_map = {**self._color_map, **other_color_map}
        return wp

    # --- 2D → 3D ---

    def extrude(self, height, taper=None):
        normal = _plane_normal(self._plane)
        direction = gp_Vec(normal.X() * height, normal.Y() * height, normal.Z() * height)
        new_shape = self._shape
        for wire in self._wires:
            face = _make_face_from_wire(wire)
            solid = BRepPrimAPI_MakePrism(face, direction).Shape()
            if new_shape is not None:
                new_shape = BRepAlgoAPI_Fuse(new_shape, solid).Shape()
            else:
                new_shape = solid
        return self._copy(_shape=new_shape, _wires=[], _selected_faces=[], _selected_edges=[])

    def revolve(self, degrees, axisStart=None, axisEnd=None):
        if not self._wires:
            return self
        wire = self._wires[-1]
        face = _make_face_from_wire(wire)
        if axisStart is not None and axisEnd is not None:
            ax = gp_Ax1(
                gp_Pnt(*axisStart),
                gp_Dir(
                    axisEnd[0] - axisStart[0],
                    axisEnd[1] - axisStart[1],
                    axisEnd[2] - axisStart[2],
                ),
            )
        else:
            # Default: revolve around Y axis at origin
            origin = _plane_origin(self._plane)
            ax = gp_Ax1(origin, gp_Dir(0, 1, 0))
        solid = BRepPrimAPI_MakeRevol(face, ax, math.radians(degrees)).Shape()
        new_shape = solid
        if self._shape is not None:
            new_shape = BRepAlgoAPI_Fuse(self._shape, solid).Shape()
        return self._copy(_shape=new_shape, _wires=[])

    def sweep(self, profile, isFrenet=False):
        """Sweep ``profile`` along this workplane's wire (the path/spine).

        The pipeline subject is the path; ``profile`` is the cross-section
        passed as argument.
        """
        if not self._wires:
            return self
        # This workplane's last wire is the PATH (spine).
        path_wire = self._wires[-1]

        # Extract the profile wire + its source workplane from the argument.
        # The profile was authored on its own workplane, not on the path's
        # workplane, so use the profile's plane as the source frame below.
        profile_plane = self._plane  # fallback: assume same as path's plane
        if isinstance(profile, TopoDS_Wire):
            wire = profile
        elif isinstance(profile, Workplane):
            profile_plane = profile._plane
            if profile._wires:
                wire = profile._wires[-1]
            elif profile._shape:
                exp = TopExp_Explorer(profile._shape, TopAbs_EDGE)
                builder = BRepBuilderAPI_MakeWire()
                while exp.More():
                    builder.Add(TopoDS.Edge_s(exp.Current()))
                    exp.Next()
                wire = builder.Wire()
            else:
                return self
        else:
            wire = profile

        # Transform the profile to the start of the path so that
        # the sweep can work correctly.  The profile is assumed to lie in
        # the workplane coordinate system (typically XY at the origin).
        # We move it so that:
        #   - its centre sits at the path start point
        #   - it is oriented perpendicular to the path tangent there
        adaptor = BRepAdaptor_CompCurve(path_wire)
        t0 = adaptor.FirstParameter()
        start_pt = adaptor.Value(t0)
        tangent_vec = adaptor.DN(t0, 1)
        tangent_dir = gp_Dir(tangent_vec)

        # Use fixed +Z binormal so the profile doesn't tilt out of the XY
        # plane on helices. Fall back to +X if tangent is nearly along Z.
        binormal = gp_Dir(0, 0, 1)
        use_binormal = abs(tangent_dir.Dot(binormal)) < 0.9

        if use_binormal:
            # X reference = radial direction (tangent × Z)
            ref = tangent_dir.Crossed(binormal)
        else:
            ref = gp_Dir(1, 0, 0)
            if abs(tangent_dir.Dot(ref)) > 0.9:
                ref = gp_Dir(0, 1, 0)

        ax2_target = gp_Ax2(start_pt, tangent_dir, ref)

        # Source coordinate system: the profile's workplane normal + origin
        origin = _plane_origin(profile_plane)
        normal = _plane_normal(profile_plane)
        xdir = _plane_xdir(profile_plane)
        ax2_source = gp_Ax2(origin, normal, xdir)

        trsf = gp_Trsf()
        trsf.SetTransformation(gp_Ax3(ax2_target), gp_Ax3(ax2_source))

        moved_wire = TopoDS.Wire_s(BRepBuilderAPI_Transform(wire, trsf, True).Shape())

        # Prefer MakePipeShell with RoundCorner transition (default Corrected
        # Frenet mode). This matches the TS implementation and gives correct
        # shapes for both straight and curved spines including closed paths
        # (torus etc.). Binormal mode is only needed when PipeShell fails.
        try:
            pipe_shell = BRepOffsetAPI_MakePipeShell(path_wire)
            pipe_shell.SetTransitionMode(BRepBuilderAPI_RoundCorner)
            pipe_shell.Add(moved_wire)
            pipe_shell.Build()
            if pipe_shell.IsDone():
                pipe_shell.MakeSolid()
                solid = pipe_shell.Shape()
            else:
                face = _make_face_from_wire(moved_wire)
                solid = BRepOffsetAPI_MakePipe(path_wire, face).Shape()
        except Exception:
            face = _make_face_from_wire(moved_wire)
            solid = BRepOffsetAPI_MakePipe(path_wire, face).Shape()
        new_shape = solid
        if self._shape is not None and not self._wires:
            new_shape = BRepAlgoAPI_Fuse(self._shape, solid).Shape()
        return self._copy(_shape=new_shape, _wires=[])

    def loft(self, section_wires_list, height=None, heights=None, ruled=False):
        """Loft through multiple cross-section wires.

        section_wires_list: list of wire-lists (one per additional section)
        height: total height (sections distributed evenly)
        heights: explicit offset for each additional section
        ruled: if True, use ruled surface
        """
        if not self._wires:
            return self
        normal = _plane_normal(self._plane)
        n = len(section_wires_list)

        # Compute offsets for each additional section
        if heights is not None:
            offsets = heights
        elif height is not None:
            offsets = [height * (i + 1) / n for i in range(n)]
        else:
            raise ValueError("loft requires either a height or heights list")

        new_shape = self._shape
        for src_wire in self._wires:
            builder = BRepOffsetAPI_ThruSections(True, ruled)
            builder.AddWire(src_wire)
            for i in range(n):
                section = section_wires_list[i]
                if isinstance(section, Workplane):
                    w = section._wires[0]
                else:
                    w = section[0]
                d = offsets[i]
                trsf = gp_Trsf()
                trsf.SetTranslation(gp_Vec(
                    normal.X() * d, normal.Y() * d, normal.Z() * d))
                moved = TopoDS.Wire_s(
                    BRepBuilderAPI_Transform(w, trsf, True).Shape())
                builder.AddWire(moved)
            builder.Build()
            solid = builder.Shape()
            if new_shape is not None:
                new_shape = BRepAlgoAPI_Fuse(new_shape, solid).Shape()
            else:
                new_shape = solid
        return self._copy(_shape=new_shape, _wires=[], _selected_faces=[], _selected_edges=[])

    # --- Cut operations ---

    def cutThruAll(self):
        if self._shape is None or not self._wires:
            return self
        bb = _BoundingBox(self._shape)
        cut_height = max(bb.xlen, bb.ylen, bb.zlen) * 4
        normal = _plane_normal(self._plane)
        new_shape = self._shape
        for wire in self._wires:
            face = _make_face_from_wire(wire)
            # Extrude in both directions
            dir_pos = gp_Vec(normal.X() * cut_height, normal.Y() * cut_height, normal.Z() * cut_height)
            dir_neg = gp_Vec(-normal.X() * cut_height, -normal.Y() * cut_height, -normal.Z() * cut_height)
            tool_pos = BRepPrimAPI_MakePrism(face, dir_pos).Shape()
            tool_neg = BRepPrimAPI_MakePrism(face, dir_neg).Shape()
            tool = BRepAlgoAPI_Fuse(tool_pos, tool_neg).Shape()
            new_shape = BRepAlgoAPI_Cut(new_shape, tool).Shape()
        return self._copy(_shape=new_shape, _wires=[], _selected_faces=[], _selected_edges=[])

    def cutBlind(self, depth):
        if self._shape is None or not self._wires:
            return self
        normal = _plane_normal(self._plane)
        direction = gp_Vec(normal.X() * depth, normal.Y() * depth, normal.Z() * depth)
        new_shape = self._shape
        for wire in self._wires:
            face = _make_face_from_wire(wire)
            tool = BRepPrimAPI_MakePrism(face, direction).Shape()
            new_shape = BRepAlgoAPI_Cut(new_shape, tool).Shape()
        return self._copy(_shape=new_shape, _wires=[], _selected_faces=[], _selected_edges=[])

    def hole(self, radius, depth=None):
        if self._shape is None:
            return self
        r = radius
        offsets = self._get_offsets()
        new_shape = self._shape

        if depth is None:
            bb = _BoundingBox(self._shape)
            cut_h = max(bb.xlen, bb.ylen, bb.zlen) * 4
        else:
            cut_h = depth

        normal = _plane_normal(self._plane)

        for cx, cy in offsets:
            center = _to_3d(self._plane, cx, cy)
            if depth is None:
                # Single centered cylinder to avoid seam edges from fusing two halves
                start = gp_Pnt(
                    center.X() - normal.X() * cut_h,
                    center.Y() - normal.Y() * cut_h,
                    center.Z() - normal.Z() * cut_h,
                )
                ax2 = gp_Ax2(start, normal)
                cyl = BRepPrimAPI_MakeCylinder(ax2, r, 2 * cut_h).Shape()
            else:
                neg_normal = gp_Dir(-normal.X(), -normal.Y(), -normal.Z())
                ax2 = gp_Ax2(center, neg_normal)
                cyl = BRepPrimAPI_MakeCylinder(ax2, r, cut_h).Shape()
            new_shape = BRepAlgoAPI_Cut(new_shape, cyl).Shape()

        return self._copy(_shape=new_shape, _wires=[], _points=None,
                         _selected_faces=[], _selected_edges=[])

    def holeOnFaces(self, radius, depth=None):
        """Cut a hole at the center of each selected face.

        Equivalent to ``faces ... | circle radius | cut`` but expressed as a
        single ``hole`` operation from FaceSelection context.
        """
        if self._shape is None or not self._selected_faces:
            return self

        new_shape = self._shape

        if depth is None:
            bb = _BoundingBox(self._shape)
            cut_h = max(bb.xlen, bb.ylen, bb.zlen) * 4
        else:
            cut_h = depth

        for face in self._selected_faces:
            center = _face_center(face)
            normal = _face_normal(face)

            if depth is None:
                # Single centered cylinder to avoid seam edges from fusing two halves
                start = gp_Pnt(
                    center.X() - normal.X() * cut_h,
                    center.Y() - normal.Y() * cut_h,
                    center.Z() - normal.Z() * cut_h,
                )
                ax2 = gp_Ax2(start, normal)
                cyl = BRepPrimAPI_MakeCylinder(ax2, radius, 2 * cut_h).Shape()
            else:
                neg_normal = gp_Dir(-normal.X(), -normal.Y(), -normal.Z())
                ax2 = gp_Ax2(center, neg_normal)
                cyl = BRepPrimAPI_MakeCylinder(ax2, radius, cut_h).Shape()
            new_shape = BRepAlgoAPI_Cut(new_shape, cyl).Shape()

        return self._copy(_shape=new_shape, _wires=[], _points=None,
                         _selected_faces=[], _selected_edges=[])

    # --- Transform ---

    @property
    def color_map(self) -> dict[int, tuple]:
        """Return the per-part color map: {id(shape): (shape, r, g, b, a)}."""
        return dict(self._color_map)

    def setColor(self, r, g, b, a=1.0):
        """Attach color metadata (RGBA, 0..1) to this workplane."""
        wp = self._copy()
        wp._color = (float(r), float(g), float(b), float(a))
        if wp._shape is not None:
            wp._color_map[id(wp._shape)] = (wp._shape, float(r), float(g), float(b), float(a))
        return wp

    def translate(self, vec):
        if isinstance(vec, (tuple, list)):
            v = gp_Vec(float(vec[0]), float(vec[1]), float(vec[2]) if len(vec) > 2 else 0)
        else:
            v = vec
        shape = _translate_shape(self._shape, v) if self._shape is not None else None
        wires = [TopoDS.Wire_s(_translate_shape(w, v)) for w in self._wires] if self._wires else []
        return self._copy(_shape=shape, _wires=wires)

    def translate_points(self, vec):
        """Translate selected points/vertices by a 3D vector.

        Used in VertexSelection/PointSelection context to offset all point
        positions while preserving the selection context.  The workplane
        origin is shifted so that the full 3D translation (including the
        component perpendicular to the plane) is applied when points are
        later converted back to 3D via ``_to_3d``.
        """
        if isinstance(vec, (tuple, list)):
            v = gp_Vec(float(vec[0]), float(vec[1]), float(vec[2]) if len(vec) > 2 else 0)
        else:
            v = vec
        # Shift the workplane origin by the 3D vector so that _to_3d
        # produces correctly translated 3D positions.
        old_origin = _plane_origin(self._plane)
        new_origin = gp_Pnt(old_origin.X() + v.X(),
                            old_origin.Y() + v.Y(),
                            old_origin.Z() + v.Z())
        ax3 = self._plane.Position()
        new_ax3 = gp_Ax3(new_origin, ax3.Direction(), ax3.XDirection())
        new_plane = gp_Pln(new_ax3)
        # Translate selected vertices in 3D
        new_verts = []
        for vert in self._selected_vertices:
            new_verts.append(TopoDS.Vertex_s(_translate_shape(vert, v)))
        # Translate the base shape too
        shape = _translate_shape(self._shape, v) if self._shape is not None else None
        return self._copy(_shape=shape, _plane=new_plane,
                          _selected_vertices=new_verts)

    def _array_placement(self, points):
        """Replicate wires or shape at the given 2D points.

        When wires exist (2D context, e.g. after faces|rect), replicates wires.
        Otherwise replicates the 3D shape as a compound.
        """
        if not points:
            return self
        # 2D wires first (face-selection context carries base shape AND active wires)
        if self._wires:
            new_wires = []
            for wire in self._wires:
                for x, y in points:
                    if x != 0 or y != 0:
                        v = gp_Vec(float(x), float(y), 0)
                        new_wires.append(TopoDS.Wire_s(_translate_shape(wire, v)))
                    else:
                        new_wires.append(wire)
            return self._copy(_wires=new_wires)
        # 3D shape: translate copies and combine as compound
        if self._shape is not None:
            builder = TopoDS_Builder()
            compound = TopoDS_Compound()
            builder.MakeCompound(compound)
            for x, y in points:
                v = gp_Vec(float(x), float(y), 0)
                copy = _translate_shape(self._shape, v)
                builder.Add(compound, copy)
            return self._copy(_shape=compound)
        return self

    def grid(self, nx, ny, spacing):
        """Replicate in a rectangular grid pattern."""
        nx, ny, sp = int(nx), int(ny), float(spacing)
        off_x = (nx - 1) * sp / 2
        off_y = (ny - 1) * sp / 2
        points = []
        for iy in range(ny):
            for ix in range(nx):
                points.append((ix * sp - off_x, iy * sp - off_y))
        return self._array_placement(points)

    def polar(self, count, radius, orient=False):
        """Replicate in a circular pattern."""
        count, radius = int(count), float(radius)
        if orient:
            return self._polar_rotate(count, radius)
        points = []
        for i in range(count):
            angle = 2 * math.pi * i / count
            points.append((radius * math.cos(angle), radius * math.sin(angle)))
        return self._array_placement(points)

    def _polar_rotate(self, count, radius):
        """Polar replicate with rotation: rotate each copy by i*360/count around Z."""
        if self._wires:
            new_wires = []
            for wire in self._wires:
                for i in range(count):
                    angle_deg = 360.0 * i / count
                    angle_rad = math.radians(angle_deg)
                    x = radius * math.cos(angle_rad)
                    y = radius * math.sin(angle_rad)
                    w = wire
                    if angle_deg != 0:
                        w = TopoDS.Wire_s(_rotate_shape(w, (0, 0, 0), (0, 0, 1), angle_deg))
                    if x != 0 or y != 0:
                        w = TopoDS.Wire_s(_translate_shape(w, gp_Vec(float(x), float(y), 0)))
                    new_wires.append(w)
            return self._copy(_wires=new_wires)
        if self._shape is not None:
            builder = TopoDS_Builder()
            compound = TopoDS_Compound()
            builder.MakeCompound(compound)
            for i in range(count):
                angle_deg = 360.0 * i / count
                angle_rad = math.radians(angle_deg)
                x = radius * math.cos(angle_rad)
                y = radius * math.sin(angle_rad)
                copy = self._shape
                if angle_deg != 0:
                    copy = _rotate_shape(copy, (0, 0, 0), (0, 0, 1), angle_deg)
                if x != 0 or y != 0:
                    copy = _translate_shape(copy, gp_Vec(float(x), float(y), 0))
                builder.Add(compound, copy)
            return self._copy(_shape=compound)
        return self

    def rotate(self, center, axis, angle):
        if self._shape is None and not self._wires:
            return self
        shape = _rotate_shape(self._shape, center, axis, float(angle)) if self._shape is not None else None
        wires = [TopoDS.Wire_s(_rotate_shape(w, center, axis, float(angle))) for w in self._wires] if self._wires else []
        return self._copy(_shape=shape, _wires=wires)

    def scale(self, sx, sy=None, sz=None, center=(0, 0, 0)):
        if self._shape is None:
            return self
        sx = float(sx)
        if sy is None:
            sy = sx
        if sz is None:
            sz = sx
        sy = float(sy)
        sz = float(sz)
        if isinstance(center, (tuple, list)):
            center = tuple(float(c) for c in center)
        shape = _scale_shape(self._shape, sx, sy, sz, center)
        return self._copy(_shape=shape)

    def mirror(self, plane_name="YZ"):
        """Mirror the shape across a plane and fuse with the original.

        plane_name: "YZ" (mirror across YZ, i.e. flip X),
                    "XZ" (flip Y), "XY" (flip Z).
        """
        if self._shape is None:
            return self
        trsf = gp_Trsf()
        pn = plane_name.upper()
        if pn == "YZ":
            trsf.SetMirror(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 0)))
        elif pn == "XZ":
            trsf.SetMirror(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 1, 0)))
        elif pn == "XY":
            trsf.SetMirror(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)))
        else:
            trsf.SetMirror(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 0)))
        mirrored = BRepBuilderAPI_Transform(self._shape, trsf, True).Shape()
        fused = BRepAlgoAPI_Fuse(self._shape, mirrored).Shape()
        return self._copy(_shape=fused)

    # --- Introspection ---

    def val(self):
        return _ValWrapper(self._shape)

    # --- Line path support (for sweep groove) ---
