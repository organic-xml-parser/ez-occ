#ifndef SURFACE_MAPPER_H
#define SURFACE_MAPPER_H

#include <Geom2d_TrimmedCurve.hxx>
#include <BRepAdaptor_Surface.hxx>
#include <BRepAdaptor_Curve.hxx>
#include <TopoDS_Wire.hxx>
#include <BRepBuilderAPI_MakeEdge.hxx>
#include <BRepBuilderAPI_MakeFace.hxx>
#include <GeomLib_IsPlanarSurface.hxx>
#include <ShapeConstruct_ProjectCurveOnSurface.hxx>

// todo: this is a workaround to a similar issue to: https://github.com/tpaviot/pythonocc-core/issues/1218
class SurfaceMapperWrapper {

public:
    static BRepBuilderAPI_MakeFace create_make_face(const TopoDS_Wire& wire,
                                                    const BRepAdaptor_Surface& surface_adaptor) {

        return BRepBuilderAPI_MakeFace(
            surface_adaptor.Surface().Surface(),
            wire);
    }

    static BRepBuilderAPI_MakeEdge create_make_edge(const Geom2d_Curve& trimmed_curve,
                                                    const BRepAdaptor_Surface& surface_adaptor) {

        return BRepBuilderAPI_MakeEdge(
            opencascade::handle<Geom2d_Curve>::DownCast(trimmed_curve.Copy()),
            surface_adaptor.Surface().Surface());
    }

    static BRepBuilderAPI_MakeEdge project_curve_to_surface(
        const BRepAdaptor_Curve& edge,
        const BRepAdaptor_Surface& face) {

        auto construct = ShapeConstruct_ProjectCurveOnSurface();

        construct.SetSurface(face.Surface().Surface());
        construct.BuildCurveMode() = true;

        opencascade::handle<Geom2d_Curve> curve2d = nullptr;

        auto input_curve = opencascade::handle<Geom_Curve>::DownCast(edge.Curve().Curve()->Copy());
        construct.PerformByProjLib(
            input_curve,
            edge.FirstParameter(),
            edge.LastParameter(),
            curve2d);

        return BRepBuilderAPI_MakeEdge(
            opencascade::handle<Geom2d_Curve>::DownCast((*curve2d).Copy()),
            face.Surface().Surface());
    }

    static bool is_planar_surface(const BRepAdaptor_Surface& surface_adaptor) {
        return GeomLib_IsPlanarSurface(surface_adaptor.Surface().Surface()).IsPlanar();
    }

};

#endif