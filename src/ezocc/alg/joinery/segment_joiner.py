from __future__ import annotations

from ezocc.humanization import Humanize
from ezocc.part_manager import Part


class SegmentJoiner:

    def get_joint(self, face_a: Part, face_b: Part) -> Part:
        if not face_a.inspect.is_face():
            raise ValueError("Input shape is not a face")

        if not face_b.inspect.is_face():
            raise ValueError("Input shape is not a face")

        shared_edge = face_a.bool.section(face_b)

        if not shared_edge.inspect.is_edge():
            raise ValueError(f"Shared edge is not of type edge (was instead {Humanize.shape_type(shared_edge.shape.ShapeType())})")

        return self._get_joint(face_a, face_b, shared_edge)

    def _get_joint(self, face_a: Part, face_b: Part, shared_edge: Part) -> Part:
        raise NotImplementedError()

