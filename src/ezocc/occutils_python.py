from __future__ import annotations

import logging
import math
import re
import typing
from enum import Enum
from enum import unique

import OCC
import OCC.Core as oc
import OCC.Core.BRep
import OCC.Core.BRepAdaptor
import OCC.Core.BRepAlgoAPI
import OCC.Core.BRepBndLib
import OCC.Core.BRepBuilderAPI
import OCC.Core.BRepFilletAPI
import OCC.Core.BRepGProp
import OCC.Core.BRepLib
import OCC.Core.BRepMesh
import OCC.Core.BRepOffsetAPI
import OCC.Core.BRepPrimAPI
import OCC.Core.BRepTools
import OCC.Core.BRepTools
import OCC.Core.Bnd
import OCC.Core.GC
import OCC.Core.GCE2d
import OCC.Core.GProp
import OCC.Core.Geom
import OCC.Core.Geom
import OCC.Core.Geom2d
import OCC.Core.GeomAPI
import OCC.Core.GeomAbs
import OCC.Core.GeomLProp
import OCC.Core.Precision
import OCC.Core.STEPControl
import OCC.Core.ShapeAnalysis
import OCC.Core.ShapeFix
import OCC.Core.ShapeUpgrade
import OCC.Core.StdFail
import OCC.Core.StlAPI
import OCC.Core.TColgp
import OCC.Core.TopAbs
import OCC.Core.TopExp
import OCC.Core.TopTools
import OCC.Core.TopTools
import OCC.Core.TopoDS
import OCC.Core.gp
from OCC.Core.NCollection import NCollection_List
from OCC.Core.TopTools import TopTools_ListIteratorOfListOfShape
from OCC.Core.gp import gp_Dir
from OCC.Core.gp import gp_Dir as dir
from OCC.Core.gp import gp_Pnt
from OCC.Core.gp import gp_Pnt as pnt
from OCC.Core.gp import gp_Vec
from OCC.Core.gp import gp_Vec as vec
from OCC.Core.gp import gp_XYZ

from util_wrapper_swig import UtilWrapper

from ezocc.data_structures.deferred_value import DeferredValue
from ezocc.data_structures.point_like import P3DLike
from ezocc.humanization import Humanize
from ezocc.type_utils import TypeValidator, TypeUtils

LOGGER = logging.getLogger("occutils_python")

class Extents:

    swizzle_property_name = re.compile("[xyz]+_(mid|min|max|span)")

    def __init__(self, shape=None):
        if shape is not None:
            bnd_box = OCC.Core.Bnd.Bnd_Box()
            OCC.Core.BRepBndLib.brepbndlib.AddOptimal(shape, bnd_box, False, False)

            self._cache_bndbox_fields(bnd_box)
        else:
            self.x_min = 0
            self.y_min = 0
            self.z_min = 0
            self.x_max = 0
            self.y_max = 0
            self.z_max = 0

    def __getattr__(self, item: str):
        if not Extents.swizzle_property_name.fullmatch(item):
            raise AttributeError("Invalid attribute request: " + item)

        coords, coord_type = item.split("_")

        result = []

        for coord in coords:
            result.append(getattr(self, f"{coord}_{coord_type}"))

        return result

    @property
    def x_mid(self):
        return Extents._mid(self.x_min, self.x_max)

    @property
    def y_mid(self):
        return Extents._mid(self.y_min, self.y_max)

    @property
    def z_mid(self):
        return Extents._mid(self.z_min, self.z_max)

    @property
    def mid(self):
        return self.x_mid, self.y_mid, self.z_mid

    @property
    def max(self):
        return self.x_max, self.y_max, self.z_max

    @property
    def min(self):
        return self.x_min, self.y_min, self.z_min

    @property
    def x_span(self):
        return self.x_max - self.x_min

    @property
    def y_span(self):
        return self.y_max - self.y_min

    @property
    def z_span(self):
        return self.z_max - self.z_min

    @staticmethod
    def _mid(val_min: float, val_max: float):
        return val_min + 0.5 * (val_max - val_min)

    def get_offset_by(self,
                      amount_x_plus: float = 0,
                      amount_x_minus: float = 0,
                      amount_y_plus: float = 0,
                      amount_y_minus: float = 0,
                      amount_z_plus: float = 0,
                      amount_z_minus: float = 0):

        result = Extents()
        result.x_min = self.x_min - amount_x_minus
        result.y_min = self.y_min - amount_y_minus
        result.z_min = self.z_min - amount_z_minus
        result.x_max = self.x_max + amount_x_plus
        result.y_max = self.y_max + amount_y_plus
        result.z_max = self.z_max + amount_z_plus
        return result

    def _cache_bndbox_fields(self, bnd_box):
        self.x_min, self.y_min, self.z_min, self.x_max, self.y_max, self.z_max = \
            bnd_box.Get()

    def get_box(self):
        return OCC.Core.BRepPrimAPI.BRepPrimAPI_MakeBox(
            gp_Pnt(*self.min),
            gp_Pnt(*self.max)).Shape()


class EllipseParams:

    def __init__(self,
                 cx: float,
                 cy: float,
                 theta: float,
                 d_theta: float):

        self.cx = cx
        self.cy = cy
        self.theta = theta
        self.d_theta = d_theta

    @staticmethod
    def angle_between(ux: float, uy: float, vx: float, vy: float):
        sign_mult = 1 if ux * vy - uy * vx >= 0 else -1

        return sign_mult * math.acos((ux * vx + uy * vy) / (math.hypot(ux, uy) * math.hypot(vx, vy)))

    # see https://www.w3.org/TR/SVG11/implnote.html#ArcConversionEndpointToCenter
    @staticmethod
    def get_ellipse_params(x1: float,
                           y1: float,
                           x2: float,
                           y2: float,
                           fa: float,
                           fs: float,
                           rx: float,
                           ry: float,
                           rot: float):

        rx = math.fabs(rx)
        ry = math.fabs(ry)

        rx2 = rx * rx
        ry2 = ry * ry

        cos_rot = math.cos(rot)
        sin_rot = math.sin(rot)

        x1p = cos_rot * ((x1 - x2) / 2) + sin_rot * ((y1 - y2) / 2)
        y1p = -sin_rot * ((x1 - x2) / 2) + cos_rot * ((y1 - y2) / 2)

        x1p2 = x1p * x1p
        y1p2 = y1p * y1p

        sqrt_term = math.sqrt(math.fabs(
                (rx2 * ry2 - rx2 * y1p2 - ry2 * x1p2) /
                (rx2 * y1p2 + ry2 * x1p2)))

        x_mult_term = rx * y1p / ry
        y_mult_term = - ry * x1p / rx

        sign_mult = 1 if fa != fs else -1

        cpx = sign_mult * sqrt_term * x_mult_term
        cpy = sign_mult * sqrt_term * y_mult_term

        hsx = (x1 + x2) / 2
        hsy = (y1 + y2) / 2

        cx = cpx * cos_rot - cpy * sin_rot + hsx
        cy = cpx * sin_rot + cpy * cos_rot + hsy

        theta = EllipseParams.angle_between(1, 0, (x1p - cpx) / rx, (y1p - cpy) / ry)
        theta = math.fmod(theta + 2 * math.pi, 2 * math.pi)

        d_theta = EllipseParams.angle_between(
                (x1p - cpx) / rx, (y1p - cpy) / ry,
                (-x1p - cpx) / rx, (-y1p - cpy) / ry)

        # correct sign of d_theta
        if fs == 0 and d_theta > 0:
            d_theta -= 2 * math.pi
        elif fs == 1 and d_theta < 0:
            d_theta += 2 * math.pi

        return EllipseParams(cx, cy, theta, d_theta)


class Val:

    def __init__(self, value: float, is_relative: bool):
        self._value = value
        self._is_relative = is_relative

    def get_value(self, relative_from: float):
        if self._is_relative:
            return self._value + relative_from
        else:
            return self._value

    @staticmethod
    def rel(value: float):
        return Val(value, True)

    @staticmethod
    def abs(value: float):
        return Val(value, False)


class WireSketcherEntry:

    def __init__(self,
                 edge: OCC.Core.TopoDS.TopoDS_Edge,
                 edge_label: typing.Optional[str],
                 v0: OCC.Core.TopoDS.TopoDS_Vertex,
                 v0_label: typing.Optional[str],
                 v1: OCC.Core.TopoDS.TopoDS_Vertex,
                 v1_label: typing.Optional[str]):
        self.edge = edge
        self.edge_label = edge_label
        self.v0 = v0
        self.v1 = v1
        self.v0_label = v0_label
        self.v1_label = v1_label


class RelativePoint:

    DEFERRED_VALUE_INPUTS = typing.Tuple[OCC.Core.TopoDS.TopoDS_Vertex, typing.List[WireSketcherEntry]]

    @staticmethod
    def ago(offset: int):
        return RelativePoint(relative_index=-offset)

    @staticmethod
    def relative(offset: int):
        return RelativePoint(relative_index=offset)

    @staticmethod
    def absolute(index: int):
        return RelativePoint(absolute_index=index)

    def __init__(self,
                 absolute_index: typing.Optional[int] = None,
                 relative_index: typing.Optional[int] = None):
        if ((absolute_index is None and relative_index is None) or
                (absolute_index is not None and relative_index is not None)):
            raise ValueError("Either absolute_index or relative_index must be non-null, but not both")

        self._absolute_index = absolute_index
        self._relative_index = relative_index

    def x(self) -> DeferredValue[DEFERRED_VALUE_INPUTS, float]:
        return DeferredValue(lambda ws: self.get_point(ws).xyz[0])

    def y(self) -> DeferredValue[DEFERRED_VALUE_INPUTS, float]:
        return DeferredValue(lambda ws: self.get_point(ws).xyz[1])

    def z(self) -> DeferredValue[DEFERRED_VALUE_INPUTS, float]:
        return DeferredValue(lambda ws: self.get_point(ws).xyz[2])

    def get_point(self,
                  sketcher_entries: DEFERRED_VALUE_INPUTS) -> P3DLike:

        verts = [sketcher_entries[0]]
        for s in sketcher_entries[1]:
            verts.append(s.v1)

        point_count = len(verts)

        abs_index = self._absolute_index if self._absolute_index is not None else point_count - self._relative_index - 1

        if abs_index < 0 or abs_index >= point_count:
            raise ValueError(f"Invalid resultant index (index was {abs_index} for a point total of {point_count})")

        return P3DLike.create(verts[abs_index])


