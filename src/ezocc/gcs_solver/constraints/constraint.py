import copy
import typing

from ezocc.gcs_solver.parameter import Parameter


class Constraint:

    def __init__(self, params: typing.Set[Parameter]):
        self.params = copy.copy(params)

    def dof_restricted(self) -> int:
        """
        @return: The degrees of freedom removed from the system.
        """
        raise NotImplementedError()

    def get_error(self) -> float:
        """
        @return: The value used for least-squares fitting. 0 should indicate that the constraint is satisfied, otherwise
        the value should scale with the error. E.g. if two points are constrained coincident, the distance between them
        could serve as the error value.
        """

        raise NotImplementedError()
