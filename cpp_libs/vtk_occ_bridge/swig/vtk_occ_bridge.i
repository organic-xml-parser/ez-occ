%include "std_vector.i"
%include "std_string.i"
%include "/third_party/pythonocc-core/src/SWIG_files/common/OccHandle.i"

%module(package="vtk_occ_bridge") vtk_occ_bridge
%feature("flatnested", "1");
%feature("autodoc", "1");
%{
#include <vtkPythonUtil.h>
#include <vtk_occ_bridge.h>
#include <iostream>

%}


%define VTK_SMARTPOINTER(vtk_t)
%{
#include <vtk_t##.h>
%}
%typemap(out) vtkSmartPointer<vtk_t>
{
    vtkSmartPointer<vtkObjectBase> castObj = static_cast<vtkSmartPointer<vtk_t>>($1);
    $result = vtkPythonUtil::GetObjectFromPointer(castObj);
}
%typemap(typecheck, precedence=SWIG_TYPECHECK_POINTER) vtk_t*
{
  $1 = vtkPythonUtil::GetPointerFromObject($input,#vtk_t) ? 1 : 0;
}
%enddef

VTK_SMARTPOINTER(vtkPolyDataMapper)
VTK_SMARTPOINTER(vtkOpenGLPolyDataMapper)

%wrap_handle(Poly_PolygonOnTriangulation)
%wrap_handle(Poly_Triangulation)

class Visualization {
public:

    class PotResult {
    public:
        PotResult(
            opencascade::handle<Poly_PolygonOnTriangulation> pot,
            opencascade::handle<Poly_Triangulation> pt,
            TopLoc_Location loc);

        opencascade::handle<Poly_PolygonOnTriangulation> pot();
        opencascade::handle<Poly_Triangulation> pt();
        TopLoc_Location loc();
        bool hasValue();
    };


    static PotResult processEdgeTest(TopoDS_Edge& edge);

    static vtkSmartPointer<vtkPolyDataMapper> getDataMapper(TopoDS_Shape& sh);
};