class WireSketcher:

    linespec_reg = re.compile("[xyz]+")

    def __init__(self, *initial_point: typing.Union[gp_Pnt, float]):
        if len(initial_point) == 0:
            initial_point = OCC.Core.gp.gp.Origin()
        elif isinstance(initial_point[0], OCC.Core.gp.gp_Pnt):
            if len(initial_point) != 1:
                raise ValueError("Only one arg supported if pnt")

            initial_point = initial_point[0]
        else:
            initial_point = OCC.Core.gp.gp_Pnt(*initial_point)

        self._initial_vertex: OCC.Core.TopoDS.TopoDS_Vertex = \
            OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeVertex(initial_point).Vertex()

        self._last_vertex: OCC.Core.TopoDS.TopoDS_Vertex = self._initial_vertex

        self._edges: typing.List[WireSketcherEntry] = []

    @property
    def initial_vertex(self) -> OCC.Core.TopoDS.TopoDS_Vertex:
        return self._initial_vertex

    @property
    def initial_vertex_pnt(self):
        return OCC.Core.BRep.BRep_Tool.Pnt(self.initial_vertex)

    @property
    def last_vertex(self) -> OCC.Core.TopoDS.TopoDS_Vertex:
        return self._last_vertex

    @property
    def last_vertex_pnt(self):
        return OCC.Core.BRep.BRep_Tool.Pnt(self.last_vertex)

    def line(self, **kwargs):
        x = None
        y = None
        z = None

        for name, item in kwargs.items():
            if not WireSketcher.linespec_reg.fullmatch(name):
                raise ValueError(f"Invalid keyword {name}")

            if "x" in name:
                if x is not None:
                    raise ValueError("Duplicate assignment for x")

                x = item

            if "y" in name:
                if y is not None:
                    raise ValueError("Duplicate assignment for y")

                y = item

            if "z" in name:
                if z is not None:
                    raise ValueError("Duplicate assignment for z")

                z = item

        if x is None:
            x = Val.rel(0)

        if y is None:
            y = Val.rel(0)

        if z is None:
            z = Val.rel(0)

        lp = self.last_vertex_pnt

        return self.line_to(x.get_value(lp.X()), y.get_value(lp.Y()), z.get_value(lp.Z()), is_relative=False)

    NLINE_TO_VALUE_TYPE = typing.Union[float, DeferredValue[RelativePoint.DEFERRED_VALUE_INPUTS, float]]

    def nline_to(self,
                 x: typing.Optional[NLINE_TO_VALUE_TYPE] = None,
                 y: typing.Optional[NLINE_TO_VALUE_TYPE] = None,
                 z: typing.Optional[NLINE_TO_VALUE_TYPE] = None,
                 dx: typing.Optional[NLINE_TO_VALUE_TYPE] = None,
                 dy: typing.Optional[NLINE_TO_VALUE_TYPE] = None,
                 dz: typing.Optional[NLINE_TO_VALUE_TYPE] = None,
                 label: str = None,
                 v0_label: str = None,
                 v1_label: str = None,
                 tol: float = 0.000001,
                 fraction: float = 1):

        if x is not None and dx is not None:
            raise ValueError("x and dx are mutually exclusive parameters")

        if y is not None and dy is not None:
            raise ValueError("y and dy are mutually exclusive parameters")

        if z is not None and dz is not None:
            raise ValueError("z and dz are mutually exclusive parameters")

        last_point_pnt = OCC.Core.BRep.BRep_Tool.Pnt(self._last_vertex)

        next_x_coordianate = last_point_pnt.X()
        next_y_coordianate = last_point_pnt.Y()
        next_z_coordianate = last_point_pnt.Z()

        if x is not None:
            next_x_coordianate = x
        elif dx is not None:
            next_x_coordianate = dx + last_point_pnt.X()

        if y is not None:
            next_y_coordianate = y
        elif dy is not None:
            next_y_coordianate = dy + last_point_pnt.Y()

        if z is not None:
            next_z_coordianate = z
        elif dz is not None:
            next_z_coordianate = dz + last_point_pnt.Z()

        next_x_coordianate = DeferredValue.of(next_x_coordianate).resolve((self.initial_vertex, self._edges))
        next_y_coordianate = DeferredValue.of(next_y_coordianate).resolve((self.initial_vertex, self._edges))
        next_z_coordianate = DeferredValue.of(next_z_coordianate).resolve((self.initial_vertex, self._edges))

        return self.line_to(next_x_coordianate, next_y_coordianate, next_z_coordianate,
                            is_relative=False,
                            label=label, v0_label=v0_label, v1_label=v1_label, tol=tol, fraction=fraction)


    def line_to(self,
                x: float = None,
                y: float = None,
                z: float = None,
                is_relative: bool = False,
                label: str = None,
                v0_label: str = None,
                v1_label: str = None,
                tol: float = 0.000001,
                fraction: float = 1):
        last_point_pnt = OCC.Core.BRep.BRep_Tool.Pnt(self._last_vertex)

        if is_relative:
            x = 0 if x is None else x
            y = 0 if y is None else y
            z = 0 if z is None else z

            next_point_pnt = gp_Pnt(
                x + last_point_pnt.X(),
                y + last_point_pnt.Y(),
                z + last_point_pnt.Z())
        else:
            x = last_point_pnt.X() if x is None else x
            y = last_point_pnt.Y() if y is None else y
            z = last_point_pnt.Z() if z is None else z

            next_point_pnt = gp_Pnt(x, y, z)

        if next_point_pnt.Distance(last_point_pnt) < tol:
            raise ValueError("Edge is zero length!")

        if fraction != 1:
            dx = next_point_pnt.X() - last_point_pnt.X()
            dy = next_point_pnt.Y() - last_point_pnt.Y()
            dz = next_point_pnt.Z() - last_point_pnt.Z()

            dx *= fraction
            dy *= fraction
            dz *= fraction

            next_point_pnt = gp_Pnt(
                last_point_pnt.X() + dx,
                last_point_pnt.Y() + dy,
                last_point_pnt.Z() + dz)

        next_vertex = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeVertex(next_point_pnt).Vertex()
        if next_point_pnt.Distance(self.initial_vertex_pnt) == 0:
            next_vertex = self.initial_vertex

        if last_point_pnt.Distance(next_point_pnt) != 0:
            self._edges.append(WireSketcherEntry(
                edge=OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(
                    self._last_vertex,
                    next_vertex
                ).Edge(),
                edge_label=label,
                v0=self._last_vertex,
                v0_label=v0_label,
                v1=next_vertex,
                v1_label=v1_label))
            self._last_vertex = next_vertex

        return self

    def get_face(self, should_reverse: bool = False):
        wire = self.get_wire()

        if should_reverse:
            wire.Reverse()

        return WireSketcher._wire_to_face(wire)

    def get_face_part(self, cache):
        wire = self.get_wire_part(cache)

        return wire.perform_make_shape(wire.cache_token.mutated("wire_sketcher_makeface"), WireSketcher._wire_to_makeface(wire.shape))

    @staticmethod
    def _wire_to_makeface(wire):
        saw = OCC.Core.ShapeAnalysis.ShapeAnalysis_Wire()
        saw.Load(wire)

        if saw.CheckClosed():
            raise ValueError("Wire is not closed")

        return OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeFace(wire)

    @staticmethod
    def _wire_to_face(wire):
        saw = OCC.Core.ShapeAnalysis.ShapeAnalysis_Wire()
        saw.Load(wire)

        if saw.CheckClosed():
            raise ValueError("Wire is not closed")

        mkf = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeFace(wire)
        if not mkf.IsDone():
            raise ValueError("Could not create face")

        sff = OCC.Core.ShapeFix.ShapeFix_Face(mkf.Face())
        sff.Perform()
        return sff.Face()

    @staticmethod
    def _are_points_connected(p0: gp_Pnt, p1: gp_Pnt):
        return p0.SquareDistance(p1) < 0.001

    @staticmethod
    def _are_edges_connected(
            e0: OCC.Core.TopoDS.TopoDS_Edge,
            e1: OCC.Core.TopoDS.TopoDS_Edge):

        bra0 = OCC.Core.BRepAdaptor.BRepAdaptor_Curve(e0)
        bra1 = OCC.Core.BRepAdaptor.BRepAdaptor_Curve(e1)

        p0 = bra0.Value(bra0.FirstParameter())
        p1 = bra0.Value(bra0.LastParameter())

        p2 = bra1.Value(bra1.FirstParameter())
        p3 = bra1.Value(bra1.LastParameter())

        return WireSketcher._are_points_connected(p0, p2) or \
               WireSketcher._are_points_connected(p0, p3) or \
               WireSketcher._are_points_connected(p1, p2) or \
               WireSketcher._are_points_connected(p1, p3)

    @staticmethod
    def _add_edge(edges_from: typing.List, edges_to: typing.List):
        for i_from, e_from in enumerate(edges_from):
            for i_to, e_to in enumerate(edges_to):

                if WireSketcher._are_edges_connected(e_from, e_to):
                    del edges_from[i_from]
                    edges_to.append(e_from)
                    return e_from

        def pnt_to_str(pnt: gp_Pnt):
            return f"({pnt.X()}, {pnt.Y()}, {pnt.Z()})"

        msg = "Edges from: "
        for e in edges_from:
            bra = OCC.Core.BRepAdaptor.BRepAdaptor_Curve(e)
            msg += "{ " + pnt_to_str(bra.Value(bra.FirstParameter())) + " -> " + pnt_to_str(bra.Value(bra.LastParameter())) + " }"

        msg += "  Edges to: "
        for e in edges_to:
            bra = OCC.Core.BRepAdaptor.BRepAdaptor_Curve(e)
            msg += "{ " + pnt_to_str(bra.Value(bra.FirstParameter())) + " -> " + pnt_to_str(bra.Value(bra.LastParameter())) + " }"

        VisualizationUtils.visualize(*(edges_from + edges_to))

        raise ValueError("Edge to add is not connected to any existing edge: " + msg)

    def get_wire_part(self, cache):
        import ezocc.part_manager as pm
        from ezocc.subshape_mapping import SubshapeMap

        subpart_names: typing.Dict[str, typing.Set[OCC.Core.TopoDS.TopoDS_Shape]] = {}
        for wse in self._edges:
            e = wse.edge
            name = wse.edge_label

            v0 = wse.v0
            name_v0 = wse.v0_label

            v1 = wse.v1
            name_v1 = wse.v1_label

            if name is not None:
                subpart_names[name] = subpart_names.get(name, set())
                subpart_names[name].add(e)

            if name_v0 is not None:
                subpart_names[name_v0] = subpart_names.get(name_v0, set())
                subpart_names[name_v0].add(v0)

            if name_v1 is not None:
                subpart_names[name_v1] = subpart_names.get(name_v1, set())
                subpart_names[name_v1].add(v1)

        part = pm.Part(pm.NoOpCacheToken(), SubshapeMap.from_single_shape(self._edges[0].edge))
        for e in self._edges[1:]:
            part = part.add(pm.Part(pm.NoOpCacheToken(), SubshapeMap.from_single_shape(e.edge)))

        part = pm.Part(pm.NoOpCacheToken(), SubshapeMap.from_unattributed_shapes(part.shape, subpart_names))

        return part.perform_make_shape(
            cache.create_token(part.shape, "wire_factory_makewire"),
            mks=self.get_makewire())

    def get_makewire(self) -> OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeWire:
        if len(self._edges) == 0:
            raise ValueError("Wire does not contain any edges.")

        makewire = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeWire()

        added_edges = [self._edges[0].edge]
        edges_to_add = [e.edge for e in self._edges[1:]]
        makewire.Add(self._edges[0].edge)

        while len(edges_to_add) != 0:
            e = WireSketcher._add_edge(edges_to_add, added_edges)
            makewire.Add(e)

        return makewire

    def get_wire(self, fix_reorder: bool = True, fix_connected: bool = True, fix_closed: bool = True):
        result = self.get_makewire().Wire()
        if not OCC.Core.BRepLib.breplib.BuildCurves3d(result):
            raise ValueError("Build curves 3d failed")

        sfw = OCC.Core.ShapeFix.ShapeFix_Wire()
        sfw.Load(result)

        if fix_reorder:
            sfw.FixReorder()

        if fix_connected:
            sfw.FixConnected()

        if fix_closed:
            sfw.FixClosed()

        result = sfw.Wire()

        return result

    def get_prism(self, *offset: typing.Union[gp_Vec, float]):
        if len(offset) == 1:
            if not isinstance(offset[0], gp_Vec):
                raise ValueError("Single argument must be a vector")

            return OCC.Core.BRepPrimAPI.BRepPrimAPI_MakePrism(self.get_face(), offset[0]).Shape()
        elif len(offset) == 3:
            return OCC.Core.BRepPrimAPI.BRepPrimAPI_MakePrism(
                self.get_face(),
                OCC.Core.gp.gp_Vec(offset[0], offset[1], offset[2])).Shape()
        else:
            raise ValueError()

    def close(self,
              tolerance: float = 0.000001,
              label: str = None,
              v0_label: str = None,
              v1_label: str = None):
        if len(self._edges) < 2:
            raise ValueError("Sketcher does not contain enough edges to close")

        if self.last_vertex_pnt.Distance(self.initial_vertex_pnt) > tolerance:
            self._edges.append(WireSketcherEntry(
                edge=OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(
                    self.last_vertex,
                    self.initial_vertex
                ).Edge(),
                edge_label=label,
                v0=self.last_vertex,
                v0_label=v0_label,
                v1=self.initial_vertex,
                v1_label=v1_label))
            self._last_vertex = self._initial_vertex

        return self

    def bezier(self,
               surface: OCC.Core.Geom.Geom_Surface,
               coords: typing.List[typing.Tuple[float, float]],
               is_relative: bool,
               label: str = None):

        last_vertex_pnt = self.last_vertex_pnt

        points = [
            (last_vertex_pnt.X(), last_vertex_pnt.Y()),
            (last_vertex_pnt.X(), last_vertex_pnt.Y())
        ]

        offset_x = last_vertex_pnt.X() if is_relative else 0
        offset_y = last_vertex_pnt.Y() if is_relative else 0

        for coord in coords:
            points.append(
                (coord[0] + offset_x, coord[1] + offset_y))

        return self._bezier_curve_edge(surface, points, label)

    def cubic_bezier(self,
                     surface: OCC.Core.Geom.Geom_Surface,
                     x1: float,
                     y1: float,
                     x2: float,
                     y2: float,
                     x: float,
                     y: float,
                     is_relative: bool,
                     label: str = None):

        last_vertex_point = self.last_vertex_pnt

        points = [(last_vertex_point.X(), last_vertex_point.Y())]

        offset_x = last_vertex_point.X() if is_relative else 0
        offset_y = last_vertex_point.Y() if is_relative else 0

        points.append((x1 + offset_x, y1 + offset_y))
        points.append((x2 + offset_x, y2 + offset_y))
        points.append((x + offset_x, y + offset_y))

        return self._bezier_curve_edge(surface, points, label=label)

    def circle_arc_to(self,
                      x: float,
                      y: float,
                      z: float,
                      radius: float,
                      direction: OCC.Core.gp.gp_Dir,
                      is_relative: bool = False,
                      shortest_curve: typing.Optional[bool] = True,
                      label: str = None,
                      v0_label: str = None,
                      v1_label: str = None):

        if radius <= 0:
            raise ValueError("Invalid radius")

        start_point = self.last_vertex_pnt
        if is_relative:
            x += start_point.X()
            y += start_point.Y()
            z += start_point.Z()

        end_point = pnt(x, y, z)
        end_vertex = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeVertex(end_point).Vertex()
        start_to_end_vec = vec(start_point, end_point)

        if not direction.IsNormal(dir(start_to_end_vec), 0.001):
            raise ValueError("Invalid normal direction!")

        midpoint = start_point.Translated(start_to_end_vec.Scaled(0.5))
        separation = start_point.Distance(end_point)

        if separation > 2 * radius:
            raise ValueError(f"Separation of points ({separation}) is greater than diameter ({2 * radius}).")

        # determine circle center by offsetting the midpoint
        # by the remaining distance to the center
        midpoint_to_center_distance = math.sqrt(radius*radius - 0.25 * separation*separation)
        midpoint_to_center_direction = start_to_end_vec.Normalized()\
            .Rotated(OCC.Core.gp.gp_Ax1(midpoint, direction), math.pi * 0.5)\
            .Normalized()
        center_point = midpoint.Translated(midpoint_to_center_direction.Scaled(midpoint_to_center_distance))

        circle = OCC.Core.gp.gp_Circ(OCC.Core.gp.gp_Ax2(center_point, direction), radius)

        edge_0 = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(
            OCC.Core.GC.GC_MakeArcOfCircle(circle, start_point, end_point, True).Value(),
            self._last_vertex,
            end_vertex
        ).Edge()

        edge_1 = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(
            OCC.Core.GC.GC_MakeArcOfCircle(circle, start_point, end_point, False).Value(),
            self._last_vertex,
            end_vertex
        ).Edge()

        if shortest_curve is None:
            self._edges.append(WireSketcherEntry(
                edge=edge_0,
                v0=self._last_vertex,
                v0_label=v0_label,
                v1_label=v1_label,
                v1=end_vertex,
                edge_label=label))
        else:

            if InterrogateUtils.length(edge_0) > InterrogateUtils.length(edge_1):
                max_length_edge = edge_0
                min_length_edge = edge_1
            else:
                max_length_edge = edge_1
                min_length_edge = edge_0

            if shortest_curve:
                self._edges.append(WireSketcherEntry(
                    edge=min_length_edge,
                    v0=self._last_vertex,
                    v0_label=v0_label,
                    v1_label=v1_label,
                    v1=end_vertex,
                    edge_label=label))
            else:
                self._edges.append(WireSketcherEntry(
                    edge=max_length_edge,
                    v0=self._last_vertex,
                    v0_label=v0_label,
                    v1_label=v1_label,
                    v1=end_vertex,
                    edge_label=label))

        self._last_vertex = end_vertex

        return self

    # attempts to sort and connect the edges
    @staticmethod
    def from_edges(*edges: OCC.Core.TopoDS.TopoDS_Edge, tolerance: float):
        edge_list = [e for e in edges]
        if len(edge_list) == 1:
            eStart = InterrogateUtils.line_points(edge_list[0])[0]
            return WireSketcher(eStart).generic_edge(edge_list[0])

        # can be used for debugging in error cases
        def viz_edges(edges_to_viz):
            edg = [e for e in edges_to_viz]
            to_viz = []
            for i, e in enumerate(edg):
                ep = InterrogateUtils.line_points(e)
                viz_edge = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(
                    ep[0],
                    ep[1].Translated(gp_Vec(0, 0, 1))
                ).Shape()

                to_viz.append(TransformUtils.translate(viz_edge, gp_Vec(0, 0, (i + 1) * 1)))

        def consume_from_edge_list(sketcher, edge_list: typing.List[OCC.Core.TopoDS.TopoDS_Edge]):
            first_ws_edge = sketcher._edges[0].edge
            last_ws_edge = sketcher._edges[-1].edge

            direct_end_connectors = [e for e in edge_list if WireSketcher._are_edges_in_order(last_ws_edge, e, tolerance=tolerance)]
            if len(direct_end_connectors) != 0:
                edge_list.remove(direct_end_connectors[0])
                sketcher.generic_edge(direct_end_connectors[0])
                return sketcher

            direct_beginning_connectors = [e for e in edge_list if WireSketcher._are_edges_in_order(e, first_ws_edge, tolerance=tolerance)]
            if len(direct_beginning_connectors) != 0:
                edge_list.remove(direct_beginning_connectors[0])

                sketcher2 = WireSketcher.from_edges(direct_beginning_connectors[0], tolerance=tolerance)
                for e in sketcher._edges:
                    sketcher2.generic_edge(e.edge)

                return sketcher2

            # determine if any reversed edge can be connected
            edges_to_reverse = [(e, WireSketcher._create_reversed_edge(e)) for e in edge_list]

            direct_end_connectors = [e for e in edges_to_reverse if
                                     WireSketcher._are_edges_in_order(last_ws_edge, e[1], tolerance=tolerance)]
            if len(direct_end_connectors) != 0:
                edge_list.remove(direct_end_connectors[0][0])
                sketcher.generic_edge(direct_end_connectors[0][1])
                return sketcher

            direct_beginning_connectors = [e for e in edges_to_reverse if
                                           WireSketcher._are_edges_in_order(e[1], first_ws_edge, tolerance=tolerance)]
            if len(direct_beginning_connectors) != 0:
                edge_list.remove(direct_beginning_connectors[0][0])

                sketcher2 = WireSketcher.from_edges(direct_beginning_connectors[0][1], tolerance=tolerance)
                for e in sketcher._edges:
                    sketcher2.generic_edge(e.edge)

                return sketcher2

            raise ValueError("Could not connect any edges!")

        # pick starting edge
        starting_edge = edge_list[0]
        edge_list.remove(starting_edge)
        ws = WireSketcher.from_edges(starting_edge, tolerance=tolerance)

        while len(edge_list) > 0:
            ws = consume_from_edge_list(ws, edge_list)

        return ws

    @staticmethod
    def _create_reversed_edge(edge: OCC.Core.TopoDS.TopoDS_Edge):
        e_start, e_end = InterrogateUtils.line_points(edge)

        start_vertex = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeVertex(e_start).Vertex()
        end_vertex = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeVertex(e_end).Vertex()

        if not OCC.Core.BRepLib.breplib.BuildCurves3d(edge):
            raise ValueError("Build curves 3d failed")

        curve = OCC.Core.BRep.BRep_Tool.Curve(edge)[0].Reversed()

        return OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(curve, start_vertex, end_vertex).Edge()


    # indicates if the end of one edge can be attached to the start of another
    @staticmethod
    def _are_edges_in_order(
            edge0: OCC.Core.TopoDS.TopoDS_Edge,
            edge1: OCC.Core.TopoDS.TopoDS_Edge,
            tolerance: float):
        e0Start, e0End = InterrogateUtils.line_points(edge0)
        e1Start, e1End = InterrogateUtils.line_points(edge1)

        return e0End.Distance(e1Start) < tolerance

    def generic_edge(self, edge: OCC.Core.TopoDS.TopoDS_Edge, label: str = None):
        eStart, eEnd = InterrogateUtils.line_points(edge)

        if self.last_vertex_pnt.Distance(eStart) > OCC.Core.Precision.precision.Confusion():
            raise ValueError("Edge not contiguous")

        start_vertex = self._last_vertex
        end_vertex = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeVertex(eEnd).Vertex()

        if not OCC.Core.BRepLib.breplib.BuildCurves3d(edge):
            raise ValueError("Build curves 3d failed")

        curve = OCC.Core.BRep.BRep_Tool.Curve(edge)[0]

        edge = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(curve, start_vertex, end_vertex).Edge()

        self._edges.append(WireSketcherEntry(edge,
                                             edge_label=label,
                                             v0=start_vertex,
                                             v1=end_vertex,
                                             v0_label=None, v1_label=None))

        self._last_vertex = end_vertex

        return self

    def _bezier_curve_edge(self,
                           surface: OCC.Core.Geom.Geom_Surface,
                           points: typing.List[typing.Tuple[float, float]],
                           label: str = None,
                           v0_label: str = None,
                           v1_label: str = None):

        if len(points) > OCC.Core.Geom2d.Geom2d_BezierCurve.MaxDegree():
            raise RuntimeError("Point length greater than bezier curve max degree.")

        poles = OCC.Core.TColgp.TColgp_Array1OfPnt2d(1, len(points))

        for i, point in enumerate(points):
            poles.SetValue(i + 1, OCC.Core.gp.gp_Pnt2d(*point))

        curve = OCC.Core.Geom2d.Geom2d_BezierCurve(poles)

        start_vertex = self._last_vertex
        end_vertex = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeVertex(surface.Value(*points[-1])).Vertex()

        self._edges.append(WireSketcherEntry(
            edge=OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(curve, surface, start_vertex, end_vertex).Edge(),
            edge_label=label,
            v0=start_vertex,
            v1=end_vertex,
            v0_label=v0_label,
            v1_label=v1_label))

        self._last_vertex = end_vertex

        return self

    def svg_arc(self,
                surface: OCC.Core.Geom.Geom_Surface,
                rx: float,
                ry: float,
                rot: float,
                fa: float,
                fs: float,
                x1: float,
                y1: float,
                is_relative: bool,
                label: str = None,
                v0_label: str = None,
                v1_label: str = None):

        curve_end_x = x1
        curve_end_y = y1

        last_vertex_pnt = self.last_vertex_pnt

        if is_relative:
            curve_end_x += last_vertex_pnt.X()
            curve_end_y += last_vertex_pnt.Y()

        curve_start_x = last_vertex_pnt.X()
        curve_start_y = last_vertex_pnt.Y()

        ellipse_params = EllipseParams.get_ellipse_params(
            curve_start_x,
            curve_start_y,
            curve_end_x,
            curve_end_y,
            fa,
            fs,
            rx,
            ry,
            rot)

        center_point = OCC.Core.gp.gp_Pnt2d(
            ellipse_params.cx,
            ellipse_params.cy)

        ellipse_axis = OCC.Core.gp.gp_Ax22d(center_point, OCC.Core.gp.gp.DX2d(), OCC.Core.gp.gp.DY2d())
        ellipse_axis.Rotate(OCC.Core.gp.gp.Origin2d(), rot)

        ellipse = OCC.Core.GCE2d.GCE2d_MakeEllipse(ellipse_axis, rx, ry).Value()

        theta_start = ellipse_params.theta
        theta_end = ellipse_params.theta + ellipse_params.d_theta

        if theta_start > theta_end:
            theta_start = theta_end
            theta_end = ellipse_params.theta

        ellipse_trimmed = OCC.Core.GCE2d.GCE2d_MakeArcOfEllipse(
            ellipse.Elips2d(),
            theta_start,
            theta_end,
            ellipse_params.d_theta > 0).Value()

        last_vertex = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeVertex(surface.Value(curve_end_x, curve_end_y)).Vertex()

        mkedge = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(ellipse_trimmed, surface, self._last_vertex, last_vertex)
        mkedge.Build()

        if not mkedge.IsDone():
            raise ValueError(f"MakeEdge failed with: " +
                             OCC.Core.BRepBuilderAPI.BRepBuilderAPI_EdgeError(mkedge.Error()).name)

        edge = mkedge.Edge()
        self._edges.append(WireSketcherEntry(
            edge=edge,
            edge_label=label,
            v0=self._last_vertex,
            v1=last_vertex,
            v0_label=v0_label,
            v1_label=v1_label))
        self._last_vertex = last_vertex

    def snap(self, *args):
        return SnapWireSketcher(self, *args)


