import pdb

import OCC.Core.GeomAbs
import OCC.Core.gp
import OCC.Core.BRepOffsetAPI
import OCC.Core.BRepBuilderAPI
import OCC.Core.TopoDS
import OCC.Core.TopAbs

from ezocc.occutils_python import InterrogateUtils
from ezocc.part_manager import Part


def offset_face_with_holes(face: Part,
                           amount: float,
                           join_type: OCC.Core.GeomAbs.GeomAbs_JoinType = OCC.Core.GeomAbs.GeomAbs_JoinType.GeomAbs_Arc) -> Part:
    if not face.inspect.is_face():
        raise ValueError("Input must be a face")

    wires = face.explore.wire.get()

    if len(wires) == 1:
        return face.extrude.offset(amount=amount, join_type=join_type).make.face()
    else:
        mko = OCC.Core.BRepOffsetAPI.BRepOffsetAPI_MakeOffset(face.shape, join_type)

        for w in wires[1:]:
            mko.AddWire(w.shape)

        mko.Perform(amount)

        offset_wires = face.perform_make_shape(face.cache_token.mutated("offset_face_with_holes", amount, join_type), mko)

        offset_wires = offset_wires.explore.wire.get()
        #print("ORIENTATIONS WIRES")
        #for w in offset_wires:
        #    print(f"o={w.shape.Orientation()}")
        #    print(f"of={w.make.face().shape.Orientation()}")

        #offset_faces = [w.make.face() for w in offset_wires]
        #print("ORIENTATIONS FACES")
        #for w in offset_faces:
        #    print(f"o={w.shape.Orientation()}")
        #    print(f"of={w.make.face().shape.Orientation()}")

        mkf = OCC.Core.BRepBuilderAPI.BRepBuilderAPI_MakeFace(offset_wires[0].shape)
        for w in offset_wires[1:]:
            mkf.Add(w.shape)

        result = face.perform_make_shape(face.cache_token.mutated("offset_face_with_holes", amount, join_type), mkf)\
            .cleanup(concat_b_splines=True, fix_small_face=True)

        return result


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
