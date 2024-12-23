import typing

import OCC.Core.gp
from vtkmodules.vtkCommonTransforms import vtkTransform

from ezocc.cad.model.directors.session_director import SessionDirector
from ezocc.cad.model.directors.session_director_range import SessionDirectorRange
from ezocc.cad.model.scene_transforms.scene_transforms import SceneTransforms
from ezocc.gears.gear_generator import GearDriver
from ezocc.occutils_python import SetPlaceablePart


class GearCouplingDirector(SessionDirector):

    def __init__(self,
                 driving_gear: SetPlaceablePart,
                 driven_gear: SetPlaceablePart):
        super().__init__()
        self._driving_gear = driving_gear
        self._driven_gear = driven_gear

    def get_range(self) -> typing.Optional[SessionDirectorRange]:
        return None

    def get_display_name(self) -> str:
        return f"gear_coupling"

    def set_value(self, value: float):
        pass

    def get_value(self) -> float:
        return 0

    def push_transform(self, scene_transforms: SceneTransforms, part: SetPlaceablePart) -> None:

        # determine the number of rotations about the driver gear's axis of rotation
        # take current driver gear direction, rotate so that axis is DZ
        # get z angle rotation
        driver_scene_transform = scene_transforms.get_transform_stack(self._driving_gear)
        driven_scene_transform = scene_transforms.get_transform_stack(part)

        driver_dr: GearDriver = self._driving_gear.part.driver(GearDriver)
        driver_axis = (
            driver_dr.get_rotation_axis().Direction().X(),
            driver_dr.get_rotation_axis().Direction().Y(),
            driver_dr.get_rotation_axis().Direction().Z())

        driver_rotation = driver_scene_transform\
            .measure_total_rotation_about_axis(driver_axis)

        driven_dr: GearDriver = self._driven_gear.part.driver(GearDriver)
        driven_axis = (
            driven_dr.get_rotation_axis().Direction().X(),
            driven_dr.get_rotation_axis().Direction().Y(),
            driven_dr.get_rotation_axis().Direction().Z())

        driver_teeth = driver_rotation / driver_dr.single_tooth_rotation_radians()

        if driver_dr.gear_spec.num_teeth == driven_dr.gear_spec.num_teeth:
            driven_target_rotation = driver_rotation
        elif driver_dr.gear_spec.num_teeth < driven_dr.gear_spec.num_teeth:
            driven_target_rotation = driver_teeth * driven_dr.single_tooth_rotation_radians()
        else:
            driven_target_rotation = -driver_teeth * driven_dr.single_tooth_rotation_radians()

        # determine the current driven location and axis
        driven_current_rotation = driven_scene_transform\
            .measure_total_rotation_about_axis(driven_axis)

        driven_current_center = driven_scene_transform.transform_point(*driven_dr.center)

        driven_current_axis = driven_scene_transform.transform_vector(*driven_axis)

        driven_rotation_delta = driven_target_rotation - driven_current_rotation
        driven_scene_transform.append_rotation_on_axis_about_point(
            driven_current_axis,
            driven_current_center,
            driven_rotation_delta)

    def get_affected_parts(self) -> typing.Set[SetPlaceablePart]:
        return {self._driven_gear}

    @staticmethod
    def _vtk_transform_vec(vtk_transform: vtkTransform, vec: OCC.Core.gp.gp_Vec) -> OCC.Core.gp.gp_Vec:
        vec = vtk_transform.TransformFloatVector(vec.X(), vec.Y(), vec.Z())
        return OCC.Core.gp.gp_Vec(*vec)

    @staticmethod
    def _vtk_transform_pnt(vtk_transform: vtkTransform, pnt: OCC.Core.gp.gp_Pnt) -> OCC.Core.gp.gp_Pnt:
        pnt = vtk_transform.TransformFloatPoint(pnt.X(), pnt.Y(), pnt.Z())
        return OCC.Core.gp.gp_Pnt(*pnt)
