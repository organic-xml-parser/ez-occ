import random
import random
import typing

from OCC.Core import TopExp, ShapeAnalysis, Precision
from OCC.Core.BRep import BRep_Tool
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_REVERSED
from OCC.Core.TopTools import TopTools_IndexedDataMapOfShapeListOfShape
from OCC.Core.gp import gp, gp_Pnt, gp_Dir, gp_Trsf, gp_Ax3

from ezocc.alg.geometry_exploration.edges.intersection_angle import get_edge_intersection_angle
from ezocc.occutils_python import ListUtils, SetPlaceableShape, InterrogateUtils
from ezocc.part_manager import Part, PartFactory, PartCache
from ezocc.type_utils import TypeValidator, TypeUtils

SHAPE_ADJACENCY_MAP = typing.Dict[SetPlaceableShape, typing.Set[SetPlaceableShape]]


def _pick_random_outer_face(solid: Part) -> Part:
    rng = random.Random()

    # pick random spots until we get an outer face
    # todo: some kind of timeout...
    while True:
        x = rng.random() * solid.xts.x_span + solid.xts.x_min
        y = rng.random() * solid.xts.y_span + solid.xts.y_min
        z = solid.xts.z_max + 1

        pick = solid.pick.dir((x, y, z), (0, 0, -1))

        try:
            if len(pick.face_list()) > 0:
                return pick.first_face()
        except ValueError:
            pass


def _get_face_normal_at_3d_point(face: SetPlaceableShape, point: gp_Pnt) -> gp_Dir:
    surf = BRep_Tool.Surface(TypeUtils.downcast_to_shape_type(face.shape))
    sa = ShapeAnalysis.ShapeAnalysis_Surface(surf)

    face_from_uv = sa.UVFromIso(point, Precision.precision.Confusion())

    normal: gp_Dir = InterrogateUtils.face_normal(face.shape, lambda *_: (face_from_uv[1], face_from_uv[2]))[1]

    if Part.of_shape(face.shape).inspect.orientation() == TopAbs_REVERSED:
        normal.Reverse()

    return normal


def _get_edge_tangent_at_3d_point(edge: Part, location: gp_Pnt, precision: float) -> gp_Dir:

    start_pnt, end_pnt = InterrogateUtils.line_points(edge.shape)
    start_tan, end_tan = InterrogateUtils.line_tangent_points(edge.shape)

    # sanity check the distance of the result
    if (start_pnt.Distance(location) > precision and
            end_pnt.Distance(location) > precision):
        raise ValueError("Neither end point of the specified curve is close to the specified location")

    is_first_point = start_pnt.Distance(location) < end_pnt.Distance(location)

    if is_first_point:
        return gp_Dir(start_tan.Normalized())
    else:
        return gp_Dir(end_tan.Normalized())


def _edge_u0_is_point(edge: Part, location: gp_Pnt, precision: float) -> bool:
    p0, p1 = InterrogateUtils.line_points(edge.shape)

    # sanity check the distance of the result
    if (p0.Distance(location) > precision and
            p1.Distance(location) > precision):
        raise ValueError("Neither end point of the specified curve is close to the specified location")

    return p0.Distance(location) < Precision.precision.Confusion()


def _get_face_intersection_angle(cache: PartCache,
                                 edge: SetPlaceableShape,
                                 face_from: SetPlaceableShape,
                                 face_to: SetPlaceableShape,
                                 precision: float = 0.00001) -> float:
    # use edge midpoint as intersection point
    line_point = InterrogateUtils.line_point(edge.shape, parameter=0.5, is_normalized_parameter=True)
    line_tangent = InterrogateUtils.line_tangent_point(edge.shape, parameter=0.5, is_normalized_parameter=True)
    line_tangent = gp_Dir(line_tangent.Normalized())
    #if Part.of_shape(edge.shape).inspect.orientation() == TopAbs_REVERSED:
    #    line_tangent.Reverse()

    norm_from = _get_face_normal_at_3d_point(face_from, line_point)
    norm_to = _get_face_normal_at_3d_point(face_to, line_point)

    # define an axis
    surface_from_tangent = norm_from.Crossed(line_tangent)
    surface_to_tangent = norm_to.Crossed(line_tangent).Reversed()

    surface_from_ax = gp_Ax3(line_point, line_tangent, surface_from_tangent)

    trsf = gp_Trsf()
    trsf.SetTransformation(gp_Ax3(gp.Origin(), gp.DZ(), gp.DX()), surface_from_ax)

    surface_to_tangent_trsf = surface_to_tangent.Transformed(trsf)

    plane_slice = PartFactory(cache).circle(0.001).make.face().transform(trsf.Inverted())

    edge_from = Part.of_shape(face_from).bool.section(plane_slice)
    edge_to = Part.of_shape(face_to).bool.section(plane_slice)

    if len(edge_from.explore.edge.get()) != 1 or len(edge_to.explore.edge.get()) != 1:
        raise ValueError("Plane section yielded multiple edges")

    return get_edge_intersection_angle(
        edge_from,
        norm_from,
        edge_to,
        line_point,
        precision,
        reference_is_in_plane=True)


class InternalFaceRemovalResult:

    def __init__(self):
        self._result: typing.Optional[Part] = None
        self._initial_face: typing.Optional[Part] = None
        self.removed_faces: typing.Set[SetPlaceableShape] = set()
        self.orphaned_faces: typing.Set[SetPlaceableShape] = set()
        self.visited_faces: typing.Set[SetPlaceableShape] = set()

    @property
    def result(self) -> Part:
        if self._result is None:
            raise ValueError("Result not set")

        return self._result

    @property
    def initial_face(self) -> Part:
        if self._initial_face is None:
            raise ValueError("Result not set")

        return self._initial_face


