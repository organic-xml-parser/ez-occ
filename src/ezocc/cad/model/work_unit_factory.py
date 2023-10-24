import typing

from ezocc.cad.model.work_unit import WorkUnitCommand
from ezocc.cad.model.workspace.workspace import Workspace
from ezocc.part_manager import PartFactory, PartQuery, Part


class WorkUnitCommandFactory:

    def get_command_list(self) -> typing.List[str]:
        return [
            TranslateWorkUnitCommand.__name__,
            FilletWorkUnitCommand.__name__,
            MakeBoxCommand.__name__
        ]

    # noinspection PyMethodMayBeStatic
    def create_command(self, cmd_name: str):
        if cmd_name == TranslateWorkUnitCommand.__name__:
            return TranslateWorkUnitCommand("", 0, 0, 0)
        elif cmd_name == FilletWorkUnitCommand.__name__:
            return FilletWorkUnitCommand("", "*e", 1)
        elif cmd_name == MakeBoxCommand.__name__:
            return MakeBoxCommand("", 1, 1, 1)
        else:
            raise ValueError(f"Unknown command name: \"{cmd_name}\"")


class AnonymousWorkUnitCommand(WorkUnitCommand):

    def __init__(self, perform_callable: typing.Callable[[Workspace, typing.Dict], None], **cmd_args):
        super().__init__(**cmd_args)
        self._perform_callable = perform_callable

    def perform(self, workspace: Workspace):
        self._perform_callable(workspace, self._cmd_args)


class ShowCachedPartCommand(WorkUnitCommand):

    def __init__(self, part_name: str, part: Part):
        super().__init__()

        self._part_name = part_name
        self._part = part

    def perform(self, workspace: Workspace):
        workspace.create_part(name=self._part_name, part=self._part)


class MakeBoxCommand(WorkUnitCommand):

    def __init__(self, part_name: str, dx: float, dy: float, dz: float):
        super().__init__(
            part_name=part_name,
            dx=dx,
            dy=dy,
            dz=dz)

    def perform(self, workspace: Workspace):
        part = PartFactory.box(
            dx=self._cmd_args['dx'].value,
            dy=self._cmd_args['dy'].value,
            dz=self._cmd_args['dz'].value
        )

        workspace.create_part(self._cmd_args['part_name'].value, part)


class FilletWorkUnitCommand(WorkUnitCommand):

    def __init__(self, target_part_name: str, edge_query: str, radius: float):
        super().__init__(
            target_part_name=target_part_name,
            edge_query=edge_query,
            radius=radius)

    def perform(self, workspace: Workspace):
        workspace.update_part(
            self._cmd_args['target_part_name'].value,
            self._perform)

    def _perform(self, part: Part) -> Part:
        shape_list = PartQuery(part, False)(self._cmd_args['edge_query'].value)

        return part.fillet.fillet_edges(self._cmd_args['radius'].value, lambda e: e in shape_list)


class TranslateWorkUnitCommand(WorkUnitCommand):

    def __init__(self, target_part_name: str, dx: float, dy: float, dz: float):
        super().__init__(
            target_part_name=target_part_name,
            dx=dx,
            dy=dy,
            dz=dz)

    def perform(self, workspace: Workspace):
        workspace.update_part(
            self._cmd_args['target_part_name'].value,
            self._perform)

    def _perform(self, part: Part) -> Part:
        return part.transform.translate(
            dx=self._cmd_args['dx'].value,
            dy=self._cmd_args['dy'].value,
            dz=self._cmd_args['dz'].value)