class LineFactory:

    class LineTypes:
        direct = 1
        sequential = 2

    def __init__(self):
        self._deltas = []
        self._line_type = LineFactory.LineTypes.sequential

    def type(self, line_type):
        self._line_type = line_type
        return self

    def up(self, times=1):
        self._deltas += [[0, 1 * times]]
        return self

    def down(self, times=1):
        self._deltas += [[0, -1 * times]]
        return self

    def left(self, times=1):
        self._deltas += [[-1 * times, 0]]
        return self

    def right(self, times=1):
        self._deltas += [[1 * times, 0]]
        return self

    def get_type(self):
        return self._line_type

    @property
    def deltas(self):
        return [tuple(d) for d in self._deltas]

    def apply(self, wire_sketcher: WireSketcher, unit_x: float, unit_y: float):
        if self._line_type == LineFactory.LineTypes.direct:
            self._apply_direct(wire_sketcher, unit_x, unit_y)
        elif self._line_type == LineFactory.LineTypes.sequential:
            self._apply_sequential(wire_sketcher, unit_x, unit_y)
        else:
            raise ValueError("Invalid type")

    def _coord_sum(self):
        sum_x = 0
        sum_y = 0

        for delta in self.deltas:
            sum_x += delta[0]
            sum_y += delta[1]

        return sum_x, sum_y

    def _apply_direct(self, wire_sketcher: WireSketcher, unit_x: float, unit_y: float):
        dx, dy = self._coord_sum()
        dx *= unit_x
        dy *= unit_y

        wire_sketcher.line_to(dx, dy, 0, True)

    def _apply_sequential(self, wire_sketcher: WireSketcher, unit_x: float, unit_y: float):
        for dx, dy in self.deltas:
            wire_sketcher.line_to(dx * unit_x, dy * unit_y, 0, True)


class SnapWireSketcher:

    def __init__(self, wire_sketcher: WireSketcher, unit_x: float, unit_y: float):
        self._unit_x = unit_x
        self._unit_y = unit_y

        self._wire_sketcher = wire_sketcher

    def line(self, line_factory_consumer: typing.Callable[[LineFactory], None]):
        line_factory = LineFactory()
        line_factory_consumer(line_factory)
        line_factory.apply(self._wire_sketcher, self._unit_x, self._unit_y)
        return self

    def snap(self, *args, **kwargs):
        return self._wire_sketcher.snap(*args, **kwargs)

    def __getattr__(self, item):
        if hasattr(self._wire_sketcher, item):
            return getattr(self._wire_sketcher, item)
        else:
            raise AttributeError


