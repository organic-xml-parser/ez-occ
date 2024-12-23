import typing

from OCC.Core.gp import gp_Vec

from ezocc.cad.model.directors.session_director import SessionDirector
from ezocc.cad.model.directors.session_director_range import SessionDirectorRange
from ezocc.cad.model.scene_transforms.scene_transforms import SceneTransforms
from ezocc.cad.model.scene_transforms.translation import Translation
from ezocc.gears.gear_generator import GearDriver, RackDriver
from ezocc.occutils_python import SetPlaceablePart


class GearToRackCouplingDirector(SessionDirector):

    def __init__(self,
                 driving_gear: SetPlaceablePart,
                 driven_rack: SetPlaceablePart):
        super().__init__()
        self._driving_gear = driving_gear
        self._driven_rack = driven_rack

    def get_range(self) -> typing.Optional[SessionDirectorRange]:
        return None

    def get_display_name(self) -> str:
        return f"gear_to_rack_coupling"

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

        driven_dr: RackDriver = self._driven_rack.part.driver(RackDriver)

        # number of teeth to offset the driven rack by
        final_driver_teeth = driver_rotation / driver_dr.single_tooth_rotation_radians()

        # determine the current driven location and axis
        driven_current_translation = driven_scene_transform.total_translation()
        driven_single_tooth_translation = gp_Vec(*driven_dr.single_tooth_translation())
        driven_translation_in_gear_direction = gp_Vec(
            driven_current_translation.delta_x,
            driven_current_translation.delta_y,
            driven_current_translation.delta_z).Dot(driven_single_tooth_translation.Normalized())
        driven_teeth_in_gear_direction = (driven_translation_in_gear_direction /
                                          driven_single_tooth_translation.Magnitude())

        remaining_teeth_to_drive = final_driver_teeth - driven_teeth_in_gear_direction

        translation_to_apply = driven_single_tooth_translation.Scaled(remaining_teeth_to_drive)

        driven_scene_transform.append_translation(Translation(
            translation_to_apply.X(),
            translation_to_apply.Y(),
            translation_to_apply.Z()
        ))

    def get_affected_parts(self) -> typing.Set[SetPlaceablePart]:
        return {self._driven_rack}
