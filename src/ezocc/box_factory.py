import math
import sys
import OCC
import typing
import OCC.Core as occ
import OCC.Core.BRepBuilderAPI
import OCC.Core.BRepPrimAPI
import OCC.Core.BRepAlgoAPI
import OCC.Core.BRepOffsetAPI
import OCC.Core.BRepFilletAPI
import OCC.Core.BOPAlgo
import OCC.Core.BRepTools as BRepTools
import OCC.Core.ShapeUpgrade
import OCC.Core.TopOpeBRepBuild
import OCC.Core.GeomAbs
import occutils
from OCC.Core.gp import gp_Trsf
import OCC.Core.TopExp as te
import OCC.Core.TopAbs as ta
import OCC.Core.gp as gp
from OCC.Core.gp import gp_Vec as vec
from OCC.Core.gp import gp_Pnt as pnt
import OCC.Core.TopoDS as TopoDS

import occutils as oc

import hole_factory
import occutils_python
import occutils_python as op


class BoxFactory:

    @staticmethod
    def make_box(
            interior_size: typing.Tuple[float, float, float],
            wall_thicknesses: typing.Tuple[float, float, float],
            post_points: typing.Tuple[float, float],
            post_radius: float,
            post_height: float,
            post_hole_radius: float,
            exterior_fillet: float,
            include_lid: bool):


        # free space within the box
        #interior_size = (50 + 6, 70 + 12, 36)
        #wall_thicknesses = (6, 6, 4)

        #post_points = (23, 33)

        interior = op.GeomUtils.square_centered(
            gp.gp_Origin(), interior_size[0], interior_size[1], consumer=lambda ws: ws.get_prism(vec(0, 0, interior_size[2])))

        exterior_xy = op.GeomUtils.square_centered(
            gp.gp_Origin(), interior_size[0] + wall_thicknesses[0] * 2, interior_size[1] + wall_thicknesses[1] * 2)

        exterior = op.BoolUtils.incremental_fuse([
            exterior_xy.get_prism(vec(0, 0, -wall_thicknesses[2])),
            exterior_xy.get_prism(vec(0, 0, interior_size[2] + (wall_thicknesses[2] if include_lid else 0)))])
        exterior = op.Cleanup.simplify_domain(exterior)

        if exterior_fillet != 0:
            exterior = op.FilletUtils.fillet_only(exterior, exterior_fillet, lambda e: op.InterrogateUtils.is_dz_line(e))

        result = op.BoolUtils.incremental_cut(exterior, [interior])

        #lid, case = op.GeomUtils.plane_cut(
        #    result,
        #    gp.gp_Pnt(0, 0, interior_size[2]), gp.gp_Dir(0, 0, 1),
        #    plane_thickness_a=0,
        #    plane_thickness_b=0.5)

        corner_post = op.GeomUtils.square(post_points[0] - post_radius, post_points[1] - post_radius, interior_size[0] / 2, interior_size[1] / 2).get_face()
        corner_post = op.FilletUtils.fillet2d(corner_post, post_radius,
                                              op.FilletUtils.vert_to_point(lambda p: p.X() < interior_size[0] / 2 and p.Y() < interior_size[1] / 2))
        corner_post = op.GeomUtils.prism(corner_post, 0, 0, post_height)
        corner_post = op.MirrorUtils.mirror_xy(corner_post)
        corner_post = op.Drill(op.CylinderBit(diameter=post_hole_radius * 2, length=post_height)) \
            .point_from(corner_post, x=-post_points[0], y=-post_points[1]) \
            .point_from(corner_post, x=post_points[0], y=-post_points[1]) \
            .point_from(corner_post, x=-post_points[0], y=post_points[1]) \
            .point_from(corner_post, x=post_points[0], y=post_points[1])\
            .perform(corner_post)

        result = op.BoolUtils.incremental_fuse([result, corner_post])

        return result