class ListUtils:

    @staticmethod
    def consume_ncollst(ncollection_list) -> typing.Generator[typing.Any, None, None]:
        while ncollection_list.Size() > 0:
            yield ncollection_list.First()
            ncollection_list.RemoveFirst()

    @staticmethod
    def list(shapes: typing.List[oc.TopoDS.TopoDS_Shape]) -> OCC.Core.TopTools.TopTools_ListOfShape:
        result = OCC.Core.TopTools.TopTools_ListOfShape()
        for shape in shapes:
            result.Append(shape)

        return result

    @staticmethod
    def iterate_list(shapes: OCC.Core.TopTools.TopTools_ListOfShape):
        it = OCC.Core.TopTools.TopTools_ListIteratorOfListOfShape(shapes)
        while it.More():
            yield it.Value()
            it.Next()

class IOUtils:

    @staticmethod
    def save_shape_step(compound: OCC.Core.TopoDS.TopoDS_Shape, filename: str):
        import OCC.Core.STEPControl

        writer = OCC.Core.STEPControl.STEPControl_Writer()
        return_status = writer.Transfer(compound, OCC.Core.STEPControl.STEPControl_StepModelType.STEPControl_AsIs)
        if return_status != OCC.Core.IFSelect.IFSelect_ReturnStatus.IFSelect_RetDone:
            raise RuntimeError("Save shape failed")

        writer.Write(filename)

    @staticmethod
    def save_shape_stl(shape: OCC.Core.TopoDS.TopoDS_Shape,
                       filename: str,
                       lin_deflection: float = 0.01,
                       ang_deflection: float = 0.5):
        mesh = OCC.Core.BRepMesh.BRepMesh_IncrementalMesh(
            shape,
            lin_deflection,
            False,
            ang_deflection)

        writer = OCC.Core.StlAPI.StlAPI_Writer()

        if not writer.Write(mesh.Shape(), filename):
            raise RuntimeError("Could not write shape")


class BoolUtils:

    @staticmethod
    def incremental_cut(shape: oc.TopoDS.TopoDS_Shape,
                        cut_tools: typing.Union[typing.List[oc.TopoDS.TopoDS_Shape], oc.TopoDS.TopoDS_Shape],
                        cleanup: bool = False):

        if isinstance(cut_tools, oc.TopoDS.TopoDS_Shape):
            cut_tools = [cut_tools]

        result = shape

        for tool in cut_tools:
            intermediate_result = OCC.Core.BRepAlgoAPI.BRepAlgoAPI_Cut(result, tool).Shape()
            if intermediate_result is None:
                VisualizationUtils.visualize(result, tool)
                raise RuntimeError("Error occurred during boolean operation")

            result = intermediate_result

        if cleanup:
            result = Cleanup.simplify_domain(result)

        return result

    @staticmethod
    def incremental_fuse(shapes: typing.List[oc.TopoDS.TopoDS_Shape],
                         cleanup: bool = False) -> OCC.Core.TopoDS.TopoDS_Shape:
        result = shapes[0]

        for shape in shapes[1:]:
            result = OCC.Core.BRepAlgoAPI.BRepAlgoAPI_Fuse(result, shape).Shape()
            if result is None:
                raise RuntimeError("Error occurred during boolean operation")

        if cleanup:
            result = Cleanup.simplify_domain(result)

        return result

    @staticmethod
    def fuse(shapes: typing.List[oc.TopoDS.TopoDS_Shape]) -> OCC.Core.TopoDS.TopoDS_Shape:

        algo = OCC.Core.BRepAlgoAPI.BRepAlgoAPI_Fuse()

        algo.SetNonDestructive(True)
        algo.SetArguments(ListUtils.list([shapes[0]]))
        algo.SetTools(ListUtils.list(shapes[1:]))

        algo.Build()

        if algo.HasErrors():
            raise RuntimeError("bool op failed")

        return algo.Shape()


class TransformUtils:

    @unique
    class Axis(Enum):
        X = 1
        Y = 2
        Z = 3

    @unique
    class AlignType(Enum):
        MIN = 0
        MID = 1
        MAX = 2

    @staticmethod
    def g_transform(shape: oc.TopoDS.TopoDS_Shape,
                    r0c0: float = 1, r0c1: float = 0, r0c2: float = 0,
                    r1c0: float = 0, r1c1: float = 1, r1c2: float = 0,
                    r2c0: float = 0, r2c1: float = 0, r2c2: float = 1):
        trsf = oc.gp.gp_GTrsf()
        trsf.SetVectorialPart(oc.gp.gp_Mat(r0c0, r0c1, r0c2, r1c0, r1c1, r1c2, r2c0, r2c1, r2c2))

        return oc.BRepBuilderAPI.BRepBuilderAPI_GTransform(shape, trsf, True).Shape()

    @staticmethod
    def g_scale(shape: OCC.Core.TopoDS.TopoDS_Shape,
                scale_x: float = 1,
                scale_y: float = 1,
                scale_z: float = 1):
        return TransformUtils.g_transform(shape, r0c0=scale_x, r1c1=scale_y, r2c2=scale_z)

    @staticmethod
    def transform(shape: oc.TopoDS.TopoDS_Shape,
                  modifier: typing.Callable[[oc.gp.gp_Trsf], None]) -> oc.TopoDS.TopoDS_Shape:
        trsf = oc.gp.gp_Trsf()

        modifier(trsf)

        return oc.BRepBuilderAPI.BRepBuilderAPI_Transform(shape, trsf, True).Shape()

    @staticmethod
    def rotate(shape: oc.TopoDS.TopoDS_Shape,
               axis: oc.gp.gp_Ax1,
               amount: float) -> oc.TopoDS.TopoDS_Shape:
        return TransformUtils.transform(shape, lambda g: g.SetRotation(axis, amount))

    @staticmethod
    def translate(shape: oc.TopoDS.TopoDS_Shape, vector: oc.gp.gp_Vec) -> oc.TopoDS.TopoDS_Shape:
        return TransformUtils.transform(shape, lambda g: g.SetTranslation(vector))

    @staticmethod
    def scale_to_dimension(shape: oc.TopoDS.TopoDS_Shape,
                           desired_length: float,
                           axis: Axis) -> OCC.Core.TopoDS.TopoDS_Shape:
        ext = Extents(shape)

        v0 = gp_Pnt(*ext.min).Coord(axis.value)
        v1 = gp_Pnt(*ext.max).Coord(axis.value)

        current_length = v1 - v0

        scale_factor = desired_length / current_length

        return TransformUtils.transform(shape, lambda g: g.SetScale(gp_Pnt(*ext.mid), scale_factor))

    @staticmethod
    def align_midpoints(to_align: oc.TopoDS.TopoDS_Shape,
                        align_to: oc.TopoDS.TopoDS_Shape,
                        axis: Axis):
        return TransformUtils.align(to_align,
                                    TransformUtils.AlignType.MID,
                                    align_to,
                                    TransformUtils.AlignType.MID,
                                    axis)

    @staticmethod
    def align_min(to_align: oc.TopoDS.TopoDS_Shape,
                  align_to: oc.TopoDS.TopoDS_Shape,
                  axis: Axis):
        return TransformUtils.align(to_align,
                                    TransformUtils.AlignType.MIN,
                                    align_to,
                                    TransformUtils.AlignType.MIN,
                                    axis)

    @staticmethod
    def align_max(to_align: oc.TopoDS.TopoDS_Shape,
                  align_to: oc.TopoDS.TopoDS_Shape,
                  axis: Axis):
        return TransformUtils.align(to_align,
                                    TransformUtils.AlignType.MAX,
                                    align_to,
                                    TransformUtils.AlignType.MAX,
                                    axis)

    @staticmethod
    def align(to_align: oc.TopoDS.TopoDS_Shape,
              to_align_type: AlignType,
              align_to: oc.TopoDS.TopoDS_Shape,
              align_to_type: AlignType,
              axis: Axis,
              offset: float = 0):
        to_align_extents = Extents(to_align)
        align_to_extents = Extents(align_to)

        from_value = TransformUtils._get_extents_param(to_align_extents, axis, to_align_type)
        to_value = TransformUtils._get_extents_param(align_to_extents, axis, align_to_type)

        delta_value = to_value - from_value + offset

        vec = oc.gp.gp_Vec()
        vec.SetCoord(axis.value, delta_value)

        return TransformUtils.translate(to_align, vec)

    @staticmethod
    def _get_extents_param(extents: Extents, axis: Axis, align_type: AlignType) -> float:
        return TransformUtils._get_point_coord(
            TransformUtils._get_extents_align_values(extents, align_type),
            axis
        )

    @staticmethod
    def _get_point_coord(pnt: oc.gp.gp_Pnt, axis: Axis) -> float:
        return pnt.Coord(axis.value)

    @staticmethod
    def _get_extents_align_values(extents: Extents, align_type: AlignType) -> oc.gp.gp_Pnt:
        if align_type == TransformUtils.AlignType.MAX:
            return gp_Pnt(*extents.max)
        elif align_type == TransformUtils.AlignType.MID:
            return gp_Pnt(*extents.mid)
        elif align_type == TransformUtils.AlignType.MIN:
            return gp_Pnt(*extents.min)

        raise ValueError(f"Unknown align type: {align_type}")


class TwoVec:

    def __init__(self, unit_x: OCC.Core.gp.gp_Vec, unit_y: OCC.Core.gp.gp_Vec):
        self.unit_x = unit_x
        self.unit_y = unit_y

    def get(self, x, y):
        result = self.unit_x.Scaled(x).Added(self.unit_y.Scaled(y))
        return [result.X(), result.Y(), result.Z()]

    @staticmethod
    def xy():
        return TwoVec(OCC.Core.gp.gp_Vec(1, 0, 0), OCC.Core.gp.gp_Vec(0, 1, 0))

    @staticmethod
    def yz():
        return TwoVec(OCC.Core.gp.gp_Vec(0, 1, 1), OCC.Core.gp.gp_Vec(0, 0, 1))

    @staticmethod
    def zx():
        return TwoVec(OCC.Core.gp.gp_Vec(0, 0, 1), OCC.Core.gp.gp_Vec(1, 0, 0))


class ExploreUtils:

    @staticmethod
    def explore(shape: oc.TopoDS.TopoDS_Shape,
                shape_type: oc.TopAbs.TopAbs_ShapeEnum,
                consumer: typing.Callable[[oc.TopoDS.TopoDS_Shape], None]):
        explorer = oc.TopExp.TopExp_Explorer(shape, shape_type)
        while explorer.More():
            consumer(explorer.Current())
            explorer.Next()

    @staticmethod
    def explore_iterate(
            shape: oc.TopoDS.TopoDS_Shape,
            shape_type: oc.TopAbs.TopAbs_ShapeEnum,
            predicate: typing.Callable[[oc.TopoDS.TopoDS_Shape], bool] = lambda s: True):
        explorer = oc.TopExp.TopExp_Explorer(shape, shape_type)
        while explorer.More():
            s = explorer.Current()
            if predicate(s):
                yield s

            explorer.Next()

    @staticmethod
    def ordered_wire_explore_iterate(
            shape: oc.TopoDS.TopoDS_Shape,
            shape_type: oc.TopAbs.TopAbs_ShapeEnum,
            predicate: typing.Callable[[oc.TopoDS.TopoDS_Shape], bool] = lambda s: True):
        explorer = OCC.Core.BRepTools.BRepTools_WireExplorer(shape)
        if shape_type != OCC.Core.TopAbs.TopAbs_EDGE:
            raise ValueError("Only edge exploration is supported")

        while explorer.More():
            s = explorer.Current()

            if predicate(s):
                yield s

            explorer.Next()

    @staticmethod
    def iterate_compound(shape: oc.TopoDS.TopoDS_Compound):
        iterator = OCC.Core.TopoDS.TopoDS_Iterator(shape)
        while iterator.More():
            yield iterator.Value()
            iterator.Next()


