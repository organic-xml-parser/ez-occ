import pdb

import OCC.Core.GeomAbs
import OCC.Core.gp
import OCC.Core.BRepOffsetAPI
import OCC.Core.BRepBuilderAPI
import OCC.Core.TopoDS
import OCC.Core.TopAbs

from ezocc.occutils_python import InterrogateUtils
from ezocc.part_manager import Part, PartFactory


def offset_face_with_holes(face: Part,
                           amount: float,
                           join_type: OCC.Core.GeomAbs.GeomAbs_JoinType = OCC.Core.GeomAbs.GeomAbs_JoinType.GeomAbs_Arc) -> Part:
    if not face.inspect.is_face():
        raise ValueError("Input must be a face")

    factory = PartFactory(face.cache_token.get_cache())

    wires = face.explore.wire.get()

    if len(wires) == 1:
        return face.extrude.offset(amount=amount, join_type=join_type).make.face()

    def normalize_wire(wire: Part):
        edges = [w.oriented.forward() for w in wire.explore.edge.get()]
        return factory.compound(*edges).make.wire()

    outer_profile = normalize_wire(wires[0]).make.face().extrude.offset(amount).make.face()

    inner_faces = [normalize_wire(w).extrude.offset(amount=-amount, join_type=join_type).make.face() for w in wires[1:]]

    return outer_profile.bool.cut(*inner_faces)


def offset_holes_in_face(face: Part,
                           amount: float,
                           join_type: OCC.Core.GeomAbs.GeomAbs_JoinType = OCC.Core.GeomAbs.GeomAbs_JoinType.GeomAbs_Arc) -> Part:
    if not face.inspect.is_face():
        raise ValueError("Input must be a face")

    wires = face.explore.wire.get()

    if len(wires) == 1:
        return face
    else:
        outer_face = wires[0].make.face()

        for w in wires[1:]:
            f = w.extrude.offset(amount=amount, join_type=join_type).make.face()
            outer_face = outer_face.bool.cut(f)

        return outer_face
