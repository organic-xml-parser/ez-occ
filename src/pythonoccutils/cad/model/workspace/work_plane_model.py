import typing

from OCC.Core.Geom import Geom_Surface

from pythonoccutils.cad.model.event import Listenable, SessionEvent, SessionEventType

import OCC.Core.gp as gp
import OCC.Core.TopoDS as TopoDS
from python_solvespace import SolverSystem, ResultFlag, Entity


class WorkPlaneEntity(Listenable):

    def __init__(self, ent: Entity, name: str, *args):
        super().__init__()
        self.ent = ent
        self.name = name
        self.args = [a for a in args]

    @property
    def entity_id(self) -> int:
        """
        Hacky as shit but I don't see another easy way to get the entity handle.
        """
        return WorkPlaneEntity.get_entity_id(self.ent)

    @staticmethod
    def get_entity_id(entity: Entity):
        return int(str(entity).replace("Entity(", "").split(", ")[0].split("=")[1]) - 1


class WorkPlaneConstraint:

    def __init__(self, name: str, *args):
        self.name = name
        self.args = [a for a in args]


class WorkPlaneModel(Listenable):

    def __init__(self,
                 geom_surface: Geom_Surface,
                 sys: SolverSystem,
                 workplane: Entity):
        super().__init__()
        self._sys = sys
        self._workplane = workplane
        self._geom_surface = geom_surface

        self._workplane_entities: typing.Dict[int, WorkPlaneEntity] = {}
        self._workplane_constraints: typing.Set[WorkPlaneConstraint] = set()

    def uv_to_xyz(self, u: float, v: float) -> typing.Tuple[float, float, float]:
        pnt = gp.gp_Pnt()
        self.geom_surface.D0(u, v, pnt)
        return pnt.X(), pnt.Y(), pnt.Z()

    @property
    def entities(self) -> typing.Dict[int, WorkPlaneEntity]:
        return self._workplane_entities.copy()

    @property
    def constraints(self) -> typing.Set[WorkPlaneConstraint]:
        return self._workplane_constraints.copy()

    @property
    def solver_system(self) -> SolverSystem:
        return self._sys

    @property
    def geom_surface(self):
        return self._geom_surface

    def get_workplane_entity(self, handle: typing.Union[int, Entity]):
        if isinstance(handle, Entity):
            handle = WorkPlaneEntity.get_entity_id(handle)

        if handle not in self._workplane_entities:
            raise ValueError("Entity not associated with a workplane entity.")

        return self._workplane_entities[handle]

    def add_entity(self, workplane_entity: WorkPlaneEntity):
        self._workplane_entities[workplane_entity.entity_id] = workplane_entity
        self.listener_manager.notify(SessionEvent(self, SessionEventType.UPDATED))

    def add_constraint(self, workplane_constraint: WorkPlaneConstraint):
        self._workplane_constraints.add(workplane_constraint)
        self.listener_manager.notify(SessionEvent(self, SessionEventType.UPDATED))