def remove_internal_faces(solid: Part) -> InternalFaceRemovalResult:
    """
    Given a solid, removes any internal faces. Useful for cleaning up self-intersecting pipes.

    TODO: how this should work
      - "surface crawler" Imagine dropping an ant (by picking an exterior face from -z direction) and allowing it to
      explore the surface of the shape. When crossing edges, it should prefer the most "acute" angle change (i.e. a 90
      degree wall would be preferred over a continuation of a horizontal plane). Provided we start with an exterior
      face, and all normals of exterior faces point outwards, this should result in the ant exploring the surface of the
      solid.
      - Degenerate (i.e. point-like) edges are not traversed by the ant, since the concept of edge tangent direction is
      not defined for them.
      - higher order tangents (i.e. cases where edge tangents are equivalent but derivatives may differ) are not
      currently respected by this algorithm, and will be treated as equivalent. In principle however,
      the comparison should be possible.
      - currently a circle face object is used to section the faces to produce two intersecting edges for the angle
      calculation. A small (~0.001) area is used for this face but a sufficiently convoluted solid could have details
      which intersect that. In theory this is not an issue if we filter the sectioned edges to only pick the two that
      intersect the vertex at the center of the circle, but I haven't implemented this.

    """

    factory = PartFactory(solid.cache_token.get_cache())

    # initial shape cleanup to ensure that face intersections are populated with edges
    solid = (factory.union(
        *[f.bool.cut(*[ff for ff in solid.explore.face.get() if ff.set_placeable != f.set_placeable]) for f in
          solid.explore.face.get()]
    ).sew.faces())

    face_adjacency_graph: SHAPE_ADJACENCY_MAP = {
        p.set_placeable_shape: set() for p in solid.explore.face.get()
    }
    face_to_edges: SHAPE_ADJACENCY_MAP = {
        p.set_placeable_shape: set() for p in solid.explore.face.get()
    }
    edge_to_faces: SHAPE_ADJACENCY_MAP = {
        p.set_placeable_shape: set() for p in solid.explore.edge.get()
    }

    shape_map: TopTools_IndexedDataMapOfShapeListOfShape = TopTools_IndexedDataMapOfShapeListOfShape()
    TopExp.topexp.MapShapesAndAncestors(solid.shape, TopAbs_EDGE, TopAbs_FACE, shape_map)

    result = InternalFaceRemovalResult()

    for e in solid.explore.edge.get():

        # skip degenerated edges
        if BRep_Tool.Degenerated(e.shape):
            continue

        index = shape_map.FindIndex(e.shape)
        faces_list = shape_map.FindFromIndex(index)
        faces_list = [f for f in ListUtils.iterate_list(faces_list)]
        faces_list = [SetPlaceableShape(f) for f in faces_list]

        # skip seam edges
        if len(faces_list) == 2 and faces_list[0] == faces_list[1]:
            continue

        faces_set = {f for f in faces_list}
        for f in faces_set:
            face_to_edges[f].add(e.set_placeable_shape)
            for ff in faces_set:
                if ff != f:
                    face_adjacency_graph[f].add(ff)

        edge_to_faces[e.set_placeable_shape].update({f for f in faces_set})

    # begin dfs traversal filtering internal faces by incidence angle

    outer_face_part = _pick_random_outer_face(solid)
    outer_face = outer_face_part.set_placeable_shape

    result._initial_face = outer_face

    removed_faces: typing.Set[SetPlaceableShape] = set()
    visited_faces: typing.Set[SetPlaceableShape] = {outer_face}
    dfs_face_stack: typing.List[SetPlaceableShape] = [outer_face]

    while len(dfs_face_stack) > 0:
        stack_top = dfs_face_stack[-1]
        dfs_face_stack.pop()
        visited_faces.add(stack_top)

        for e in face_to_edges[stack_top]:
            next_faces = [f for f in face_adjacency_graph[stack_top] if f not in visited_faces and e in face_to_edges[f]]
            if len(next_faces) == 0:
                continue
            elif len(next_faces) == 1:
                dfs_face_stack.append(next_faces[0])
                continue
            else:
                incidence_angles = {_get_face_intersection_angle(solid.cache_token.get_cache(), e, stack_top, f): f for f in next_faces}
                selected_angle = min(incidence_angles.keys())
                next_face = incidence_angles[selected_angle]
                discarded_faces = [f for f in incidence_angles.values() if f != next_face]
                removed_faces.update({*discarded_faces})
                visited_faces.update({*discarded_faces})
                #factory.compound(
                #    *[Part.of_shape(p) for p in discarded_faces],
                #    Part.of_shape(stack_top).name("top"),
                #    Part.of_shape(next_face).name("next").tr.mv(dz=1)
                #    ).preview()
                dfs_face_stack.append(next_face)

    result.visited_faces = visited_faces
    result.removed_faces = removed_faces
    result.orphaned_faces = {
        f for f in solid.explore.face.get() if
        f.set_placeable_shape not in visited_faces and f.set_placeable_shape not in removed_faces
    }
    result._result = factory.compound(
        *[f for f in solid.explore.face.get() if f.set_placeable_shape in visited_faces and f.set_placeable_shape not in removed_faces]
    ).make.shell().make.solid()

    return result


