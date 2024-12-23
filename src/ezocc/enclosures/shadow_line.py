import typing

from OCC.Core.TopAbs import TopAbs_REVERSED
from OCC.Core.gp import gp_Pnt, gp_Dir

from ezocc.alg.wires_from_edges import WiresFromEdges
from ezocc.cad.visualization_widgets.visualization_widgets import PartWidgets
from ezocc.part_manager import Part

import math

from OCC.Core.gp import gp_Pnt2d, gp_Vec2d, gp_Vec, gp_Pnt, gp_XY, gp_Ax1

from ezocc.constants import Constants
from ezocc.humanization import Humanize
from ezocc.occutils_python import InterrogateUtils, WireSketcher
from ezocc.part_cache import InMemoryPartCache
from ezocc.part_manager import PartCache, Part, PartFactory
import OCC.Core.BRep
import OCC.Core.BRepAdaptor
import OCC.Core.Geom2d
import OCC.Core.GeomAPI
import OCC.Core.BRepBuilderAPI
import OCC.Core.GeomProjLib
import OCC.Core.GeomAdaptor

from util_wrapper_swig import SurfaceMapperWrapper

class ShadowLine:

    @staticmethod
    def shadow_line_spine(to_cut: Part, cut_plane: Part) -> Part:
        spine = cut_plane.bool.section(to_cut)\
            .cleanup(concat_b_splines=True, fix_small_face=True) #.make.face()

        wires = WiresFromEdges(to_cut.cache_token.get_cache()).get_wires(*spine.explore.edge.get())

        cut_wires = wires.explore.wire.order_by(lambda w: -len(w.explore.edge.get())).get()

        if len(cut_wires) != 2:
            raise ValueError(f"{len(cut_wires)} wires were found after slicing with cut plane, instead of expected (2)."
                             f" Either the cut plane does not encompass the part, or the part does not contain a "
                             f"cavity.")

        wire_outer, wire_inner = cut_wires

        return wire_inner.make.wire()

    @staticmethod
    def find_edge_normal_vector(shadow_line_spine: Part, cut_plane: Part) -> typing.Tuple[gp_Pnt, gp_Dir, gp_Dir]:
        if not shadow_line_spine.inspect.is_wire():
            raise ValueError("Expected wire input")

        cache = shadow_line_spine.cache_token.get_cache()

        # find an edge midpoint
        # calculate the normal to that edge
        # make this the basis for the shadow line tool
        line_edge = shadow_line_spine.explore.edge.get()[0]
        line_edge.cleanup.build_curves_3d()

        cut_plane_face = next(f for f in cut_plane.explore.face.get() if f.bool.intersects(line_edge))
        cut_plane_face.cleanup.build_curves_3d()

        #try:
        #    curve = OCC.Core.BRepAdaptor.BRepAdaptor_Curve(line_edge.shape)
        #    surface = OCC.Core.BRepAdaptor.BRepAdaptor_Surface(cut_plane_face.shape)
        #    curve_edge = SurfaceMapperWrapper.project_curve_to_surface(curve, surface)

        #    curve = OCC.Core.BRepAdaptor.BRepAdaptor_CompCurve(curve_edge.Edge(), cut_plane_face.shape)

        #except:
        #    line_edge.print().preview(cut_plane_face)
        #    raise

        midpoint = InterrogateUtils.line_point(line_edge.shape, 0)
        midpoint_dir = InterrogateUtils.line_tangent_point(line_edge.shape, 0)

        surf = OCC.Core.BRepAdaptor.BRepAdaptor_Surface(cut_plane_face.shape)

        uv = SurfaceMapperWrapper.project_point_to_surface(midpoint, surf)

        def normal_mapper(umin, vmin, umax, vmax):
            return uv.X(), uv.Y()

        wall_parallel_origin, wall_parallel_dir = InterrogateUtils.face_normal(cut_plane_face.shape, uv_mapper=normal_mapper)

        wall_normal_dir = midpoint_dir.Rotated(gp_Ax1(midpoint, wall_parallel_dir), math.radians(90))\
            .Normalized()

        if cut_plane_face.inspect.orientation() == TopAbs_REVERSED:
            wall_normal_dir = wall_normal_dir.Reversed()

        wall_normal_dir = gp_Dir(*Humanize.xyz(wall_normal_dir))

        normal_arrow = WireSketcher(*Humanize.xyz(midpoint))\
            .line_to(*Humanize.xyz(wall_normal_dir), is_relative=True)\
            .get_wire_part(cache)

        parallel_arrow = WireSketcher(*Humanize.xyz(wall_parallel_origin)) \
            .line_to(*Humanize.xyz(wall_parallel_dir), is_relative=True) \
            .get_wire_part(cache)

        # for debugging normals
        #normal_arrow.preview(parallel_arrow, cut_plane, line_edge)

        return midpoint, wall_normal_dir, wall_parallel_dir
