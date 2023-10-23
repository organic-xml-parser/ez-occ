import pdb

import OCC.Core.TopoDS


class TypeValidator:

    SHAPE = OCC.Core.TopoDS.TopoDS_Shape
    VERTEX = OCC.Core.TopoDS.TopoDS_Vertex
    EDGE = OCC.Core.TopoDS.TopoDS_Edge
    WIRE = OCC.Core.TopoDS.TopoDS_Wire
    FACE = OCC.Core.TopoDS.TopoDS_Face
    SOLID = OCC.Core.TopoDS.TopoDS_Solid
    COMPSOLID = OCC.Core.TopoDS.TopoDS_CompSolid
    COMPOUND = OCC.Core.TopoDS.TopoDS_Compound

    ALL_SHAPE_TYPES = [
        SHAPE,
        VERTEX,
        EDGE,
        WIRE,
        FACE,
        SOLID,
        COMPSOLID,
        COMPOUND
    ]

    @staticmethod
    def is_any_shape(obj) -> bool:
        return any(isinstance(obj, t) for t in TypeValidator.ALL_SHAPE_TYPES)

    @staticmethod
    def assert_is_any_shape(obj):
        if not TypeValidator.is_any_shape(obj):
            raise ValueError(f"Obj is not an instance of any TopoDS_Shape: {obj}")