class Explorer:

    def __init__(self, shape: OCC.Core.TopoDS.TopoDS_Shape, shape_type: oc.TopAbs.TopAbs_ShapeEnum):
        self.shape = shape
        self.shape_type = shape_type
        self.predicate = lambda s: True
        self.key = lambda s: 0.0

    def filter_by(self, predicate: typing.Callable[[OCC.Core.TopoDS.TopoDS_Shape], bool]):
        old_pred = self.predicate

        self.predicate = lambda e: (old_pred(e) and predicate(e))
        return self

    def order_by(self, key: typing.Callable[[OCC.Core.TopoDS.TopoDS_Shape], float]):
        self.key = key
        return self

    def get(self):
        result = [s for s in ExploreUtils.explore_iterate(self.shape, self.shape_type) if self.predicate(s)]
        result.sort(key=self.key)
        return result

    def get_single(self) -> OCC.Core.TopoDS.TopoDS_Shape:
        result = [s for s in ExploreUtils.explore_iterate(self.shape, self.shape_type) if self.predicate(s)]
        if len(result) != 1:
            raise RuntimeError("Unable to return single element")

        return result[0]

    @staticmethod
    def shape_explorer(shape: OCC.Core.TopoDS.TopoDS_Shape):
        return Explorer(shape, OCC.Core.TopAbs.TopAbs_ShapeEnum.TopAbs_SHAPE)

    @staticmethod
    def solid_explorer(shape: OCC.Core.TopoDS.TopoDS_Shape):
        return Explorer(shape, OCC.Core.TopAbs.TopAbs_ShapeEnum.TopAbs_SOLID)

    @staticmethod
    def face_explorer(shape: OCC.Core.TopoDS.TopoDS_Shape):
        return Explorer(shape, OCC.Core.TopAbs.TopAbs_ShapeEnum.TopAbs_FACE)

    @staticmethod
    def vertex_explorer(shape: OCC.Core.TopoDS.TopoDS_Shape):
        return Explorer(shape, OCC.Core.TopAbs.TopAbs_ShapeEnum.TopAbs_VERTEX)

    @staticmethod
    def edge_explorer(shape: OCC.Core.TopoDS.TopoDS_Shape):
        return Explorer(shape, OCC.Core.TopAbs.TopAbs_ShapeEnum.TopAbs_EDGE)

    @staticmethod
    def wire_explorer(shape: OCC.Core.TopoDS.TopoDS_Shape):
        return Explorer(shape, OCC.Core.TopAbs.TopAbs_ShapeEnum.TopAbs_WIRE)

    @staticmethod
    def by_depth_mid_order():
        return lambda s: Extents(s).z_mid

    @staticmethod
    def by_depth_max_filter(max_depth: float):
        return lambda s: Extents(s).z_span < max_depth

    @staticmethod
    def extents_filter(filter: typing.Callable[[Extents], bool]) -> \
            typing.Callable[[OCC.Core.TopoDS.TopoDS_Shape], bool]:

        return lambda s: filter(Extents(s))

    @staticmethod
    def is_x_line_filter(tolerance: float):
        return Explorer.extents_filter(
            lambda e: e.z_span < tolerance < e.x_span and e.y_span < tolerance)

    @staticmethod
    def is_y_line_filter(tolerance: float):
        return Explorer.extents_filter(
            lambda e: e.z_span < tolerance and e.y_span > tolerance > e.x_span)

    @staticmethod
    def is_z_line_filter(tolerance: float):
        return Explorer.extents_filter(
            lambda e: e.z_span > tolerance > e.x_span and e.y_span < tolerance)

    @staticmethod
    def extents_order(k: typing.Callable[[Extents], float]) -> \
            typing.Callable[[OCC.Core.TopoDS.TopoDS_Shape], float]:

        def result(shape) -> float:
            ext = Extents(shape)

            return k(ext)

        return result


