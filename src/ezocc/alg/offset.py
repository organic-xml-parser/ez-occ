import json
import pdb

import OCC.Core.TopoDS

import OCC.Core.BRepOffsetAPI
import OCC.Core.BRepBuilderAPI
import OCC.Core.Geom
import OCC.Core.ProjLib
import OCC.Core.BRepAdaptor
import OCC.Core.GeomAdaptor
import OCC.Core.ShapeConstruct
import typing

from ezocc.alg.cleanup import RemoveDanglingFaces
from ezocc.occutils_python import SetPlaceableShape, SetPlaceablePart, ListUtils, WireSketcher, GeomUtils, \
    InterrogateUtils
from ezocc.part_cache import InMemoryPartCache
from ezocc.part_manager import Part, PartCache, PartFactory

from util_wrapper_swig import SurfaceMapperWrapper


class Offsetter:

    def __init__(self,
                 cache : PartCache,
                 part: Part,
                 amount: float):
        self._cache = cache
        self._part = part
        self._amount = amount

    def run(self) -> Part:
        factory = PartFactory(self._cache)

        if not self._part.inspect.is_solid():
            raise ValueError("Part should be a solid")

        # cache intersections
        edges_to_faces: typing.Dict[SetPlaceablePart, typing.Set[SetPlaceablePart]] = dict()
        vertexes_to_faces: typing.Dict[SetPlaceablePart, typing.Set[SetPlaceablePart]] = dict()
        offset_faces: typing.Dict[SetPlaceablePart, SetPlaceableShape] = dict()

        # stores the edge transformations between original and offset part
        edge_mappings: typing.Dict[SetPlaceableShape, typing.Set[SetPlaceableShape]] = dict()
        vertex_mappings: typing.Dict[SetPlaceableShape, typing.Set[SetPlaceableShape]] = dict()

        for f in self._part.explore.face.get():
            set_f = SetPlaceablePart(f)
            for e in f.explore.edge.get():
                set_e = SetPlaceablePart(e)

                if set_e not in edges_to_faces:
                    edges_to_faces[set_e] = set()

                edges_to_faces[set_e].add(set_f)

                for v in e.explore.vertex.get():
                    set_v = SetPlaceablePart(v)

                    if set_v not in vertexes_to_faces:
                        vertexes_to_faces[set_v] = set()

                    vertexes_to_faces[set_v].add(set_f)

            offset_faces[set_f] = self._offset(set_f, edge_mappings, vertex_mappings)

        # for all the original shared edges, create a loft
        lofts = []
        for edge, faces in edges_to_faces.items():
            created_edges = edge_mappings[SetPlaceableShape(edge.part.shape)]

            if len(created_edges) != 2:
                continue

            w0, w1 = created_edges

            # create a spine for the loft
            try:
                lofts.append(factory.loft([
                    Part.of_shape(w0.shape).make.wire(),
                    Part.of_shape(w1.shape).make.wire()
                ], is_solid=False).explore.face.get()[0])
            except:
                pass

        vert_faces = []
        for vertex, faces in vertexes_to_faces.items():
            created_vertexes = vertex_mappings[SetPlaceableShape(vertex.part.shape)]

            if len(created_vertexes) != 3:
                continue

            created_vertexes = [v for v in created_vertexes]
            vert_faces.append(WireSketcher(*InterrogateUtils.vertex_to_xyz(created_vertexes[0].shape)) \
                .line_to(*InterrogateUtils.vertex_to_xyz(created_vertexes[1].shape)) \
                .line_to(*InterrogateUtils.vertex_to_xyz(created_vertexes[2].shape)) \
                .close().get_face_part(cache))

        result = factory.union(*[Part.of_shape(f) for f in offset_faces.values()], *lofts, *vert_faces)\
            .sew()

        result = RemoveDanglingFaces(result, cache).run()

        return result

    def _offset(self,
                face: SetPlaceablePart,
                edge_mappings: typing.Dict[SetPlaceableShape, typing.Set[SetPlaceableShape]],
                vertex_mappings: typing.Dict[SetPlaceableShape, typing.Set[SetPlaceableShape]]) -> SetPlaceableShape:
        mko = OCC.Core.BRepOffsetAPI.BRepOffsetAPI_MakeOffsetShape()

        mko.PerformBySimple(face.part.shape, self._amount)

        for e in face.part.explore.edge.get():
            e = SetPlaceableShape(e.shape)
            for em in ListUtils.iterate_list(mko.Generated(e.shape)):
                if e not in edge_mappings:
                    edge_mappings[e] = set()

                edge_mappings[e].add(SetPlaceableShape(em))

        for v in face.part.explore.vertex.get():
            v = SetPlaceableShape(v.shape)

            for vm in ListUtils.iterate_list(mko.Generated(v.shape)):
                if v not in vertex_mappings:
                    vertex_mappings[v] = set()

                vertex_mappings[v].add(SetPlaceableShape(vm))

        return SetPlaceableShape(mko.Shape())


if __name__ == '__main__':
    cache = InMemoryPartCache()
    factory = PartFactory(cache)

    shape = factory.cylinder(5, 10).bool.union(factory.box(6, 6, 6).tr.mv(dx=3))

    Offsetter(cache, shape, 2).run().preview() #.do(lambda p: factory.arrange(*p.explore.face.get(), spacing=10)).preview()