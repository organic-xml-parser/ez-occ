import OCC.Core.TopoDS
from OCC.Core import TopExp, TopAbs
from OCC.Core.BRep import BRep_Tool
from OCC.Core.TopTools import TopTools_IndexedDataMapOfShapeListOfShape

from ezocc.occutils_python import ListUtils, SetPlaceableShape


class SeamIdentifier:

    def __init__(self, shape: OCC.Core.TopoDS.TopoDS_Shape):
        self._shape = shape

        self._shape_map: TopTools_IndexedDataMapOfShapeListOfShape = TopTools_IndexedDataMapOfShapeListOfShape()
        TopExp.topexp.MapShapesAndAncestors(
            self._shape,
            TopAbs.TopAbs_EDGE,
            TopAbs.TopAbs_FACE,
            self._shape_map)

    def is_degenerated(self, edge: OCC.Core.TopoDS.TopoDS_Edge):
        return BRep_Tool.Degenerated(edge)

    def is_seam(self, edge: OCC.Core.TopoDS.TopoDS_Edge):
        index = self._shape_map.FindIndex(edge)
        faces_list = self._shape_map.FindFromIndex(index)
        faces_list = [f for f in ListUtils.iterate_list(faces_list)]
        faces_list = [SetPlaceableShape(f) for f in faces_list]

        return len(faces_list) == 2 and faces_list[0] == faces_list[1]
