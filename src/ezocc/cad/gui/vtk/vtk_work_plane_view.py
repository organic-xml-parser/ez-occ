from __future__ import annotations

import math
import pdb
import typing

import OCC.Core.BRepBuilderAPI
from OCC.Core.Geom2d import Geom2d_TrimmedCurve
from OCC.Core.gp import gp_Pnt, gp_OZ, gp_Pnt2d, gp_Lin, gp_Dir2d, gp_Dir, gp_Vec, gp_Ax1
from vtkmodules.vtkCommonCore import vtkPoints
from vtkmodules.vtkCommonDataModel import vtkPolyData
from vtkmodules.vtkCommonTransforms import vtkTransform
from vtkmodules.vtkFiltersCore import vtkGlyph3D
from vtkmodules.vtkInteractionWidgets import vtkHandleWidget

import ezocc.occutils_python
from ezocc.cad.gui.render_spec import RenderingColorSpec, EntityRenderingColorSpec, RenderSpec
from ezocc.cad.gui.vtk.vtk_occ_bridging import VtkActorsBuilder, VtkOccActorMap, VtkActorBuilder

from ezocc.cad.model.workspace.work_plane_controller import WorkPlaneController
from ezocc.cad.model.workspace.work_plane_model import WorkPlaneModel, WorkPlaneEntity, WorkPlaneConstraint

# noinspection PyUnresolvedReferences
import vtkmodules.vtkInteractionStyle
# noinspection PyUnresolvedReferences
import vtkmodules.vtkRenderingOpenGL2
from vtkmodules.vtkCommonColor import vtkNamedColors
from vtkmodules.vtkFiltersSources import vtkCylinderSource, vtkSphereSource
from vtkmodules.vtkRenderingCore import (
    vtkActor,
    vtkPolyDataMapper,
    vtkRenderWindow,
    vtkRenderWindowInteractor,
    vtkRenderer, vtkProp3D, vtkAssembly, vtkTextActor
)

from ezocc.part_manager import Part


class WorkPlaneEntityActor:

    def __init__(self,
                 renderer: vtkRenderer,
                 workplane_entity: WorkPlaneEntity):
        self._renderer = renderer
        self._workplane_entity = workplane_entity
        self._actor = None
        self.update()

        self._workplane_entity.listener_manager.add_listener(lambda _: self.update())

    def update(self):
        if self._actor is not None:
            self._renderer.RemoveActor(self._actor)

        self._actor = self.build_actor(self._workplane_entity)

        self._renderer.AddActor(self._actor)

    def build_actor(self, workplane_entity: WorkPlaneEntity) -> vtkProp3D:
        raise NotImplementedError()


class PointActor(WorkPlaneEntityActor):

    source = vtkSphereSource()
    source.SetRadius(0.1)

    @staticmethod
    def workplane_entity_to_xyz(
            workplane_entity: WorkPlaneEntity,
            workplane_model: WorkPlaneModel) -> typing.Tuple[float, float, float]:
        u, v = workplane_model.solver_system.params(workplane_entity.ent.params)

        return workplane_model.uv_to_xyz(u, v)

    def __init__(self,
                 workplane_view: WorkPlaneView,
                 workplane_model: WorkPlaneModel,
                 interactor: vtkRenderWindowInteractor,
                 renderer: vtkRenderer,
                 workplane_entity: WorkPlaneEntity):
        self._workplane_view = workplane_view
        self._workplane_model = workplane_model
        self._interactor = interactor
        super().__init__(renderer, workplane_entity)

    def build_actor(self, workplane_entity: WorkPlaneEntity) -> vtkProp3D:
        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(PointActor.source.GetOutputPort())

        actor = vtkActor()
        actor.SetMapper(mapper)

        trsf = vtkTransform()

        x, y, z = PointActor.workplane_entity_to_xyz(workplane_entity, self._workplane_model)
        trsf.Translate(x, y, z)

        actor.SetUserTransform(trsf)

        return actor


class CurveActor(WorkPlaneEntityActor):

    def __init__(self,
                 workplane_model: WorkPlaneModel,
                 renderer: vtkRenderer,
                 workplane_entity: WorkPlaneEntity):
        self._workplane_model = workplane_model
        super().__init__(renderer, workplane_entity)

    def build_actor(self, workplane_entity: WorkPlaneEntity) -> vtkProp3D:
        geom_2d_curve = self.get_geom_2d_curve(workplane_entity)

        edge = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(geom_2d_curve, self._workplane_model.geom_surface).Edge()

        part = Part(edge)

        ercs = EntityRenderingColorSpec((255, 255, 255), (255, 255, 255))
        rcs = RenderingColorSpec(ercs, ercs, ercs, ercs)

        rs = RenderSpec(False, False, False)

        actor_map = VtkOccActorMap()

        assemblies = VtkActorsBuilder({part}, rcs, rs).get_vtk_actors(actor_map)

        if len(assemblies) != 1:
            raise ValueError("Expected 1 assembly")

        return next(iter(assemblies))

    def get_geom_2d_curve(self, workplane_entity: WorkPlaneEntity):
        """
        @return: The 2D curve (in uv surface coordinates) that will be mapped to 3d, then triangulated to provide a
        view.
        """

        raise NotImplementedError()


