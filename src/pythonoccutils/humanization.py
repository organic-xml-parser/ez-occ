import OCC.Core.TopAbs
import OCC.Core.GeomAbs

class Humanize:

    @staticmethod
    def curve_type(curve_type: OCC.Core.GeomAbs.GeomAbs_CurveType):
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
