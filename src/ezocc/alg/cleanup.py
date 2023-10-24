import pdb
import typing

from OCC.Core.TopTools import TopTools_IndexedDataMapOfShapeListOfShape

from ezocc.occutils_python import SetPlaceableShape, Explorer, ListUtils
from ezocc.part_manager import Part, PartCache, PartFactory

import OCC.Core.ShapeAnalysis
import OCC.Core.ShapeUpgrade
import OCC.Core.ShapeFix
import OCC.Core.TopExp
import OCC.Core.TopAbs

class RemoveDanglingFaces:

    def __init__(self, part: Part, cache: PartCache):
        self._part = part
        self._cache = cache


    def run(self) -> Part:
        factory = PartFactory(self._cache)

        self._result = self._part

        while True:
            self._result.print("RESULT")
            edges_to_faces: typing.Dict[SetPlaceableShape, typing.Set[SetPlaceableShape]] = dict()

            for f in self._result.explore.face.get():
                set_f = SetPlaceableShape(f.shape)
                for e in f.explore.edge.get():
                    set_e = SetPlaceableShape(e.shape)

                    if set_e not in edges_to_faces:
                        edges_to_faces[set_e] = set()

                    edges_to_faces[set_e].add(set_f)

            rejected = set()
            for edge, faces in edges_to_faces.items():
                # if an edge only has a single face, that face should be removed
                if len(faces) == 1:
                    face = next(f for f in faces)

                    # don't reject closed faces
                    if len(Part.of_shape(face.shape).explore.edge.get()) != 1:
                        rejected.add(*faces)

            print(f"{len(rejected)} faces rejected")

            if len(rejected) == 0:
                return self._result

            new_result = factory.shell(*[f for f in self._result.explore.face.get() if SetPlaceableShape(f.shape) not in rejected])

            if len(new_result.explore.face.get()) == len(self._result.explore.face.get()):
                raise ValueError("No change after face removal")

            factory.arrange(new_result, factory.compound(*[Part.of_shape(f.shape) for f in rejected]), spacing=10).preview()


            self._result = new_result