class GeomUtils:

    @staticmethod
    def build_curves_3d(shape: OCC.Core.TopoDS.TopoDS_Shape):
        if not OCC.Core.BRepLib.breplib.BuildCurves3d(shape):
            raise ValueError("Build curves 3d failed")

    @staticmethod
    def circle_wire(radius: float) -> OCC.Core.TopoDS.TopoDS_Wire:
        circ = OCC.Core.gp.gp_Circ(OCC.Core.gp.gp.XOY(), radius)
        edge = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(circ).Shape()
        return OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeWire(edge).Wire()

    @staticmethod
    def circle_face(radius: float) -> OCC.Core.TopoDS.TopoDS_Face:
        return OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeFace(
            GeomUtils.circle_wire(radius)
        ).Face()

    @staticmethod
    def offset(shape: OCC.Core.TopoDS.TopoDS_Wire,
               amount: float,
               join_type: OCC.Core.GeomAbs.GeomAbs_JoinType = OCC.Core.GeomAbs.GeomAbs_Arc,
               is_open_result: bool = False) -> OCC.Core.TopoDS.TopoDS_Shape:

        mko = OCC.Core.BRepOffsetAPI.BRepOffsetAPI_MakeOffset(shape, join_type, is_open_result)
        mko.Perform(amount)
        return mko.Shape()

    @staticmethod
    def pipe(spine: OCC.Core.TopoDS.TopoDS_Wire,
             profile: OCC.Core.TopoDS.TopoDS_Wire):

        mps = OCC.Core.BRepOffsetAPI.BRepOffsetAPI_MakePipeShell(spine)
        mps.Add(profile)

        if not mps.IsReady():
            raise RuntimeError("PipeBuilder failure")

        mps.Build()
        mps.MakeSolid()
        return mps.Shape()

    @staticmethod
    def plane_section(to_section: OCC.Core.TopoDS.TopoDS_Shape,
                      origin: OCC.Core.gp.gp_Pnt,
                      dir: OCC.Core.gp.gp_Dir):

        plane = OCC.Core.gp.gp_Pln(origin, dir)
        #plane = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeFace(plane).Shape()

        return OCC.Core.BRepAlgoAPI.BRepAlgoAPI_Section(to_section, plane).Shape()

    @staticmethod
    def plane_cut(to_section: OCC.Core.TopoDS.TopoDS_Shape,
                  origin: OCC.Core.gp.gp_Pnt,
                  dir: OCC.Core.gp.gp_Dir,
                  plane_thickness_a: float = 0,
                  plane_thickness_b: float = 0,
                  plane_thickness: float = 0):

        if plane_thickness != 0:
            if plane_thickness_a != 0 or plane_thickness_b != 0:
                raise ValueError("Either use plane_thickness or (plane_thickness_a, plane_thickness_b), not both.")

            plane_thickness_a = plane_thickness * 0.5
            plane_thickness_b = plane_thickness * 0.5

        dir_a = dir
        dir_b = OCC.Core.gp.gp_Dir(-dir.X(), -dir.Y(), -dir.Z())

        plane_origin_a = origin.Translated(gp_Vec(
            dir_a.X() * plane_thickness_a,
            dir_a.Y() * plane_thickness_a,
            dir_a.Z() * plane_thickness_a))

        plane_origin_b = origin.Translated(gp_Vec(
            dir_b.X() * plane_thickness_b,
            dir_b.Y() * plane_thickness_b,
            dir_b.Z() * plane_thickness_b))

        plane_a = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeFace(OCC.Core.gp.gp_Pln(plane_origin_a, dir_a)).Face()
        plane_b = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeFace(OCC.Core.gp.gp_Pln(plane_origin_b, dir_b)).Face()

        half_space_a = OCC.Core.BRepPrimAPI.BRepPrimAPI_MakeHalfSpace(plane_a, plane_origin_a.Translated(gp_Vec(dir_a))).Shape()
        half_space_b = OCC.Core.BRepPrimAPI.BRepPrimAPI_MakeHalfSpace(plane_b, plane_origin_b.Translated(gp_Vec(dir_b))).Shape()

        return OCC.Core.BRepAlgoAPI.BRepAlgoAPI_Common(to_section, half_space_a).Shape(), \
               OCC.Core.BRepAlgoAPI.BRepAlgoAPI_Common(to_section, half_space_b).Shape()

    @staticmethod
    def square(x0: float, y0: float, x1: float, y1: float):

        return WireSketcher(pnt(x0, y0, 0))\
            .line_to(x1, y0, 0) \
            .line_to(x1, y1, 0) \
            .line_to(x0, y1, 0) \
            .close()

    @staticmethod
    def square_from_corner(corner_x: float, corner_y: float, dx: float, dy:float):
        return WireSketcher(pnt(corner_x, corner_y, 0))\
            .line_to(dx, 0, 0, is_relative=True) \
            .line_to(0, dy, 0, is_relative=True) \
            .line_to(-dx, 0, 0, is_relative=True) \
            .close()

    @staticmethod
    def square_centered(origin: OCC.Core.gp.gp_Pnt = OCC.Core.gp.gp.Origin(),
                        side_length_0: float = 10,
                        side_length_1: float = None,
                        tv: TwoVec = None,
                        consumer=lambda e: e):

        hsl_0 = side_length_0 / 2

        if tv is None:
            tv = TwoVec.xy()

        if side_length_1 is None:
            side_length_1 = side_length_0

        hsl_1 = side_length_1 / 2

        ws = WireSketcher(origin.Translated(oc.gp.gp_Vec(*tv.get(-hsl_0, -hsl_1))))
        ws.line_to(*tv.get(side_length_0, 0), is_relative=True)
        ws.line_to(*tv.get(0, side_length_1), is_relative=True)
        ws.line_to(*tv.get(-side_length_0, 0), is_relative=True)
        ws.close()

        return consumer(ws)

    @staticmethod
    def prism(shape, dx: float, dy: float, dz: float):
        if type(shape) == WireSketcher:
            shape = shape.getFace()

        if shape.ShapeType() == OCC.Core.TopAbs.TopAbs_ShapeEnum.TopAbs_WIRE:
            shape = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeFace(
                OCC.Core.TopoDS.topods.Wire(shape)).Shape()

        vec = OCC.Core.gp.gp_Vec(dx, dy, dz)

        return OCC.Core.BRepPrimAPI.BRepPrimAPI_MakePrism(shape, vec).Shape()

    @staticmethod
    def prisms(shape, *d_coords: float, **bool_kwargs):
        if len(d_coords) == 0 or len(d_coords) % 3 != 0:
            raise ValueError("Coords must be a multiple of 3")

        result = GeomUtils.prism(shape, d_coords[0], d_coords[1], d_coords[2])

        for i in range(1, len(d_coords) // 3):
            dx = d_coords[i * 3]
            dy = d_coords[i * 3 + 1]
            dz = d_coords[i * 3 + 2]
            result = BoolUtils.incremental_fuse([result, GeomUtils.prism(shape, dx, dy, dz)], **bool_kwargs)

        return result

    @staticmethod
    def regular_polygon(r: float, num_points: int) -> OCC.Core.TopoDS.TopoDS_Shape:

        ws = WireSketcher(OCC.Core.gp.gp_Pnt(r * math.cos(0), r * math.sin(0), 0))

        angle_increment = (math.pi * 2) / num_points
        for i in range(1, num_points):
            angle = i * angle_increment
            ws.line_to(r * math.cos(angle), r * math.sin(angle), 0)

        ws.close()

        return ws.get_wire()

    @staticmethod
    def face_with_holes(outer_wire: OCC.Core.TopoDS.TopoDS_Wire, *inner_wires: OCC.Core.TopoDS.TopoDS_Wire):
        mkf = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeFace(outer_wire)
        for w in inner_wires:
            mkf.Add(w.Reversed())

        return mkf.Face()

    @staticmethod
    def loft(wires: typing.List[OCC.Core.TopoDS.TopoDS_Wire], is_solid=True, is_ruled=True, pres3d=1.0e-6):
        ts = OCC.Core.BRepOffsetAPI.BRepOffsetAPI_ThruSections(is_solid, is_ruled, pres3d)

        if len(wires) < 2:
            raise ValueError("Must specify at least 2 wires")

        for w in wires:
            if w.ShapeType() != OCC.Core.TopAbs.TopAbs_WIRE:
                raise ValueError(f"Cannot add non-wire: {w}")

            ts.AddWire(w)

        return ts.Shape()

    @staticmethod
    def make_compound(*shapes) -> OCC.Core.TopoDS.TopoDS_Compound:
        builder = OCC.Core.BRep.BRep_Builder()
        result = OCC.Core.TopoDS.TopoDS_Compound()

        builder.MakeCompound(result)

        for s in shapes:
            builder.Add(result, s)

        return result


class MirrorUtils:

    @staticmethod
    def mirror_x(shape: OCC.Core.TopoDS.TopoDS_Shape, x_coord: float = 0, to_compound: bool = True):
        result = TransformUtils.transform(shape, lambda g: g.SetMirror(OCC.Core.gp.gp.YOZ().Translated(vec(x_coord, 0, 0))))
        return GeomUtils.make_compound(result, shape) if to_compound else result

    @staticmethod
    def mirror_y(shape: OCC.Core.TopoDS.TopoDS_Shape, y_coord: float = 0, to_compound: bool = True):
        result = TransformUtils.transform(shape, lambda g: g.SetMirror(OCC.Core.gp.gp.ZOX().Translated(vec(0, y_coord, 0))))
        return GeomUtils.make_compound(result, shape) if to_compound else result

    @staticmethod
    def mirror_z(shape: OCC.Core.TopoDS.TopoDS_Shape, z_coord: float = 0, to_compound: bool = True):
        result = TransformUtils.transform(shape, lambda g: g.SetMirror(OCC.Core.gp.gp.XOY().Translated(vec(0, 0, z_coord))))
        return GeomUtils.make_compound(result, shape) if to_compound else result

    @staticmethod
    def mirror_xy(shape: OCC.Core.TopoDS.TopoDS_Shape,
                  x_coord: float = 0,
                  y_coord: float = 0,
                  to_compound: bool = True):
        return MirrorUtils.mirror_y(MirrorUtils.mirror_x(shape, x_coord, to_compound), y_coord, to_compound)


class InterrogateUtils:

    @staticmethod
    def vertex_to_xyz(vertex: OCC.Core.TopoDS.TopoDS_Vertex) -> typing.Tuple[float, float, float]:
        p = OCC.Core.BRep.BRep_Tool.Pnt(vertex)
        return p.X(), p.Y(), p.Z()

    @staticmethod
    def is_parent_shape(parent: OCC.Core.TopoDS.TopoDS_Shape, child: OCC.Core.TopoDS.TopoDS_Shape):
        if parent.ShapeType() > child.ShapeType():
            # e.g. FACE cannot contain SOLID
            return False

        for s in ExploreUtils.explore_iterate(parent, child.ShapeType()):
            if s == child:
                return True

        return False

    @staticmethod
    def face_normal(face: OCC.Core.TopoDS.TopoDS_Face,
                    uv_mapper: typing.Callable[
                        [float, float, float, float],
                        typing.Tuple[float, float]] = None,
                    resolution: float = 0.0001) -> typing.Tuple[gp_Pnt, gp_Dir]:

        if face.ShapeType() != OCC.Core.TopAbs.TopAbs_FACE:
            raise ValueError(f"Supplied argument is not a face: {face}")

        if not isinstance(face, OCC.Core.TopoDS.TopoDS_Face):
            face = TypeUtils.downcast_to_shape_type(face)


        if uv_mapper is None:
            uv_mapper = lambda umn, umx, vmn, vmx: (umn + (umx - umn) / 2, vmn + (vmx - vmn) / 2)

        surf = OCC.Core.BRep.BRep_Tool.Surface(face)

        u_min, u_max, v_min, v_max = OCC.Core.BRepTools.breptools.UVBounds(face)

        u_select, v_select = uv_mapper(u_min, u_max, v_min, v_max)

        slprops = OCC.Core.GeomLProp.GeomLProp_SLProps(surf, u_select, v_select, 1, resolution)

        return slprops.Value(), slprops.Normal()

    @staticmethod
    def is_singleton_compound(shape: OCC.Core.TopoDS.TopoDS_Shape) -> bool:
        return shape.ShapeType() == OCC.Core.TopAbs.TopAbs_COMPOUND and \
               len([s for s in InterrogateUtils.traverse_direct_subshapes(shape)]) == 1

    @staticmethod
    def is_empty_compound(shape: OCC.Core.TopoDS.TopoDS_Shape) -> bool:
        return shape.ShapeType() == OCC.Core.TopAbs.TopAbs_COMPOUND and \
               len([s for s in InterrogateUtils.traverse_direct_subshapes(shape)]) == 0

    @staticmethod
    def is_compound_of(shape: OCC.Core.TopoDS.TopoDS_Shape, st: OCC.Core.TopAbs.TopAbs_ShapeEnum) -> bool:
        return shape.ShapeType() == OCC.Core.TopAbs.TopAbs_COMPOUND and \
               all(s.ShapeType() == st for s in InterrogateUtils.traverse_direct_subshapes(shape))

    @staticmethod
    def outer_wire(shape: OCC.Core.TopoDS.TopoDS_Shape) -> OCC.Core.TopoDS.TopoDS_Wire:
        st = shape.ShapeType()

        if st == OCC.Core.TopAbs.TopAbs_WIRE:
            return OCC.Core.TopoDS.topods.Wire(shape)
        elif st == OCC.Core.TopAbs.TopAbs_FACE:
            return OCC.Core.BRepTools.breptools.OuterWire(OCC.Core.TopoDS.topods.Face(shape))
        else:
            raise ValueError(f"Shape {shape} cannot be converted to outer wire")

    @staticmethod
    def line_points(shape: OCC.Core.TopoDS.TopoDS_Edge) -> typing.Tuple[gp_Pnt, gp_Pnt]:

        adaptor = OCC.Core.BRepAdaptor.BRepAdaptor_Curve(shape)
        return InterrogateUtils._get_end_points(adaptor)

    @staticmethod
    def wire_points(shape: OCC.Core.TopoDS.TopoDS_Wire) -> typing.Tuple[gp_Pnt, gp_Pnt]:
        adaptor = OCC.Core.BRepAdaptor.BRepAdaptor_CompCurve(shape)
        return InterrogateUtils._get_end_points(adaptor)

    @staticmethod
    def wire_tangent_points(shape: OCC.Core.TopoDS.TopoDS_Wire) -> typing.Tuple[gp_Vec, gp_Vec]:

        adaptor = OCC.Core.BRepAdaptor.BRepAdaptor_CompCurve(shape)

        t0 = OCC.Core.gp.gp_Vec()
        adaptor.D1(
            adaptor.FirstParameter(),
            adaptor.Value(adaptor.FirstParameter()),
            t0)

        t1 = OCC.Core.gp.gp_Vec()
        adaptor.D1(
            adaptor.LastParameter(),
            adaptor.Value(adaptor.LastParameter()),
            t1)

        return t0, t1

    @staticmethod
    def line_tangent_point(shape: OCC.Core.TopoDS.TopoDS_Edge, parameter: float, is_normalized_parameter: bool = True) -> gp_Vec:
        adaptor = OCC.Core.BRepAdaptor.BRepAdaptor_Curve(shape)

        if is_normalized_parameter:
            parameter = adaptor.FirstParameter() + parameter * (adaptor.LastParameter() - adaptor.FirstParameter())

        tangent = OCC.Core.gp.gp_Vec()
        adaptor.D1(
            parameter,
            adaptor.Value(parameter),
            tangent)

        return tangent


    @staticmethod
    def line_point(shape: OCC.Core.TopoDS.TopoDS_Edge, parameter: float, is_normalized_parameter: bool = True) -> gp_Pnt:
        adaptor = OCC.Core.BRepAdaptor.BRepAdaptor_Curve(shape)

        if is_normalized_parameter:
            parameter = adaptor.FirstParameter() + parameter * (adaptor.LastParameter() - adaptor.FirstParameter())

        pnt = OCC.Core.gp.gp_Pnt()
        adaptor.D0(
            parameter,
            pnt)

        return pnt


    @staticmethod
    def line_tangent_points(shape: OCC.Core.TopoDS.TopoDS_Edge) -> typing.Tuple[gp_Vec, gp_Vec]:

        adaptor = OCC.Core.BRepAdaptor.BRepAdaptor_Curve(shape)

        t0 = OCC.Core.gp.gp_Vec()
        adaptor.D1(
            adaptor.FirstParameter(),
            adaptor.Value(adaptor.FirstParameter()),
            t0)

        t1 = OCC.Core.gp.gp_Vec()
        adaptor.D1(
            adaptor.LastParameter(),
            adaptor.Value(adaptor.LastParameter()),
            t1)

        return t0, t1

    @staticmethod
    def line_tangent_points_d2(shape: OCC.Core.TopoDS.TopoDS_Edge) -> typing.Tuple[gp_Vec, gp_Vec]:



        adaptor = OCC.Core.BRepAdaptor.BRepAdaptor_Curve(shape)

        t0_d1 = OCC.Core.gp.gp_Vec()
        t0_d2 = OCC.Core.gp.gp_Vec()
        adaptor.D2(
            adaptor.FirstParameter(),
            adaptor.Value(adaptor.FirstParameter()),
            t0_d1,
            t0_d2)

        t1_d1 = OCC.Core.gp.gp_Vec()
        t1_d2 = OCC.Core.gp.gp_Vec()
        adaptor.D2(
            adaptor.LastParameter(),
            adaptor.Value(adaptor.LastParameter()),
            t1_d1,
            t1_d2)

        return t0_d2, t1_d2

    @staticmethod
    def traverse_direct_subshapes(shape: OCC.Core.TopoDS.TopoDS_Shape) -> \
            typing.Generator[OCC.Core.TopoDS.TopoDS_Shape, None, None]:
        iterator = OCC.Core.TopoDS.TopoDS_Iterator(shape)

        while iterator.More():
            shp = iterator.Value()
            yield shp
            iterator.Next()

    @staticmethod
    def traverse_all_subshapes(shape: OCC.Core.TopoDS.TopoDS_Shape) -> \
            typing.Generator[OCC.Core.TopoDS.TopoDS_Shape, None, None]:
        if not isinstance(shape, OCC.Core.TopoDS.TopoDS_Shape):
            raise ValueError("TopoDS_Shape expected")

        iterator = OCC.Core.TopoDS.TopoDS_Iterator(shape)

        while iterator.More():
            shp = iterator.Value()

            yield shp
            for subshp in InterrogateUtils.traverse_all_subshapes(shp):
                yield subshp

            iterator.Next()

    @staticmethod
    def linear_properties(shape: OCC.Core.TopoDS.TopoDS_Shape) -> OCC.Core.GProp.GProp_GProps:
        gprops = OCC.Core.GProp.GProp_GProps()
        OCC.Core.BRepGProp.brepgprop.LinearProperties(shape, gprops)
        return gprops

    @staticmethod
    def surface_properties(shape: OCC.Core.TopoDS.TopoDS_Shape) -> OCC.Core.GProp.GProp_GProps:
        gprops = OCC.Core.GProp.GProp_GProps()
        OCC.Core.BRepGProp.brepgprop.SurfaceProperties(shape, gprops)
        return gprops

    @staticmethod
    def volume_properties(shape: OCC.Core.TopoDS.TopoDS_Shape) -> OCC.Core.GProp.GProp_GProps:
        gprops = OCC.Core.GProp.GProp_GProps()
        OCC.Core.BRepGProp.brepgprop.VolumeProperties(shape, gprops)
        return gprops

    @staticmethod
    def dimension_properties(shape: OCC.Core.TopoDS.TopoDS_Shape) -> OCC.Core.GProp.GProp_GProps:
        ta = OCC.Core.TopAbs
        if shape.ShapeType() in [ta.TopAbs_EDGE, ta.TopAbs_WIRE]:
            return InterrogateUtils.linear_properties(shape)
        elif shape.ShapeType() == ta.TopAbs_FACE:
            return InterrogateUtils.surface_properties(shape)
        elif shape.ShapeType() in [ta.TopAbs_SOLID, ta.TopAbs_SHELL]:
            return InterrogateUtils.volume_properties(shape)
        else:
            raise ValueError(f"Unable to compute geom props for shape: {shape}")

    @staticmethod
    def _center_of_mass(shape: OCC.Core.TopoDS.TopoDS_Shape) -> typing.Tuple[typing.Tuple[float, float, float], float]:
        ta = OCC.Core.TopAbs
        if shape.ShapeType() != ta.TopAbs_COMPOUND:
            dim_props = InterrogateUtils.dimension_properties(shape)
            com_pnt = dim_props.CentreOfMass()
            return (com_pnt.X(), com_pnt.Y(), com_pnt.Z()), dim_props.Mass()
        else:
            com_to_weight = []
            com_total_weight = 0
            for s in InterrogateUtils.traverse_direct_subshapes(shape):
                cw = InterrogateUtils._center_of_mass(s)
                com_to_weight.append(cw)
                com_total_weight += cw[1]

            com_result = [0, 0, 0]

            for com, weight in com_to_weight:
                com_result[0] += com[0] * weight / com_total_weight
                com_result[1] += com[1] * weight / com_total_weight
                com_result[2] += com[2] * weight / com_total_weight

            return com_result, com_total_weight

    @staticmethod
    def center_of_mass(shape: OCC.Core.TopoDS.TopoDS_Shape) -> typing.Tuple[float, float, float]:
        return InterrogateUtils._center_of_mass(shape)[0]

    @staticmethod
    def curve_type(shape: OCC.Core.TopoDS.TopoDS_Edge) -> OCC.Core.GeomAbs.GeomAbs_CurveType:
        return OCC.Core.BRepAdaptor.BRepAdaptor_Curve(shape).GetType()

    @staticmethod
    def is_curve_type(shape: OCC.Core.TopoDS.TopoDS_Edge,
                      expected_type: OCC.Core.GeomAbs.GeomAbs_CurveType):

        return OCC.Core.BRepAdaptor.BRepAdaptor_Curve(shape).GetType() == expected_type

    @staticmethod
    def _is_curve_type(adapter: OCC.Core.BRepAdaptor.BRepAdaptor_Curve,
                       expected_type: OCC.Core.GeomAbs.GeomAbs_CurveType):

        return adapter.GetType() == expected_type

    @staticmethod
    def _get_end_points(adaptor: OCC.Core.BRepAdaptor.BRepAdaptor_Curve):
        return adaptor.Value(adaptor.FirstParameter()), adaptor.Value(adaptor.LastParameter())

    @staticmethod
    def is_straight_line(adaptor: typing.Union[OCC.Core.TopoDS.TopoDS_Edge, OCC.Core.BRepAdaptor.BRepAdaptor_Curve]) -> bool:
        if isinstance(adaptor, OCC.Core.TopoDS.TopoDS_Edge):
            adaptor = OCC.Core.BRepAdaptor.BRepAdaptor_Curve(adaptor)

        if InterrogateUtils._is_curve_type(adaptor, OCC.Core.GeomAbs.GeomAbs_CurveType.GeomAbs_Line):
            return True
        elif InterrogateUtils._is_curve_type(adaptor, OCC.Core.GeomAbs.GeomAbs_CurveType.GeomAbs_BSplineCurve) and \
              adaptor.Degree() == 1:
            return True

        return False

    @staticmethod
    def is_straight_edge(shape: OCC.Core.TopoDS.TopoDS_Edge):
        adaptor = OCC.Core.BRepAdaptor.BRepAdaptor_Curve(shape)
        return InterrogateUtils.is_straight_line(adaptor)

    @staticmethod
    def is_edge_type(shape: OCC.Core.TopoDS.TopoDS_Edge, curve_type: OCC.Core.GeomAbs.GeomAbs_CurveType):
        adaptor = OCC.Core.BRepAdaptor.BRepAdaptor_Curve(shape)
        return InterrogateUtils._is_curve_type(adaptor, curve_type)

    @staticmethod
    def is_dz_line(shape: OCC.Core.TopoDS.TopoDS_Edge, tol: float = 0.0001):
        adaptor = OCC.Core.BRepAdaptor.BRepAdaptor_Curve(shape)
        first_point, last_point = InterrogateUtils._get_end_points(adaptor)

        return InterrogateUtils.is_straight_line(adaptor) and \
               math.fabs(first_point.X() - last_point.X()) < tol and \
               math.fabs(first_point.Y() - last_point.Y()) < tol and \
               math.fabs(first_point.Z() - last_point.Z()) > tol

    @staticmethod
    def is_dy_line(shape: OCC.Core.TopoDS.TopoDS_Edge, tol: float = 0.0001):
        adaptor = OCC.Core.BRepAdaptor.BRepAdaptor_Curve(shape)
        first_point, last_point = InterrogateUtils._get_end_points(adaptor)

        return InterrogateUtils.is_straight_line(adaptor) and \
               math.fabs(first_point.X() - last_point.X()) < tol and \
               math.fabs(first_point.Y() - last_point.Y()) > tol and \
               math.fabs(first_point.Z() - last_point.Z()) < tol

    @staticmethod
    def is_dx_line(shape: OCC.Core.TopoDS.TopoDS_Edge, tol: float = 0.0001):
        adaptor = OCC.Core.BRepAdaptor.BRepAdaptor_Curve(shape)
        first_point, last_point = InterrogateUtils._get_end_points(adaptor)

        return InterrogateUtils.is_straight_line(adaptor) and \
               math.fabs(first_point.X() - last_point.X()) > tol and \
               math.fabs(first_point.Y() - last_point.Y()) < tol and \
               math.fabs(first_point.Z() - last_point.Z()) < tol

    @staticmethod
    def length(shape: OCC.Core.TopoDS.TopoDS_Shape):
        if shape.ShapeType() != OCC.Core.TopAbs.TopAbs_EDGE and shape.ShapeType() != OCC.Core.TopAbs.TopAbs_WIRE:
            raise ValueError(f"ShapeType does not have meaningful length "
                             f"(is a: {Humanize.shape_type(shape.ShapeType())}).")

        gprops = OCC.Core.GProp.GProp_GProps()

        OCC.Core.BRepGProp.brepgprop.LinearProperties(shape, gprops)

        return gprops.Mass()


class FilletUtils:

    @staticmethod
    def fillet(shape: OCC.Core.TopoDS.TopoDS_Shape,
               amount: float,
               edge_selector: typing.Callable[[], typing.Iterable[OCC.Core.TopoDS.TopoDS_Shape]]):

        mkf = OCC.Core.BRepFilletAPI.BRepFilletAPI_MakeFillet(shape)

        for edge in edge_selector():
            mkf.Add(amount, OCC.Core.TopoDS.topods.Edge(edge))

        return mkf.Shape()

    @staticmethod
    def fillet_only(
            shape: OCC.Core.TopoDS.TopoDS_Shape,
            amount: float,
            edge_selector: typing.Callable[[OCC.Core.TopoDS.TopoDS_Edge], bool]):

        mkf = OCC.Core.BRepFilletAPI.BRepFilletAPI_MakeFillet(shape)

        for edge in Explorer.edge_explorer(shape)\
                .filter_by(lambda e: edge_selector(OCC.Core.TopoDS.topods.Edge(e))).get():

            mkf.Add(amount, OCC.Core.TopoDS.topods.Edge(edge))

        return mkf.Shape()

    @staticmethod
    def chamfer_only(
            shape: OCC.Core.TopoDS.TopoDS_Shape,
            amount: float,
            edge_selector: typing.Callable[[OCC.Core.TopoDS.TopoDS_Edge], bool]):

        mkf = OCC.Core.BRepFilletAPI.BRepFilletAPI_MakeChamfer(shape)

        for edge in Explorer.edge_explorer(shape)\
                .filter_by(lambda e: edge_selector(OCC.Core.TopoDS.topods.Edge(e))).get():

            mkf.Add(amount, OCC.Core.TopoDS.topods.Edge(edge))

        return mkf.Shape()

    @staticmethod
    def chamfer(shape: OCC.Core.TopoDS.TopoDS_Shape,
                amount: float,
                edge_selector: typing.Callable[[], typing.Iterable[OCC.Core.TopoDS.TopoDS_Shape]] = None):

        if edge_selector is None:
            edge_selector = Explorer.edge_explorer(shape).get

        mkc = OCC.Core.BRepFilletAPI.BRepFilletAPI_MakeChamfer(shape)

        for edge in edge_selector():
            mkc.Add(amount, OCC.Core.TopoDS.topods.Edge(edge))

        return mkc.Shape()

    @staticmethod
    def vert_to_point(pnt_operator):
        def result(vertex):
            pnt = OCC.Core.BRep.BRep_Tool.Pnt(vertex)
            return pnt_operator(pnt)

        return result

    @staticmethod
    def fillet2d(face: OCC.Core.TopoDS.TopoDS_Face,
                 radius: float,
                 vertex_selector: typing.Callable[[OCC.Core.TopoDS.TopoDS_Vertex], bool] = lambda v: True):
        edges = Explorer(face, OCC.Core.TopAbs.TopAbs_EDGE)\
            .get()

        sae = OCC.Core.ShapeAnalysis.ShapeAnalysis_Edge()

        mkf = OCC.Core.BRepFilletAPI.BRepFilletAPI_MakeFillet2d(face)

        for i in range(0, len(edges)):
            lv = sae.LastVertex(edges[i])
            for j in range(i, len(edges)):
                fv = sae.FirstVertex(edges[j])

                if lv.IsSame(fv) and vertex_selector(fv):
                    mkf.AddFillet(fv, radius)

        last = sae.LastVertex(edges[-1])
        if last.IsSame(sae.FirstVertex(edges[0])) and vertex_selector(last):
            mkf.AddFillet(last, radius)

        try:
            return mkf.Shape()
        except RuntimeError as e:
            print(str(mkf.Status()))
            #OCC.Core.BRepFilletAPI.ChFi2d_ConstructionError
            raise e


class Cleanup:

    @staticmethod
    def simplify_domain(shape: OCC.Core.TopoDS.TopoDS_Shape,
                        unify_edges: bool = True,
                        unify_faces: bool = True,
                        concat_b_splines: bool = False):
        unif = OCC.Core.ShapeUpgrade.ShapeUpgrade_UnifySameDomain()
        unif.Initialize(shape, unify_edges, unify_faces, concat_b_splines)
        unif.Build()
        return unif.Shape()


class DrillOperation:

    def __init__(self, shapes: typing.List[OCC.Core.TopoDS.TopoDS_Shape], is_inverted: bool):
        self.shapes = shapes
        self.is_inverted = is_inverted


class Bit:

    def __init__(self):
        self.is_inverted = False

    def get_cut_tools(self,
                      shape: OCC.Core.TopoDS.TopoDS_Shape,
                      origin: OCC.Core.gp.gp_Pnt,
                      direction: OCC.Core.gp.gp_Dir) -> typing.Generator[DrillOperation, None, None]:
        raise NotImplementedError()

    def invert(self):
        self.is_inverted = not self.is_inverted
        return self

    def then(self, other: Bit) -> Bit:
        return CombineBit(self, other)

    @staticmethod
    def align_tool(tool: OCC.Core.TopoDS.TopoDS_Shape,
                   is_inverted: bool,
                   point: OCC.Core.gp.gp_Pnt,
                   direction: OCC.Core.gp.gp_Dir) -> DrillOperation:

        tool = TransformUtils.transform(tool, lambda t: t.SetRotation(
            OCC.Core.gp.gp_Quaternion(
                OCC.Core.gp.gp_Vec(0, 0, 1),
                OCC.Core.gp.gp_Vec(direction))))

        return DrillOperation(
            [TransformUtils.translate(tool, OCC.Core.gp.gp_Vec(point.XYZ()))],
            is_inverted)


class CombineBit(Bit):

    def __init__(self, *bits: Bit):
        super().__init__()

        if len(bits) == 0:
            raise ValueError()

        self._bits = [b for b in bits]

    def get_cut_tools(self,
            shape: OCC.Core.TopoDS.TopoDS_Shape,
            origin: OCC.Core.gp.gp_Pnt,
            direction: OCC.Core.gp.gp_Dir) -> typing.Generator[DrillOperation, None, None]:

        for bit in self._bits:
            for d in bit.get_cut_tools(shape, origin, direction):
                if self.is_inverted:
                    d.is_inverted = not d.is_inverted

                yield d


class ShapeBit(Bit):

    def __init__(self,
                 shape: OCC.Core.TopoDS.TopoDS_Shape,
                 length_offset: float = 0):
        super().__init__()
        self._shape = shape

        if length_offset != 0:
            self._shape = TransformUtils.translate(self._shape, gp_Vec(0, 0, length_offset))

    def get_cut_tools(self,
            shape: OCC.Core.TopoDS.TopoDS_Shape,
            origin: OCC.Core.gp.gp_Pnt,
            direction: OCC.Core.gp.gp_Dir) -> typing.Generator[DrillOperation, None, None]:

        yield Bit.align_tool(self._shape, self.is_inverted, origin, direction)


class HexPocketBit(ShapeBit):

    def __init__(self, hex_z_span: float = 3, hex_flat_span: float = 1, length_offset: float = 0):
        shape = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeFace(
            GeomUtils.regular_polygon(1, 6)).Shape()
        shape = TransformUtils.scale_to_dimension(shape, hex_flat_span, TransformUtils.Axis.Y)
        shape = GeomUtils.prism(shape, dx=0, dy=0, dz=hex_z_span)

        super().__init__(shape, length_offset)

    def get_cut_tools(self,
            shape: OCC.Core.TopoDS.TopoDS_Shape,
            origin: OCC.Core.gp.gp_Pnt,
            direction: OCC.Core.gp.gp_Dir) -> typing.Generator[DrillOperation, None, None]:

        return super().get_cut_tools(shape, origin, direction)


class CylinderBit(Bit):

    def __init__(self,
                 diameter: float,
                 length: float,
                 length_offset: float = 0):
        super().__init__()
        self._diameter = diameter
        self._length = length
        self._tool = OCC.Core.BRepPrimAPI.BRepPrimAPI_MakeCylinder(diameter / 2, length).Shape()

        if length_offset != 0:
            self._tool = TransformUtils.translate(self._tool, gp_Vec(0, 0, length_offset))

    def get_cut_tools(self,
            shape: OCC.Core.TopoDS.TopoDS_Shape,
            origin: OCC.Core.gp.gp_Pnt,
            direction: OCC.Core.gp.gp_Dir) -> typing.Generator[DrillOperation, None, None]:

        yield Bit.align_tool(self._tool, self.is_inverted, origin, direction)


class CountersinkBit(Bit):

    def __init__(self, diameter: float, length: float, depth_offset: float = 0, d2: float = 0):
        super().__init__()
        self._diameter = diameter
        self._length = length
        self._tool = OCC.Core.BRepPrimAPI.BRepPrimAPI_MakeCone(diameter / 2, d2 / 2, length).Shape()
        self._tool = TransformUtils.translate(self._tool, OCC.Core.gp.gp_Vec(0, 0, depth_offset))

    def get_cut_tools(self,
            shape: OCC.Core.TopoDS.TopoDS_Shape,
            origin: OCC.Core.gp.gp_Pnt,
            direction: OCC.Core.gp.gp_Dir) -> typing.Iterable[OCC.Core.TopoDS.TopoDS_Shape]:

        yield Bit.align_tool(self._tool, self.is_inverted, origin, direction)


class Drill:

    def __init__(self, bit: Bit, direction: typing.Tuple[float, float, float] = None):
        self._operations: typing.List[typing.Callable[[OCC.Core.TopoDS.TopoDS_Shape], DrillOperation]] = []
        self._default_bit = bit

        if direction is None:
            direction = (0, 0, -1)

        self._default_direction = direction

    def point_from(self,
                   shape,
                   x: float = 0,
                   y: float = 0,
                   z: float = 0,
                   dx: float = None,
                   dy: float = None,
                   dz: float = None,
                   bit: Bit = None):

        dx, dy, dz = self._default_direction if dx is None else (dx, dy, dz)

        ip = Drill.get_intersecting_points(shape, x, y, z, dx, dy, dz)

        if len(ip.items()) == 0:
            LOGGER.warning("No intersecting points found for point")
            return self

        start_point = ip[min(ip.keys())]

        self.point(start_point.X(), start_point.Y(), start_point.Z(), dx, dy, dz, bit)

        return self

    def square_pattern_centered(self,
                                shape: OCC.Core.TopoDS.TopoDS_Shape,
                                x: float = 0,
                                y: float = 0,
                                z: float = 0,
                                du: float = 32,
                                dv: float = None,
                                axis: OCC.Core.gp.gp_Ax2 = OCC.Core.gp.gp.XOY(),
                                u_count: int = 2,
                                v_count: int = 2):

        dv = du if dv is None else dv

        u_unit = OCC.Core.gp.gp_Vec(axis.XDirection()).Scaled(du)
        v_unit = OCC.Core.gp.gp_Vec(axis.YDirection()).Scaled(dv)

        u_offset = OCC.Core.gp.gp_Vec(axis.XDirection()).Scaled(-(u_count - 1) * du / 2)
        v_offset = OCC.Core.gp.gp_Vec(axis.YDirection()).Scaled(-(v_count - 1) * dv / 2)

        origin = OCC.Core.gp.gp_Pnt(x, y, z).Translated(u_offset).Translated(v_offset)

        l_xyz = axis.Direction().X(), axis.Direction().Y(), axis.Direction().Z()

        for i_u in range(0, u_count):
            for i_v in range(0, v_count):
                p = origin.Translated(u_unit.Scaled(i_u)).Translated(v_unit.Scaled(i_v))
                self.point_from(shape, p.X(), p.Y(), p.Z(), *l_xyz)

        return self


    def point(self,
              x: float, y: float, z: float,
              dx: float = 0, dy: float = 0, dz: float = 0,
              bit: Bit = None):

        if bit is None:
            bit = self._default_bit

        def get_cut_tools(shape: OCC.Core.TopoDS.TopoDS_Shape) -> typing.List[DrillOperation]:
            return [d for d in bit.get_cut_tools(
                shape,
                OCC.Core.gp.gp_Pnt(x, y, z),
                OCC.Core.gp.gp_Dir(OCC.Core.gp.gp_Vec(dx, dy, dz).Normalized()))]

        self._operations.append(get_cut_tools)

        return self

    def get_drill_ops(self, shape: OCC.Core.TopoDS.TopoDS_Shape) -> typing.List[DrillOperation]:
        cut_tools = []
        for op in self._operations:
            cut_tools += op(shape)

        return cut_tools

    def perform(self, shape: OCC.Core.TopoDS.TopoDS_Shape) -> OCC.Core.TopoDS.TopoDS_Shape:
        result = shape
        for op in self.get_drill_ops(shape):
            if op.is_inverted:
                result = BoolUtils.incremental_fuse([result] + op.shapes)
            else:
                result = BoolUtils.incremental_cut(result, op.shapes)

        return result

    @staticmethod
    def get_intersecting_points(shape,
                          x: float, y:float, z:float,
                          dx: float, dy: float, dz: float):
        # create the infinite wire

        start_line = OCC.Core.GC.GC_MakeLine(
            OCC.Core.gp.gp_Pnt(x, y, z),
            OCC.Core.gp.gp_Dir(dx, dy, dz))

        start_wire = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(start_line.Value()).Shape()

        vertexes = []
        for f in Explorer.face_explorer(shape).get():
            common = OCC.Core.BRepAlgoAPI.BRepAlgoAPI_Section(f, start_wire).Shape()
            intersections = Explorer.vertex_explorer(common).get()

            vertexes += [OCC.Core.BRep.BRep_Tool.Pnt(v) for v in intersections]


        result = {}
        for v in vertexes:
            proj = OCC.Core.GeomAPI.GeomAPI_ProjectPointOnCurve(v, start_line.Value())
            result[proj.Parameter(1)] = v

        return result


class MathUtils:


    @staticmethod
    def lerp(x0: float = 0,
             y0: float = 0,
             z0: float = 0,
             x1: float = 0,
             y1: float = 0,
             z1: float = 0,
             coordinate_proportional: typing.Optional[float] = None,
             coordinate_absolute: typing.Optional[float] = None) -> typing.Tuple[float, float, float]:

        if coordinate_proportional is None and coordinate_absolute is None:
            raise ValueError("One of coordinate_proportional/coordinate_absolute must be supplied.")

        if coordinate_proportional is not None and coordinate_absolute is not None:
            raise ValueError("Only one of coordinate_proportional/coordinate_absolute must be supplied.")

        dx, dy, dz = x1 - x0, y1 - y0, z1 - z0

        length = math.hypot(dx, dy, dz)

        if length == 0:
            raise ValueError("Cannot interpolate on zero length")

        target_length = coordinate_absolute if coordinate_proportional is None else \
            (coordinate_proportional * length)

        x_result = x0 + target_length * dx / length
        y_result = y0 + target_length * dy / length
        z_result = z0 + target_length * dz / length

        return x_result, y_result, z_result


class VisualizationUtils:
    edge_cone = OCC.Core.BRepPrimAPI.BRepPrimAPI_MakeCone(0.5, 0, 1).Shape()
    norm_cone = GeomUtils.make_compound(
        OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(gp_Pnt(0, 0, 0), gp_Pnt(0, 0, 5)).Shape(),
        TransformUtils.translate(
            OCC.Core.BRepPrimAPI.BRepPrimAPI_MakeCone(0.5, 0, 1).Shape(),
            gp_Vec(0, 0, 4))
        )

    @staticmethod
    def display_face(face: OCC.Core.TopoDS.TopoDS_Face, show_face_normals: bool):
        if show_face_normals:
            surf_props = InterrogateUtils.surface_properties(face)

            normal_pnt, normal_dir = InterrogateUtils.face_normal(
                face,
                uv_mapper=lambda umn, umx, vmn, vmx: (umn + (umx - umn) / 2, vmn + (vmx - vmn) / 2))

            normal_vec = gp_Vec(normal_dir)

            if face.Orientation() == OCC.Core.TopAbs.TopAbs_Orientation.TopAbs_REVERSED:
                normal_vec = normal_vec.Multiplied(-1)

            norm_cone = TransformUtils.transform(VisualizationUtils.norm_cone,
                                                 lambda t: t.SetRotation(OCC.Core.gp.gp_Quaternion(gp_Vec(0, 0, 1), normal_vec)))

            norm_cone = TransformUtils.translate(norm_cone, gp_Vec(gp_Pnt(0, 0, 0), normal_pnt))

            return [norm_cone]

        return []

    @staticmethod
    def display_edge(edge: OCC.Core.TopoDS.TopoDS_Edge, show_edge_orientations: bool, show_edge_endpoints: bool):
        adaptor = OCC.Core.BRepAdaptor.BRepAdaptor_Curve(edge)

        to_return = []

        if show_edge_orientations:
            param = adaptor.FirstParameter() + 0.5 * (adaptor.LastParameter() - adaptor.FirstParameter())

            pnt_pos = adaptor.Value(param)

            vec_tangent = gp_Vec()
            adaptor.D1(param, pnt_pos, vec_tangent)

            edge_cone = TransformUtils.translate(VisualizationUtils.edge_cone, gp_Vec(0, 0, -0.5))
            edge_cone = TransformUtils.transform(edge_cone, lambda t: t.SetRotation(OCC.Core.gp.gp_Quaternion(gp_Vec(0, 0, 1), vec_tangent)))
            edge_cone = TransformUtils.translate(edge_cone, OCC.Core.gp.gp_Vec(OCC.Core.gp.gp.Origin(), pnt_pos))

            to_return.append(edge_cone)

        if show_edge_endpoints:
            start = adaptor.Value(adaptor.FirstParameter())
            end = adaptor.Value(adaptor.LastParameter())

            v0 = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeVertex(start).Shape()
            v1 = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeVertex(end).Shape()

            to_return.append(v0)
            to_return.append(v1)

        return to_return

    @staticmethod
    def arrange(*shapes: OCC.Core.TopoDS.TopoDS_Shape, spacing: float = 1) -> \
        typing.Generator[OCC.Core.TopoDS.TopoDS_Shape, None, None]:

        x_min = 0

        for s in shapes:
            ext = Extents(s)
            dx = x_min - ext.x_min
            yield TransformUtils.translate(s, vec(dx, 0, 0))
            x_min += ext.x_span
            x_min += spacing


    @staticmethod
    def visualize(*shapes: OCC.Core.TopoDS.TopoDS_Shape,
                  labels: typing.Dict[str, typing.List[OCC.Core.TopoDS.TopoDS_Shape]] = None,
                  show_edge_orientations: bool = False,
                  show_edge_endpoints: bool = False,
                  show_face_normals: bool = False,
                  arrange_shapes: bool = False,
                  display=None):

        if len(shapes) == 0:
            raise ValueError("No shapes to visualize.")

        from OCC.Display.SimpleGui import init_display
        import OCC.Display.OCCViewer

        start_display: typing.Callable[[], None] = None
        if display is None:
            display: OCC.Display.OCCViewer.Viewer3d = None
            display, start_display, add_menu, add_function_to_menu = init_display()
            # display.Context.SetDeviationAngle(0.01)
            # display.Context.SetDeviationCoefficient(0.01)
            display.SetPerspectiveProjection()
            display.EnableAntiAliasing()
            display.set_bg_gradient_color([0, 0, 0], [0, 0, 0])
        elif not isinstance(display, OCC.Display.OCCViewer.Viewer3d):
            raise ValueError("Display must be of type Viewer3d")

        if arrange_shapes:
            VisualizationUtils.visualize(
                *[s for s in VisualizationUtils.arrange(*shapes)],
                show_edge_endpoints=show_edge_endpoints,
                show_face_normals=show_face_normals,
                show_edge_orientations=show_edge_orientations,
                arrange_shapes=False,
                display=display)
            return

        if labels is None:
            labels = {}

        for shape in shapes:
            face_annotations = []
            edge_annotations = []

            for f in Explorer.face_explorer(shape).get():
                face_annotations += VisualizationUtils.display_face(f, show_face_normals)

            for e in Explorer.edge_explorer(shape).get():
                edge_annotations += VisualizationUtils.display_edge(e, show_edge_orientations, show_edge_endpoints)

            ais_face_annotations = display.DisplayShape(GeomUtils.make_compound(*face_annotations), color="GREEN")
            ais_edge_annotations = display.DisplayShape(GeomUtils.make_compound(*edge_annotations), color="RED")

            for s in ais_face_annotations:
                display.GetContext().Deactivate(s)

            for s in ais_edge_annotations:
                display.GetContext().Deactivate(s)

            display.DisplayShape(shape)

        for label, shapelist in labels.items():
            for shape in shapelist:
                display_pnt = pnt(*InterrogateUtils.center_of_mass(shape))

                display.DisplayMessage(display_pnt, label, message_color=(1, 1, 1))
                display.DisplayShape(shape, color="BLUE")

        if start_display is not None:
            start_display()


class Align:

    align_re = re.compile("[xyz]+_(mid|min|max)_to_(mid|min|max)")

    def __init__(self, shape: OCC.Core.TopoDS.TopoDS_Shape):
        if not isinstance(shape, OCC.Core.TopoDS.TopoDS_Shape):
            raise ValueError("Argument not a shape")

        self._shape = shape

    def __getattr__(self, item: str):
        if not Align.align_re.fullmatch(item):
            raise AttributeError()

        args = item.split("_")

        axes = args[0]

        arg_from = args[1]
        arg_to = args[3]

        shape_from_ext = Extents(self._shape)

        def return_func(dest_shape: OCC.Core.TopoDS.TopoDS_Shape,
                        translate_consumer: typing.Callable[[float, float, float], None] = None):
            dest_shape_ext = Extents(dest_shape)

            offsets = {}

            for a in axes:
                if a in offsets:
                    raise ValueError("Duplicate axis: " + a)

                a_from = getattr(shape_from_ext, a + "_" + arg_from)
                a_to = getattr(dest_shape_ext, a + "_" + arg_to)

                offsets[a] = a_to - a_from

            offset_tuple = (
                offsets.get("x", 0),
                offsets.get("y", 0),
                offsets.get("z", 0)
            )

            if translate_consumer is not None:
                translate_consumer(*offset_tuple)

            return TransformUtils.translate(self._shape, OCC.Core.gp.gp_Vec(*offset_tuple))

        return return_func


class GPUtils:

    @staticmethod
    def xyz(vector_like: typing.Union[gp_Pnt, gp_Dir, gp_Vec, gp_XYZ]) -> typing.Tuple[float, float, float]:
        return vector_like.X(), vector_like.Y(), vector_like.Z()


class SetPlaceableShape:

    def __init__(self, shape: OCC.Core.TopoDS.TopoDS_Shape):
        TypeValidator.assert_is_any_shape(shape)

        self._shape = shape

    @property
    def shape(self) -> OCC.Core.TopoDS.TopoDS_Shape:
        return self._shape

    def __str__(self) -> str:
        if self.shape.Orientable():
            orientation_str = f"orientation({Humanize.orientation(self.shape.Orientation())})"
        else:
            orientation_str = ""

        return f"SetPlaceableShape(shape_class({str(self._shape)}) shape_hash({str(hash(self))}) shape_id({str(id(self._shape))}) id({id(self)})) {orientation_str}"

    def __repr__(self):
        return str(self)

    def __hash__(self) -> int:
        return UtilWrapper.shape_map_hasher_hash_code(self._shape)

    def __eq__(self, other: SetPlaceableShape) -> bool:
        return UtilWrapper.shape_map_hasher_equal(self.shape, other.shape)


class SetPlaceablePart:

    UPPER_BOUND = 10000

    def __init__(self, part: Part):
        self._part = part
        self._sps = SetPlaceableShape(part.shape)

    @property
    def part(self) -> Part:
        return self._part

    def __hash__(self) -> int:
        return self._sps.__hash__()

    def __eq__(self, other: SetPlaceablePart) -> bool:
        return self._sps.__eq__(other._sps)