from __future__ import annotations

import typing
from collections import OrderedDict

from pythonoccutils.cad.model.workspace.workspace import Workspace

from .event import Listenable, SessionEvent, SessionEventType


class CmdArg(Listenable):
    """
    Castable arg input. arg has an associated type and can provide to/from str methods for display/input purposes.
    """

    def __init__(self, value):
        super().__init__()
        self._expected_type = type(value)
        self._value = value

    def __hash__(self) -> int:
        return hash((self._expected_type, self._value))

    def __eq__(self, o: object) -> bool:
        return isinstance(o, CmdArg) and o._value == self._value and o._expected_type == self._expected_type

    @property
    def value(self):
        return self._value

    @property
    def expected_type(self):
        return self._expected_type

    def from_str(self, str_value: str):
        new_val = CmdArg.str_to_value(str_value, self._expected_type)

        if not isinstance(new_val, self._expected_type):
            raise ValueError("Value type is not correct")

        if new_val == self._value:
            # nothing to do
            return

        self._value = new_val

        self.listener_manager.notify(SessionEvent(self, SessionEventType.UPDATED))

    def to_str(self) -> str:
        return str(self._value)

    @staticmethod
    def str_to_value(str_value: str, expected_type):
        if expected_type.__name__ == 'str':
            return str_value
        elif expected_type in [int, float, bool]:
            return expected_type(str_value)
        else:
            raise ValueError(f"Cannot convert type {expected_type} to/from str in CmdArg.")


class WorkUnitCommand(Listenable):
    """
    Encapsulates the subcomponent of the "operation" defined by a WorkUnit. Typically, there will be a single command
    per work unit, e.g. "chamfer". It is important that WorkUnitCommands are serializable, as they must be stored as
    part of the document.
    """

    def __init__(self, **cmd_args):
        super().__init__()
        self._cmd_args = OrderedDict()
        for k, v in cmd_args.items():
            carg = CmdArg(v)
            carg.listener_manager.add_listener(self._cmd_arg_changed)
            self._cmd_args[k] = carg

    def _cmd_arg_changed(self, cmd_arg):
        # notify listeners that this entity has changed
        self.listener_manager.notify(SessionEvent(self, SessionEventType.INDIRECT))

    @property
    def cmd_args(self):
        return self._cmd_args.copy()

    def perform(self, workspace: Workspace):
        raise NotImplementedError()

    def __eq__(self, o: object) -> bool:
        return isinstance(o, WorkUnitCommand) and self._cmd_args == o._cmd_args

    def __hash__(self) -> int:
        return hash(frozenset(self._cmd_args.items()))


class WorkUnit(Listenable):
    """
    Defines a single "operation" (term deliberately left vague) that may be performed on one or more parts, outputting
    one or more result parts. WorkUnits have exactly one parent unit, on which they "depend": The combined output of all
    work units are provided by the tree leaf nodes.

    WorkUnits are stored as a doubly-linked tree, allowing for backtracking from the end of a work history.

    WorkUnits operations are performed by commands. These follow the Command Pattern to allow for retrieval, storage,
    and repeatability.
    """

    # stored cache of generated workspaces, to avoid re-generating
    workspace_cache = {}

    def __init__(self, name: str, parent: typing.Optional[WorkUnit], commands: typing.List[WorkUnitCommand]):
        super().__init__()
        self.name = name
        self.parent = parent
        self.child_nodes: typing.List[WorkUnit] = []
        self._commands = commands.copy()

        for c in commands:
            c.listener_manager.add_listener(self._command_changed)

        self.listener_manager.add_listener(self.notify_children_indirect)

    def notify_children_indirect(self, session_event: SessionEvent):
        for c in self.child_nodes:
            c.listener_manager.notify(SessionEvent(c, SessionEventType.INDIRECT))

    def add_command(self, cmd: WorkUnitCommand):
        if cmd in self._commands:
            raise ValueError("Command already present. Cannot add duplicate command.")

        self._commands.append(cmd)
        cmd.listener_manager.add_listener(self._command_changed)

        self.listener_manager.notify(SessionEvent(self, SessionEventType.UPDATED))

    def remove_command(self, cmd):
        if cmd not in self._commands:
            raise ValueError("Command is not managed by this work unit")

        self._commands.remove(cmd)
        self.listener_manager.notify(SessionEvent(self, SessionEventType.UPDATED))

    def move_command_previous(self, cmd):
        if cmd not in self._commands:
            raise ValueError("Command is not managed by this work unit.")

        index = self._commands.index(cmd)
        if index > 0:
            self._commands[index - 1], self._commands[index] = self._commands[index], self._commands[index - 1]
            self.listener_manager.notify(SessionEvent(self, SessionEventType.UPDATED))

    def move_command_next(self, cmd):
        if cmd not in self._commands:
            raise ValueError("Command is not managed by this work unit.")

        index = self._commands.index(cmd)
        if index < (self._commands.__len__() - 1):
            self._commands[index + 1], self._commands[index] = self._commands[index], self._commands[index + 1]
            self.listener_manager.notify(SessionEvent(self, SessionEventType.UPDATED))

    def _command_changed(self, cmd):
        self.listener_manager.notify(SessionEvent(self, SessionEventType.INDIRECT))

    @property
    def commands(self) -> typing.List[WorkUnitCommand]:
        return self._commands.copy()

    def traverse(self) -> typing.Generator[WorkUnit, None, None]:
        yield self

        for c in self.child_nodes:
            for w in c.traverse():
                yield w

    def _cache_key(self):
        return (self.name,
                self.parent._cache_key() if self.parent is not None else None,
                tuple(self.child_nodes),
                tuple(self._commands))

    def perform(self) -> Workspace:
        cache_key = self._cache_key()

        if cache_key in WorkUnit.workspace_cache:
            return WorkUnit.workspace_cache[cache_key].copy()

        if self.parent is None:
            wsp = Workspace({})
        else:
            wsp = self.parent.perform()

        for c in self._commands:
            c.perform(wsp)

        WorkUnit.workspace_cache[cache_key] = wsp

        return wsp.copy()

    def add_child(self, work_unit: WorkUnit) -> WorkUnit:
        if work_unit.parent != self:
            raise ValueError("Work unit does not have parent set to this element.")

        if work_unit in self.child_nodes:
            raise ValueError("Duplicate child node.")

        self.child_nodes.append(work_unit)
        self.listener_manager.notify(SessionEvent(self, SessionEventType.UPDATED))
        return work_unit

    def remove_child(self, work_unit: WorkUnit):
        if work_unit.parent != self:
            raise ValueError("Work unit does not have parent set to this element")

        if work_unit not in self.child_nodes:
            raise ValueError("Work unit not present in child nodes")

        self.child_nodes.remove(work_unit)
        self.listener_manager.notify(SessionEvent(self, SessionEventType.UPDATED))

    @staticmethod
    def is_parent(parent: WorkUnit, potential_child: WorkUnit):
        return any(wu == potential_child for wu in parent.traverse())
