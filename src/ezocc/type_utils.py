import pdb

import OCC.Core.TopoDS
import OCC.Core.TopAbs

from ezocc import humanization
from ezocc.humanization import Humanize


class TypeValidator:

    ALL_SHAPE_TYPES = [
        OCC.Core.TopAbs.TopAbs_ShapeEnum.TopAbs_SHAPE,
        OCC.Core.TopAbs.TopAbs_ShapeEnum.TopAbs_VERTEX,
        OCC.Core.TopAbs.TopAbs_ShapeEnum.TopAbs_EDGE,
        OCC.Core.TopAbs.TopAbs_ShapeEnum.TopAbs_WIRE,
        OCC.Core.TopAbs.TopAbs_ShapeEnum.TopAbs_FACE,
        OCC.Core.TopAbs.TopAbs_ShapeEnum.TopAbs_SHELL,
        OCC.Core.TopAbs.TopAbs_ShapeEnum.TopAbs_SOLID,
        OCC.Core.TopAbs.TopAbs_ShapeEnum.TopAbs_COMPSOLID,
        OCC.Core.TopAbs.TopAbs_ShapeEnum.TopAbs_COMPOUND
    ]

    ALL_SHAPE_CLASSES = [
        OCC.Core.TopoDS.TopoDS_Shape,
        OCC.Core.TopoDS.TopoDS_Vertex,
        OCC.Core.TopoDS.TopoDS_Edge,
        OCC.Core.TopoDS.TopoDS_Wire,
        OCC.Core.TopoDS.TopoDS_Face,
        OCC.Core.TopoDS.TopoDS_Shell,
        OCC.Core.TopoDS.TopoDS_Solid,
        OCC.Core.TopoDS.TopoDS_CompSolid,
        OCC.Core.TopoDS.TopoDS_Compound
    ]

    @staticmethod
    def is_shape_class(obj) -> bool:
        for s in TypeValidator.ALL_SHAPE_CLASSES:
            if isinstance(obj, s):
                return True

        return False

    @staticmethod
    def is_any_shape(obj) -> bool:
        if not TypeValidator.is_shape_class(obj):
            return False

        return obj.ShapeType() in TypeValidator.ALL_SHAPE_TYPES

    @staticmethod
    def assert_is_any_shape(obj):
        if not TypeValidator.is_any_shape(obj):
            raise ValueError(f"Obj is not an instance of any TopoDS_Shape: {obj}")

    @staticmethod
    def assert_is_shape_type_or_simpler(obj: OCC.Core.TopoDS.TopoDS_Shape,
                                        shape_type: OCC.Core.TopAbs.TopAbs_ShapeEnum):
        TypeValidator.assert_is_any_shape(obj)

        actual_shape_index = TypeValidator.ALL_SHAPE_TYPES.index(obj.ShapeType())
        max_shape_index = TypeValidator.ALL_SHAPE_TYPES.index(shape_type)

        if actual_shape_index > max_shape_index:
            raise ValueError(f"Expected the object's shape type to be of {Humanize.shape_type(shape_type)} or simpler. "
                             f"(instead was {Humanize.shape_type(obj.ShapeType())})")

    @staticmethod
    def assert_is_shape_type_or_more_complex(obj: OCC.Core.TopoDS.TopoDS_Shape,
                                             shape_type: OCC.Core.TopAbs.TopAbs_ShapeEnum):
        TypeValidator.assert_is_any_shape(obj)

        actual_shape_index = TypeValidator.ALL_SHAPE_TYPES.index(obj.ShapeType())
        max_shape_index = TypeValidator.ALL_SHAPE_TYPES.index(shape_type)

        if actual_shape_index < max_shape_index:
            raise ValueError(f"Expected the object's shape type to be of {Humanize.shape_type(shape_type)} or more "
                             f"complex. (instead was {Humanize.shape_type(obj.ShapeType())})")
