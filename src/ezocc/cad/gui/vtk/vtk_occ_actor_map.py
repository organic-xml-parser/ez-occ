from __future__ import annotations

import copy
import typing

from vtkmodules.vtkRenderingCore import vtkActor

from ezocc.cad.gui.vtk.vtk_occ_actor import VtkOccActor
from ezocc.occutils_python import SetPlaceablePart


class VtkOccActorMap:
    """
    Used to track the relationship between vtk and OCC entities. This can be useful for
    determining e.g. the Part corresponding to a given vtkActor when it is selected.
    """

    def __init__(self):
        # records relation between vtk actors and associated parts etc.
        self._actor_map: typing.Dict[vtkActor, VtkOccActor] = {}

        # records part relations back to actors
        self._part_to_occ_actors: typing.Dict[SetPlaceablePart, typing.Set[VtkOccActor]] = {}

    def contains_part(self, part: SetPlaceablePart) -> bool:
        return part in self._part_to_occ_actors

    def get_occ_actors(self, part: SetPlaceablePart) -> typing.Set[VtkOccActor]:
        if part not in self._part_to_occ_actors:
            raise ValueError(f"Part: {part} not present in the actor map, candidates are: {self._part_to_occ_actors}")

        return copy.copy(self._part_to_occ_actors[part])

    def occ_actors(self) -> typing.Generator[VtkOccActor, None, None]:
        for occ_actors in self._part_to_occ_actors.values():
            for occ_actor in occ_actors:
                yield occ_actor

    def clear(self):
        self._actor_map.clear()
        self._part_to_occ_actors.clear()

    def add_entry(self, vtk_occ_actor: VtkOccActor):
        vtk_actor = vtk_occ_actor.actor

        if vtk_actor in self._actor_map:
            raise ValueError("Actor already present")

        self._actor_map[vtk_actor] = vtk_occ_actor

        if vtk_occ_actor.part not in self._part_to_occ_actors:
            self._part_to_occ_actors[vtk_occ_actor.part] = set()

        self._part_to_occ_actors[vtk_occ_actor.part].add(vtk_occ_actor)

    def get_vtk_occ_actor(self, vtk_actor: vtkActor) -> VtkOccActor:
        return self._actor_map[vtk_actor]

