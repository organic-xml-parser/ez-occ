import typing

import OCC.Core.TopAbs
import OCC.Core.GeomAbs
from OCC.Core.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone, GeomAbs_Sphere, GeomAbs_Torus, \
    GeomAbs_BezierSurface, GeomAbs_BSplineSurface, GeomAbs_SurfaceOfExtrusion, GeomAbs_SurfaceOfRevolution, \
    GeomAbs_OtherSurface, GeomAbs_OffsetSurface
from OCC.Core.gp import gp_Pnt, gp_Dir, gp_Vec, gp_XYZ, gp_Pnt2d, gp_Vec2d, gp_Dir2d, gp_XY


class Humanize:

    @staticmethod
    def xy(xy: typing.Union[gp_Pnt2d, gp_Vec2d, gp_Dir2d, gp_XY]):
        return xy.X(), xy.Y()

    @staticmethod
    def xyz(xyz: typing.Union[gp_Pnt, gp_Vec, gp_Dir, gp_XYZ]):
        return xyz.X(), xyz.Y(), xyz.Z()

    @staticmethod
    def curve_type(curve_type: OCC.Core.GeomAbs.GeomAbs_CurveType) -> str:
        GeomAbs_Line = 0
        GeomAbs_Circle = 1
        GeomAbs_Ellipse = 2
        GeomAbs_Hyperbola = 3
        GeomAbs_Parabola = 4
        GeomAbs_BezierCurve = 5
        GeomAbs_BSplineCurve = 6
        GeomAbs_OffsetCurve = 7
        GeomAbs_OtherCurve = 8

        if curve_type == OCC.Core.GeomAbs.GeomAbs_CurveType.GeomAbs_Line:
            return "line"

        if curve_type == OCC.Core.GeomAbs.GeomAbs_CurveType.GeomAbs_Circle:
            return "circle"

        if curve_type == OCC.Core.GeomAbs.GeomAbs_CurveType.GeomAbs_Ellipse:
            return "ellipse"

        if curve_type == OCC.Core.GeomAbs.GeomAbs_CurveType.GeomAbs_Hyperbola:
            return "hyperbola"

        if curve_type == OCC.Core.GeomAbs.GeomAbs_CurveType.GeomAbs_Parabola:
            return "parabola"

        if curve_type == OCC.Core.GeomAbs.GeomAbs_CurveType.GeomAbs_BezierCurve:
            return "bezier_curve"

        if curve_type == OCC.Core.GeomAbs.GeomAbs_CurveType.GeomAbs_BSplineCurve:
            return "b_spline_curve"

        if curve_type == OCC.Core.GeomAbs.GeomAbs_CurveType.GeomAbs_OffsetCurve:
            return "offset_curve"

        if curve_type == OCC.Core.GeomAbs.GeomAbs_CurveType.GeomAbs_OtherCurve:
            return "other_curve"

        raise ValueError(f"Unknown curve type: {curve_type}")

    @staticmethod
    def shape_type(st: OCC.Core.TopAbs.TopAbs_ShapeEnum) -> str:
        if st == OCC.Core.TopAbs.TopAbs_COMPOUND:
            return "compound"

        if st == OCC.Core.TopAbs.TopAbs_COMPSOLID:
            return "compsolid"

        if st == OCC.Core.TopAbs.TopAbs_SOLID:
            return "solid"

        if st == OCC.Core.TopAbs.TopAbs_SHELL:
            return "shell"
        if st == OCC.Core.TopAbs.TopAbs_FACE:
            return "face"

        if st == OCC.Core.TopAbs.TopAbs_WIRE:
            return "wire"

        if st == OCC.Core.TopAbs.TopAbs_EDGE:
            return "edge"

        if st == OCC.Core.TopAbs.TopAbs_VERTEX:
            return "vertex"

        if st == OCC.Core.TopAbs.TopAbs_SHAPE:
            return "shape"

        raise ValueError(f"Unkonwn shape type: {st}")

    @staticmethod
    def surface_type(surface_type: OCC.Core.GeomAbs.GeomAbs_SurfaceType) -> str:
        types = {
            GeomAbs_Plane: "GeomAbs_Plane",
            GeomAbs_Cylinder: "GeomAbs_Cylinder",
            GeomAbs_Cone: "GeomAbs_Cone",
            GeomAbs_Sphere: "GeomAbs_Sphere",
            GeomAbs_Torus: "GeomAbs_Torus",
            GeomAbs_BezierSurface: "GeomAbs_BezierSurface",
            GeomAbs_BSplineSurface: "GeomAbs_BSplineSurface",
            GeomAbs_SurfaceOfRevolution: "GeomAbs_SurfaceOfRevolution",
            GeomAbs_SurfaceOfExtrusion: "GeomAbs_SurfaceOfExtrusion",
            GeomAbs_OffsetSurface: "GeomAbs_OffsetSurface",
            GeomAbs_OtherSurface: "GeomAbs_OtherSurface"
        }

        return types[surface_type]

    @staticmethod
    def orientation(orientation: OCC.Core.TopAbs.TopAbs_Orientation) -> str:
        types = {
            OCC.Core.TopAbs.TopAbs_FORWARD: "TopAbs_FORWARD",
            OCC.Core.TopAbs.TopAbs_REVERSED: "TopAbs_REVERSED",
            OCC.Core.TopAbs.TopAbs_INTERNAL: "TopAbs_INTERNAL",
            OCC.Core.TopAbs.TopAbs_EXTERNAL: "TopAbs_EXTERNAL"
        }

        return types[orientation]

    @staticmethod
    def orientation_shorthand(orientation: OCC.Core.TopAbs.TopAbs_Orientation) -> str:
        types = {
            OCC.Core.TopAbs.TopAbs_FORWARD: "FWD",
            OCC.Core.TopAbs.TopAbs_REVERSED: "REV",
            OCC.Core.TopAbs.TopAbs_INTERNAL: "INT",
            OCC.Core.TopAbs.TopAbs_EXTERNAL: "EXT"
        }

        return types[orientation]
