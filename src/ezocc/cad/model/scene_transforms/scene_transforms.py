import copy
import typing

from ezocc.cad.model.scene_transforms.scene_transform_stack import SceneTransformStack
from ezocc.occutils_python import SetPlaceablePart


class SceneTransforms:
    """
    Associates parts with transform stacks.
    """

    def __init__(self):
        self._transforms: typing.Dict[SetPlaceablePart, SceneTransformStack] = {}

    def get_transform_stack(self, part: SetPlaceablePart) -> SceneTransformStack:
        if part not in self._transforms:
            self._transforms[part] = SceneTransformStack()

        return self._transforms[part]

    def set_transform_stack(self, part: SetPlaceablePart, transform_stack: SceneTransformStack):
        self._transforms[part] = copy.deepcopy(transform_stack)

    def transforms(self) -> typing.Dict[SetPlaceablePart, SceneTransformStack]:
        return self._transforms.copy()
