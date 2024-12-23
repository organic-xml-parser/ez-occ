import json
import os.path

from ezocc.cad.model.scene_transforms.scene_transform_stack import Translation, EulerRotation
from ezocc.cad.model.session import Session
from ezocc.occutils_python import SetPlaceablePart


class SessionUtils:

    @staticmethod
    def _get_part_name(part: SetPlaceablePart) -> str:
        subshapes = part.part.subshapes

        if subshapes.contains_shape(subshapes.root_shape):
            name = subshapes.name_for_shape(subshapes.root_shape)
        else:
            name = "unnamed"

        name += "-" + str(id(part))

        return name

    @staticmethod
    def save_stls(session: Session, output_dir: str):
        for sp in session.parts:
            name = SessionUtils._get_part_name(sp)
            file = os.path.join(output_dir, name)

            sp.part.save.single_stl(file)

    @staticmethod
    def save_keyframes(session: Session, frame: int, output_dir: str):
        json_doc = {"keyframe": frame, "transforms": {}}

        for sp in session.parts:
            transform_stack = session.scene_transforms.get_transform_stack(sp)

            name = SessionUtils._get_part_name(sp)

            translation = transform_stack.total_translation()
            rotation = transform_stack.total_rotation()

            json_doc["transforms"][name] = []

            for transform in transform_stack.stack:
                if isinstance(transform, Translation):
                    element = {
                        "type": "translation",
                        "x": transform.delta_x,
                        "y": transform.delta_y,
                        "z": transform.delta_z
                    }
                elif isinstance(transform, EulerRotation):
                    element = {
                        "type": "rotation",
                        "x": transform.theta_x,
                        "y": transform.theta_y,
                        "z": transform.theta_z
                    }
                else:
                    raise ValueError()

                json_doc["transforms"][name].append(element)

        with open(os.path.join(output_dir, f"keyframes-{frame}.json"), "w") as f:
            json.dump(json_doc, f)

