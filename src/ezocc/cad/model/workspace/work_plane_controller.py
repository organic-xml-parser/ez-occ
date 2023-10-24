import typing

import OCC.Core.gp as gp
import OCC.Core.TopoDS as TopoDS
from python_solvespace import SolverSystem, ResultFlag, Entity, Constraint

from ezocc.cad.model.workspace.work_plane_model import WorkPlaneModel, WorkPlaneEntity, WorkPlaneConstraint


class WorkPlaneController:
    """
    Defines a 2D coordinate system onto which sketch entities may be placed and constrained. Simple examples are the
    XYZ coordinate planes.
    
    More complex plane mappings should be possible, however. For example sketching on a curved surface may be enabled by
    mapping the surface to a 2D space (OCC provides a way to do this using Handle(Geom_Surface)). Once the surface is 
    mapped to a WorkPlane it may be sketched on like any other 2D surface.

    WorkPlanes should enable importing of external geometric entities (TopoDS_Shape) where there is a well-defined way
    to do so. Sketch entities may be added along with constraints, corresponding to the standard solvespace workflow.

    The resulting solved `WorkPlane` sketch entities can then be mapped to OCC types, using the Geom_Surface and OCC
    curve mapping.

    The MVC pattern is used with the WorkPlaneController acting as the Controller, WorkPlaneModel the model, and the
    WorkPlaneView defined depending on the interface used. (For Vtk, this would be VtkWorkPlaneView)
    """

    def __init__(self, geom_surface):
        self._sys = SolverSystem()
        self._wp = self._sys.create_2d_base()

        self._work_plane_model = WorkPlaneModel(geom_surface, self._sys, self._wp)

    def add_entity(self, name: str, *args) -> WorkPlaneEntity:
        entity = getattr(self._sys, f"add_{name}")(*args, self._wp)

        wpe = WorkPlaneEntity(entity, name, *args)

        self._work_plane_model.add_entity(wpe)

        return wpe

    def add_constraint(self, name: str, *args):
        constrain_method = getattr(self._sys, name)

        wpc = WorkPlaneConstraint(name, *args)
        constrain_method(*args, self._wp)

        self._work_plane_model.add_constraint(wpc)

    @property
    def model(self):
        return self._work_plane_model


    @staticmethod
    def from_face(face: TopoDS.TopoDS_Face):
        # todo: generate Geom_Surface from face, and map u/v extents
        raise NotImplementedError()