class LineActor(CurveActor):

    def __init__(self, workplane_model: WorkPlaneModel, renderer: vtkRenderer, workplane_entity: WorkPlaneEntity):
        super().__init__(workplane_model, renderer, workplane_entity)

    def get_geom_2d_curve(self,
                          workplane_entity: WorkPlaneEntity):
        p0, p1 = workplane_entity.args

        w_p0 = self._workplane_model.get_workplane_entity(p0)
        w_p1 = self._workplane_model.get_workplane_entity(p1)

        x0, y0 = self._workplane_model.solver_system.params(w_p0.ent.params)
        x1, y1 = self._workplane_model.solver_system.params(w_p1.ent.params)

        dx, dy = x1 - x0, y1 - y0

        length = math.hypot(dx, dy)

        import OCC.Core.GC
        line = OCC.Core.Geom2d.Geom2d_Line(gp_Pnt2d(x0, y0), gp_Dir2d(dx, dy))
        return OCC.Core.Geom2d.Geom2d_TrimmedCurve(line, 0, length)


class WorkPlaneConstraintActor:

    def __init__(self,
                 model: WorkPlaneModel,
                 renderer: vtkRenderer,
                 wpc: WorkPlaneConstraint):
        self._model = model
        self._renderer = renderer
        self._wpc = wpc

        self._actor = None
        self.update()
        model.listener_manager.add_listener(lambda _: self.update())

    def update(self):
        if self._actor is not None:
            self._renderer.RemoveActor(self._actor)

        # create actor
        self._actor = self.build_actor()

        self._renderer.AddActor(self._actor)

    def build_actor(self) -> vtkProp3D:
        raise NotImplementedError()


class DistConstraintActor(WorkPlaneConstraintActor):

    def __init__(self,
                 model: WorkPlaneModel,
                 renderer: vtkRenderer,
                 wpc: WorkPlaneConstraint):
        super().__init__(model, renderer, wpc)

    def build_actor(self) -> vtkProp3D:
        p0, p1, dist = self._wpc.args
        w_p0 = self._model.get_workplane_entity(p0)
        w_p1 = self._model.get_workplane_entity(p1)

        xyz_0 = PointActor.workplane_entity_to_xyz(w_p0, self._model)
        xyz_1 = PointActor.workplane_entity_to_xyz(w_p1, self._model)

        gp_p0 = gp_Pnt(*xyz_0)
        gp_p1 = gp_Pnt(*xyz_1)

        vec = gp_Vec(xyz_1[0] - xyz_0[0], xyz_1[1] - xyz_0[1], xyz_1[2] - xyz_0[2])\
            .Normalized()\
            .Rotated(gp_Ax1(gp_p0, OCC.Core.gp.gp_DZ()), math.pi / 2)\
            .Scaled(0.1)

        edge_center = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(
            gp_p0.Translated(vec),
            gp_p1.Translated(vec)).Edge()

        edge_left = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(
            gp_p0,
            gp_p0.Translated(vec.Scaled(2))).Edge()

        edge_right = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeEdge(
            gp_p1,
            gp_p1.Translated(vec.Scaled(2))).Edge()

        shape = ezocc.occutils_python.GeomUtils.make_compound(edge_center, edge_left, edge_right)

        ercs = EntityRenderingColorSpec((255, 0, 255), (255, 255, 255))
        rcs = RenderingColorSpec(ercs, ercs, ercs, ercs)

        rs = RenderSpec(False, False, False)

        actor_map = VtkOccActorMap()

        assemblies = VtkActorsBuilder({Part(shape)}, rcs, rs).get_vtk_actors(actor_map)

        return next(iter(assemblies))


class WorkPlaneView:

    def __init__(self, workplane_model: WorkPlaneModel):
        self._workplane_model = workplane_model

        self._renderer = vtkRenderer()
        self._render_window = vtkRenderWindow()
        self._render_window.AddRenderer(self._renderer)

        self._interactor = vtkRenderWindowInteractor()
        self._interactor.SetRenderWindow(self._render_window)

        self._actors = []
        self.update()

        self._interactor.Start()

    def update(self):
        for wpe in self._workplane_model.entities.values():
            if wpe.name == "point_2d":
                self._actors.append(PointActor(self, self._workplane_model, self._interactor, self._renderer, wpe))
            elif wpe.name == "line_2d":
                self._actors.append(LineActor(self._workplane_model, self._renderer, wpe))

        for wpc in self._workplane_model.constraints:
            if wpc.name == "distance":
                self._actors.append(DistConstraintActor(self._workplane_model, self._renderer, wpc))

        self._renderer.ResetCamera()
