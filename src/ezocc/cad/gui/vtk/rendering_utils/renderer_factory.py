import typing

import OCC.Core.TopAbs
from vtkmodules.vtkCommonCore import vtkPoints, vtkIdList
from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkPolyLine, vtkPolyData
from vtkmodules.vtkRenderingCore import vtkRenderer, vtkActor, vtkPolyDataMapper, vtkProperty, \
    vtkFXAAOptions, vtkTexture, vtkCamera
from vtkmodules.vtkRenderingOpenGL2 import vtkOpenGLFXAAPass, vtkSSAOPass, vtkRenderStepsPass

from ezocc.cad.gui.vtk.rendering_utils.texture_factory import TextureFactory, EnvironmentCubemaps
from ezocc.cad.gui.vtk.vtk_occ_actor import VtkOccActor
from ezocc.cad.model.session import Session


class SessionRenderer:

    def __init__(self,
                 environment_cubemaps: EnvironmentCubemaps,
                 scene_renderer: vtkRenderer,
                 vertex_selection_renderer: vtkRenderer,
                 face_selection_renderer: vtkRenderer,
                 edge_selection_renderer: vtkRenderer,
                 extra_actors: typing.List[vtkActor]):
        self.environment_cubemaps = environment_cubemaps
        self.scene_renderer = scene_renderer
        self.vertex_selection_renderer = vertex_selection_renderer
        self.face_selection_renderer = face_selection_renderer
        self.edge_selection_renderer = edge_selection_renderer
        self.extra_actors = extra_actors

    def add_actor(self, vtk_occ_actor: VtkOccActor):
        self.scene_renderer.AddActor(vtk_occ_actor.actor)

        if vtk_occ_actor.shape_type == OCC.Core.TopAbs.TopAbs_FACE:
            self.face_selection_renderer.AddActor(vtk_occ_actor.actor)
        elif vtk_occ_actor.shape_type == OCC.Core.TopAbs.TopAbs_EDGE:
            self.edge_selection_renderer.AddActor(vtk_occ_actor.actor)

    def remove_actor(self, vtk_occ_actor: VtkOccActor):
        self.scene_renderer.RemoveActor(vtk_occ_actor.actor)

        if vtk_occ_actor.shape_type == OCC.Core.TopAbs.TopAbs_FACE:
            self.face_selection_renderer.RemoveActor(vtk_occ_actor.actor)
        elif vtk_occ_actor.shape_type == OCC.Core.TopAbs.TopAbs_EDGE:
            self.edge_selection_renderer.RemoveActor(vtk_occ_actor.actor)


class RendererFactory:

    @staticmethod
    def _get_grid_actor(x_min: float, x_step: float, x_count: int,
                        y_min: float, y_step: float, y_count: int) -> vtkActor:

        grid_points = vtkPoints()
        edges_cell_array = vtkCellArray()
        y_max = y_min + y_step * (y_count - 1)
        x_max = x_min + x_step * (x_count - 1)

        for i in range(0, x_count):
            id_a = grid_points.InsertNextPoint((i * x_step, 0, 0))
            id_b = grid_points.InsertNextPoint((i * x_step, y_max, 0))

            poly_line = vtkPolyLine()
            poly_line_id_list: vtkIdList = poly_line.GetPointIds()
            poly_line_id_list.InsertNextId(id_a)
            poly_line_id_list.InsertNextId(id_b)

            edges_cell_array.InsertNextCell(poly_line)

        for i in range(0, y_count):
            id_a = grid_points.InsertNextPoint((0, i * y_step, 0))
            id_b = grid_points.InsertNextPoint((x_max, i * y_step, 0))

            poly_line = vtkPolyLine()
            poly_line_id_list: vtkIdList = poly_line.GetPointIds()
            poly_line_id_list.InsertNextId(id_a)
            poly_line_id_list.InsertNextId(id_b)

            edges_cell_array.InsertNextCell(poly_line)

        poly_data = vtkPolyData()
        poly_data.SetPoints(grid_points)
        poly_data.SetLines(edges_cell_array)

        result = vtkActor()
        poly_data_mapper = vtkPolyDataMapper()
        poly_data_mapper.SetInputData(poly_data)
        result.SetMapper(poly_data_mapper)

        props: vtkProperty = result.GetProperty()

        props.RenderLinesAsTubesOff()
        props.LightingOff()

        return result

    @staticmethod
    def get_session_renderer(session: Session) -> SessionRenderer:
        environment_cubemaps = TextureFactory.get_cubemap()

        scene_renderer = vtkRenderer()
        scene_renderer.SetUseFXAA(True)
        scene_renderer.UseImageBasedLightingOn()
        scene_renderer.AutomaticLightCreationOff()
        scene_renderer.SetEnvironmentTexture(environment_cubemaps.environment_cubemap_texture)
        scene_renderer.SetEnvironmentUp(1, 0, 0)
        scene_renderer.SetEnvironmentRight(0, 0, -1)
        scene_renderer.UseSphericalHarmonicsOff()
        scene_renderer.SetBackground(0.2, 0.2, 0.2)
        scene_scale = max(max(*p.part.xts.xyz_span) for p in session.parts) if len(session.parts) > 0 else 1

        base_pass = vtkRenderStepsPass()
        ssao = vtkSSAOPass()
        ssao.SetBlur(0.05 * scene_scale)
        ssao.SetRadius(0.05 * scene_scale)
        ssao.SetBias(0.005 * scene_scale)
        ssao.SetKernelSize(128)

        fxaa_pass = vtkOpenGLFXAAPass()
        opt = vtkFXAAOptions()
        opt.SetUseHighQualityEndpoints(True)
        fxaa_pass.SetFXAAOptions(opt)

        ssao.SetDelegatePass(base_pass)
        fxaa_pass.SetDelegatePass(ssao)

        scene_renderer.SetPass(fxaa_pass)

        face_selection_renderer = vtkRenderer()
        face_selection_renderer.SetActiveCamera(scene_renderer.GetActiveCamera())

        edge_selection_renderer = vtkRenderer()
        edge_selection_renderer.SetActiveCamera(scene_renderer.GetActiveCamera())

        vertex_selection_renderer = vtkRenderer()
        vertex_selection_renderer.SetActiveCamera(scene_renderer.GetActiveCamera())

        return SessionRenderer(environment_cubemaps=environment_cubemaps,
                               scene_renderer=scene_renderer,
                               vertex_selection_renderer=vertex_selection_renderer,
                               face_selection_renderer=face_selection_renderer,
                               edge_selection_renderer=edge_selection_renderer,
                               extra_actors=[])
