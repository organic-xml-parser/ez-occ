%include "std_vector.i"
%include "std_map.i"
%include "std_string.i"
%include "/third_party/pythonocc-core/src/SWIG_files/common/OccHandle.i"

%module(package="util_wrapper") util_wrapper
%feature("flatnested", "1");
%feature("autodoc", "1");
%{
#include <util_wrapper.h>
#include <surface_mapper.h>
%}

%template(StringList) std::vector<std::string>;
%template(ShapeList) std::vector<TopoDS_Shape>;

class UtilWrapper {
public:
    static std::string shape_to_string(const TopoDS_Shape& shape);

    static int shape_map_hasher_hash_code(const TopoDS_Shape& shape);

    static bool shape_map_hasher_equal(const TopoDS_Shape& a, const TopoDS_Shape& b);
};

class SurfaceMapperWrapper {

public:
    static BRepBuilderAPI_MakeFace create_make_face(const TopoDS_Wire& wire,
                                                    const BRepAdaptor_Surface& surface_adaptor);

    static BRepBuilderAPI_MakeEdge create_make_edge(const Geom2d_Curve& trimmed_curve,
                                                    const BRepAdaptor_Surface& surface_adaptor);

    static bool is_planar_surface(const BRepAdaptor_Surface& surface_adaptor);

    static BRepBuilderAPI_MakeEdge project_curve_to_surface(
        const BRepAdaptor_Curve& edge,
        const BRepAdaptor_Surface& face);

    static gp_Pnt2d project_point_to_surface(
        const gp_Pnt& point,
        const BRepAdaptor_Surface& surf);
};