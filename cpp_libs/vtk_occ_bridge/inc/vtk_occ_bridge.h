#ifndef VTK_OCC_BRIDGE_H
#define VTK_OCC_BRIDGE_H

#include <IVtkTools_ShapeDataSource.hxx>
#include <IVtkOCC_Shape.hxx>
#include <vtkPolyDataMapper.h>
#include <vtkPolyDataAlgorithm.h>
#include <Poly_PolygonOnTriangulation.hxx>
#include <Poly_Triangulation.hxx>
#include <TopLoc_Location.hxx>
#include <BRep_Tool.hxx>

#include <iostream>

class Visualization {
public:

    class PotResult {
        Handle(Poly_PolygonOnTriangulation) _pot;
        Handle(Poly_Triangulation) _pt;
        TopLoc_Location _loc;

    public:
        PotResult(Handle(Poly_PolygonOnTriangulation) pot,
                  Handle(Poly_Triangulation) pt,
                  TopLoc_Location loc) : _pot(pot), _pt(pt), _loc(loc) {}


        Handle(Poly_PolygonOnTriangulation) pot() {
            return _pot;
        }

        Handle(Poly_Triangulation) pt() {
            return _pt;
        }

        TopLoc_Location loc() {
            return _loc;
        }

        bool hasValue() {
            return !_pot.IsNull();
        }

    };


    //static vtkPolyDataAlgorithm* getShapeDataSource(const TopoDS_Shape& sh) {
    //    IVtkTools_ShapeDataSource* occSource = vtkSmartPointer<IVtkTools_ShapeDataSource>::New();
    //    occSource->SetShape(new IVtkOCC_Shape(sh));
//
    //    std::cout << "Returning source object" << std::endl;
    //    std::cout << occSource->GetObjectName() << std::endl;
//
    //    return occSource;
//
    //    //vtkSmartPointer<vtkPolyDataMapper> mapper = vtkSmartPointer<vtkPolyDataMapper>::New();
    //    //mapper->SetInputConnection(occSource->GetOutputPort());
    //    //mapper->SetResolveCoincidentTopologyToPolygonOffset();
    //}

    static PotResult processEdgeTest(const TopoDS_Edge& edge) {
        Handle(Poly_PolygonOnTriangulation) polOnTri;
        Handle(Poly_Triangulation) tri;
        TopLoc_Location loc;
        BRep_Tool::PolygonOnTriangulation (edge,
                                           polOnTri,
                                           tri,
                                           loc,
                                           1);


        return PotResult(polOnTri, tri, loc);

        //return PotResult { aPolyOnTriangulation, aTriangulation, aLocation, !aPolyOnTriangulation.IsNull() };
    }

    static vtkSmartPointer<vtkPolyDataMapper> getDataMapper(const TopoDS_Shape& sh) {
        std::cout << "Creating vtk occ shape" << std::endl;

        IVtkOCC_Shape::Handle vtkOccShape = new IVtkOCC_Shape(sh);

        std::cout << "Creating data source" << std::endl;

        vtkSmartPointer<IVtkTools_ShapeDataSource> occSource = vtkSmartPointer<IVtkTools_ShapeDataSource>::New();

        std::cout << "source->setshape" << std::endl;

        occSource->SetShape(vtkOccShape);

        std::cout << "Returning source object" << std::endl;
        std::cout << occSource->GetClassName() << std::endl;
        std::cout << "Returning source object" << std::endl;

        //return occSource;

        vtkSmartPointer<vtkPolyDataMapper> mapper = vtkSmartPointer<vtkPolyDataMapper>::New();
        mapper->SetInputConnection(occSource->GetOutputPort());
        mapper->SetResolveCoincidentTopologyToPolygonOffset();

        std::cout << "Returned result GetClassName value: " << mapper->GetClassName() << std::endl;

        std::cout << "Returned result pointer value: " << mapper.GetPointer() << std::endl;

        return mapper;
    }
};

#endif
