import typing

from ezocc.gcs_solver.constraints.constraint import Constraint
from ezocc.gcs_solver.parameter import Parameter
from ezocc.part_manager import Part, PartCache


class Entity:
    """
    Represents a geometric "thing" present in the sketch which uses the specified input parameters to describe its
    dimensions.
    """

    def __init__(self, params: typing.List[Parameter]):
        self.params = params

    def get_implicit_constraints(self) -> typing.Set[Constraint]:
        """
        @return: any constraints which are required for the well-formed presentation of the object
        """
        return set()

    def get_part(self, cache: PartCache) -> Part:
        """
        @return: an opencascade shape representing this entity
        """

        raise NotImplementedError()
